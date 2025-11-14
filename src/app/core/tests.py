import datetime
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.utils import timezone
from rest_framework import status as http_status
from rest_framework.test import APIClient

from .models import Transaction, Batch, Account, Category, CategoryPattern, Status
from .tasks import process_single_batch


class BatchIngestionAPITest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = '/api/integrations/transactions/'

        self.food_category = Category.objects.create(name='food')
        CategoryPattern.objects.create(category=self.food_category, pattern='restaurant')
        CategoryPattern.objects.create(category=self.food_category, pattern='starbucks')

        self.transport_category = Category.objects.create(name='transport')
        CategoryPattern.objects.create(category=self.transport_category, pattern='uber')
        CategoryPattern.objects.create(category=self.transport_category, pattern='lyft')

        self.valid_payload = {
            "accounts": [
                {
                    "account_id": "acc_123",
                    "name": "Chase Checking",
                    "type": "depository",
                    "subtype": "checking",
                    "mask": "1234"
                }
            ],
            "transactions": [
                {
                    "transaction_id": "txn_001",
                    "account_id": "acc_123",
                    "amount": -25.50,
                    "iso_currency_code": "USD",
                    "date": "2024-01-15T10:30:00Z",
                    "name": "Starbucks Coffee",
                    "merchant_name": "Starbucks",
                    "payment_channel": "in store",
                    "pending": False
                },
                {
                    "transaction_id": "txn_002",
                    "account_id": "acc_123",
                    "amount": -15.75,
                    "iso_currency_code": "USD",
                    "date": "2024-01-16T14:20:00Z",
                    "name": "Uber Trip",
                    "merchant_name": "Uber",
                    "payment_channel": "online",
                    "pending": False
                }
            ],
            "total_transactions": 2,
            "request_id": "req_test_001"
        }

    @patch('core.views.process_batch_async.delay')
    def test_successful_ingestion_returns_202_accepted(self, mock_celery_task):
        """Test that valid transaction data returns 202 ACCEPTED"""
        # Mock the celery task
        mock_celery_task.return_value = MagicMock()

        response = self.client.post(self.url, self.valid_payload, format='json')

        # Assert response status
        self.assertEqual(response.status_code, http_status.HTTP_202_ACCEPTED)

        # Assert response contains batch_id and total_transactions
        self.assertIn('batch_id', response.data)
        self.assertEqual(response.data['total_transactions'], 2)

        # Assert batch was created
        batch = Batch.objects.get(batch_id=response.data['batch_id'])
        self.assertEqual(batch.total_transactions, 2)
        self.assertEqual(batch.status, Status.PENDING)

        # Assert accounts were created
        account = Account.objects.get(account_id='acc_123')
        self.assertEqual(account.name, 'Chase Checking')

        # Assert transactions were created
        self.assertEqual(Transaction.objects.count(), 2)
        txn1 = Transaction.objects.get(transaction_id='txn_001')
        self.assertEqual(txn1.amount, Decimal('-25.50'))
        self.assertEqual(txn1.merchant_name, 'Starbucks')
        self.assertEqual(txn1.ingestion_status, Status.PENDING)

        # Assert celery task was called
        mock_celery_task.assert_called_once_with(batch.batch_id)

    def test_invalid_schema_missing_required_fields(self):
        """Test that missing required fields returns 400 BAD REQUEST"""
        invalid_payload = {
            "accounts": [
                {
                    "account_id": "acc_123",
                    "name": "Chase Checking"
                    # Missing 'type' field
                }
            ],
            "transactions": [
                {
                    "transaction_id": "txn_001",
                    "account_id": "acc_123"
                    # Missing required fields: amount, iso_currency_code, date, name
                }
            ],
            "total_transactions": 1
        }

        response = self.client.post(self.url, invalid_payload, format='json')

        # Assert response status
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

        # Assert no batch or transactions were created
        self.assertEqual(Batch.objects.count(), 0)
        self.assertEqual(Transaction.objects.count(), 0)


