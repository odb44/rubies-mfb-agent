
from __future__ import annotations

import argparse
import calendar
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, ROUND_DOWN
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.engine import make_url

from rubies_banking_api.config import get_settings
from rubies_banking_api.db.database import SessionLocal
from rubies_banking_api.models.account import Account
from rubies_banking_api.models.card import Card
from rubies_banking_api.models.customer import Customer
from rubies_banking_api.models.loan import Loan
from rubies_banking_api.models.loan_application import LoanApplication
from rubies_banking_api.models.repayment import Repayment
from rubies_banking_api.models.transaction import Transaction
from rubies_banking_api.models.loan_eligibility_profile import (
    LoanEligibilityProfile,
)


# Reserved exclusively for this local demonstration.
DEMO_PREFIX = "CUST-DEMO-"
ACCOUNT_PREFIX = "90000000"
LOAN_PREFIX = "DEMO-LOAN-"
REPAYMENT_PREFIX = "DEMO-REPAY-"
LAGOS = ZoneInfo("Africa/Lagos")

LOAN_PRINCIPAL = Decimal("200000.00")
LOAN_TERM_MONTHS = 6
MONEY_QUANTUM = Decimal("0.01")

PROFILES = [
    {
        "reference": "CUST-DEMO-001",
        "name": "Demo Customer",
        "phone": "08012345678",
        "email": "demo.customer@rubies.local",
        "account": "9000000001",
        "card": "DEMO-CARD-001",
        "masked_card": "**** **** **** 1001",
        "application": "DEMO-APP-001",
        "application_status": "APPROVED",
        "loan_scenario": "ACTIVE",
    },
    {
        "reference": "CUST-DEMO-002",
        "name": "Ada Okafor",
        "phone": "+2348000000002",
        "email": "ada.okafor@rubies.local",
        "account": "9000000002",
        "card": "DEMO-CARD-002",
        "masked_card": "**** **** **** 1002",
        "application": "DEMO-APP-002",
        "application_status": "APPROVED",
        "loan_scenario": "OVERDUE",
    },
    {
        "reference": "CUST-DEMO-003",
        "name": "Tunde Balogun",
        "phone": "+2348000000003",
        "email": "tunde.balogun@rubies.local",
        "account": "9000000003",
        "card": "DEMO-CARD-003",
        "masked_card": "**** **** **** 1003",
        "application": "DEMO-APP-003",
        "application_status": "APPROVED",
        "loan_scenario": "REPAID",
    },
    {
        "reference": "CUST-DEMO-004",
        "name": "Chioma Eze",
        "phone": "+2348000000004",
        "email": "chioma.eze@rubies.local",
        "account": "9000000004",
        "card": "DEMO-CARD-004",
        "masked_card": "**** **** **** 1004",
        "application": "DEMO-APP-004",
        "application_status": "APPROVED",
        "loan_scenario": None,
    },
    {
        "reference": "CUST-DEMO-005",
        "name": "Ibrahim Musa",
        "phone": "+2348000000005",
        "email": "ibrahim.musa@rubies.local",
        "account": "9000000005",
        "card": "DEMO-CARD-005",
        "masked_card": "**** **** **** 1005",
        "application": "DEMO-APP-005",
        "application_status": "PENDING",
        "loan_scenario": None,
    },
]


# Synthetic financial data reserved exclusively for local demonstrations.
# These values are not customer-submitted or verified financial information.
ELIGIBILITY_PROFILE_FIXTURES = {
    "CUST-DEMO-001": {
        "employment_type": "SALARIED",
        "monthly_income": Decimal("450000.00"),
        "monthly_expenses": Decimal("180000.00"),
        "existing_monthly_debt": Decimal("50000.00"),
    },
    "CUST-DEMO-002": {
        "employment_type": "SALARIED",
        "monthly_income": Decimal("350000.00"),
        "monthly_expenses": Decimal("160000.00"),
        "existing_monthly_debt": Decimal("40000.00"),
    },
    "CUST-DEMO-003": {
        "employment_type": "BUSINESS_OWNER",
        "monthly_income": Decimal("600000.00"),
        "monthly_expenses": Decimal("250000.00"),
        "existing_monthly_debt": Decimal("75000.00"),
    },
    "CUST-DEMO-004": {
        "employment_type": "SELF_EMPLOYED",
        "monthly_income": Decimal("300000.00"),
        "monthly_expenses": Decimal("140000.00"),
        "existing_monthly_debt": Decimal("0.00"),
    },
    "CUST-DEMO-005": {
        "employment_type": "SALARIED",
        "monthly_income": Decimal("250000.00"),
        "monthly_expenses": Decimal("120000.00"),
        "existing_monthly_debt": Decimal("25000.00"),
    },
}


