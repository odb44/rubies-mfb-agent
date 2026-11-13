
from uuid import UUID

from rubies_shared.identity import CustomerIdentity

from rubies_banking_api.models.chat_message import ChatMessage
from rubies_banking_api.models.chat_session import ChatSession
from rubies_banking_api.repositories.chat_repository import ChatRepository
from rubies_banking_api.repositories.customer_repository import (
    CustomerRepository,
)


class ChatService:
    """Handles customer chat history operations."""

    def __init__(
        self,
        chat_repository: ChatRepository,
        customer_repository: CustomerRepository,
    ) -> None:
        self.chat_repository = chat_repository
        self.customer_repository = customer_repository

    def _resolve_customer(self, identity: CustomerIdentity):
        """Validate identity and resolve the internal customer record."""
        if not identity.verified:
            raise ValueError("A verified customer identity is required.")

        customer = self.customer_repository.get_by_reference(
            identity.customer_id
        )

        if customer is None or not customer.is_active:
            raise ValueError("The customer account is not available.")

        return customer

    def list_customer_chats(
        self,
        identity: CustomerIdentity,
        limit: int = 20,
        offset: int = 0,
    ) -> list[ChatSession]:
        """List active conversations belonging to the authenticated customer."""
        customer = self._resolve_customer(identity)

        return self.chat_repository.list_active_for_customer(
            customer_id=customer.id,
            limit=limit,
            offset=offset,
        )

    def create_customer_chat(
        self,
        identity: CustomerIdentity,
        content: str,
    ) -> ChatSession:
        """Create a conversation with its first customer message."""
        customer = self._resolve_customer(identity)
        content = content.strip()

        if not content:
            raise ValueError("Message content cannot be empty.")

        return self.chat_repository.create_with_first_message(
            customer_id=customer.id,
            content=content,
        )

    def get_customer_chat(
        self,
        identity: CustomerIdentity,
        chat_id: UUID,
    ) -> ChatSession:
        """Retrieve a conversation belonging to the authenticated customer."""
        customer = self._resolve_customer(identity)

        chat = self.chat_repository.get_by_id(
            chat_id=chat_id,
            customer_id=customer.id,
        )

        if chat is None:
            raise LookupError("Chat conversation not found.")

        return chat

    def add_customer_message(
        self,
        identity: CustomerIdentity,
        chat_id: UUID,
        content: str,
    ) -> ChatMessage:
        """Add a customer message to an existing active conversation."""
        customer = self._resolve_customer(identity)
        content = content.strip()

        if not content:
            raise ValueError("Message content cannot be empty.")

        chat = self.chat_repository.get_by_id(
            chat_id=chat_id,
            customer_id=customer.id,
        )

        if chat is None:
            raise LookupError("Chat conversation not found.")

        if chat.status != "ACTIVE":
            raise ValueError(
                "Archived conversations cannot receive messages."
            )

        return self.chat_repository.add_message(
            chat=chat,
            content=content,
        )

    def update_customer_chat_status(
        self,
        identity: CustomerIdentity,
        chat_id: UUID,
        new_status: str,
    ) -> ChatSession:
        """Archive or reactivate a customer's conversation."""
        customer = self._resolve_customer(identity)

        if new_status not in {"ACTIVE", "ARCHIVED"}:
            raise ValueError("Invalid chat status.")

        chat = self.chat_repository.get_by_id(
            chat_id=chat_id,
            customer_id=customer.id,
        )

        if chat is None:
            raise LookupError("Chat conversation not found.")

        return self.chat_repository.update_status(
            chat=chat,
            new_status=new_status,
        )

def add_assistant_message(
    self,
    identity: CustomerIdentity,
    chat_id: UUID,
    content: str,
) -> ChatMessage:
    """Persist an assistant response for an authenticated customer's chat."""
    customer = self._resolve_customer(identity)
    content = content.strip()

    if not content:
        raise ValueError("Message content cannot be empty.")

    chat = self.chat_repository.get_by_id(
        chat_id=chat_id,
        customer_id=customer.id,
    )

    if chat is None:
        raise LookupError("Chat conversation not found.")

    if chat.status != "ACTIVE":
        raise ValueError("Archived conversations cannot receive messages.")

    return self.chat_repository.add_assistant_message(
        chat=chat,
        content=content,
    )