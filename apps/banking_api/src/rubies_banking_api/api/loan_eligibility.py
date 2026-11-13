
"""HTTP endpoint for preliminary loan eligibility assessments."""

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from rubies_observability import get_correlation_id
from rubies_security.identity import (
    CustomerMismatchError,
    IdentityVerificationError,
)
from rubies_shared.identity import CustomerIdentity
from sqlalchemy.orm import Session

from rubies_banking_api.api.dependencies import get_customer_identity
from rubies_banking_api.db.database import get_db
from rubies_banking_api.repositories.audit_repository import AuditRepository
from rubies_banking_api.repositories.customer_repository import CustomerRepository
from rubies_banking_api.schemas.loan_eligibility import (
    LoanEligibilityRequest,
    LoanEligibilityResponse,
)
from rubies_banking_api.services.loan_eligibility_service import (
    LoanEligibilityService,
)

router = APIRouter(
    prefix="/api/loans/eligibility",
    tags=["Loan Eligibility"],
)


def _build_service(db: Session) -> LoanEligibilityService:
    """Build the eligibility service with request-scoped repositories."""
    return LoanEligibilityService(
        customer_repository=CustomerRepository(db),
        audit_repository=AuditRepository(db),
    )


@router.post(
    "/check",
    response_model=LoanEligibilityResponse,
    status_code=status.HTTP_200_OK,
)
def check_loan_eligibility(
    request: LoanEligibilityRequest,
    db: Annotated[Session, Depends(get_db)],
    identity: Annotated[CustomerIdentity, Depends(get_customer_identity)],
) -> LoanEligibilityResponse:
    """
    Assess preliminary loan eligibility for the authenticated customer.

    This endpoint does not create or approve a loan application.
    """
    correlation_id = get_correlation_id() or uuid4().hex
    service = _build_service(db)

    try:
        assessment = service.assess_eligibility(
            identity,
            product_code=request.product_code,
            requested_amount=request.requested_amount,
            term_months=request.term_months,
            correlation_id=correlation_id,
        )

        db.commit()

        return LoanEligibilityResponse(
            result=assessment.result,
            product_code=assessment.product_code,
            requested_amount=assessment.requested_amount,
            term_months=assessment.term_months,
            currency=assessment.currency,
            disposable_income=assessment.disposable_income,
            estimated_monthly_principal=(
                assessment.estimated_monthly_principal
            ),
            reason_codes=list(assessment.reason_codes),
            explanation=assessment.explanation,
            policy_document_id=assessment.policy_document_id,
            policy_version=assessment.policy_version,
            ruleset_version=assessment.ruleset_version,
            assessed_at=assessment.assessed_at,
            correlation_id=assessment.correlation_id,
        )

    except IdentityVerificationError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A verified customer identity is required.",
        ) from exc

    except CustomerMismatchError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The authenticated customer is not available.",
        ) from exc

    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    except Exception:
        db.rollback()
        raise
