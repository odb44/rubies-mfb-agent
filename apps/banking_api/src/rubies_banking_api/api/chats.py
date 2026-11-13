
import secrets
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from rubies_shared.identity import CustomerIdentity
from sqlalchemy.orm import Session

from rubies_banking_api.api.dependencies import get_customer_identity
from rubies_banking_api.config import get_settings
from rubies_banking_api.db.database import get_db
from rubies_banking_api.repositories.chat_repository import ChatRepository
from rubies_banking_api.repositories.customer_repository import (
    CustomerRepository,
)
from rubies_banking_api.services.chat_service import ChatService

router = APIRouter(
    prefix="/api/customer/chats",
    tags=["Customer Chats"],
)


class CreateChatRequest(BaseModel):
    content: str = Field(min_length=1, max_length=10000)


class AddChatMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=10000)


class UpdateChatStatusRequest(BaseModel):
    status: Literal["ACTIVE", "ARCHIVED"]


class ChatMessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    created_at: datetime


class ChatListItem(BaseModel):
    id: UUID
    title: str
    status: str
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime


class ChatListResponse(BaseModel):
    items: list[ChatListItem]
    limit: int
    offset: int


class CreateChatResponse(BaseModel):
    id: UUID
    title: str
    status: str
    created_at: datetime
    first_message: str


class ChatDetailResponse(BaseModel):
    id: UUID
    title: str
    status: str
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime
    messages: list[ChatMessageResponse]


class UpdateChatStatusResponse(BaseModel):
    id: UUID
    title: str
    status: str
    updated_at: datetime


def get_chat_service(db: Session) -> ChatService:
    """Construct the chat service with its repositories."""
    return ChatService(
        chat_repository=ChatRepository(db),
        customer_repository=CustomerRepository(db),
    )


@router.get("", response_model=ChatListResponse)
def list_customer_chats(
    db: Annotated[Session, Depends(get_db)],
    identity: Annotated[
        CustomerIdentity,
        Depends(get_customer_identity),
    ],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ChatListResponse:
    """List active conversations belonging to the authenticated customer."""
    service = get_chat_service(db)

    try:
        chats = service.list_customer_chats(
            identity,
            limit=limit,
            offset=offset,
        )

        return ChatListResponse(
            items=[
                ChatListItem(
                    id=chat.id,
                    title=chat.title,
                    status=chat.status,
                    created_at=chat.created_at,
                    updated_at=chat.updated_at,
                    last_message_at=chat.last_message_at,
                )
                for chat in chats
            ],
            limit=limit,
            offset=offset,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc


def require_agent_service(
    token: Annotated[
        str | None,
        Header(alias="X-Agent-Service-Token"),
    ] = None,
) -> None:
    configured_token = get_settings().agent_service_token

    if len(configured_token) < 32:
        raise HTTPException(
            status_code=503,
            detail="Agent service authentication is not configured.",
        )

    if not token or not secrets.compare_digest(token, configured_token):
        raise HTTPException(
            status_code=403,
            detail="Agent service authentication failed.",
        )

@router.post(
    "",
    response_model=CreateChatResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_customer_chat(
    request: CreateChatRequest,
    db: Annotated[Session, Depends(get_db)],
    identity: Annotated[
        CustomerIdentity,
        Depends(get_customer_identity),
    ],
) -> CreateChatResponse:
    """Create a conversation with its first customer message."""
    service = get_chat_service(db)

    try:
        chat = service.create_customer_chat(
            identity,
            content=request.content,
        )

        db.commit()
        db.refresh(chat)

        return CreateChatResponse(
            id=chat.id,
            title=chat.title,
            status=chat.status,
            created_at=chat.created_at,
            first_message=request.content.strip(),
        )

    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    except Exception:
        db.rollback()
        raise


@router.get(
    "/{chat_id}",
    response_model=ChatDetailResponse,
)
def get_customer_chat(
    chat_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    identity: Annotated[
        CustomerIdentity,
        Depends(get_customer_identity),
    ],
) -> ChatDetailResponse:
    """Retrieve a conversation and its messages."""
    service = get_chat_service(db)

    try:
        chat = service.get_customer_chat(
            identity=identity,
            chat_id=chat_id,
        )

        return ChatDetailResponse(
            id=chat.id,
            title=chat.title,
            status=chat.status,
            created_at=chat.created_at,
            updated_at=chat.updated_at,
            last_message_at=chat.last_message_at,
            messages=[
                ChatMessageResponse(
                    id=message.id,
                    role=message.role,
                    content=message.content,
                    created_at=message.created_at,
                )
                for message in chat.messages
            ],
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "/{chat_id}/messages",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_customer_message(
    chat_id: UUID,
    request: AddChatMessageRequest,
    db: Annotated[Session, Depends(get_db)],
    identity: Annotated[
        CustomerIdentity,
        Depends(get_customer_identity),
    ],
) -> ChatMessageResponse:
    """Persist a customer message in an existing conversation."""
    service = get_chat_service(db)

    try:
        message = service.add_customer_message(
            identity=identity,
            chat_id=chat_id,
            content=request.content,
        )

        db.commit()
        db.refresh(message)

        return ChatMessageResponse(
            id=message.id,
            role=message.role,
            content=message.content,
            created_at=message.created_at,
        )

    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    except LookupError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except Exception:
        db.rollback()
        raise


@router.patch(
    "/{chat_id}",
    response_model=UpdateChatStatusResponse,
)
def update_customer_chat_status(
    chat_id: UUID,
    request: UpdateChatStatusRequest,
    db: Annotated[Session, Depends(get_db)],
    identity: Annotated[
        CustomerIdentity,
        Depends(get_customer_identity),
    ],
) -> UpdateChatStatusResponse:
    """Archive or reactivate a customer's conversation."""
    service = get_chat_service(db)

    try:
        chat = service.update_customer_chat_status(
            identity=identity,
            chat_id=chat_id,
            new_status=request.status,
        )

        db.commit()
        db.refresh(chat)

        return UpdateChatStatusResponse(
            id=chat.id,
            title=chat.title,
            status=chat.status,
            updated_at=chat.updated_at,
        )

    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    except LookupError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except Exception:
        db.rollback()
        raise


@router.post(
    "/{chat_id}/assistant-messages",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_assistant_message(
    chat_id: UUID,
    request: AddChatMessageRequest,
    db: Annotated[Session, Depends(get_db)],
    identity: Annotated[
        CustomerIdentity,
        Depends(get_customer_identity),
    ],
    _: Annotated[None, Depends(require_agent_service)],
) -> ChatMessageResponse:
    """Persist an assistant response from the trusted Agent API."""
    service = get_chat_service(db)

    try:
        message = service.add_assistant_message(
            identity=identity,
            chat_id=chat_id,
            content=request.content,
        )

        db.commit()
        db.refresh(message)

        return ChatMessageResponse(
            id=message.id,
            role=message.role,
            content=message.content,
            created_at=message.created_at,
        )

    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc

    except LookupError as exc:
        db.rollback()
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except Exception:
        db.rollback()
        raise
    