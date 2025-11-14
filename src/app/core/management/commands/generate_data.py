import json
import random
import uuid
from datetime import datetime, timedelta

from django.core.management import BaseCommand, call_command


class Command(BaseCommand):
    """
    Generate transaction data and seed categories.

    Usage:
        python manage.py generate_data
    """

    help = 'Generate data for transactions and seed categories'


    def handle(self, *args, **options):
        call_command('seed_categories')
        generate_transaction_data()




def generate_transaction_data():

    NUM_ACCOUNTS = 50
    NUM_TRANSACTIONS = 10000

    FIRST_NAMES = ["Sipho", "Thabo", "Lethabo", "Jabulani", "Lerato", "Naledi", "Jaco", "Pieter", "Anika", "David"]

    ACCOUNT_TYPES = [
        ("depository", "cheque"),
        ("depository", "savings"),
        ("credit", "credit card"),
        ("investment", "unit trust")
    ]
    MERCHANTS = [
        "Shoprite", "Checkers", "Pick n Pay", "Woolworths", "Engen", "Shell", "MTN", "Vodacom", "Nando's",
        "KFC", "Steers", "Takealot", "Eskom", "DStv"
    ]

    accounts = []
    for i in range(NUM_ACCOUNTS):
        account_type, subtype = random.choice(ACCOUNT_TYPES)
        accounts.append({
            "account_id": f"acc_{1001 + i}",
            "name": f"{random.choice(FIRST_NAMES)}",
            "type": account_type,
            "subtype": subtype,
            "mask": str(random.randint(1000, 9999))
        })

    all_transactions = []
    start_date = datetime(2025, 9, 1)
    end_date = datetime(2025, 10, 31)

    for _ in range(NUM_TRANSACTIONS):
        account = random.choice(accounts)
        total_days = (end_date - start_date).days
        random_days = random.randrange(total_days)
        transaction_date = start_date + timedelta(days=random_days,
                                                  hours=random.randint(0, 23),
                                                  minutes=random.randint(0, 59))

        all_transactions.append({
            "transaction_id": f"tx_{uuid.uuid4().hex[:10]}",
            "account_id": account["account_id"],
            "amount": round(random.uniform(-5000, 5000), 2),
            "iso_currency_code": "ZAR",
            "date": transaction_date.isoformat() + "Z",
            "authorized_date": transaction_date.strftime("%Y-%m-%d"),
            "name": random.choice(MERCHANTS),
            "merchant_name": random.choice(MERCHANTS),
            "payment_channel": random.choice(["online", "in store"]),
            "pending": False
        })

    final_json_output = []
    transaction_index = 0
    while transaction_index < len(all_transactions):
        num_in_request = random.randint(10, 20)

        request_transactions = all_transactions[transaction_index: transaction_index + num_in_request]

        account_ids_in_request = {t['account_id'] for t in request_transactions}
        accounts_in_request = [acc for acc in accounts if acc['account_id'] in account_ids_in_request]

        final_json_output.append({
            "accounts": accounts_in_request,
            "transactions": request_transactions,
            "total_transactions": len(request_transactions),
            "request_id": f"req_{uuid.uuid4().hex[:12]}"
        })

        transaction_index += num_in_request

    with open("generated_transactions.json", "w") as json_file:
        json.dump(final_json_output, json_file, indent=4)
