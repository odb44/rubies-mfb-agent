"""HTTP endpoints for read-only account and transaction enquiries."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from rubies_security.identity import (
    CustomerMismatchError,
    IdentityVerificationError,
)
from rubies_shared.identity import CustomerIdentity
from sqlalchemy.orm import Session

from rubies_banking_api.api.dependencies import get_customer_identity
from rubies_banking_api.db.database import get_db
from rubies_banking_api.repositories.customer_repository import (
    CustomerRepository,
)
from rubies_banking_api.models.account import Account
from rubies_banking_api.repositories.transaction_repository import (
    TransactionRepository,
)
from rubies_banking_api.services.transaction_enquiry_service import (
    TransactionEnquiryService,
)

router = APIRouter(tags=["Transaction Enquiries"])


class TransactionResponse(BaseModel):
    """Safe transaction fields returned in a mini statement."""

    reference: str
    transaction_type: str
    amount: Decimal
    status: str
    description: str | None
    created_at: datetime


class TransactionStatusResponse(BaseModel):
    """Safe details returned for a transaction status enquiry."""

    reference: str
    status: str
    transaction_type: str
    amount: Decimal
    currency: str
    created_at: datetime


class MiniStatementResponse(BaseModel):
    """Paginated transactions belonging to an account."""

    account_reference: str
    currency: str
    items: list[TransactionResponse]
    limit: int
    offset: int


def _build_service(db: Session) -> TransactionEnquiryService:
    """Build the transaction enquiry service for a request."""
    return TransactionEnquiryService(
        transaction_repository=TransactionRepository(db),
        customer_repository=CustomerRepository(db),
    )


def _map_identity_error(exc: IdentityVerificationError) -> HTTPException:
    return HTTPException(
        status_code=401,
        detail="A verified customer identity is required.",
    )


def _map_customer_error(exc: CustomerMismatchError) -> HTTPException:
    return HTTPException(
        status_code=403,
        detail="The requested resource is not available to this customer.",
    )


@router.get("/api/accounts/{account_reference}/balance")
def get_account_balance(
    account_reference: str,
    db: Annotated[Session, Depends(get_db)],
    identity: Annotated[CustomerIdentity, Depends(get_customer_identity)],
) -> dict[str, object]:
    """Return the balance for an account owned by the verified customer."""
    if not identity.verified:
        raise HTTPException(status_code=401, detail="A verified customer identity is required.")

    customer = CustomerRepository(db).get_by_reference(identity.customer_id)
    if customer is None or not customer.is_active:
        raise HTTPException(status_code=403, detail="The customer account is not available.")

    account = db.scalar(
        select(Account).where(Account.account_number == account_reference)
    )
    if account is None or account.customer_id != customer.id:
        raise HTTPException(status_code=404, detail="The requested account is not available.")
    if account.status != "ACTIVE":
        raise HTTPException(status_code=409, detail="The account is not active.")

    return {
        "success": True,
        "data": {
            "account_reference": account.account_number,
            "balance": str(account.balance),
            "currency": account.currency,
            "status": account.status,
        },
    }


@router.get(
    "/api/accounts/{account_reference}/mini-statement",
    response_model=MiniStatementResponse,
)
def get_mini_statement(
    account_reference: str,
    db: Annotated[Session, Depends(get_db)],
    identity: Annotated[
        CustomerIdentity,
        Depends(get_customer_identity),
    ],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> MiniStatementResponse:
    """Return recent transactions for an account owned by the customer."""
    service = _build_service(db)

    try:
        # The service validates ownership and returns the validated account
        # alongside its transactions. Do not perform a second account lookup.
        account, transactions = service.get_mini_statement(
            identity,
            account_reference=account_reference,
            limit=limit,
            offset=offset,
        )

        return MiniStatementResponse(
            account_reference=account.account_number,
            currency=account.currency,
            items=[
                TransactionResponse(
                    reference=transaction.reference,
                    transaction_type=transaction.transaction_type,
                    amount=transaction.amount,
                    status=transaction.status,
                    description=transaction.description,
                    created_at=transaction.created_at,
                )
                for transaction in transactions
            ],
            limit=limit,
            offset=offset,
        )

    except IdentityVerificationError as exc:
        raise _map_identity_error(exc) from exc
    except CustomerMismatchError as exc:
        raise _map_customer_error(exc) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail="The requested account is not available.",
        ) from exc


@router.get(
    "/api/transactions/{transaction_reference}/status",
    response_model=TransactionStatusResponse,
)
def get_transaction_status(
    transaction_reference: str,
    db: Annotated[Session, Depends(get_db)],
    identity: Annotated[
        CustomerIdentity,
        Depends(get_customer_identity),
    ],
) -> TransactionStatusResponse:
    """Return the status of a transaction owned by the customer."""
    service = _build_service(db)

    try:
        transaction = service.get_transaction_status(
            identity,
            transaction_reference=transaction_reference,
        )

        return TransactionStatusResponse(
            reference=transaction.reference,
            status=transaction.status,
            transaction_type=transaction.transaction_type,
            amount=transaction.amount,
            currency=transaction.account.currency,
            created_at=transaction.created_at,
        )

    except IdentityVerificationError as exc:
        raise _map_identity_error(exc) from exc
    except CustomerMismatchError as exc:
        raise _map_customer_error(exc) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail="The requested transaction is not available.",
        ) from exc
