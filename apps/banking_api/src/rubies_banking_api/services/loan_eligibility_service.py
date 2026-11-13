
"""Preliminary, policy-driven loan eligibility assessment."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from rubies_security.identity import (
    CustomerMismatchError,
    require_customer_match,
    require_verified_identity,
)
from rubies_shared.audit import AuditEvent
from rubies_shared.identity import CustomerIdentity

from rubies_banking_api.models.customer import Customer
from rubies_banking_api.repositories.audit_repository import AuditRepository
from rubies_banking_api.repositories.customer_repository import CustomerRepository

POLICY_DOCUMENT_ID = "RB-POL-LOAN-001"
POLICY_VERSION = "0.3"
RULESET_VERSION = "loan-eligibility-v0.3"
FEATURE_SCHEMA_VERSION = "loan-eligibility-profile-v1"

PROFILE_FRESHNESS_DAYS = 90

ELIGIBLE_FOR_REVIEW = "ELIGIBLE_FOR_REVIEW"
NOT_ELIGIBLE_UNDER_CURRENT_RULES = "NOT_ELIGIBLE_UNDER_CURRENT_RULES"
INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
OUT_OF_SCOPE = "OUT_OF_SCOPE"

PRODUCT_RULES = {
    "SALARY_ADVANCE": {
        "minimum_amount": Decimal("20000.00"),
        "maximum_amount": Decimal("200000.00"),
        "minimum_term": 1,
        "maximum_term": 3,
        "employment_types": {"SALARIED"},
    },
    "MICRO_BUSINESS": {
        "minimum_amount": Decimal("50000.00"),
        "maximum_amount": Decimal("500000.00"),
        "minimum_term": 3,
        "maximum_term": 6,
        "employment_types": {"SELF_EMPLOYED", "BUSINESS_OWNER"},
    },
}


@dataclass(frozen=True, slots=True)
class LoanEligibilityAssessment:
    """Structured result of a preliminary eligibility assessment."""

    result: str
    product_code: str
    requested_amount: Decimal
    term_months: int
    currency: str
    disposable_income: Decimal | None
    estimated_monthly_principal: Decimal | None
    reason_codes: tuple[str, ...]
    explanation: str
    policy_document_id: str
    policy_version: str
    ruleset_version: str
    assessed_at: datetime
    correlation_id: str


class LoanEligibilityService:
    """Evaluate preliminary loan eligibility using deterministic policy rules."""

    def __init__(
        self,
        customer_repository: CustomerRepository,
        audit_repository: AuditRepository,
    ) -> None:
        self.customer_repository = customer_repository
        self.audit_repository = audit_repository

    def _resolve_customer(self, identity: CustomerIdentity) -> Customer:
        """Resolve the verified identity to its active customer record."""
        verified_identity = require_verified_identity(identity)

        customer = self.customer_repository.get_by_reference(
            verified_identity.customer_id
        )

        if customer is None:
            raise CustomerMismatchError(
                "The verified customer could not be found."
            )

        require_customer_match(
            verified_identity,
            customer.customer_reference,
        )

        if not customer.is_active:
            raise CustomerMismatchError(
                "The customer record is not active."
            )

        return customer

    def _record_assessment(
        self,
        *,
        customer: Customer,
        product_code: str,
        requested_amount: Decimal,
        term_months: int,
        result: str,
        reason_codes: tuple[str, ...],
        correlation_id: str,
        assessed_at: datetime,
    ) -> None:
        """Persist a minimal audit event without financial profile values."""
        self.audit_repository.record(
            AuditEvent(
                event_id=f"AUD-{uuid4().hex}",
                occurred_at=assessed_at,
                actor_id=customer.customer_reference,
                action="CHECK_LOAN_ELIGIBILITY",
                outcome="COMPLETED",
                correlation_id=correlation_id,
                details={
                    "customer_reference": customer.customer_reference,
                    "product_code": product_code,
                    "requested_amount": str(requested_amount),
                    "term_months": term_months,
                    "result": result,
                    "reason_codes": list(reason_codes),
                    "policy_document_id": POLICY_DOCUMENT_ID,
                    "policy_version": POLICY_VERSION,
                    "ruleset_version": RULESET_VERSION,
                    "feature_schema_version": FEATURE_SCHEMA_VERSION,
                },
            )
        )

    def _build_assessment(
        self,
        *,
        customer: Customer,
        product_code: str,
        requested_amount: Decimal,
        term_months: int,
        result: str,
        reason_codes: tuple[str, ...],
        explanation: str,
        correlation_id: str,
        assessed_at: datetime,
        disposable_income: Decimal | None = None,
        estimated_monthly_principal: Decimal | None = None,
    ) -> LoanEligibilityAssessment:
        """Create an assessment and persist its audit event."""
        self._record_assessment(
            customer=customer,
            product_code=product_code,
            requested_amount=requested_amount,
            term_months=term_months,
            result=result,
            reason_codes=reason_codes,
            correlation_id=correlation_id,
            assessed_at=assessed_at,
        )

        return LoanEligibilityAssessment(
            result=result,
            product_code=product_code,
            requested_amount=requested_amount,
            term_months=term_months,
            currency="NGN",
            disposable_income=disposable_income,
            estimated_monthly_principal=estimated_monthly_principal,
            reason_codes=reason_codes,
            explanation=explanation,
            policy_document_id=POLICY_DOCUMENT_ID,
            policy_version=POLICY_VERSION,
            ruleset_version=RULESET_VERSION,
            assessed_at=assessed_at,
            correlation_id=correlation_id,
        )

    def assess_eligibility(
        self,
        identity: CustomerIdentity,
        *,
        product_code: str,
        requested_amount: Decimal,
        term_months: int,
        correlation_id: str,
        now: datetime | None = None,
    ) -> LoanEligibilityAssessment:
        """
        Assess a customer's preliminary eligibility under the current policy.

        This operation does not create, approve, modify, or disburse a loan.
        """
        verified_identity = require_verified_identity(identity)

        normalized_product = product_code.strip().upper()

        if not normalized_product:
            raise ValueError("A loan product code is required.")

        if requested_amount <= Decimal("0"):
            raise ValueError("Requested amount must be greater than zero.")

        if term_months <= 0:
            raise ValueError("Term must be greater than zero.")

        if not correlation_id.strip():
            raise ValueError("A correlation ID is required.")

        assessed_at = now or datetime.now(UTC)

        if assessed_at.tzinfo is None or assessed_at.utcoffset() is None:
            raise ValueError("now must be timezone-aware.")

        customer = self._resolve_customer(verified_identity)

        if not any(account.status == "ACTIVE" for account in customer.accounts):
            return self._build_assessment(
                customer=customer,
                product_code=normalized_product,
                requested_amount=requested_amount,
                term_months=term_months,
                result=NOT_ELIGIBLE_UNDER_CURRENT_RULES,
                reason_codes=("NO_ACTIVE_ACCOUNT",),
                explanation=(
                    "An active customer account is required for this "
                    "loan product."
                ),
                correlation_id=correlation_id,
                assessed_at=assessed_at,
            )

        product = PRODUCT_RULES.get(normalized_product)

        if product is None:
            return self._build_assessment(
                customer=customer,
                product_code=normalized_product,
                requested_amount=requested_amount,
                term_months=term_months,
                result=OUT_OF_SCOPE,
                reason_codes=("UNSUPPORTED_LOAN_PRODUCT",),
                explanation=(
                    "This loan product is not covered by the current "
                    "eligibility policy."
                ),
                correlation_id=correlation_id,
                assessed_at=assessed_at,
            )

        failed_rules: list[str] = []

        if not (
            product["minimum_amount"]
            <= requested_amount
            <= product["maximum_amount"]
        ):
            failed_rules.append("REQUESTED_AMOUNT_OUT_OF_RANGE")

        if not (
            product["minimum_term"]
            <= term_months
            <= product["maximum_term"]
        ):
            failed_rules.append("REQUESTED_TERM_OUT_OF_RANGE")

        profile = customer.loan_eligibility_profile

        if profile is None:
            return self._build_assessment(
                customer=customer,
                product_code=normalized_product,
                requested_amount=requested_amount,
                term_months=term_months,
                result=INSUFFICIENT_DATA,
                reason_codes=("ELIGIBILITY_PROFILE_MISSING",),
                explanation=(
                    "Financial eligibility information is not available."
                ),
                correlation_id=correlation_id,
                assessed_at=assessed_at,
            )

        if profile.verification_status != "VERIFIED":
            return self._build_assessment(
                customer=customer,
                product_code=normalized_product,
                requested_amount=requested_amount,
                term_months=term_months,
                result=INSUFFICIENT_DATA,
                reason_codes=("FINANCIAL_PROFILE_NOT_VERIFIED",),
                explanation=(
                    "Financial information must be verified before "
                    "eligibility can be assessed."
                ),
                correlation_id=correlation_id,
                assessed_at=assessed_at,
            )

        # A verified profile is valid for no more than 90 calendar days.
        # Updating the profile must not renew its verification timestamp.
        verified_at = profile.verified_at

        if verified_at is None:
            return self._build_assessment(
                customer=customer,
                product_code=normalized_product,
                requested_amount=requested_amount,
                term_months=term_months,
                result=INSUFFICIENT_DATA,
                reason_codes=(
                    "FINANCIAL_PROFILE_VERIFICATION_TIMESTAMP_MISSING",
                ),
                explanation=(
                    "The financial profile has no verification timestamp. "
                    "It must be verified before eligibility can be assessed."
                ),
                correlation_id=correlation_id,
                assessed_at=assessed_at,
            )

        if verified_at.tzinfo is None or verified_at.utcoffset() is None:
            return self._build_assessment(
                customer=customer,
                product_code=normalized_product,
                requested_amount=requested_amount,
                term_months=term_months,
                result=INSUFFICIENT_DATA,
                reason_codes=(
                    "FINANCIAL_PROFILE_VERIFICATION_TIMESTAMP_INVALID",
                ),
                explanation=(
                    "The financial profile verification timestamp is invalid. "
                    "The profile must be verified again."
                ),
                correlation_id=correlation_id,
                assessed_at=assessed_at,
            )

        verified_at_utc = verified_at.astimezone(UTC)
        assessed_at_utc = assessed_at.astimezone(UTC)

        if verified_at_utc > assessed_at_utc:
            return self._build_assessment(
                customer=customer,
                product_code=normalized_product,
                requested_amount=requested_amount,
                term_months=term_months,
                result=INSUFFICIENT_DATA,
                reason_codes=(
                    "FINANCIAL_PROFILE_VERIFICATION_TIMESTAMP_IN_FUTURE",
                ),
                explanation=(
                    "The financial profile verification timestamp is in "
                    "the future. The profile must be verified again."
                ),
                correlation_id=correlation_id,
                assessed_at=assessed_at,
            )

        profile_age = assessed_at_utc - verified_at_utc

        if profile_age > timedelta(days=PROFILE_FRESHNESS_DAYS):
            return self._build_assessment(
                customer=customer,
                product_code=normalized_product,
                requested_amount=requested_amount,
                term_months=term_months,
                result=INSUFFICIENT_DATA,
                reason_codes=("FINANCIAL_PROFILE_STALE",),
                explanation=(
                    "The financial profile was verified more than "
                    f"{PROFILE_FRESHNESS_DAYS} calendar days ago. "
                    "Updated financial information must be verified "
                    "before eligibility can be assessed."
                ),
                correlation_id=correlation_id,
                assessed_at=assessed_at,
            )

        if profile.employment_type not in product["employment_types"]:
            failed_rules.append("EMPLOYMENT_TYPE_NOT_SUPPORTED")

        required_financial_values = (
            profile.monthly_income,
            profile.monthly_expenses,
            profile.existing_monthly_debt,
        )

        if any(value is None for value in required_financial_values):
            return self._build_assessment(
                customer=customer,
                product_code=normalized_product,
                requested_amount=requested_amount,
                term_months=term_months,
                result=INSUFFICIENT_DATA,
                reason_codes=("REQUIRED_FINANCIAL_DATA_MISSING",),
                explanation=(
                    "Monthly income, expenses and existing monthly debt "
                    "must all be available."
                ),
                correlation_id=correlation_id,
                assessed_at=assessed_at,
            )

        monthly_income = profile.monthly_income
        monthly_expenses = profile.monthly_expenses
        existing_monthly_debt = profile.existing_monthly_debt

        if (
            monthly_income <= Decimal("0")
            or monthly_expenses < Decimal("0")
            or existing_monthly_debt < Decimal("0")
        ):
            return self._build_assessment(
                customer=customer,
                product_code=normalized_product,
                requested_amount=requested_amount,
                term_months=term_months,
                result=INSUFFICIENT_DATA,
                reason_codes=("INVALID_FINANCIAL_DATA",),
                explanation=(
                    "The financial information contains invalid values."
                ),
                correlation_id=correlation_id,
                assessed_at=assessed_at,
            )

        disposable_income = (
            monthly_income
            - monthly_expenses
            - existing_monthly_debt
        )

        estimated_monthly_principal = (
            requested_amount / Decimal(term_months)
        ).quantize(Decimal("0.01"))

        if disposable_income <= Decimal("0"):
            failed_rules.append("NON_POSITIVE_DISPOSABLE_INCOME")
        elif disposable_income < estimated_monthly_principal:
            failed_rules.append("AFFORDABILITY_THRESHOLD_NOT_MET")

        if failed_rules:
            return self._build_assessment(
                customer=customer,
                product_code=normalized_product,
                requested_amount=requested_amount,
                term_months=term_months,
                result=NOT_ELIGIBLE_UNDER_CURRENT_RULES,
                reason_codes=tuple(failed_rules),
                explanation=(
                    "The requested loan does not meet one or more "
                    "requirements under the current preliminary "
                    "eligibility policy."
                ),
                correlation_id=correlation_id,
                assessed_at=assessed_at,
                disposable_income=disposable_income,
                estimated_monthly_principal=estimated_monthly_principal,
            )

        return self._build_assessment(
            customer=customer,
            product_code=normalized_product,
            requested_amount=requested_amount,
            term_months=term_months,
            result=ELIGIBLE_FOR_REVIEW,
            reason_codes=("PRELIMINARY_AFFORDABILITY_RULES_MET",),
            explanation=(
                "The customer meets the current preliminary product "
                "and affordability rules. This is not a loan approval."
            ),
            correlation_id=correlation_id,
            assessed_at=assessed_at,
            disposable_income=disposable_income,
            estimated_monthly_principal=estimated_monthly_principal,
        )
