from typing import Dict, List, Any , TypedDict , Annotated
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import create_react_agent, ToolNode
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage, ToolMessage
from langchain.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_core.runnables.passthrough import RunnablePassthrough
import json
import uuid 

from app.services.db_service import fetch_vendor_data
from app.config import OPENAI_API_KEY


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], "Conversation history"]
    filters: Annotated[Dict[str, Any], "Filters for vendor query which has {'column':'value'}"]
    last_tool_result: Annotated[Dict[str, Any], "Last tool output"]
    response: Annotated[str, "Final assistant response"]


llm = ChatOpenAI(
        model="qwen-plus-latest",
        temperature=0,
        openai_api_key=OPENAI_API_KEY,
        base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    )


@tool
def vendor_tool_node(filters: Dict[str, Any]) -> Dict[str, Any]:
    """Executes the vendor fetch tool safely."""
    print("inside",filters)
    result = fetch_vendor_data(filters)
    print(result)
    return {
        "messages": filters["messages"],  
        "last_tool_result": result
    }

def to_openai_format(messages):
    formatted = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            formatted.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            formatted.append({"role": "assistant", "content": msg.content})
        else:
            formatted.append({"role": "system", "content": msg.content})
    return formatted

def summarize_results(state: Dict[str, Any]) -> Dict[str, Any]:

    tool_output_message = next(
        (msg for msg in reversed(state['messages']) if isinstance(msg, ToolMessage)),
        None
    )
    if not tool_output_message:
        return {"response": "No tool output found."}
        
    result = tool_output_message.content
    
    # Check if the result is a string representing a dict
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except json.JSONDecodeError:
            return {"response": "Unexpected tool output."}

    messages = state.get("messages", [])

    if not isinstance(result, dict):
        return {"response": "Unexpected tool output."}

    if "error" in result:
        if result["error"] == "missing_filters":
            response = "I’ll need more details. Could you provide: " + ", ".join(result["missing"])
        elif result["error"] == "invalid_filters":
            response = (
                f"Some filters were invalid: {result['invalid']}. "
                f"Allowed filters are: {', '.join(result['allowed'])}."
            )
        elif result["error"] == "forbidden_keyword":
            response = f"⚠️ Your input contained a forbidden keyword ({result['value']}). Please rephrase safely."
        else:
            response = f"Sorry, DB error: {result.get('message', 'unknown')}."
    elif "results" in result:
        vendors = result["results"]
        if not vendors:
            response = "No vendors found with your filters."
        else:
            summary = []
            for v in vendors[:5]:
                summary.append(
                    f"- {v['name']} ({v['company']}) "
                    f" - Services: {v['services']} "
                    f" - City: {v['cities']} "
                    f" - Country: {v['countries']} "
                    f" - Contact: {v['contact']}"
                )
            response = "\n".join(summary)
    else:
        response = "Unexpected output."
        
    messages.append(AIMessage(content=response))
    return {"messages": messages, "response": response}

def call_tool_with_parsed_input(state: Dict[str, Any]) -> Dict[str, Any]:
    last_message = state['messages'][-1]
    
    try:
        json_output = json.loads(last_message.content)
        query_dict = json_output.get("query", {})
        tool_output = vendor_tool_node.invoke({"filters": query_dict})
    except (json.JSONDecodeError, KeyError) as e:
        tool_output = {"error": "parsing_error", "message": str(e)}

    # Append the tool's output as a ToolMessage to the conversation history
    state['messages'].append(ToolMessage(content=json.dumps(tool_output), tool_call_id=str(uuid.uuid4()), name="vendor_search"))
    return state

def clarify_request(state: Dict[str, Any]) -> Dict[str, Any]:
    messages = state.get("messages", [])
    response = "I need more information to find the right results. Could you please specify the services, cities, or countries you are interested in?"
    messages.append(AIMessage(content=response))
    return {"messages": messages, "response": response}

prompt_template = ChatPromptTemplate.from_messages([
    ("system", """
You are a database query assistant. Your sole purpose is to convert a user's request into a JSON object that can be used to query a vendor database.
You must always respond with a single JSON object. Do not include any other text, dialogue, or explanation.
The JSON object must have a single key named 'query'. The value of 'query' must be a dictionary of key-value pairs.
The keys in this inner dictionary MUST be one of the following: 'services', 'cities', 'countries', 'company', or 'name'.
Extract the relevant column and value from the user's query and format it correctly. If the user asks for information without providing a specific filter, you must still provide the empty query dictionary.

Examples:
- User: "Tell me about vendors providing motor services in London"
- JSON response: `{{"query": {{"services": "motor services", "cities": "London"}}}}`
- User: "Find vendors named 'Global Marine' in Brazil"
- JSON response: `{{"query": {{"name": "Global Marine", "countries": "Brazil"}}}}`
- User: "What services do you offer?"
- JSON response: `{{"query": {{}}}}`
"""),
    ("placeholder", "{messages}")
])

agent_chain = prompt_template | llm

def call_llm(state: Dict[str, Any]) -> Dict[str, Any]:
    ai_message = agent_chain.invoke(state)
    state['messages'].append(ai_message)
    return state

graph = StateGraph(AgentState)
graph.add_node("agent", RunnableLambda(call_llm))
graph.add_node("call_tool", RunnableLambda(call_tool_with_parsed_input))
graph.add_node("summarize", summarize_results)
graph.add_node("clarify", RunnableLambda(clarify_request))

def route_logic(state):
    last_message= state["messages"][-1]
    try: 
        json_output = json.loads(last_message.content)
        if 'query' in json_output and isinstance(json_output['query'], dict) and json_output['query']:
            return "call_tool"
        return "clarify"
    except (json.JSONDecodeError, KeyError):
        return "clarify"


graph.set_entry_point("agent")
graph.add_conditional_edges("agent", route_logic, {"call_tool": "call_tool", "clarify": "clarify"})
graph.add_edge("call_tool", "summarize")
graph.add_edge("summarize", END)
graph.add_edge("clarify", END)


vendorbot = graph.compile()

sessions: Dict[str, List[Dict[str, str]]] = {}


def chat_with_llm(user_id: str, user_message: str) -> str:
    print(user_id,user_message)
    if user_id not in sessions:
        sessions[user_id] = []

    sessions[user_id].append(HumanMessage(content=user_message))
    print(sessions)
    formated_message = to_openai_format(sessions[user_id])
    print(formated_message)
    result = vendorbot.invoke({"messages":formated_message})
    print(result.get("response", "⚠️ No response"))

    response = result.get("response", "⚠️ No response generated.")
    
    sessions[user_id] = result['messages']

    return response
