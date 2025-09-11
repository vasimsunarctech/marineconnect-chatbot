from typing import Dict, List, Any , TypedDict , Annotated

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode, create_react_agent
from langchain.tools import Tool

from app.services.db_service import fetch_vendor_data
from app.config import OPENAI_API_KEY


class AgentState(TypedDict):
    messages: Annotated[list, "Conversation history"]
    filters: Annotated[Dict[str, Any], "Filters for vendor query"]
    last_tool_result: Annotated[Dict[str, Any], "Last tool output"]
    response: Annotated[str, "Final assistant response"]


llm = ChatOpenAI(
        model="qwen-plus-latest",
        temperature=0,
        openai_api_key=OPENAI_API_KEY,
        base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    )



def vendor_tool_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Executes the vendor fetch tool safely."""
    filters = state.get("filters", {})
    result = fetch_vendor_data(filters)
    return {
        "messages": state["messages"],  
        "last_tool_result": result
    }



def summarize_results(state: Dict[str, Any]) -> Dict[str, Any]:
    result = state.get("last_tool_result", {})
    messages = state.get("messages", [])
    if not isinstance(result, dict):
        return {"response": "Unexpected tool output."}

    if "error" in result:
        if result["error"] == "missing_filters":
            return {
                "response": (
                    "I’ll need more details. Could you provide: "
                    + ", ".join(result["missing"])
                )
            }
        if result["error"] == "invalid_filters":
            return {
                "response": (
                    f"Some filters were invalid: {result['invalid']}. "
                    f"Allowed filters are: {', '.join(result['allowed'])}."
                )
            }
        if result["error"] == "forbidden_keyword":
            return {
                "response": f"⚠️ Your input contained a forbidden keyword ({result['value']}). Please rephrase safely."
            }
        return {"response": f"Sorry, DB error: {result.get('message','unknown')}."}

    if "results" in result:
        vendors = result["results"]
        if not vendors:
            return {"response": "No vendors found with your filters."}

        summary = []
        for v in vendors[:5]:
            summary.append(
                f"{v['name']} ({v['company']}) "
                f"- Services: {v['services']} "
                f"- City: {v['cities']} "
                f"- Country: {v['countries']} "
                f"- Contact: {v['contact']}"
            )
            response = "\n".join(summary)
    else:
        response = "Unexpected output."
        
    messages.append({"role": "assistant", "content": response})
    return {"messages": messages, "response": response}

fetch_tool = Tool.from_function(
    func=fetch_vendor_data,
    name="fetch_vendors",
    description=(
        "Fetch vendors with filters from the Vendor table. "
        "Input: JSON string with keys like services, cities, countries, company, name. "
        "Output: JSON string {\"results\":[...]} or {\"error\":...}."
    ),
)


graph = StateGraph(AgentState)


clarify_node = create_react_agent(llm, tools=[fetch_tool])
graph.add_node("clarify", clarify_node)

graph.add_node("fetch_vendors", vendor_tool_node)


graph.add_node("summarize", summarize_results)


graph.add_edge("clarify", "fetch_vendors")
graph.add_edge("fetch_vendors", "summarize")
graph.add_edge("summarize", END)


graph.set_entry_point("clarify")


vendorbot = graph.compile()



sessions: Dict[str, List[Dict[str, str]]] = {}


def chat_with_llm(user_id: str, user_message: str) -> str:
    if user_id not in sessions:
        sessions[user_id] = []

    sessions[user_id].append({"role": "user", "content": user_message})


   
    result = vendorbot.invoke({"message":[("user",sessions[user_id])]})
    print(result.get("response", "⚠️ No response"))

    response = result.get("response", "⚠️ No response generated.")
    

    sessions[user_id].append({"role": "assistant", "content": response})

    return response
