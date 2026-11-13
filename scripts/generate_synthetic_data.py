"""Generate reproducible synthetic data for the Rubies MFB demo."""

import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

SEED = 20261027
OUTPUT = Path("data/synthetic/demo_dataset.json")
RNG = random.Random(SEED)

# Fixed reference date: repeatable output across runs and machines.
NOW = datetime(2026, 10, 27, 0, 0, tzinfo=UTC)
TODAY = NOW.date()

NAMES = [
    "Ada Okafor",
    "Tunde Adebayo",
    "Chioma Eze",
    "Ibrahim Musa",
    "Ngozi Obi",
    "Chinedu Okoro",
    "Amina Bello",
    "Emeka Nwosu",
    "Fatima Yusuf",
    "Bola Adeyemi",
    "Kelechi Umeh",
    "Sadiq Abdullahi",
    "Funmi Bakare",
    "David Ojo",
    "Amaka Ibe",
    "Yusuf Garba",
    "Tosin Lawal",
    "Blessing James",
    "Samuel Danjuma",
    "Zainab Sule",
]

SCENARIOS = [
    "failed_debit",
    "pending_transfer",
    "duplicate_debit",
    "beneficiary_not_credited",
    "lost_card",
    "active_loan",
    "insufficient_history",
]


def stable_id(value: str) -> str:
    """Generate a repeatable UUID from a unique dataset identifier."""
    return str(uuid5(NAMESPACE_URL, f"rubies-mfb-demo:{value}"))


