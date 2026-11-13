
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from rubies_banking_api.models.chat_message import ChatMessage
from rubies_banking_api.models.chat_session import ChatSession


class ChatRepository:
    """Handles database access for customer chat sessions and messages."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_active_for_customer(
        self,
        customer_id: int,
        limit: int = 20,
        offset: int = 0,
    ) -> list[ChatSession]:
        """Return active chat sessions belonging to a customer."""
        statement = (
            select(ChatSession)
            .where(
                ChatSession.customer_id == customer_id,
                ChatSession.status == "ACTIVE",
            )
            .order_by(
                ChatSession.last_message_at.desc(),
                ChatSession.created_at.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(statement).all())

    def get_by_id(
        self,
        chat_id: UUID,
        customer_id: int,
    ) -> ChatSession | None:
        """Find a chat session belonging to a specific customer."""
        statement = select(ChatSession).where(
            ChatSession.id == chat_id,
            ChatSession.customer_id == customer_id,
        )
        return self.db.scalar(statement)

    def create_with_first_message(
        self,
        customer_id: int,
        content: str,
    ) -> ChatSession:
        """Create a conversation and persist its first customer message."""
        now = datetime.now(UTC)

        chat = ChatSession(
            customer_id=customer_id,
            title=" ".join(content.split())[:60],
            status="ACTIVE",
            created_at=now,
            updated_at=now,
            last_message_at=now,
        )

        self.db.add(chat)
        self.db.flush()

        message = ChatMessage(
            chat_session_id=chat.id,
            role="USER",
            content=content,
            created_at=now,
        )

        self.db.add(message)
        self.db.flush()

        return chat

    def add_message(
        self,
        chat: ChatSession,
        content: str,
    ) -> ChatMessage:
        """Persist a customer message in an existing conversation."""
        now = datetime.now(UTC)

        message = ChatMessage(
            chat_session_id=chat.id,
            role="USER",
            content=content,
            created_at=now,
        )

        self.db.add(message)
        chat.last_message_at = now
        chat.updated_at = now

        self.db.flush()
        return message

    def update_status(
        self,
        chat: ChatSession,
        new_status: str,
    ) -> ChatSession:
        """Update a conversation's status."""
        chat.status = new_status
        chat.updated_at = datetime.now(UTC)

        self.db.flush()
        return chat


def add_assistant_message(
    self,
    chat: ChatSession,
    content: str,
) -> ChatMessage:
    """Persist an assistant response in an existing conversation."""
    now = datetime.now(UTC)

    message = ChatMessage(
        chat_session_id=chat.id,
        role="ASSISTANT",
        content=content,
        created_at=now,
    )

    self.db.add(message)
    chat.last_message_at = now
    chat.updated_at = now

    self.db.flush()
    return message