def assert_safe_database() -> None:
    """Refuse to seed a database outside the expected local development DB."""
    url = make_url(get_settings().database_url)

    if (
        url.drivername != "postgresql+psycopg"
        or url.host not in {"localhost", "127.0.0.1", "::1"}
        or url.database != "rubies_mfb"
    ):
        raise RuntimeError(
            "Refusing to seed. Expected the local PostgreSQL database "
            "'rubies_mfb' on localhost. Check your database configuration."
        )


def add_months(value: date, months: int) -> date:
    """Add calendar months without overflowing the destination month."""
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])

    return date(year, month, day)


def get_or_create_customer(db, profile: dict) -> Customer:
    customer = db.scalar(
        select(Customer).where(
            Customer.customer_reference == profile["reference"]
        )
    )

    if customer is None:
        # Never take over a phone number or email already assigned to
        # a different customer.
        phone_owner = db.scalar(
            select(Customer).where(
                Customer.phone_number == profile["phone"]
            )
        )
        email_owner = db.scalar(
            select(Customer).where(
                Customer.email == profile["email"]
            )
        )

        if phone_owner or email_owner:
            raise RuntimeError(
                f"Phone/email collision while creating "
                f"{profile['reference']}; no changes should be applied."
            )

        customer = Customer(
            customer_reference=profile["reference"],
            full_name=profile["name"],
            email=profile["email"],
            phone_number=profile["phone"],
            is_active=True,
        )
        db.add(customer)
        db.flush()
        return customer

    # Preserve existing customer identity and contact details.
    # In particular, do not overwrite the existing first demo customer's
    # registered phone number.
    if not customer.is_active:
        customer.is_active = True

    return customer


def get_or_create_account(db, customer: Customer, profile: dict) -> Account:
    account = db.scalar(
        select(Account).where(
            Account.account_number == profile["account"]
        )
    )

    if account is not None and account.customer_id != customer.id:
        raise RuntimeError(
            f"Account {profile['account']} belongs to another customer."
        )

    if account is None:
        account = Account(
            customer_id=customer.id,
            account_number=profile["account"],
            currency="NGN",
            balance=Decimal("550000.00"),
            status="ACTIVE",
        )
        db.add(account)
        db.flush()
    else:
        account.currency = "NGN"
        account.balance = Decimal("550000.00")
        account.status = "ACTIVE"

    return account


def get_or_create_transaction(
    db,
    account: Account,
    reference: str,
    transaction_type: str,
    amount: Decimal,
    status: str,
    description: str,
    created_at: datetime,
) -> Transaction:
    transaction = db.scalar(
        select(Transaction).where(
            Transaction.reference == reference
        )
    )

    if transaction is not None and transaction.account_id != account.id:
        raise RuntimeError(
            f"Transaction {reference} belongs to another account."
        )

    if transaction is None:
        transaction = Transaction(
            account_id=account.id,
            reference=reference,
            transaction_type=transaction_type,
            amount=amount,
            status=status,
            description=description,
            created_at=created_at,
        )
        db.add(transaction)
    else:
        transaction.transaction_type = transaction_type
        transaction.amount = amount
        transaction.status = status
        transaction.description = description
        transaction.created_at = created_at

    return transaction


