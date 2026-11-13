
"""Business rules for read-only loan enquiries."""

from rubies_security.identity import (
    CustomerMismatchError,
    IdentityVerificationError,
)
from rubies_shared.identity import CustomerIdentity

from rubies_banking_api.models.customer import Customer
from rubies_banking_api.models.loan import Loan
from rubies_banking_api.models.loan_application import LoanApplication
from rubies_banking_api.repositories.customer_repository import (
    CustomerRepository,
)
from rubies_banking_api.repositories.loan_application_repository import (
    LoanApplicationRepository,
)
from rubies_banking_api.repositories.loan_repository import LoanRepository


class LoanEnquiryService:
    """Enforce customer identity and ownership for loan enquiries."""

    def __init__(
        self,
        loan_repository: LoanRepository,
        loan_application_repository: LoanApplicationRepository,
        customer_repository: CustomerRepository,
    ) -> None:
        self.loan_repository = loan_repository
        self.loan_application_repository = loan_application_repository
        self.customer_repository = customer_repository

    def _resolve_customer(self, identity: CustomerIdentity) -> Customer:
        """Resolve the verified identity to an active customer."""
        if not identity.verified:
            raise IdentityVerificationError(
                "A verified customer identity is required."
            )

        customer = self.customer_repository.get_by_reference(
            identity.customer_id
        )

        if customer is None or not customer.is_active:
            raise CustomerMismatchError(
                "The customer account is not available."
            )

        return customer

    def get_customer_loan_overview(
        self,
        identity: CustomerIdentity,
    ) -> tuple[list[Loan], list[LoanApplication]]:
        """
        Retrieve all loans and applications belonging to the
        authenticated customer.
        """
        customer = self._resolve_customer(identity)

        loans = self.loan_repository.list_all_by_customer(customer.id)

        applications = (
            self.loan_application_repository.list_by_customer(customer.id)
        )

        # Verify ownership of every loan and its linked application.
        for loan in loans:
            if loan.customer_id != customer.id:
                raise CustomerMismatchError(
                    "The requested loan is not available to this customer."
                )

            if loan.application.customer_id != customer.id:
                raise CustomerMismatchError(
                    "The requested loan is not available to this customer."
                )

        # Verify ownership of every application.
        for application in applications:
            if application.customer_id != customer.id:
                raise CustomerMismatchError(
                    "The requested loan application is not available "
                    "to this customer."
                )

        return loans, applications

    def get_active_loans(
        self,
        identity: CustomerIdentity,
    ) -> list[Loan]:
        """Retrieve active and overdue loans for the authenticated customer."""
        customer = self._resolve_customer(identity)

        loans = self.loan_repository.list_active_by_customer(customer.id)

        for loan in loans:
            if loan.customer_id != customer.id:
                raise CustomerMismatchError(
                    "The requested loan is not available to this customer."
                )

            if loan.application.customer_id != customer.id:
                raise CustomerMismatchError(
                    "The requested loan is not available to this customer."
                )

        return loans

    def get_loan_status(
        self,
        identity: CustomerIdentity,
        *,
        loan_reference: str,
    ) -> Loan:
        """Retrieve a loan after validating customer ownership."""
        customer = self._resolve_customer(identity)

        loan = self.loan_repository.get_by_reference(loan_reference)

        if loan is None:
            raise ValueError("Loan not found.")

        if loan.customer_id != customer.id:
            raise CustomerMismatchError(
                "The requested loan is not available to this customer."
            )

        if loan.application.customer_id != customer.id:
            raise CustomerMismatchError(
                "The requested loan is not available to this customer."
            )

        return loan

    def get_loan_application_status(
        self,
        identity: CustomerIdentity,
        *,
        application_reference: str,
    ) -> LoanApplication:
        """Retrieve an application after validating customer ownership."""
        customer = self._resolve_customer(identity)

        application = (
            self.loan_application_repository.get_by_reference(
                application_reference
            )
        )

        if application is None:
            raise ValueError("Loan application not found.")

        if application.customer_id != customer.id:
            raise CustomerMismatchError(
                "The requested loan application is not available "
                "to this customer."
            )

        return application
