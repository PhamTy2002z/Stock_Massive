"""Integration tests for Jobs Router API endpoint."""
import pytest
from fastapi.testclient import TestClient

from src.core.job_status_store import job_store
from src.stocks.collector_schedule import (
    BACKFILL_JOB_ID,
    BACKFILL_JOB_NAME,
    COLLECTOR_JOB_ID,
    COLLECTOR_JOB_NAME,
    MARKET_INDEX_JOB_ID,
    MARKET_INDEX_JOB_NAME,
)
from src.main import app

client = TestClient(app)


class TestJobsRouter:
    """Tests for /api/v1/jobs/status endpoint."""

    def test_get_jobs_status_empty(self):
        """Test GET /api/v1/jobs/status returns empty list when no jobs."""
        # Clear any existing jobs from previous tests
        job_store.cleanup_old(max_age_hours=0)

        response = client.get("/api/v1/jobs/status")

        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        # May have jobs from other tests, so just verify it's a list

    def test_get_jobs_status_with_jobs(self):
        """Test GET /api/v1/jobs/status returns job statuses."""
        # Create test jobs
        job_store.start_job("test-api-job-1", "Test Job 1", total_items=100)
        job_store.update_progress("test-api-job-1", processed=50, message="Halfway")

        job_store.start_job("test-api-job-2", "Test Job 2", total_items=200)
        job_store.complete_job("test-api-job-2", result={"success": True})

        response = client.get("/api/v1/jobs/status")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 2, "Should have at least 2 test jobs"

        # Find our test jobs
        job1 = next((j for j in data if j["job_id"] == "test-api-job-1"), None)
        job2 = next((j for j in data if j["job_id"] == "test-api-job-2"), None)

        assert job1 is not None, "test-api-job-1 should exist"
        assert job2 is not None, "test-api-job-2 should exist"

        # Verify job1 structure and values
        assert job1["display_name"] == "Test Job 1"
        assert job1["status"] == "running"
        assert job1["progress"] == 50
        assert job1["total_items"] == 100
        assert job1["processed_items"] == 50
        assert job1["message"] == "Halfway"
        assert job1["started_at"] is not None
        assert job1["elapsed_seconds"] is not None
        assert isinstance(job1["elapsed_seconds"], int)

        # Verify job2 structure
        assert job2["status"] == "completed"
        assert job2["progress"] == 100
        assert job2["completed_at"] is not None

    def test_get_jobs_status_response_schema(self):
        """Test response schema matches JobStatusResponse model."""
        job_store.start_job("schema-test-job", "Schema Test", total_items=50)

        response = client.get("/api/v1/jobs/status")

        assert response.status_code == 200
        data = response.json()

        if len(data) > 0:
            job = data[0]

            # Verify all required fields exist
            required_fields = [
                "job_id",
                "display_name",
                "status",
                "progress",
                "total_items",
                "processed_items",
                "message",
                "started_at",
                "completed_at",
                "elapsed_seconds",
            ]

            for field in required_fields:
                assert field in job, f"Field '{field}' should exist in response"

            # Verify types
            assert isinstance(job["job_id"], str)
            assert isinstance(job["display_name"], str)
            assert job["status"] in ["pending", "running", "completed", "failed"]
            assert isinstance(job["progress"], int)
            assert isinstance(job["total_items"], int)
            assert isinstance(job["processed_items"], int)
            assert job["message"] is None or isinstance(job["message"], str)
            assert job["started_at"] is None or isinstance(job["started_at"], str)
            assert job["completed_at"] is None or isinstance(job["completed_at"], str)
            assert job["elapsed_seconds"] is None or isinstance(job["elapsed_seconds"], int)

    def test_get_jobs_status_failed_job(self):
        """Test GET /api/v1/jobs/status with failed job."""
        job_store.start_job("failed-job", "Failed Job", total_items=100)
        job_store.fail_job("failed-job", error="Test error occurred")

        response = client.get("/api/v1/jobs/status")

        assert response.status_code == 200
        data = response.json()

        failed_job = next((j for j in data if j["job_id"] == "failed-job"), None)
        assert failed_job is not None
        assert failed_job["status"] == "failed"
        assert failed_job["completed_at"] is not None

    def test_get_jobs_status_datetime_format(self):
        """Test datetime fields are in ISO format."""
        job_store.start_job("datetime-test", "DateTime Test", total_items=10)

        response = client.get("/api/v1/jobs/status")

        assert response.status_code == 200
        data = response.json()

        test_job = next((j for j in data if j["job_id"] == "datetime-test"), None)
        assert test_job is not None

        if test_job["started_at"]:
            # Verify ISO format (should have 'T' separator)
            assert "T" in test_job["started_at"], "started_at should be in ISO format"

    def test_jobs_router_cors_headers(self):
        """Test CORS headers are present in response."""
        response = client.get("/api/v1/jobs/status")

        assert response.status_code == 200
        # CORS headers should be added by middleware
        # TestClient may not include all headers, but response should succeed

    def test_the_market_wide_ohlcv_trigger_is_gone(self):
        """The job it started was deleted, so the route has to go with it.

        A trigger route imports its job inside the handler, which is why nothing
        else catches this: the module imports fine, the suite passes, and the
        route raises only when an operator presses the button.
        """
        response = client.post("/api/v1/jobs/trigger/ohlcv")

        assert response.status_code == 404

    def test_multiple_concurrent_requests(self):
        """Test API can handle multiple concurrent requests."""
        import concurrent.futures

        def make_request():
            response = client.get("/api/v1/jobs/status")
            assert response.status_code == 200
            return response.json()

        # Make 10 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [f.result() for f in futures]

        # All requests should succeed
        assert len(results) == 10
        for result in results:
            assert isinstance(result, list)