def get_or_create_card(db, customer: Customer, profile: dict) -> Card:
    card = db.scalar(
        select(Card).where(
            Card.card_reference == profile["card"]
        )
    )

    if card is not None and card.customer_id != customer.id:
        raise RuntimeError(
            f"Card {profile['card']} belongs to another customer."
        )

    if card is None:
        card = Card(
            customer_id=customer.id,
            card_reference=profile["card"],
            masked_number=profile["masked_card"],
            card_type="DEBIT",
            status="ACTIVE",
        )
        db.add(card)
        db.flush()
    else:
        card.masked_number = profile["masked_card"]
        card.card_type = "DEBIT"
        # Reset only this reserved demo card so the lost-card scenario
        # can be demonstrated again after reseeding.
        card.status = "ACTIVE"

    return card


def get_or_create_loan_application(
    db,
    customer: Customer,
    profile: dict,
    applied_at: datetime,
) -> LoanApplication:
    reference = profile["application"]

    application = db.scalar(
        select(LoanApplication).where(
            LoanApplication.application_reference == reference
        )
    )

    if application is not None and application.customer_id != customer.id:
        raise RuntimeError(
            f"Loan application {reference} belongs to another customer."
        )

    if application is None:
        application = LoanApplication(
            application_reference=reference,
            customer_id=customer.id,
            requested_amount=LOAN_PRINCIPAL,
            currency="NGN",
            purpose="Personal expenses",
            status=profile["application_status"],
            applied_at=applied_at,
        )
        db.add(application)
        db.flush()
    else:
        application.requested_amount = LOAN_PRINCIPAL
        application.currency = "NGN"
        application.purpose = "Personal expenses"
        application.status = profile["application_status"]
        application.applied_at = applied_at

    return application


def build_repayment_schedule(
    scenario: str,
    today: date,
    disbursed_at: date,
) -> list[dict]:
    """Build a deterministic six-installment principal repayment schedule."""
    base_installment = (
        LOAN_PRINCIPAL / LOAN_TERM_MONTHS
    ).quantize(MONEY_QUANTUM, rounding=ROUND_DOWN)

    installments = [
        base_installment
        for _ in range(LOAN_TERM_MONTHS - 1)
    ]
    installments.append(
        LOAN_PRINCIPAL - sum(installments)
    )

    schedule = []

    for number, principal_due in enumerate(installments, start=1):
        due_date = add_months(disbursed_at, number)

        if scenario == "ACTIVE":
            repayment_status = (
                "PAID" if number == 1 else "PENDING"
            )
        elif scenario == "OVERDUE":
            if number <= 2:
                repayment_status = "PAID"
            elif number == 3:
                repayment_status = "OVERDUE"
            else:
                repayment_status = "PENDING"
        elif scenario == "REPAID":
            repayment_status = "PAID"
        else:
            raise ValueError(
                f"Unsupported demo loan scenario: {scenario}"
            )

        paid_at = None

        if repayment_status == "PAID":
            # Keep payment timestamps before their due dates.
            paid_datetime = datetime.combine(
                due_date - timedelta(days=1),
                time(12, 0),
                tzinfo=UTC,
            )
            paid_at = paid_datetime

        schedule.append(
            {
                "installment_number": number,
                "principal_due": principal_due,
                "due_date": due_date,
                "status": repayment_status,
                "paid_at": paid_at,
            }
        )

    return schedule


