import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class QueueService:
    """Unified job dispatcher. Transparently directs background jobs to either
    Celery + Redis (production) or an in-process ThreadPool (development / testing).
    """

    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="fbr-inline-worker-")

    def enqueue_fbr_submission(
        self,
        job_id: str,
        tenant_id: str,
        correlation_id: str,
        countdown: int = 0,
    ):
        """Enqueue an FBR submission job."""
        if settings.QUEUE_BACKEND == "celery":
            try:
                from backend.app.workers.tasks import submit_invoice_to_fbr_task
                submit_invoice_to_fbr_task.apply_async(
                    args=[job_id, correlation_id, tenant_id],
                    queue="fbr_submission",
                    countdown=countdown,
                )
                logger.info(f"Dispatched FBR submission job {job_id} to Celery queue 'fbr_submission' (countdown={countdown}s)")
                return
            except Exception as exc:
                logger.warning(f"Failed to dispatch to Celery, falling back to inline executor: {exc}")

        # Inline execution via ThreadPool
        if settings.QUEUE_INLINE_EXECUTION == "manual":
            logger.info(f"Manual queue mode active; job {job_id} not auto-dispatched to thread")
            return

        def _run_with_delay():
            if countdown > 0:
                time.sleep(countdown)
            from backend.app.workers.tasks import submit_invoice_to_fbr_task
            submit_invoice_to_fbr_task(job_id=job_id, correlation_id=correlation_id, tenant_id=tenant_id)

        try:
            self._executor.submit(_run_with_delay)
            logger.info(f"Dispatched FBR submission job {job_id} to inline ThreadPool (countdown={countdown}s)")
        except RuntimeError:
            pass

    def enqueue_pdf_generation(
        self,
        invoice_id: str,
        tenant_id: str,
        correlation_id: str,
        user_id: Optional[str] = None,
        countdown: int = 0,
    ):
        """Enqueue an asynchronous PDF invoice generation job."""
        if settings.QUEUE_BACKEND == "celery":
            try:
                from backend.app.workers.tasks import generate_invoice_pdf_task
                generate_invoice_pdf_task.apply_async(
                    args=[invoice_id, correlation_id, tenant_id, user_id],
                    queue="pdf_generation",
                    countdown=countdown,
                )
                logger.info(f"Dispatched PDF generation for invoice {invoice_id} to Celery queue 'pdf_generation'")
                return
            except Exception as exc:
                logger.warning(f"Failed to dispatch PDF task to Celery, falling back to inline executor: {exc}")

        # Inline execution via ThreadPool
        if settings.QUEUE_INLINE_EXECUTION == "manual":
            return

        def _run_pdf():
            if countdown > 0:
                time.sleep(countdown)
            from backend.app.workers.tasks import generate_invoice_pdf_task
            generate_invoice_pdf_task(invoice_id=invoice_id, correlation_id=correlation_id, tenant_id=tenant_id, user_id=user_id)

        try:
            self._executor.submit(_run_pdf)
            logger.info(f"Dispatched PDF generation for invoice {invoice_id} to inline ThreadPool")
        except RuntimeError:
            pass

    def enqueue_note_submission(
        self,
        note_type: str,
        note_id: str,
        tenant_id: str,
        correlation_id: str,
        countdown: int = 0,
    ):
        """Enqueue an asynchronous Credit or Debit note FBR submission job."""
        if settings.QUEUE_BACKEND == "celery":
            try:
                from backend.app.workers.tasks import submit_note_to_fbr_task
                submit_note_to_fbr_task.apply_async(
                    args=[note_type, note_id, tenant_id, correlation_id],
                    queue="fbr_submission",
                    countdown=countdown,
                )
                logger.info(f"Dispatched {note_type} note submission {note_id} to Celery queue 'fbr_submission'")
                return
            except Exception as exc:
                logger.warning(f"Failed to dispatch note task to Celery, falling back to inline executor: {exc}")

        if settings.QUEUE_INLINE_EXECUTION == "manual":
            return

        def _run_note():
            if countdown > 0:
                time.sleep(countdown)
            from backend.app.workers.tasks import submit_note_to_fbr_task
            submit_note_to_fbr_task(note_type=note_type, note_id=note_id, tenant_id=tenant_id, correlation_id=correlation_id)

        try:
            self._executor.submit(_run_note)
            logger.info(f"Dispatched {note_type} note submission {note_id} to inline ThreadPool")
        except RuntimeError:
            pass

    def enqueue_batch_fbr_submission(
        self,
        batch_job_id: str,
        tenant_id: str,
        correlation_id: str,
        countdown: int = 0,
    ):
        """Enqueue an asynchronous Batch FBR submission processing job."""
        if settings.QUEUE_BACKEND == "celery":
            try:
                from backend.app.workers.tasks import process_batch_fbr_submission_task
                process_batch_fbr_submission_task.apply_async(
                    args=[batch_job_id, tenant_id, correlation_id],
                    queue="fbr_submission",
                    countdown=countdown,
                )
                logger.info(f"Dispatched batch FBR job {batch_job_id} to Celery queue 'fbr_submission'")
                return
            except Exception as exc:
                logger.warning(f"Failed to dispatch batch task to Celery, falling back to inline executor: {exc}")

        if settings.QUEUE_INLINE_EXECUTION == "manual":
            return

        def _run_batch():
            if countdown > 0:
                time.sleep(countdown)
            from backend.app.workers.tasks import process_batch_fbr_submission_task
            process_batch_fbr_submission_task(batch_job_id=batch_job_id, tenant_id=tenant_id, correlation_id=correlation_id)

        try:
            self._executor.submit(_run_batch)
            logger.info(f"Dispatched batch FBR job {batch_job_id} to inline ThreadPool")
        except RuntimeError:
            pass

    def enqueue_task(
        self,
        task_name: str,
        args: list = None,
        kwargs: dict = None,
        queue_name: str = "default",
        countdown: int = 0
    ):
        """Generic task dispatcher supporting both Celery and inline execution."""
        args = args or []
        kwargs = kwargs or {}

        if settings.QUEUE_BACKEND == "celery":
            try:
                from backend.app.workers.celery_app import celery_app
                celery_app.send_task(
                    task_name,
                    args=args,
                    kwargs=kwargs,
                    queue=queue_name,
                    countdown=countdown,
                )
                logger.info(f"Dispatched task {task_name} to Celery queue '{queue_name}'")
                return
            except Exception as exc:
                logger.warning(f"Failed to dispatch {task_name} to Celery, falling back to inline executor: {exc}")

        if settings.QUEUE_INLINE_EXECUTION == "manual":
            return

        def _run_task():
            if countdown > 0:
                time.sleep(countdown)
            try:
                import importlib
                module_name, func_name = task_name.rsplit(".", 1)
                mod = importlib.import_module(module_name)
                func = getattr(mod, func_name)
                func(*args, **kwargs)
            except Exception as e:
                logger.exception(f"Error executing inline task {task_name}: {e}")

        try:
            self._executor.submit(_run_task)
        except RuntimeError:
            pass


queue_service = QueueService()
