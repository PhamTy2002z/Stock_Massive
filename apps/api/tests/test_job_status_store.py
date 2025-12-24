"""Unit tests for JobStatusStore - thread-safe job status tracking."""
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pytest

from src.core.job_status_store import JobStatus, JobStatusStore, job_store


class TestJobStatusStore:
    """Tests for JobStatusStore singleton and thread-safety."""

    def test_singleton_pattern(self):
        """Verify JobStatusStore is a singleton."""
        store1 = JobStatusStore()
        store2 = JobStatusStore()
        assert store1 is store2, "JobStatusStore should be a singleton"
        assert store1 is job_store, "job_store should be the same instance"

    def test_start_job(self):
        """Test starting a new job."""
        job_id = "test-job-1"
        store = JobStatusStore()

        store.start_job(job_id, "Test Job", total_items=100)

        statuses = store.get_all_statuses()
        assert len(statuses) > 0, "Should have at least one job"

        job = next((j for j in statuses if j.job_id == job_id), None)
        assert job is not None, "Job should exist"
        assert job.status == "running"
        assert job.total_items == 100
        assert job.processed_items == 0
        assert job.progress == 0
        assert job.started_at is not None

    def test_update_progress(self):
        """Test updating job progress."""
        job_id = "test-job-2"
        store = JobStatusStore()

        store.start_job(job_id, "Test Job Progress", total_items=100)
        store.update_progress(job_id, processed=50, message="Halfway done")

        statuses = store.get_all_statuses()
        job = next((j for j in statuses if j.job_id == job_id), None)

        assert job is not None
        assert job.processed_items == 50
        assert job.progress == 50
        assert job.message == "Halfway done"

    def test_complete_job(self):
        """Test marking job as completed."""
        job_id = "test-job-3"
        store = JobStatusStore()

        store.start_job(job_id, "Test Job Complete", total_items=100)
        result = {"processed": 100, "success": True}
        store.complete_job(job_id, result=result)

        statuses = store.get_all_statuses()
        job = next((j for j in statuses if j.job_id == job_id), None)

        assert job is not None
        assert job.status == "completed"
        assert job.progress == 100
        assert job.processed_items == 100
        assert job.completed_at is not None
        assert job.result == result

    def test_fail_job(self):
        """Test marking job as failed."""
        job_id = "test-job-4"
        store = JobStatusStore()

        store.start_job(job_id, "Test Job Fail", total_items=100)
        error_msg = "Something went wrong"
        store.fail_job(job_id, error=error_msg)

        statuses = store.get_all_statuses()
        job = next((j for j in statuses if j.job_id == job_id), None)

        assert job is not None
        assert job.status == "failed"
        assert job.error == error_msg
        assert job.completed_at is not None

    def test_thread_safety_concurrent_updates(self):
        """Test thread-safety with concurrent updates to different jobs."""
        store = JobStatusStore()
        num_threads = 10

        def create_and_update_job(thread_id: int):
            job_id = f"thread-job-{thread_id}"
            store.start_job(job_id, f"Thread Job {thread_id}", total_items=100)

            for i in range(1, 101):
                store.update_progress(job_id, processed=i, message=f"Progress {i}")
                time.sleep(0.001)  # Small delay to increase contention

            store.complete_job(job_id, result={"thread_id": thread_id})

        # Run jobs in parallel
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(create_and_update_job, i) for i in range(num_threads)]
            for future in futures:
                future.result()  # Wait for completion

        # Verify all jobs completed successfully
        statuses = store.get_all_statuses()
        thread_jobs = [j for j in statuses if j.job_id.startswith("thread-job-")]

        assert len(thread_jobs) == num_threads, f"Expected {num_threads} jobs, got {len(thread_jobs)}"

        for job in thread_jobs:
            assert job.status == "completed", f"Job {job.job_id} should be completed"
            assert job.progress == 100, f"Job {job.job_id} should have 100% progress"
            assert job.processed_items == 100, f"Job {job.job_id} should have processed 100 items"

    def test_thread_safety_same_job_updates(self):
        """Test thread-safety with concurrent updates to same job (edge case)."""
        store = JobStatusStore()
        job_id = "shared-job"
        store.start_job(job_id, "Shared Job", total_items=1000)

        num_threads = 10
        updates_per_thread = 10

        def update_shared_job(thread_id: int):
            for i in range(updates_per_thread):
                # Each thread updates progress
                progress = thread_id * updates_per_thread + i + 1
                store.update_progress(job_id, processed=progress, message=f"Thread {thread_id} update {i}")
                time.sleep(0.001)

        # Run concurrent updates
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(update_shared_job, i) for i in range(num_threads)]
            for future in futures:
                future.result()

        # Verify job still exists and is consistent
        statuses = store.get_all_statuses()
        job = next((j for j in statuses if j.job_id == job_id), None)

        assert job is not None, "Shared job should exist"
        assert job.status == "running", "Job should still be running"
        assert 0 <= job.processed_items <= 1000, "Processed items should be within bounds"
        assert job.message is not None, "Message should be set"

    def test_get_all_statuses_filters_today(self):
        """Test that get_all_statuses only returns jobs from today."""
        store = JobStatusStore()

        # Create a job today
        today_job_id = "today-job"
        store.start_job(today_job_id, "Today's Job", total_items=10)

        statuses = store.get_all_statuses()
        today_jobs = [j for j in statuses if j.job_id == today_job_id]

        assert len(today_jobs) == 1, "Should find today's job"
        assert today_jobs[0].started_at.date() == datetime.now().date()

    def test_cleanup_old_jobs(self):
        """Test cleanup of old jobs (basic test - no actual old jobs)."""
        store = JobStatusStore()

        # Create a fresh job
        job_id = "cleanup-test-job"
        store.start_job(job_id, "Cleanup Test", total_items=10)

        # Try to cleanup jobs older than 24 hours (should remove nothing recent)
        removed = store.cleanup_old(max_age_hours=24)

        # Verify the fresh job still exists
        statuses = store.get_all_statuses()
        job = next((j for j in statuses if j.job_id == job_id), None)
        assert job is not None, "Recent job should not be removed"

    def test_update_nonexistent_job(self):
        """Test updating a job that doesn't exist (should not crash)."""
        store = JobStatusStore()

        # Try to update a job that doesn't exist
        store.update_progress("nonexistent-job", processed=50, message="Test")
        store.complete_job("nonexistent-job", result={"test": True})
        store.fail_job("nonexistent-job", error="Test error")

        # Should not crash - no assertion needed, just verify no exception

    def test_job_status_dataclass(self):
        """Test JobStatus dataclass initialization."""
        job = JobStatus(
            job_id="test-123",
            display_name="Test Job",
            status="running",
            progress=50,
            total_items=100,
            processed_items=50,
            message="Testing",
            started_at=datetime.now(),
        )

        assert job.job_id == "test-123"
        assert job.display_name == "Test Job"
        assert job.status == "running"
        assert job.progress == 50
        assert job.total_items == 100
        assert job.processed_items == 50
        assert job.message == "Testing"
        assert job.started_at is not None
        assert job.completed_at is None
        assert job.result is None
        assert job.error is None