def get_or_create_loan(
    db,
    customer: Customer,
    application: LoanApplication,
    profile: dict,
    today: date,
) -> Loan | None:
    """Create or update a reserved demo loan and its repayment schedule."""
    scenario = profile["loan_scenario"]

    if scenario is None:
        # The application is intentionally approved but not disbursed,
        # or remains pending. Do not create a loan.
        existing_loan = db.scalar(
            select(Loan).where(
                Loan.application_id == application.id
            )
        )

        if existing_loan is not None:
            raise RuntimeError(
                f"{profile['application']} is configured without a "
                "disbursed loan, but an existing loan is linked to it. "
                "Refusing to delete or silently alter that loan."
            )

        return None

    suffix = profile["reference"][-3:]
    loan_reference = f"{LOAN_PREFIX}{suffix}"

    loan = db.scalar(
        select(Loan).where(
            Loan.loan_reference == loan_reference
        )
    )

    if loan is not None and (
        loan.customer_id != customer.id
        or loan.application_id != application.id
    ):
        raise RuntimeError(
            f"Loan {loan_reference} belongs to another customer "
            "or application."
        )

    # The application_id is unique on Loan. Check for a conflicting
    # loan reference linked to this application before creating anything.
    linked_loan = db.scalar(
        select(Loan).where(
            Loan.application_id == application.id
        )
    )

    if linked_loan is not None and linked_loan.loan_reference != loan_reference:
        raise RuntimeError(
            f"Application {application.application_reference} is already "
            f"linked to loan {linked_loan.loan_reference}."
        )

    if scenario == "ACTIVE":
        disbursed_date = today - timedelta(days=45)
        loan_status = "ACTIVE"
    elif scenario == "OVERDUE":
        disbursed_date = today - timedelta(days=125)
        loan_status = "OVERDUE"
    elif scenario == "REPAID":
        disbursed_date = today - timedelta(days=210)
        loan_status = "REPAID"
    else:
        raise ValueError(
            f"Unsupported demo loan scenario: {scenario}"
        )

    schedule = build_repayment_schedule(
        scenario,
        today,
        disbursed_date,
    )

    outstanding_balance = sum(
        (
            item["principal_due"]
            for item in schedule
            if item["status"] != "PAID"
        ),
        Decimal("0.00"),
    )

    disbursed_at = datetime.combine(
        disbursed_date,
        time(10, 0),
        tzinfo=UTC,
    )

    if loan is None:
        loan = Loan(
            loan_reference=loan_reference,
            application_id=application.id,
            customer_id=customer.id,
            principal=LOAN_PRINCIPAL,
            currency="NGN",
            term_months=LOAN_TERM_MONTHS,
            status=loan_status,
            outstanding_balance=outstanding_balance,
            disbursed_at=disbursed_at,
        )
        db.add(loan)
        db.flush()
    else:
        loan.principal = LOAN_PRINCIPAL
        loan.currency = "NGN"
        loan.term_months = LOAN_TERM_MONTHS
        loan.status = loan_status
        loan.outstanding_balance = outstanding_balance
        loan.disbursed_at = disbursed_at

    for item in schedule:
        repayment_reference = (
            f"{REPAYMENT_PREFIX}{suffix}-{item['installment_number']:02d}"
        )

        repayment = db.scalar(
            select(Repayment).where(
                Repayment.repayment_reference == repayment_reference
            )
        )

        if repayment is not None and repayment.loan_id != loan.id:
            raise RuntimeError(
                f"Repayment {repayment_reference} belongs to another loan."
            )

        if repayment is None:
            repayment = Repayment(
                repayment_reference=repayment_reference,
                loan_id=loan.id,
                installment_number=item["installment_number"],
                principal_due=item["principal_due"],
                due_date=item["due_date"],
                status=item["status"],
                paid_at=item["paid_at"],
            )
            db.add(repayment)
        else:
            repayment.installment_number = item["installment_number"]
            repayment.principal_due = item["principal_due"]
            repayment.due_date = item["due_date"]
            repayment.status = item["status"]
            repayment.paid_at = item["paid_at"]

    db.flush()

    # Reconcile the persisted schedule against the loan balance.
    persisted_repayments = db.scalars(
        select(Repayment).where(
            Repayment.loan_id == loan.id
        )
    ).all()

    persisted_balance = sum(
        (
            repayment.principal_due
            for repayment in persisted_repayments
            if repayment.status != "PAID"
        ),
        Decimal("0.00"),
    )

    if persisted_balance != loan.outstanding_balance:
        raise RuntimeError(
            f"Loan balance reconciliation failed for {loan_reference}: "
            f"loan balance={loan.outstanding_balance}, "
            f"unpaid scheduled principal={persisted_balance}."
        )

    if len(persisted_repayments) != LOAN_TERM_MONTHS:
        raise RuntimeError(
            f"Expected {LOAN_TERM_MONTHS} repayments for {loan_reference}; "
            f"found {len(persisted_repayments)}."
        )

    return loan


