"""Validate structure and financial consistency of synthetic demo data."""

import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

DATASET_PATH = Path("data/synthetic/demo_dataset.json")


def validate_dataset() -> None:
    """Check identifiers, relationships, scenarios and loan reconciliation."""
    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found: {DATASET_PATH}. Run the generator first."
        )

    data = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    errors: list[str] = []

    customers = data["customers"]
    accounts = data["accounts"]
    cards = data["cards"]
    transactions = data["transactions"]
    applications = data["loan_applications"]
    loans = data["loans"]
    repayments = data["repayments"]

    customer_ids = {record["customer_id"] for record in customers}
    account_ids = {record["account_id"] for record in accounts}
    loan_ids = {record["loan_id"] for record in loans}
    application_by_id = {
        application["application_id"]: application
        for application in applications
    }
    account_by_id = {
        account["account_id"]: account for account in accounts
    }
    loan_by_id = {loan["loan_id"]: loan for loan in loans}

    reference_date = date.fromisoformat(data["metadata"]["reference_date"])

    def check_unique(records: list[dict], field: str) -> None:
        values = [record[field] for record in records]
        duplicates = [
            value
            for value, count in Counter(values).items()
            if count > 1
        ]
        if duplicates:
            errors.append(
                f"{field}: duplicate values found: {duplicates[:5]}"
            )

    for records, field in [
        (customers, "customer_id"),
        (accounts, "account_id"),
        (accounts, "account_number"),
        (cards, "card_id"),
        (transactions, "transaction_id"),
        (transactions, "reference"),
        (applications, "application_id"),
        (loans, "loan_id"),
        (repayments, "repayment_id"),
    ]:
        check_unique(records, field)

    if len(customers) != 20:
        errors.append(f"Expected 20 customers; found {len(customers)}.")

    if len(accounts) != len(customers):
        errors.append("Expected one account per customer.")

    if len(cards) != len(customers):
        errors.append("Expected one card per customer.")

    for account in accounts:
        if account["customer_id"] not in customer_ids:
            errors.append(
                f"Account {account['account_id']} references an unknown customer."
            )

        if account["balance"] < 0:
            errors.append(
                f"Account {account['account_id']} has a negative balance."
            )

        if account["currency"] != "NGN":
            errors.append(
                f"Account {account['account_id']} has unexpected currency."
            )

    for card in cards:
        if card["customer_id"] not in customer_ids:
            errors.append(
                f"Card {card['card_id']} references an unknown customer."
            )

        if card["account_id"] not in account_ids:
            errors.append(
                f"Card {card['card_id']} references an unknown account."
            )

        account = account_by_id.get(card["account_id"])
        if account and account["customer_id"] != card["customer_id"]:
            errors.append(
                f"Card {card['card_id']} and its account have different owners."
            )

    transactions_by_scenario: dict[str, list[dict]] = defaultdict(list)

    for transaction in transactions:
        if transaction["customer_id"] not in customer_ids:
            errors.append(
                f"Transaction {transaction['reference']} has an unknown customer."
            )

        if transaction["account_id"] not in account_ids:
            errors.append(
                f"Transaction {transaction['reference']} has an unknown account."
            )

        account = account_by_id.get(transaction["account_id"])
        if account and account["customer_id"] != transaction["customer_id"]:
            errors.append(
                f"Transaction {transaction['reference']} and account have "
                "different owners."
            )

        if transaction["amount"] <= 0:
            errors.append(
                f"Transaction {transaction['reference']} has an invalid amount."
            )

        if transaction["status"] not in {"SUCCESS", "FAILED", "PENDING"}:
            errors.append(
                f"Transaction {transaction['reference']} has an unknown status."
            )

        scenario_id = transaction.get("scenario_id")
        if scenario_id:
            transactions_by_scenario[scenario_id].append(transaction)

    duplicate_pair = transactions_by_scenario.get(
        "DUPLICATE-DEBIT-CUST-0003", []
    )

    if len(duplicate_pair) != 2:
        errors.append(
            "Duplicate-debit scenario must contain exactly two linked transactions."
        )
    else:
        first, second = duplicate_pair

        for field in ("customer_id", "account_id", "amount", "transaction_type"):
            if first[field] != second[field]:
                errors.append(
                    f"Duplicate-debit transactions disagree on {field}."
                )

        if first["customer_id"] != "CUST-0003":
            errors.append(
                "Duplicate-debit transactions must belong to CUST-0003."
            )

        if any(tx["status"] != "SUCCESS" for tx in duplicate_pair):
            errors.append(
                "Both duplicate-debit test transactions must be successful."
            )

        if first["reference"] == second["reference"]:
            errors.append("Duplicate-debit transactions must have distinct references.")

    for application in applications:
        if application["customer_id"] not in customer_ids:
            errors.append(
                f"Application {application['application_id']} "
                "references an unknown customer."
            )

        if application["status"] not in {"PENDING", "REJECTED", "APPROVED"}:
            errors.append(
                f"Application {application['application_id']} "
                "has an invalid status."
            )

    loans_by_status = Counter(loan["status"] for loan in loans)

    if loans_by_status["REPAID"] != 3:
        errors.append(
            f"Expected exactly 3 repaid loans; found {loans_by_status['REPAID']}."
        )

    if loans_by_status["OVERDUE"] < 1:
        errors.append("Expected at least one overdue loan.")

    repayments_by_loan: dict[str, list[dict]] = defaultdict(list)

    for repayment in repayments:
        loan_id = repayment["loan_id"]

        if loan_id not in loan_ids:
            errors.append(
                f"Repayment {repayment['repayment_id']} references an unknown loan."
            )
            continue

        if repayment["customer_id"] not in customer_ids:
            errors.append(
                f"Repayment {repayment['repayment_id']} "
                "references an unknown customer."
            )

        loan = loan_by_id[loan_id]
        if repayment["customer_id"] != loan["customer_id"]:
            errors.append(
                f"Repayment {repayment['repayment_id']} and loan have different owners."
            )

        if repayment["principal_due"] <= 0:
            errors.append(
                f"Repayment {repayment['repayment_id']} has an invalid amount."
            )

        if repayment["status"] not in {"PAID", "PENDING", "OVERDUE"}:
            errors.append(
                f"Repayment {repayment['repayment_id']} has an invalid status."
            )

        due_date = date.fromisoformat(repayment["due_date"])

        if repayment["status"] == "PAID":
            if not repayment["paid_at"]:
                errors.append(
                    f"Paid repayment {repayment['repayment_id']} lacks paid_at."
                )
            elif date.fromisoformat(repayment["paid_at"]) > reference_date:
                errors.append(
                    f"Repayment {repayment['repayment_id']} is paid in the future."
                )

        elif repayment["paid_at"] is not None:
            errors.append(
                f"Unpaid repayment {repayment['repayment_id']} has paid_at set."
            )

        if repayment["status"] == "OVERDUE" and due_date >= reference_date:
            errors.append(
                f"Overdue repayment {repayment['repayment_id']} is not past due."
            )

        if repayment["status"] == "PENDING" and due_date < reference_date:
            errors.append(
                f"Pending repayment {repayment['repayment_id']} is already past due."
            )

        repayments_by_loan[loan_id].append(repayment)

    for loan in loans:
        loan_id = loan["loan_id"]
        application = application_by_id.get(loan["application_id"])

        if application is None:
            errors.append(
                f"Loan {loan_id} references an unknown application."
            )
            continue

        if application["status"] != "APPROVED":
            errors.append(
                f"Loan {loan_id} is linked to a "
                f"{application['status']} application."
            )

        if loan["customer_id"] != application["customer_id"]:
            errors.append(
                f"Loan {loan_id} and its application have different owners."
            )

        if loan["principal"] <= 0:
            errors.append(f"Loan {loan_id} has an invalid principal.")

        if loan["term_months"] <= 0:
            errors.append(f"Loan {loan_id} has an invalid term.")

        if not 0 <= loan["outstanding_balance"] <= loan["principal"]:
            errors.append(f"Loan {loan_id} has an invalid outstanding balance.")

        schedule = repayments_by_loan.get(loan_id, [])
        schedule.sort(key=lambda record: record["installment_number"])

        if len(schedule) != loan["term_months"]:
            errors.append(
                f"Loan {loan_id} should have {loan['term_months']} instalments; "
                f"found {len(schedule)}."
            )

        installment_numbers = [
            repayment["installment_number"] for repayment in schedule
        ]
        expected_numbers = list(range(1, loan["term_months"] + 1))

        if installment_numbers != expected_numbers:
            errors.append(
                f"Loan {loan_id} has missing, duplicate or unordered instalments."
            )

        scheduled_principal = sum(
            repayment["principal_due"] for repayment in schedule
        )

        if scheduled_principal != loan["principal"]:
            errors.append(
                f"Loan {loan_id} scheduled principal ({scheduled_principal}) "
                f"does not equal principal ({loan['principal']})."
            )

        calculated_outstanding = sum(
            repayment["principal_due"]
            for repayment in schedule
            if repayment["status"] != "PAID"
        )

        if calculated_outstanding != loan["outstanding_balance"]:
            errors.append(
                f"Loan {loan_id} outstanding balance "
                f"({loan['outstanding_balance']}) does not reconcile with "
                f"unpaid principal ({calculated_outstanding})."
            )

        statuses = {repayment["status"] for repayment in schedule}

        if loan["status"] == "REPAID":
            if loan["outstanding_balance"] != 0:
                errors.append(f"Repaid loan {loan_id} has an outstanding balance.")

            if schedule and any(
                repayment["status"] != "PAID" for repayment in schedule
            ):
                errors.append(f"Repaid loan {loan_id} has unpaid instalments.")

        elif loan["status"] == "OVERDUE":
            if loan["outstanding_balance"] <= 0:
                errors.append(f"Overdue loan {loan_id} has no outstanding principal.")

            if "OVERDUE" not in statuses:
                errors.append(f"Overdue loan {loan_id} has no overdue instalment.")

        elif loan["status"] == "ACTIVE":
            if loan["outstanding_balance"] <= 0:
                errors.append(f"Active loan {loan_id} has no outstanding principal.")

            if "OVERDUE" in statuses:
                errors.append(
                    f"Active loan {loan_id} has an overdue instalment."
                )

        else:
            errors.append(f"Loan {loan_id} has unknown status {loan['status']}.")

    scenarios = {customer["scenario"] for customer in customers}
    required_scenarios = {
        "failed_debit",
        "pending_transfer",
        "duplicate_debit",
        "beneficiary_not_credited",
        "lost_card",
        "active_loan",
        "insufficient_history",
}


    missing_scenarios = required_scenarios - scenarios
    if missing_scenarios:
        errors.append(f"Missing customer scenarios: {sorted(missing_scenarios)}")

    print("=== Synthetic Dataset Validation ===")
    print(f"Customers: {len(customers)}")
    print(f"Accounts: {len(accounts)}")
    print(f"Cards: {len(cards)}")
    print(f"Transactions: {len(transactions)}")
    print(f"Loan applications: {len(applications)}")
    print(f"Loans: {len(loans)}")
    print(f"Repayments: {len(repayments)}")
    print("Transaction statuses:", dict(Counter(tx["status"] for tx in transactions)))
    print("Loan application statuses:", dict(Counter(app["status"] for app in applications)))
    print("Loan statuses:", dict(loans_by_status))

    if errors:
        print(f"\nFAILED: {len(errors)} validation issue(s)")
        for error in errors:
            print(f"- {error}")
        raise SystemExit(1)

    print("\nSynthetic dataset validation passed.")


if __name__ == "__main__":
    validate_dataset()