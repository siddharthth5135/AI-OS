import asyncio
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging.logger import get_logger
from app.core.observability.metrics import WS_MESSAGES
from app.core.security.jwt import decode_token
from app.db.models.task import Task
from app.db.session.database import get_db
from app.repositories.user_repository import UserRepository
from app.services.streaming.connection_manager import connection_manager

logger = get_logger("ai_os.api.websocket")
ws_router = APIRouter()


@ws_router.websocket("/ws/chat")
async def websocket_chat(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token"),
    db: AsyncSession = Depends(get_db),
):
    """
    WebSocket endpoint for real-time bi-directional conversation streaming.
    Authenticates connection via JWT token query param, establishes heartbeat pings,
    and forwards incoming messages to the orchestrator stream processor.
    """
    # AUTH — before accepting connection
    try:
        payload = decode_token(token)
        user_repo = UserRepository()
        user = await user_repo.get_by_id(db, UUID(payload["sub"]))
        if not user or not user.is_active:
            await websocket.accept()
            await websocket.close(code=4001, reason="Unauthorized")
            return
    except Exception as e:
        logger.error(f"WebSocket auth error: {str(e)}")
        await websocket.accept()
        await websocket.close(code=4001, reason="Invalid token")
        return

    session_id = str(uuid4())
    await connection_manager.connect(websocket, str(user.id), session_id)

    try:
        await websocket.send_json(
            {
                "type": "connected",
                "data": {"session_id": session_id, "user_id": str(user.id)},
            }
        )
        WS_MESSAGES.labels(direction="sent").inc()
    except Exception:
        connection_manager.disconnect(str(user.id), session_id)
        return

    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=60.0)
                WS_MESSAGES.labels(direction="received").inc()
            except asyncio.TimeoutError:
                # Send heartbeat ping
                try:
                    await websocket.send_json({"type": "ping"})
                    WS_MESSAGES.labels(direction="sent").inc()
                except Exception:
                    break
                continue
            except WebSocketDisconnect:
                break
            except Exception as e:
                try:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "data": {
                                "message": f"Invalid message format: {str(e)}",
                                "code": "invalid_format",
                            },
                        }
                    )
                    WS_MESSAGES.labels(direction="sent").inc()
                    continue
                except Exception:
                    break

            if data.get("type") == "ping":
                try:
                    await websocket.send_json({"type": "pong"})
                    WS_MESSAGES.labels(direction="sent").inc()
                except Exception:
                    break
                continue

            if data.get("type") == "pong":
                continue

            if data.get("type") == "chat":
                query = data.get("query", "").strip()
                if not query:
                    continue
                await handle_chat_ws(
                    websocket, user, session_id, query, data.get("doc_ids", []), db
                )

    except Exception as e:
        logger.error("ws_error", error=str(e), user_id=str(user.id))
    finally:
        connection_manager.disconnect(str(user.id), session_id)
        logger.info("ws_disconnected", user_id=str(user.id), session_id=session_id)


async def handle_chat_ws(
    ws: WebSocket, user, session_id: str, query: str, doc_ids: list, db: AsyncSession
):
    """
    Handles a single incoming WebSocket chat query. Creates a task record,
    submits it to the stream processor of the agent orchestrator, and transmits
    the returned execution progress/token stream events back to the client.
    """
    orchestrator = ws.app.state.orchestrator

    # Create task record
    task = Task(
        user_id=user.id,
        task_type="chat",
        status="pending",
        input_data={"query": query, "session_id": session_id},
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    try:
        await ws.send_json(
            {
                "type": "task_update",
                "data": {"status": "classifying", "task_id": str(task.id)},
            }
        )
        WS_MESSAGES.labels(direction="sent").inc()
    except Exception:
        raise WebSocketDisconnect()

    try:
        async for event in orchestrator.process_stream(
            query=query,
            user_id=user.id,
            session_id=session_id,
            task_id=str(task.id),
            context={"doc_ids": doc_ids, "session_history": True},
        ):
            if event.type in ["task_update", "token", "task_completed", "error"]:
                await ws.send_json({"type": event.type, "data": event.data})
                WS_MESSAGES.labels(direction="sent").inc()
    except WebSocketDisconnect:
        logger.info("ws_chat_disconnect_mid_stream", task_id=str(task.id))
        raise
    except Exception as e:
        logger.error("ws_chat_error", error=str(e))
        try:
            await ws.send_json(
                {
                    "type": "error",
                    "data": {"message": "Processing failed", "code": "internal_error"},
                }
            )
            WS_MESSAGES.labels(direction="sent").inc()
        except Exception:
            pass
