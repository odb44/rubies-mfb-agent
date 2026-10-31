import traceback
from rubies_banking_api.db.database import SessionLocal
from rubies_banking_api.repositories.transaction_repository import TransactionRepository
from rubies_banking_api.api.transactions import (
    TransactionResponse,
    MiniStatementResponse,
)

db = SessionLocal()

try:
    repository = TransactionRepository(db)
    account = repository.get_account_by_number("9000000001")

    if account is None:
        print("FAIL: Account not found")
    else:
        transactions = repository.list_by_account(
            account.id,
            limit=10,
            offset=0,
        )

        print("Building transaction response objects...")

        items = [
            TransactionResponse(
                reference=t.reference,
                transaction_type=t.transaction_type,
                amount=t.amount,
                status=t.status,
                description=t.description,
                created_at=t.created_at,
            )
            for t in transactions
        ]

        print("Transaction response objects:", len(items))

        response = MiniStatementResponse(
            account_reference=account.account_number,
            currency=account.currency,
            items=items,
            limit=10,
            offset=0,
        )

        print("\nSERIALIZED RESPONSE:")
        print(response.model_dump_json(indent=2))
        print("\nPASS: Response construction and serialization succeeded.")

except Exception:
    print("\nFAIL: Response construction or serialization failed.")
    traceback.print_exc()

finally:
    db.close()
