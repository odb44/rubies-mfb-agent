from __future__ import annotations

import argparse
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.engine import make_url

from rubies_banking_api.config import get_settings
from rubies_banking_api.db.database import SessionLocal
from rubies_banking_api.models.customer import Customer
from rubies_banking_api.models.account import Account
from rubies_banking_api.models.transaction import Transaction
from rubies_banking_api.models.card import Card
from rubies_banking_api.models.loan_application import LoanApplication


# Reserved exclusively for this local demonstration.
DEMO_PREFIX = "CUST-DEMO-"
ACCOUNT_PREFIX = "90000000"
LAGOS = ZoneInfo("Africa/Lagos")

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
    },
]


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
            requested_amount=Decimal("200000.00"),
            currency="NGN",
            purpose="Personal expenses",
            status="PENDING",
            applied_at=applied_at,
        )
        db.add(application)
    else:
        application.requested_amount = Decimal("200000.00")
        application.currency = "NGN"
        application.purpose = "Personal expenses"
        application.status = "PENDING"
        application.applied_at = applied_at

    return application


def seed_demo_data(db) -> None:
    today_lagos = datetime.now(LAGOS).date()
    yesterday = today_lagos - timedelta(days=1)

    yesterday_morning = datetime.combine(
        yesterday, time(9, 15), tzinfo=LAGOS
    ).astimezone(UTC)

    yesterday_later = datetime.combine(
        yesterday, time(9, 17), tzinfo=LAGOS
    ).astimezone(UTC)

    today_morning = datetime.combine(
        today_lagos, time(10, 30), tzinfo=LAGOS
    ).astimezone(UTC)

    for profile in PROFILES:
        customer = get_or_create_customer(db, profile)
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

        get_or_create_loan_application(
            db=db,
            customer=customer,
            profile=profile,
            applied_at=today_morning,
        )

        print(
            f"Prepared {profile['reference']}: "
            f"{profile['name']} | "
            f"phone={customer.phone_number} | "
            f"account={account.account_number}"
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

    print("\nVerification passed:")
    print("- 5 demo customers")
    print("- 5 independently owned accounts")
    print("- 20 demo transactions")
    print("- 5 active demo debit cards")
    print("- 5 pending loan applications")
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
    