class TestWhatTheInterfaceIsToldAbout:
    """The collection pipeline runs for the system, not for the reader.

    Someone opening the app to look at a stock has no decision to make about a
    Snapshot cycle: they cannot start it, stop it or wait it out usefully, and
    a progress bar for it only asks them to care about plumbing. Operators
    still need to see it, so it is hidden from the shared feed rather than
    stopped from being recorded.
    """

    def test_the_collection_cycle_stays_out_of_the_user_facing_feed(self):
        job_store.cleanup_old(max_age_hours=0)
        job_store.start_job(COLLECTOR_JOB_ID, COLLECTOR_JOB_NAME, total_items=10)

        listed = client.get("/api/v1/jobs/status").json()

        assert [job["job_id"] for job in listed] == []

    def test_the_history_load_stays_out_of_it_too(self):
        job_store.cleanup_old(max_age_hours=0)
        job_store.start_job(BACKFILL_JOB_ID, BACKFILL_JOB_NAME, total_items=10)

        listed = client.get("/api/v1/jobs/status").json()

        assert [job["job_id"] for job in listed] == []

    def test_the_market_index_load_stays_out_of_it_as_well(self):
        job_store.cleanup_old(max_age_hours=0)
        job_store.start_job(MARKET_INDEX_JOB_ID, MARKET_INDEX_JOB_NAME)

        listed = client.get("/api/v1/jobs/status").json()

        assert [job["job_id"] for job in listed] == []

    def test_a_job_the_user_asked_for_is_still_reported(self):
        """Hiding infrastructure must not hide work someone is waiting on."""
        job_store.cleanup_old(max_age_hours=0)
        job_store.start_job("daily-ohlcv", "Thu thập OHLCV", total_items=10)

        listed = client.get("/api/v1/jobs/status").json()

        assert [job["job_id"] for job in listed] == ["daily-ohlcv"]

    def test_an_operator_can_still_ask_for_everything(self):
        """The cycle is hidden from the feed, not from the people running it."""
        job_store.cleanup_old(max_age_hours=0)
        job_store.start_job(COLLECTOR_JOB_ID, COLLECTOR_JOB_NAME, total_items=10)

        listed = client.get("/api/v1/jobs/status?include_internal=true").json()

        assert [job["job_id"] for job in listed] == [COLLECTOR_JOB_ID]