def generate_dataset() -> dict[str, object]:
    """Generate customers, banking records, loan applications and repayments."""
    customers = []
    accounts = []
    cards = []
    transactions = []
    loan_applications = []
    loans = []
    repayments = []

    for index, name in enumerate(NAMES, start=1):
        customer_id = f"CUST-{index:04d}"
        account_id = f"ACC-{index:04d}"
        scenario = SCENARIOS[index - 1] if index <= len(SCENARIOS) else "standard"

        customers.append(
            {
                "customer_id": customer_id,
                "full_name": name,
                "email": f"customer{index:02d}@example.test",
                "phone": f"+234800000{index:04d}",
                "kyc_status": "VERIFIED",
                "status": "ACTIVE",
                "scenario": scenario,
                "synthetic": True,
            }
        )

        opening_balance = RNG.randint(20_000, 500_000)

        accounts.append(
            {
                "account_id": account_id,
                "customer_id": customer_id,
                "account_number": f"900000{index:04d}",
                "currency": "NGN",
                "opening_balance": opening_balance,
                "balance": opening_balance,
                "status": "ACTIVE",
                "synthetic": True,
            }
        )

        cards.append(
            {
                "card_id": f"CARD-{index:04d}",
                "customer_id": customer_id,
                "account_id": account_id,
                "masked_pan": f"5399********{index:04d}",
                "card_type": "DEBIT",
                "status": "BLOCKED" if scenario == "lost_card" else "ACTIVE",
                "synthetic": True,
            }
        )

        transaction_count = 2 if scenario == "insufficient_history" else 30
        balance = opening_balance

        for tx_index in range(1, transaction_count + 1):
            transaction_type = RNG.choice(["CREDIT", "DEBIT", "TRANSFER"])
            amount = RNG.randint(1_000, 50_000)
            status = "SUCCESS"
            scenario_id = None

            description = {
                "CREDIT": "Synthetic deposit",
                "DEBIT": "Synthetic purchase",
                "TRANSFER": "Synthetic transfer",
            }[transaction_type]

            if scenario == "failed_debit" and tx_index == 1:
                transaction_type = "DEBIT"
                status = "FAILED"
                description = "Failed debit reported by customer"

            elif scenario == "pending_transfer" and tx_index == 1:
                transaction_type = "TRANSFER"
                status = "PENDING"
                description = "Pending transfer; outcome unconfirmed"

            elif scenario == "duplicate_debit" and tx_index in (1, 2):
                transaction_type = "DEBIT"
                amount = 25_000
                description = "Potential duplicate-debit test transaction"
                scenario_id = "DUPLICATE-DEBIT-CUST-0003"

            elif scenario == "beneficiary_not_credited" and tx_index == 1:
                transaction_type = "TRANSFER"
                description = "Transfer reported as not received"

            if status == "SUCCESS":
                if transaction_type == "CREDIT":
                    balance += amount
                else:
                    balance = max(0, balance - amount)

            created_at = NOW - timedelta(
                days=RNG.randint(0, 89),
                hours=RNG.randint(0, 23),
                minutes=RNG.randint(0, 59),
            )

            transactions.append(
                {
                    "transaction_id": stable_id(f"transaction:{index}:{tx_index}"),
                    "reference": f"TXN-{index:04d}-{tx_index:04d}",
                    "customer_id": customer_id,
                    "account_id": account_id,
                    "transaction_type": transaction_type,
                    "amount": amount,
                    "currency": "NGN",
                    "status": status,
                    "description": description,
                    "created_at": created_at.isoformat(),
                    "scenario_id": scenario_id,
                    "synthetic": True,
                }
            )

        accounts[-1]["balance"] = balance

    # Preserve the intended distribution of application outcomes.
    application_statuses = ["PENDING"] * 5 + ["REJECTED"] * 4 + ["APPROVED"] * 21
    RNG.shuffle(application_statuses)

    approved_loan_number = 0

    for application_index in range(1, 31):
        customer_index = ((application_index - 1) % len(NAMES)) + 1
        customer_id = f"CUST-{customer_index:04d}"
        application_id = f"LOAN-APP-{application_index:04d}"
        application_status = application_statuses[application_index - 1]

        requested_amount = RNG.choice([50_000, 100_000, 150_000, 250_000, 300_000, 500_000])

        applied_date = TODAY - timedelta(days=RNG.randint(1, 120))

        loan_applications.append(
            {
                "application_id": application_id,
                "customer_id": customer_id,
                "requested_amount": requested_amount,
                "currency": "NGN",
                "purpose": RNG.choice(
                    [
                        "Working capital",
                        "School fees",
                        "Medical expenses",
                        "Equipment purchase",
                        "Personal needs",
                    ]
                ),
                "status": application_status,
                "applied_at": applied_date.isoformat(),
                "synthetic": True,
            }
        )

        if application_status != "APPROVED":
            continue

        approved_loan_number += 1
        loan_id = f"LOAN-{application_index:04d}"
        principal = requested_amount

        # Assign outcomes by approved-loan sequence, not application ID.
        # This guarantees exactly 3 repaid loans and at least 1 overdue loan.
        if approved_loan_number <= 3:
            loan_status = "REPAID"
            term_months = 3
            applied_date = TODAY - timedelta(days=180)

        elif approved_loan_number == 4:
            loan_status = "OVERDUE"
            term_months = 6
            applied_date = TODAY - timedelta(days=150)

        else:
            loan_status = "ACTIVE"
            term_months = 12
            applied_date = TODAY - timedelta(days=90)

        # Divide the full principal without losing any remainder.
        base_principal, remainder = divmod(principal, term_months)
        installment_amounts = [
            base_principal + (1 if installment <= remainder else 0)
            for installment in range(1, term_months + 1)
        ]

        loan_repayments = []

        for installment, principal_due in enumerate(installment_amounts, start=1):
            due_date = applied_date + timedelta(days=30 * installment)

            if loan_status == "REPAID":
                repayment_status = "PAID"

            elif loan_status == "OVERDUE":
                repayment_status = "OVERDUE" if due_date < TODAY else "PENDING"

            else:
                # The active loan has a 12-month term and a 90-day history.
                # Past instalments have been paid; future ones remain pending.
                repayment_status = "PAID" if due_date < TODAY else "PENDING"

            repayment = {
                "repayment_id": stable_id(f"repayment:{loan_id}:{installment}"),
                "loan_id": loan_id,
                "customer_id": customer_id,
                "installment_number": installment,
                "principal_due": principal_due,
                "due_date": due_date.isoformat(),
                "status": repayment_status,
                "paid_at": (
                    (due_date - timedelta(days=1)).isoformat()
                    if repayment_status == "PAID"
                    else None
                ),
                "synthetic": True,
            }

            repayments.append(repayment)
            loan_repayments.append(repayment)

        # Outstanding principal is derived from unpaid instalments.
        outstanding_balance = sum(
            repayment["principal_due"]
            for repayment in loan_repayments
            if repayment["status"] != "PAID"
        )

        loans.append(
            {
                "loan_id": loan_id,
                "application_id": application_id,
                "customer_id": customer_id,
                "principal": principal,
                "currency": "NGN",
                "term_months": term_months,
                "status": loan_status,
                "outstanding_balance": outstanding_balance,
                "disbursed_at": applied_date.isoformat(),
                "synthetic": True,
            }
        )

    return {
        "metadata": {
            "dataset_name": "rubies_mfb_synthetic_demo",
            "version": 3,
            "seed": SEED,
            "generated_at": NOW.isoformat(),
            "reference_date": TODAY.isoformat(),
            "synthetic_only": True,
            "currency": "NGN",
        },
        "customers": customers,
        "accounts": accounts,
        "cards": cards,
        "transactions": transactions,
        "loan_applications": loan_applications,
        "loans": loans,
        "repayments": repayments,
    }


def main() -> None:
    """Write the synthetic dataset to disk."""
    dataset = generate_dataset()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(dataset, indent=2),
        encoding="utf-8",
    )

    print(f"Dataset written to {OUTPUT}")
    for key in (
        "customers",
        "accounts",
        "cards",
        "transactions",
        "loan_applications",
        "loans",
        "repayments",
    ):
        print(f"{key.replace('_', ' ').title()}: {len(dataset[key])}")


if __name__ == "__main__":
    main()
