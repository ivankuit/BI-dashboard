from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ValidationError
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.http import Http404
from django.db.models import Sum, Count, Case, When, IntegerField, DecimalField
from django.utils import timezone
from django.core.cache import cache
from decimal import Decimal
from datetime import datetime, time
from .serializers import (
    BatchIngestionRequestSerializer,
    BatchIngestionResponseSerializer,
    AccountSummarySerializer,
    TopCategorySerializer
)
from .models import Transaction, Status
from .tasks import process_batch_async
from .utils import validate_date_range, validate_account
import logging

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class BatchIngestionView(APIView):
    """
    API endpoint for batch ingestion of accounts and transactions.

    POST /api/integrations/transactions/
    """

    def post(self, request):
        """
        Handle batch ingestion of accounts and transactions.

        Accepts a payload with accounts and transactions, creates or updates accounts,
        creates a batch record to be processd, and creates transaction records.

        Returns the batch_id and total_transactions.
        """
        # Deserialize and validate the request data
        serializer = BatchIngestionRequestSerializer(data=request.data)

        if not serializer.is_valid():
            logger.error(f"Batch ingestion validation failed: {serializer.errors}")
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Create the batch and associated records
            batch = serializer.save()

            # Kick off async processing task
            process_batch_async.delay(batch.batch_id)
            logger.info(f"Triggered async processing for batch {batch.batch_id}")

            # Serialize the response
            response_serializer = BatchIngestionResponseSerializer(batch)

            logger.info(f"Successfully created batch {batch.batch_id} with {batch.total_transactions} transactions")

            return Response(
                response_serializer.data,
                status=status.HTTP_202_ACCEPTED
            )

        except Exception as e:
            logger.exception(f"Error during batch ingestion: {str(e)}")
            return Response(
                {"error": "An error occurred during batch ingestion"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AccountSummaryAPIView(APIView):
    """
    API endpoint for account transaction summary and analytics.

    GET /api/reports/account/{account_id}/summary/
    Query parameters:
    - start_date: YYYY-MM-DD format (required)
    - end_date: YYYY-MM-DD format (required)
    """

    def get(self, request, account_id):
        """
        Retrieve transaction summary with metrics, top categories, and processing status.

        Calculations:
        - total_transactions: Count of all transactions in date range
        - total_spend: Sum of negative amounts (expenses)
        - total_income: Sum of positive amounts (income)
        - net: Algebraic sum (total_income + total_spend)
        - top_categories: Top 3 spending categories with counts and percentages
        - processing_status: Breakdown by ingestion status

        Results are cached for 5 minutes using account_id, start_date, and end_date as cache keys.
        """
        try:
            # Extract and validate query parameters
            start_date_str = request.query_params.get('start_date')
            end_date_str = request.query_params.get('end_date')

            # Check required parameters
            if not start_date_str:
                raise ValidationError({
                    'error': 'Missing required parameter',
                    'detail': 'start_date is required (format: YYYY-MM-DD)'
                })

            if not end_date_str:
                raise ValidationError({
                    'error': 'Missing required parameter',
                    'detail': 'end_date is required (format: YYYY-MM-DD)'
                })

            # Validate date range
            start_date, end_date = validate_date_range(start_date_str, end_date_str)

            # Generate cache key based on account_id, start_date, and end_date
            cache_key = f"account_summary:{account_id}:{start_date_str}:{end_date_str}"

            # Try to get cached result
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.info(
                    f"Cache hit for account summary: {account_id} "
                    f"({start_date_str} to {end_date_str})"
                )
                return Response(cached_result, status=status.HTTP_200_OK)

            validate_account(account_id)

            # Convert dates to timezone-aware datetimes for DateTimeField comparison

            start_datetime = timezone.make_aware(datetime.combine(start_date, time.min))
            end_datetime = timezone.make_aware(datetime.combine(end_date, time.max))

            transactions_qs = Transaction.objects.filter(
                account_id=account_id,
                date__gte=start_datetime,
                date__lte=end_datetime
            )


            summary_metrics = transactions_qs.aggregate(
                total_transactions=Count('id'),
                total_spend=Sum(
                    Case(
                        When(amount__lt=0, then='amount'),
                        default=0,
                        output_field=DecimalField()
                    )
                ),
                total_income=Sum(
                    Case(
                        When(amount__gte=0, then='amount'),
                        default=0,
                        output_field=DecimalField()
                    )
                )
            )

            # Extract values with defaults
            total_transactions = summary_metrics['total_transactions'] or 0
            total_spend = summary_metrics['total_spend'] or Decimal('0.00')
            total_income = summary_metrics['total_income'] or Decimal('0.00')
            net = total_income + total_spend  # total_spend is negative

            # Calculate top 3 spending categories
            # Filter for expenses only (amount < 0), group by category
            top_categories_data = (
                transactions_qs
                .filter(amount__lt=0)
                .values('category')
                .annotate(
                    total_spend=Sum('amount'),
                    transaction_count=Count('id')
                )
                .order_by('total_spend')  # Most negative = highest spend
                [:3]
            )

            # Convert to list and make amounts absolute for display
            top_categories = [
                {
                    'category': cat['category'] or 'Uncategorized',
                    'total_spend': abs(cat['total_spend']),
                    'transaction_count': cat['transaction_count']
                }
                for cat in top_categories_data
            ]

            # Calculate processing status breakdown
            status_breakdown_data = transactions_qs.values('ingestion_status').annotate(
                count=Count('id')
            )

            # Map status codes to names
            status_map = {
                Status.PENDING: 'pending',
                Status.PROCESSING: 'processing',
                Status.COMPLETED: 'completed',
                Status.FAILED: 'failed'
            }

            # Initialize status counts
            processing_status = {
                'pending': 0,
                'processing': 0,
                'completed': 0,
                'failed': 0
            }

            # Populate status counts
            for item in status_breakdown_data:
                status_code = item['ingestion_status']
                status_name = status_map.get(status_code, 'unknown')
                if status_name in processing_status:
                    processing_status[status_name] = item['count']

            # Build response data
            response_data = {
                'account_id': account_id,
                'date_range': {
                    'start': start_date,
                    'end': end_date
                },
                'metrics': {
                    'total_transactions': total_transactions,
                    'total_spend': abs(total_spend),  # Display as positive
                    'total_income': total_income,
                    'net': net
                },
                'top_categories': top_categories,
                'processing_status': processing_status
            }

            # Serialize and return response
            serializer = AccountSummarySerializer(
                data=response_data,
                context={'total_spend': total_spend}  # For percentage calculation
            )
            serializer.is_valid(raise_exception=True)

            # Cache the result for 5 minutes (300 seconds)
            cache.set(cache_key, serializer.data, timeout=300)

            logger.info(
                f"Account summary generated for {account_id} "
                f"({start_date} to {end_date}): {total_transactions} transactions (cached)"
            )

            return Response(serializer.data, status=status.HTTP_200_OK)

        except ValidationError as e:
            logger.warning(f"Validation error for account {account_id}: {e.detail}")
            return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)

        except Http404 as e:
            logger.warning(f"Account not found: {account_id}")
            return Response(
                {'detail': 'Account not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        except Exception as e:
            logger.exception(f"Error generating account summary for {account_id}: {str(e)}")
            return Response(
                {
                    'error': 'Internal server error',
                    'detail': 'An error occurred while generating the account summary'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
