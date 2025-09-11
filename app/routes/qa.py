from fastapi import APIRouter, HTTPException, Form, Depends
from sqlalchemy.orm import Session
from app.langchain.qa_chain import get_qa_chain
from app.langchain.llm import chat_with_llm
from app.db.database import get_db
from app.models.chat import ChatSession, ChatMessage
from uuid import UUID
from langchain_core.messages import HumanMessage, AIMessage
from sqlalchemy import desc
import json

router = APIRouter()

@router.post("/chat/new")
async def create_chat(question: str = Form(...), db: Session = Depends(get_db)):
    chat_session = ChatSession(user_id=1, title=question)
    db.add(chat_session)
    db.commit()
    db.refresh(chat_session)
    return {"session_id": chat_session.id, "title": chat_session.title}

@router.get("/chats")
async def get_chats(db: Session = Depends(get_db)):
    sessions = db.query(ChatSession).all()
    
    return {"sessions": sessions}


@router.post("/chat/{session_id}/ask")
async def ask_question(
    session_id: str,
    question: str = Form(...),
    db: Session = Depends(get_db)
):
    # Validate UUID format (optional but cleaner)
    try:
        uuid_obj = UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID format")

    # Get chat session
    session = db.query(ChatSession).filter(ChatSession.id == str(uuid_obj)).first()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    
    # Get recent history for LLM context only (not for response)
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(desc(ChatMessage.created_at))
        .limit(10)
        .all()
    )

    chat_history = []
    for msg in messages:
        if msg.role == "user":
            chat_history.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            chat_history.append(AIMessage(content=msg.content))

    # Store user query
    user_msg = ChatMessage(session_id=session_id, role="user", content=question)
    db.add(user_msg)
    db.commit()
    db.refresh(user_msg)

    # Get LLM response
    try:
        chain = await get_qa_chain()
        result = await chain.ainvoke({
            "question": question,
            "history": chat_history
        })

    except Exception as e:
        return {"error": "Invalid response format from AI", "raw_output": str(e)}

    summary = result.get("summary", "")
    advice_points = result.get("advice_points", [])
    followup_questions = result.get("followup_questions", [])

    # Store assistant response
    assistant_msg = ChatMessage(
        session_id=session_id,
        role="assistant",
        content=summary,
        advice_points=json.dumps(advice_points) if advice_points else None,
        followup_questions=json.dumps(followup_questions) if followup_questions else None
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    def safe_json(value):
        if not value:
            return []
        try:
            return json.loads(value) if isinstance(value, str) else value
        except:
            return []

    return {
        "session_id": session_id,
        "messages": [
            {
                "id": user_msg.id,
                "role": user_msg.role,
                "content": user_msg.content,
                "advice_points": [],
                "followup_questions": [],
                "timestamp": user_msg.created_at,
            },
            {
                "id": assistant_msg.id,
                "role": assistant_msg.role,
                "content": assistant_msg.content,
                "advice_points": safe_json(assistant_msg.advice_points),
                "followup_questions": safe_json(assistant_msg.followup_questions),
                "timestamp": assistant_msg.created_at,
            }
        ]
    }

@router.get("/chat/{session_id}/history")
async def get_chat_history(session_id: str, db: Session = Depends(get_db)):
    messages = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).order_by(ChatMessage.id).all()

    def try_parse_json(value):
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return None
        return value  # already a list or None

    history = [
        {
            "id": msg.id,
            "role": msg.role,
            "content": msg.content,
            "advice_points": try_parse_json(msg.advice_points),
            "followup_questions": try_parse_json(msg.followup_questions),
            "timestamp": msg.created_at,
        }
        for msg in messages
    ]

    return {
        "session_id": session_id,
        "messages": history
    }

@router.post("/chat_llm")
def chat_llm_bot(User_query:str=Form(...)):
    print(User_query)
    resp = chat_with_llm("1",User_query)
    return {"response":resp}
   
   