def get_or_create_eligibility_profile(
    db,
    customer: Customer,
    customer_reference: str,
) -> LoanEligibilityProfile:
    """Create a synthetic, unverified eligibility fixture if it is missing."""
    fixture = ELIGIBILITY_PROFILE_FIXTURES.get(customer_reference)

    if fixture is None:
        raise RuntimeError(
            f"Missing eligibility fixture for {customer_reference}."
        )

    existing = db.scalar(
        select(LoanEligibilityProfile).where(
            LoanEligibilityProfile.customer_id == customer.id
        )
    )

    if existing is not None:
        # Preserve any existing customer profile, including its source,
        # financial values and verification state.
        return existing

    eligibility_profile = LoanEligibilityProfile(
        customer_id=customer.id,
        employment_type=fixture["employment_type"],
        monthly_income=fixture["monthly_income"],
        monthly_expenses=fixture["monthly_expenses"],
        existing_monthly_debt=fixture["existing_monthly_debt"],
        profile_source="DEMO_FIXTURE",
        verification_status="UNVERIFIED",
        verified_at=None,
    )

    db.add(eligibility_profile)
    db.flush()
    return eligibility_profile


def seed_demo_data(db) -> None:
    today_lagos = datetime.now(LAGOS).date()
    yesterday = today_lagos - timedelta(days=1)

    yesterday_morning = datetime.combine(
        yesterday,
        time(9, 15),
        tzinfo=LAGOS,
    ).astimezone(UTC)

    yesterday_later = datetime.combine(
        yesterday,
        time(9, 17),
        tzinfo=LAGOS,
    ).astimezone(UTC)

    today_morning = datetime.combine(
        today_lagos,
        time(10, 30),
        tzinfo=LAGOS,
    ).astimezone(UTC)

    for profile in PROFILES:
        customer = get_or_create_customer(db, profile)

        get_or_create_eligibility_profile(
            db=db,
            customer=customer,
            customer_reference=profile["reference"],
        )

        account = get_or_create_account(db, customer, profile)

        # Use reserved, deterministic references so rerunning the seed
        # updates these rows instead of duplicating them.
        suffix = profile["reference"][-3:]

        get_or_create_transaction(
            db=db,
            account=account,
            reference=f"DEMO-DEP-{suffix}",
            transaction_type="DEPOSIT",
            amount=Decimal("600000.00"),
            status="SUCCESSFUL",
            description="Demo salary deposit",
            created_at=yesterday_morning - timedelta(days=10),
        )

        get_or_create_transaction(
            db=db,
            account=account,
            reference=f"DEMO-DUP-A-{suffix}",
            transaction_type="WITHDRAWAL",
            amount=Decimal("25000.00"),
            status="SUCCESSFUL",
            description="Demo POS purchase",
            created_at=yesterday_morning,
        )

        get_or_create_transaction(
            db=db,
            account=account,
            reference=f"DEMO-DUP-B-{suffix}",
            transaction_type="WITHDRAWAL",
            amount=Decimal("25000.00"),
            status="SUCCESSFUL",
            description="Demo POS purchase duplicate",
            created_at=yesterday_later,
        )

        get_or_create_transaction(
            db=db,
            account=account,
            reference=f"DEMO-TRANSFER-{suffix}",
            transaction_type="TRANSFER",
            amount=Decimal("15000.00"),
            status="PENDING",
            description="Demo transfer awaiting beneficiary credit",
            created_at=today_morning,
        )

        get_or_create_card(db, customer, profile)

        application = get_or_create_loan_application(
            db=db,
            customer=customer,
            profile=profile,
            applied_at=today_morning,
        )

        loan = get_or_create_loan(
            db=db,
            customer=customer,
            application=application,
            profile=profile,
            today=today_lagos,
        )

        loan_summary = (
            f"{loan.loan_reference} ({loan.status})"
            if loan is not None
            else "No disbursed loan"
        )

        print(
            f"Prepared {profile['reference']}: "
            f"{profile['name']} | "
            f"phone={customer.phone_number} | "
            f"account={account.account_number} | "
            f"application={application.status} | "
            f"loan={loan_summary}"
        )

    db.flush()

    # Verify the essential demo records before committing.
    for profile in PROFILES:
        customer = db.scalar(
            select(Customer).where(
                Customer.customer_reference == profile["reference"]
            )
        )

        if customer is None:
            raise RuntimeError(
                f"Verification failed for {profile['reference']}."
            )

        eligibility_profile = db.scalar(
            select(LoanEligibilityProfile).where(
                LoanEligibilityProfile.customer_id == customer.id
            )
        )

        if eligibility_profile is None:
            raise RuntimeError(
                f"Eligibility profile verification failed for "
                f"{profile['reference']}."
            )

        account = db.scalar(
            select(Account).where(
                Account.account_number == profile["account"]
            )
        )

        if account is None or account.customer_id != customer.id:
            raise RuntimeError(
                f"Account ownership verification failed for "
                f"{profile['reference']}."
            )

        transactions = db.scalars(
            select(Transaction).where(
                Transaction.account_id == account.id,
                Transaction.reference.like("DEMO-%"),
            )
        ).all()

        if len(transactions) != 4:
            raise RuntimeError(
                f"Expected four demo transactions for "
                f"{profile['reference']}; found {len(transactions)}."
            )

        card = db.scalar(
            select(Card).where(
                Card.card_reference == profile["card"],
                Card.customer_id == customer.id,
            )
        )

        if card is None:
            raise RuntimeError(
                f"Card verification failed for {profile['reference']}."
            )

        application = db.scalar(
            select(LoanApplication).where(
                LoanApplication.application_reference
                == profile["application"],
                LoanApplication.customer_id == customer.id,
            )
        )

        if application is None:
            raise RuntimeError(
                f"Loan application verification failed for "
                f"{profile['reference']}."
            )

        loan = db.scalar(
            select(Loan).where(
                Loan.application_id == application.id
            )
        )

        if profile["loan_scenario"] is None:
            if loan is not None:
                raise RuntimeError(
                    f"Unexpected disbursed loan for "
                    f"{profile['reference']}."
                )
        else:
            if loan is None:
                raise RuntimeError(
                    f"Loan verification failed for {profile['reference']}."
                )

            if loan.customer_id != customer.id:
                raise RuntimeError(
                    f"Loan ownership verification failed for "
                    f"{profile['reference']}."
                )

            expected_status = profile["loan_scenario"]

            if loan.status != expected_status:
                raise RuntimeError(
                    f"Expected loan status {expected_status} for "
                    f"{profile['reference']}; found {loan.status}."
                )

            repayments = db.scalars(
                select(Repayment).where(
                    Repayment.loan_id == loan.id
                )
            ).all()

            if len(repayments) != LOAN_TERM_MONTHS:
                raise RuntimeError(
                    f"Repayment verification failed for "
                    f"{profile['reference']}."
                )

            unpaid_principal = sum(
                (
                    repayment.principal_due
                    for repayment in repayments
                    if repayment.status != "PAID"
                ),
                Decimal("0.00"),
            )

            if unpaid_principal != loan.outstanding_balance:
                raise RuntimeError(
                    f"Outstanding balance does not reconcile for "
                    f"{profile['reference']}."
                )

    print("\nVerification passed:")
    print("- 5 demo customers")
    print("- 5 independently owned accounts")
    print("- 5 loan eligibility profiles present")
    print("- Newly created synthetic profiles remain UNVERIFIED")
    print("- 20 demo transactions")
    print("- 5 active demo debit cards")
    print("- 3 disbursed demo loans")
    print("- 1 active loan")
    print("- 1 overdue loan")
    print("- 1 fully repaid loan")
    print("- 18 repayment schedule entries")
    print("- 1 approved application awaiting disbursement")
    print("- 1 pending loan application")
    print("- Loan balances reconcile with unpaid principal.")
    print("- Existing unrelated records are not deleted.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed five isolated Rubies MFB demo customers."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Commit changes. Without this flag, changes are rolled back.",
    )
    args = parser.parse_args()

    assert_safe_database()

    with SessionLocal() as db:
        try:
            seed_demo_data(db)

            if args.apply:
                db.commit()
                print("\nDemo data committed successfully.")
            else:
                db.rollback()
                print(
                    "\nDRY RUN ONLY: no changes were committed. "
                    "Use --apply to persist the demo data."
                )
        except Exception:
            db.rollback()
            raise


if __name__ == "__main__":
    main()
