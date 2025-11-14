"""
Usage:
    python manage.py simulate_integration
    python manage.py simulate_integration --all
"""

import json
import os
import random

import requests
from django.core.management import BaseCommand


class Command(BaseCommand):
    """
    Simulate integration command that loads transaction batches from JSON and posts to API.
    By default, posts a single randomly chosen transaction.
    Use --all flag to post all transactions.
    """

    help = 'Load transaction to simulate integration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Process all transactions instead of just one random transaction'
        )

    def handle(self, *args, **options):
        api_url = 'http://localhost:8000/api/integrations/transactions/'
        timeout = 300
        process_all = options.get('all', False)

        # Load transactions from transactions.json file
        try:
            simulation_file = 'transactions.json'
            batches = self.load_batches_from_json(simulation_file)

            if process_all:
                print(f'Processing all {len(batches)} transactions...')
                for idx, batch_data in enumerate(batches, 1):
                    print(f'Processing transaction {idx}/{len(batches)}')
                    self.post_batch_with_tracking(batch_data, api_url, timeout)
            else:
                batch_data = random.choice(batches)
                print('Processing one random transaction...')
                self.post_batch_with_tracking(batch_data, api_url, timeout)

        except FileNotFoundError:
            print("Make sure to run 'python manage.py generate_data' first")
            return

    def load_batches_from_json(self, json_file_path):
        if not os.path.isabs(json_file_path):
            base_dir = os.path.dirname(os.path.abspath(__file__))
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(base_dir)))
            json_file_path = os.path.join(base_dir, json_file_path)

        if not os.path.exists(json_file_path):
            raise FileNotFoundError(f"JSON file not found: {json_file_path}")

        with open(json_file_path, 'r') as f:
            batches = json.load(f)

        return batches


    def post_batch_with_tracking(self, batch_data, api_url, timeout):
        try:
            response = requests.post(api_url, json=batch_data, timeout=timeout)
            if response.status_code == 202:
                response_data = response.json()
                batch_id = response_data.get('batch_id')
                total_transactions = response_data.get('total_transactions')
                print(f'Batch ID: {batch_id} accepted, total transactions: {total_transactions}')
            else:
                print(f"Failed with status {response.status_code}. {response.text}")

        except Exception as e:
           print(f"Error: {str(e)}")