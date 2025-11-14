from rest_framework import serializers
from .models import Account, Transaction, Batch
from django.db import transaction
from datetime import datetime


class FlexibleDateField(serializers.DateField):
    """
    DateField that accepts both date (YYYY-MM-DD) and datetime (ISO format) strings.
    Extracts just the date part if datetime is provided.
    """
    def to_internal_value(self, value):
        if value is None:
            return None

        if isinstance(value, str):
            # Try to parse as datetime first, then extract date
            try:
                dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                return dt.date()
            except (ValueError, AttributeError):
                pass

        # Fall back to default DateField behavior
        return super().to_internal_value(value)


class AccountSerializer(serializers.Serializer):
    """
    Serializer for account data in batch ingestion payload.
    """
    account_id = serializers.CharField(max_length=255)
    name = serializers.CharField(max_length=255)
    type = serializers.CharField(max_length=100)
    subtype = serializers.CharField(max_length=100, required=False, allow_null=True, allow_blank=True)
    mask = serializers.CharField(max_length=10, required=False, allow_null=True, allow_blank=True)


class TransactionSerializer(serializers.Serializer):
    """
    Serializer for transaction data in batch ingestion payload.
    """
    transaction_id = serializers.CharField(max_length=255)
    account_id = serializers.CharField(max_length=255)
    amount = serializers.DecimalField(max_digits=19, decimal_places=2)
    iso_currency_code = serializers.CharField(max_length=3)
    date = serializers.DateTimeField()
    authorized_date = FlexibleDateField(required=False, allow_null=True)
    name = serializers.CharField(max_length=255)
    merchant_name = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)
    payment_channel = serializers.CharField(max_length=50, required=False, allow_null=True, allow_blank=True)
    pending = serializers.BooleanField(default=False)


class BatchIngestionRequestSerializer(serializers.Serializer):
    """
    Serializer for the batch ingestion request payload.
    """
    accounts = AccountSerializer(many=True)
    transactions = TransactionSerializer(many=True)
    total_transactions = serializers.IntegerField()
    request_id = serializers.CharField(max_length=255, required=False, allow_null=True, allow_blank=True)

    def validate(self, data):
        """
        Validation rules can be added here on incoming data
        """

        return data

    @transaction.atomic
    def create(self, validated_data):
        """
        Create or update accounts, create batch, and create transactions.
        """
        accounts_data = validated_data.pop('accounts')
        transactions_data = validated_data.pop('transactions')
        total_transactions = validated_data.pop('total_transactions')
        request_id = validated_data.pop('request_id', None)

        # Bulk upsert accounts for better performance
        account_objects = []
        for account_data in accounts_data:
            account_objects.append(Account(
                account_id=account_data['account_id'],
                name=account_data['name'],
                type=account_data['type'],
                subtype=account_data.get('subtype'),
                mask=account_data.get('mask'),
            ))

        # Use bulk_create with update_conflicts for upsert behavior
        Account.objects.bulk_create(
            account_objects,
            update_conflicts=True,
            update_fields=['name', 'type', 'subtype', 'mask'],
            unique_fields=['account_id'],
            batch_size=500
        )

        batch = Batch.objects.create(
            total_transactions=total_transactions,
            request_id=request_id
        )

        transaction_objects = [
            Transaction(
                transaction_id=transaction_data['transaction_id'],
                account_id=transaction_data['account_id'],
                batch=batch,
                amount=transaction_data['amount'],
                currency=transaction_data['iso_currency_code'],
                date=transaction_data['date'],
                authorized_date=transaction_data.get('authorized_date'),
                description=transaction_data['name'],
                merchant_name=transaction_data.get('merchant_name'),
                payment_channel=transaction_data.get('payment_channel'),
                pending=transaction_data.get('pending', False),
            )
            for transaction_data in transactions_data
        ]

        # Use bulk_create with ignore_conflicts to skip duplicate transaction_ids
        Transaction.objects.bulk_create(
            transaction_objects,
            ignore_conflicts=True,
            batch_size=1000
        )

        return batch


class BatchIngestionResponseSerializer(serializers.ModelSerializer):
    """
    Serializer for the batch ingestion response.
    """
    class Meta:
        model = Batch
        fields = ['batch_id', 'total_transactions']


# Analytics API Serializers

class TopCategorySerializer(serializers.Serializer):
    """
    Serializer for top spending categories.
    """
    category = serializers.CharField()
    total_spend = serializers.DecimalField(max_digits=12, decimal_places=2)
    transaction_count = serializers.IntegerField()
    percentage_of_spend = serializers.SerializerMethodField()

    def get_percentage_of_spend(self, obj):
        """
        Calculate percentage of total spend for this category.
        """
        total_spend = self.context.get('total_spend', 0)
        if total_spend == 0:
            return 0.0
        category_spend = abs(obj.get('total_spend', 0))
        return round((category_spend / abs(total_spend)) * 100, 2)


class StatusBreakdownSerializer(serializers.Serializer):
    """
    Serializer for processing status breakdown.
    """
    pending = serializers.IntegerField(default=0)
    processing = serializers.IntegerField(default=0)
    completed = serializers.IntegerField(default=0)
    failed = serializers.IntegerField(default=0)


class MetricsSerializer(serializers.Serializer):
    """
    Serializer for summary metrics.
    """
    total_transactions = serializers.IntegerField()
    total_spend = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_income = serializers.DecimalField(max_digits=12, decimal_places=2)
    net = serializers.DecimalField(max_digits=12, decimal_places=2)


class DateRangeSerializer(serializers.Serializer):
    """
    Serializer for date range.
    """
    start = serializers.DateField()
    end = serializers.DateField()


class AccountSummarySerializer(serializers.Serializer):
    """
    Main response serializer for account summary endpoint.
    """
    account_id = serializers.CharField()
    date_range = DateRangeSerializer()
    metrics = MetricsSerializer()
    top_categories = TopCategorySerializer(many=True)
    processing_status = StatusBreakdownSerializer()