from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
from openai import APIError

from backend.api.schemas import ChatRequest, ChatResponse, InformationResponse
from backend.services.chatService import get_chat_service
from backend.services.errors import PromptNotFoundError

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", summary="Send the conversation to the workshop agent")
def chat(body: ChatRequest) -> ChatResponse:
    """Run one turn of the conversation and return the assistant's reply.

    Creates the session if `session_id` is missing or unknown, loads what was already
    gathered from the database, and asks the agent. The server keeps no history: send
    the whole conversation again on every turn, with the `session_id` of the response.

    Sync on purpose: the LLM and database calls block, so FastAPI runs this in its
    threadpool instead of the event loop.
    """
    service = get_chat_service()
    messages: list[AnyMessage] = [
        HumanMessage(m.content) if m.role == "user" else AIMessage(m.content) for m in body.messages
    ]

    try:
        session_id = service.ensure_session(body.session_id)
        state = service.chat(session_id, messages)
    except PromptNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except APIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return ChatResponse(
        session_id=session_id,
        reply=str(state["messages"][-1].text),
        information=InformationResponse(**asdict(state["information"])),
    )
