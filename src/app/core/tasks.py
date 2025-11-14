from celery import shared_task
from django.db import transaction
from .models import Batch, Transaction, Status
from .services import DatabaseCategorizer, TransactionEnrichmentService
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_pending_batches(self):
    """
    Celery task that processes all pending batches.
    This task runs periodically (every 5 minutes) to process batches that are in PENDING status.
    """
    logger.info("Starting to process pending batches")

    # Get all pending batches ordered by creation time (oldest first)
    pending_batches = Batch.objects.filter(status=Status.PENDING).order_by('created_at')

    if not pending_batches.exists():
        logger.info("No pending batches to process")
        return {"processed": 0, "failed": 0}

    processed_count = 0
    failed_count = 0

    for batch in pending_batches:
        try:
            logger.info(f"Processing batch {batch.batch_id}")
            process_single_batch(batch.batch_id)
            processed_count += 1
        except Exception as e:
            logger.error(f"Failed to process batch {batch.batch_id}: {str(e)}")
            failed_count += 1
            # Mark batch as failed
            batch.status = Status.FAILED
            batch.save(update_fields=['status', 'updated_at'])

    logger.info(f"Finished processing batches. Processed: {processed_count}, Failed: {failed_count}")
    return {"processed": processed_count, "failed": failed_count}


@transaction.atomic
def process_single_batch(batch_id):
    """
    Process a single batch and its transactions.

    This function:
    1. Updates batch status to PROCESSING
    2. Processes all transactions in the batch (enrichment logic can be added here)
    3. Updates batch status to COMPLETED
    """
    batch = Batch.objects.select_for_update().get(batch_id=batch_id)

    if batch.status in [Status.PROCESSING, Status.COMPLETED]:
        logger.warning(f"Batch {batch_id} is already {batch.status}")
        return

    batch.status = Status.PROCESSING
    batch.save(update_fields=['status', 'updated_at'])

    try:
        categorizer = DatabaseCategorizer()
        enrichment_service = TransactionEnrichmentService(categorizer)

        transactions = Transaction.objects.filter(batch=batch, ingestion_status=Status.PENDING)

        logger.info(f"Processing {transactions.count()} transactions for batch {batch_id}")

        transactions_to_update = []
        for txn in transactions:
            category = enrichment_service.enrich_transaction(
                merchant_name=txn.merchant_name,
                description=txn.description
            )
            txn.category = category
            txn.ingestion_status = Status.COMPLETED

            transactions_to_update.append(txn)

        Transaction.objects.bulk_update(
            transactions_to_update,
            ['category', 'ingestion_status', 'updated_at'],
            batch_size=1000
        )

        logger.info(f"Successfully enriched and categorized {len(transactions_to_update)} transactions")

        batch.status = Status.COMPLETED
        batch.save(update_fields=['status', 'updated_at'])

        logger.info(f"Successfully processed batch {batch_id}")

    except Exception as e:
        logger.error(f"Error processing batch {batch_id}: {str(e)}")
        batch.status = Status.FAILED
        batch.save(update_fields=['status', 'updated_at'])
        raise


@shared_task
def process_batch_async(batch_id):
    """
    Async task to process a single batch.
    Can be called from the API to process a batch immediately instead of waiting for the periodic task.
    """

    logger.info(f"Async processing batch {batch_id}")
    try:
        process_single_batch(batch_id)
        return {"status": "success", "batch_id": str(batch_id)}
    except Exception as e:
        logger.error(f"Failed to process batch {batch_id}: {str(e)}")
        return {"status": "failed", "batch_id": str(batch_id), "error": str(e)}