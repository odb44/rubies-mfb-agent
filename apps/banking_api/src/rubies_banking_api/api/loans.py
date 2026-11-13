
"""HTTP endpoints for read-only loan enquiries."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from rubies_security.identity import (
    CustomerMismatchError,
    IdentityVerificationError,
)
from rubies_shared.identity import CustomerIdentity
from sqlalchemy.orm import Session

from rubies_banking_api.api.dependencies import get_customer_identity
from rubies_banking_api.db.database import get_db
from rubies_banking_api.models.loan import Loan
from rubies_banking_api.models.loan_application import LoanApplication
from rubies_banking_api.models.repayment import Repayment
from rubies_banking_api.repositories.customer_repository import (
    CustomerRepository,
)
from rubies_banking_api.repositories.loan_application_repository import (
    LoanApplicationRepository,
)
from rubies_banking_api.repositories.loan_repository import LoanRepository
from rubies_banking_api.services.loan_enquiry_service import LoanEnquiryService

router = APIRouter(tags=["Loan Enquiries"])


class LoanStatusResponse(BaseModel):
    """Safe details returned for a loan status enquiry."""

    loan_reference: str
    status: str
    principal: Decimal
    outstanding_balance: Decimal
    currency: str
    term_months: int
    disbursed_at: datetime
    next_repayment_date: date | None
    next_repayment_amount: Decimal | None


class LoanApplicationStatusResponse(BaseModel):
    """Safe details returned for a loan application status enquiry."""

    application_reference: str
    status: str
    requested_amount: Decimal
    currency: str
    purpose: str
    applied_at: datetime
    created_at: datetime


class CustomerLoanOverviewResponse(BaseModel):
    """Combined loan and application information for a customer."""

    loans: list[LoanStatusResponse]
    applications: list[LoanApplicationStatusResponse]


def _build_service(db: Session) -> LoanEnquiryService:
    """Build the loan enquiry service for a request."""
    return LoanEnquiryService(
        loan_repository=LoanRepository(db),
        loan_application_repository=LoanApplicationRepository(db),
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


def _get_next_repayment(loan: Loan) -> Repayment | None:
    """Return the earliest unpaid repayment for a loan."""
    outstanding_repayments = [
        repayment
        for repayment in loan.repayments
        if repayment.status in {"PENDING", "OVERDUE"}
    ]

    if not outstanding_repayments:
        return None

    return min(
        outstanding_repayments,
        key=lambda repayment: (
            repayment.due_date,
            repayment.installment_number,
        ),
    )


def _build_loan_status_response(loan: Loan) -> LoanStatusResponse:
    """Build a loan response including its next scheduled repayment."""
    next_repayment = _get_next_repayment(loan)

    return LoanStatusResponse(
        loan_reference=loan.loan_reference,
        status=loan.status,
        principal=loan.principal,
        outstanding_balance=loan.outstanding_balance,
        currency=loan.currency,
        term_months=loan.term_months,
        disbursed_at=loan.disbursed_at,
        next_repayment_date=(
            next_repayment.due_date if next_repayment else None
        ),
        next_repayment_amount=(
            next_repayment.principal_due if next_repayment else None
        ),
    )


def _build_application_status_response(
    application: LoanApplication,
) -> LoanApplicationStatusResponse:
    """Build a safe loan application response."""
    return LoanApplicationStatusResponse(
        application_reference=application.application_reference,
        status=application.status,
        requested_amount=application.requested_amount,
        currency=application.currency,
        purpose=application.purpose,
        applied_at=application.applied_at,
        created_at=application.created_at,
    )


@router.get(
    "/api/loans/status",
    response_model=CustomerLoanOverviewResponse,
)
def get_customer_loan_status(
    db: Annotated[Session, Depends(get_db)],
    identity: Annotated[
        CustomerIdentity,
        Depends(get_customer_identity),
    ],
) -> CustomerLoanOverviewResponse:
    """
    Return all loans and loan applications for the authenticated customer.
    """
    service = _build_service(db)

    try:
        loans, applications = service.get_customer_loan_overview(identity)

        return CustomerLoanOverviewResponse(
            loans=[
                _build_loan_status_response(loan)
                for loan in loans
            ],
            applications=[
                _build_application_status_response(application)
                for application in applications
            ],
        )

    except IdentityVerificationError as exc:
        raise _map_identity_error(exc) from exc

    except CustomerMismatchError as exc:
        raise _map_customer_error(exc) from exc


@router.get(
    "/api/loans/{loan_reference}/status",
    response_model=LoanStatusResponse,
)
def get_loan_status(
    loan_reference: str,
    db: Annotated[Session, Depends(get_db)],
    identity: Annotated[
        CustomerIdentity,
        Depends(get_customer_identity),
    ],
) -> LoanStatusResponse:
    """Return the status of a loan owned by the authenticated customer."""
    service = _build_service(db)

    try:
        loan = service.get_loan_status(
            identity,
            loan_reference=loan_reference,
        )

        return _build_loan_status_response(loan)

    except IdentityVerificationError as exc:
        raise _map_identity_error(exc) from exc

    except CustomerMismatchError as exc:
        raise _map_customer_error(exc) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail="The requested loan is not available.",
        ) from exc


@router.get(
    "/api/loan-applications/{application_reference}/status",
    response_model=LoanApplicationStatusResponse,
)
def get_loan_application_status(
    application_reference: str,
    db: Annotated[Session, Depends(get_db)],
    identity: Annotated[
        CustomerIdentity,
        Depends(get_customer_identity),
    ],
) -> LoanApplicationStatusResponse:
    """Return the status of an application owned by the customer."""
    service = _build_service(db)

    try:
        application = service.get_loan_application_status(
            identity,
            application_reference=application_reference,
        )

        return _build_application_status_response(application)

    except IdentityVerificationError as exc:
        raise _map_identity_error(exc) from exc

    except CustomerMismatchError as exc:
        raise _map_customer_error(exc) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail="The requested loan application is not available.",
        ) from exc