class AccountSummaryAPITest(TestCase):
    """Tests for the account summary API endpoint"""

    def setUp(self):
        """Set up test client and sample data"""
        self.client = APIClient()

        # Create test account
        self.account = Account.objects.create(
            account_id='acc_summary_test',
            name='Test Summary Account',
            type='depository',
            subtype='checking'
        )

        # Create test batch
        self.batch = Batch.objects.create(
            total_transactions=10,
            request_id='req_summary_test',
            status=Status.COMPLETED
        )

        self.food_category = Category.objects.create(name='food')
        self.transport_category = Category.objects.create(name='transport')
        self.shopping_category = Category.objects.create(name='shopping')


        self.transactions = [
            # Food transactions (3 transactions, total -60.00)
            Transaction.objects.create(
                transaction_id='txn_summary_001',
                account_id=self.account.account_id,
                batch=self.batch,
                amount=Decimal('-25.00'),
                currency='USD',
                date=timezone.datetime(2024, 1, 5, 10, 0, tzinfo=datetime.UTC),
                description='Restaurant meal',
                merchant_name='Restaurant A',
                category='food',
                ingestion_status=Status.COMPLETED
            ),
            Transaction.objects.create(
                transaction_id='txn_summary_002',
                account_id=self.account.account_id,
                batch=self.batch,
                amount=Decimal('-15.00'),
                currency='USD',
                date=timezone.datetime(2024, 1, 10, 12, 0, tzinfo=datetime.UTC),
                description='Coffee shop',
                merchant_name='Coffee Shop',
                category='food',
                ingestion_status=Status.COMPLETED
            ),
            Transaction.objects.create(
                transaction_id='txn_summary_003',
                account_id=self.account.account_id,
                batch=self.batch,
                amount=Decimal('-20.00'),
                currency='USD',
                date=timezone.datetime(2024, 1, 15, 14, 0, tzinfo=datetime.UTC),
                description='Fast food',
                merchant_name='Fast Food',
                category='food',
                ingestion_status=Status.COMPLETED
            ),
            # Transport transactions (2 transactions, total -45.00)
            Transaction.objects.create(
                transaction_id='txn_summary_004',
                account_id=self.account.account_id,
                batch=self.batch,
                amount=Decimal('-30.00'),
                currency='USD',
                date=timezone.datetime(2024, 1, 8, 9, 0, tzinfo=datetime.UTC),
                description='Uber ride',
                merchant_name='Uber',
                category='transport',
                ingestion_status=Status.COMPLETED
            ),
            Transaction.objects.create(
                transaction_id='txn_summary_005',
                account_id=self.account.account_id,
                batch=self.batch,
                amount=Decimal('-15.00'),
                currency='USD',
                date=timezone.datetime(2024, 1, 20, 18, 0, tzinfo=datetime.UTC),
                description='Lyft ride',
                merchant_name='Lyft',
                category='transport',
                ingestion_status=Status.COMPLETED
            ),
            # Shopping transaction (1 transaction, total -100.00)
            Transaction.objects.create(
                transaction_id='txn_summary_006',
                account_id=self.account.account_id,
                batch=self.batch,
                amount=Decimal('-100.00'),
                currency='USD',
                date=timezone.datetime(2024, 1, 12, 16, 0, tzinfo=datetime.UTC),
                description='Online purchase',
                merchant_name='Amazon',
                category='shopping',
                ingestion_status=Status.COMPLETED
            ),
            # Income transaction (positive amount)
            Transaction.objects.create(
                transaction_id='txn_summary_007',
                account_id=self.account.account_id,
                batch=self.batch,
                amount=Decimal('2500.00'),
                currency='USD',
                date=timezone.datetime(2024, 1, 1, 8, 0, tzinfo=datetime.UTC),
                description='Salary deposit',
                merchant_name='Employer Inc',
                category='income',
                ingestion_status=Status.COMPLETED
            ),
            # Pending transaction
            Transaction.objects.create(
                transaction_id='txn_summary_008',
                account_id=self.account.account_id,
                batch=self.batch,
                amount=Decimal('-50.00'),
                currency='USD',
                date=timezone.datetime(2024, 1, 25, 11, 0, tzinfo=datetime.UTC),
                description='Pending purchase',
                merchant_name='Store',
                category='shopping',
                ingestion_status=Status.PENDING
            ),
            # Failed transaction
            Transaction.objects.create(
                transaction_id='txn_summary_009',
                account_id=self.account.account_id,
                batch=self.batch,
                amount=Decimal('-25.00'),
                currency='USD',
                date=timezone.datetime(2024, 1, 28, 15, 0, tzinfo=datetime.UTC),
                description='Failed transaction',
                merchant_name='Store',
                category='other',
                ingestion_status=Status.FAILED
            ),
            # Transaction outside date range (February)
            Transaction.objects.create(
                transaction_id='txn_summary_010',
                account_id=self.account.account_id,
                batch=self.batch,
                amount=Decimal('-999.99'),
                currency='USD',
                date=timezone.datetime(2024, 2, 15, 10, 0, tzinfo=datetime.UTC),
                description='February transaction',
                merchant_name='Store',
                category='other',
                ingestion_status=Status.COMPLETED
            ),
        ]

        self.base_url = f'/api/reports/account/{self.account.account_id}/summary/'

    def test_successful_summary_with_valid_date_range(self):
        """Test successful summary retrieval with valid parameters"""
        response = self.client.get(
            self.base_url,
            {'start_date': '2024-01-01', 'end_date': '2024-01-31'}
        )

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

        # Assert date range
        self.assertEqual(response.data['date_range']['start'], '2024-01-01')
        self.assertEqual(response.data['date_range']['end'], '2024-01-31')

        # Assert metrics (9 transactions in January, excluding Feb transaction)
        metrics = response.data['metrics']
        self.assertEqual(metrics['total_transactions'], 9)
        self.assertEqual(float(metrics['total_income']), 2500.00)
        # Total spend: 25 + 15 + 20 + 30 + 15 + 100 + 50 + 25 = 280.00
        self.assertEqual(float(metrics['total_spend']), 280.00)
        # Net: 2500 - 280 = 2220.00
        self.assertEqual(float(metrics['net']), 2220.00)

    def test_top_categories_ordered_by_spend(self):
        """Test that top categories are ordered correctly by spending"""
        response = self.client.get(
            self.base_url,
            {'start_date': '2024-01-01', 'end_date': '2024-01-31'}
        )

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

        top_categories = response.data['top_categories']

        # Should have 3 top categories max
        self.assertLessEqual(len(top_categories), 3)

        # Top 3 should be: shopping (150), food (60), transport (45)
        self.assertEqual(len(top_categories), 3)

        # Shopping is #1 (100 + 50 pending = 150)
        self.assertEqual(top_categories[0]['category'], 'shopping')
        self.assertEqual(float(top_categories[0]['total_spend']), 150.00)

        # Food is #2 (25 + 15 + 20 = 60)
        self.assertEqual(top_categories[1]['category'], 'food')
        self.assertEqual(float(top_categories[1]['total_spend']), 60.00)

        # Transport is #3 (30 + 15 = 45)
        self.assertEqual(top_categories[2]['category'], 'transport')
        self.assertEqual(float(top_categories[2]['total_spend']), 45.00)


    def test_missing_start_date_parameter(self):
        """Test that missing start_date returns 400 BAD REQUEST"""
        response = self.client.get(
            self.base_url,
            {'end_date': '2024-01-31'}
        )

        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)


        """Test that missing end_date returns 400 BAD REQUEST"""
        response = self.client.get(
            self.base_url,
            {'start_date': '2024-01-01'}
        )

        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)


        """Test that invalid date format returns 400 BAD REQUEST"""
        response = self.client.get(
            self.base_url,
            {'start_date': '01-01-2024', 'end_date': '2024-01-31'}  # Wrong format
        )

        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)


        """Test that end_date before start_date returns 400 BAD REQUEST"""
        response = self.client.get(
            self.base_url,
            {'start_date': '2024-01-31', 'end_date': '2024-01-01'}
        )

        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)


        """Test that date range exceeding 365 days returns 400 BAD REQUEST"""
        response = self.client.get(
            self.base_url,
            {'start_date': '2023-01-01', 'end_date': '2024-12-31'}  # > 365 days
        )

        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)


        """Test that non-existent account"""
        non_existent_url = '/api/reports/account/non_existent_account_id/summary/'

        response = self.client.get(
            non_existent_url,
            {'start_date': '2024-01-01', 'end_date': '2024-01-31'}
        )

        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

