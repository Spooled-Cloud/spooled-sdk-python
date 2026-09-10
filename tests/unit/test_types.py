"""Unit tests for Pydantic types/models."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError as PydanticValidationError

from spooled.types.auth import (
    LoginParams,
    ValidateResponse,
)
from spooled.types.jobs import (
    BulkEnqueueParams,
    BulkJobItem,
    ClaimedJob,
    ClaimJobsParams,
    CompleteJobParams,
    CreateJobParams,
    FailJobParams,
    Job,
    JobHeartbeatParams,
    JobSummary,
    PurgeDlqParams,
)
from spooled.types.organizations import (
    CreateOrganizationParams,
)
from spooled.types.schedules import (
    CreateScheduleParams,
    Schedule,
)
from spooled.types.webhooks import (
    CreateOutgoingWebhookParams,
    OutgoingWebhook,
    OutgoingWebhookDelivery,
    UpdateOutgoingWebhookParams,
)
from spooled.types.workers import (
    RegisterWorkerParams,
)
from spooled.types.workflows import (
    CreateWorkflowParams,
    WorkflowJob,
    WorkflowJobDefinition,
    WorkflowResponse,
)


class TestValidateResponse:
    """POST /auth/validate is {valid, error?, claims?}."""

    def test_maps_claims_onto_organization_id(self) -> None:
        got = ValidateResponse.model_validate(
            {
                "valid": True,
                "claims": {
                    "org_id": "org_1",
                    "api_key_id": "key_1",
                    "queues": ["emails"],
                    "exp": 1700003600,
                    "iat": 1700000000,
                },
            }
        )
        assert got.valid is True
        assert got.organization_id == "org_1"
        assert got.api_key_id == "key_1"
        assert got.queues == ["emails"]
        assert got.expires_at == datetime.fromtimestamp(1700003600, tz=timezone.utc)
        assert got.error is None

    def test_maps_error_when_invalid(self) -> None:
        got = ValidateResponse.model_validate({"valid": False, "error": "Invalid token"})
        assert got.valid is False
        assert got.error == "Invalid token"
        assert got.organization_id is None


class TestCreateJobParams:
    """Tests for CreateJobParams."""

    def test_minimal_params(self) -> None:
        """Test minimal required params."""
        params = CreateJobParams(
            queue_name="test-queue",
            payload={"key": "value"},
        )
        assert params.queue_name == "test-queue"
        assert params.payload == {"key": "value"}
        assert params.priority == 0
        assert params.max_retries == 3

    def test_minimal_create_dump_omits_queue_defaults(self) -> None:
        """Unset queue defaults are omitted so the server can apply its policy."""
        params = CreateJobParams(queue_name="test-queue", payload={"key": "value"})

        data = params.model_dump(exclude_none=True, exclude_unset=True, mode="json")

        assert data == {"queue_name": "test-queue", "payload": {"key": "value"}}
        assert "max_retries" not in data
        assert "timeout_seconds" not in data

    def test_explicit_create_defaults_remain_in_dump(self) -> None:
        """Explicit defaults are still sent when the caller chose them."""
        params = CreateJobParams(
            queue_name="test-queue",
            payload={"key": "value"},
            max_retries=3,
            timeout_seconds=300,
        )

        data = params.model_dump(exclude_none=True, exclude_unset=True, mode="json")

        assert data["max_retries"] == 3
        assert data["timeout_seconds"] == 300

    def test_all_params(self) -> None:
        """Test all params."""
        now = datetime.now()
        params = CreateJobParams(
            queue_name="test-queue",
            payload={"key": "value"},
            priority=5,
            max_retries=5,
            timeout_seconds=600,
            scheduled_at=now,
            expires_at=now,
            idempotency_key="unique-123",
            tags={"env": "prod"},
            parent_job_id="job_parent",
            completion_webhook="https://example.com/webhook",
        )
        assert params.priority == 5
        assert params.idempotency_key == "unique-123"

    def test_tags_accept_object_and_string_array(self) -> None:
        """POST /jobs tags is JSON: object with bool values, or a string array."""
        object_tags = CreateJobParams(queue_name="q", payload={}, tags={"urgent": True})
        assert object_tags.tags == {"urgent": True}
        array_tags = CreateJobParams(queue_name="q", payload={}, tags=["urgent"])
        assert array_tags.tags == ["urgent"]

    def test_payload_accepts_non_object_json(self) -> None:
        """POST /jobs payload is serde_json::Value, not only objects."""
        params = CreateJobParams(queue_name="q", payload="plain-string")
        assert params.payload == "plain-string"
        assert BulkJobItem(payload=False).payload is False

    def test_queue_name_validation(self) -> None:
        """Test queue_name validation."""
        # Empty name
        with pytest.raises(PydanticValidationError):
            CreateJobParams(queue_name="", payload={})

        # Too long (> 100)
        with pytest.raises(PydanticValidationError):
            CreateJobParams(queue_name="x" * 101, payload={})

    def test_priority_bounds(self) -> None:
        """Test priority validation bounds."""
        # Valid bounds
        CreateJobParams(queue_name="q", payload={}, priority=-100)
        CreateJobParams(queue_name="q", payload={}, priority=100)

        # Invalid
        with pytest.raises(PydanticValidationError):
            CreateJobParams(queue_name="q", payload={}, priority=-101)
        with pytest.raises(PydanticValidationError):
            CreateJobParams(queue_name="q", payload={}, priority=101)

    def test_max_retries_bounds(self) -> None:
        """Test max_retries validation bounds."""
        CreateJobParams(queue_name="q", payload={}, max_retries=0)
        CreateJobParams(queue_name="q", payload={}, max_retries=100)

        with pytest.raises(PydanticValidationError):
            CreateJobParams(queue_name="q", payload={}, max_retries=-1)
        with pytest.raises(PydanticValidationError):
            CreateJobParams(queue_name="q", payload={}, max_retries=101)

    def test_timeout_bounds(self) -> None:
        """Test timeout_seconds validation bounds."""
        CreateJobParams(queue_name="q", payload={}, timeout_seconds=1)
        CreateJobParams(queue_name="q", payload={}, timeout_seconds=86400)

        with pytest.raises(PydanticValidationError):
            CreateJobParams(queue_name="q", payload={}, timeout_seconds=0)
        with pytest.raises(PydanticValidationError):
            CreateJobParams(queue_name="q", payload={}, timeout_seconds=86401)

    def test_extra_fields_forbidden(self) -> None:
        """Test extra fields not allowed."""
        with pytest.raises(PydanticValidationError):
            CreateJobParams(
                queue_name="q",
                payload={},
                unknown_field="value",
            )


class TestJob:
    """Tests for Job model."""

    def test_full_job(self) -> None:
        """Test full job model."""
        now = datetime.now()
        job = Job(
            id="job_123",
            organization_id="org_1",
            queue_name="emails",
            status="pending",
            payload={"to": "user@example.com"},
            retry_count=0,
            max_retries=3,
            created_at=now,
            priority=5,
            timeout_seconds=300,
        )
        assert job.id == "job_123"
        assert job.status == "pending"

    def test_status_literal(self) -> None:
        """Test status must be valid literal."""
        now = datetime.now()
        # Valid statuses
        for status in [
            "pending",
            "scheduled",
            "processing",
            "completed",
            "failed",
            "deadletter",
            "cancelled",
        ]:
            job = Job(
                id="job_123",
                organization_id="org_1",
                queue_name="q",
                status=status,
                payload={},
                retry_count=0,
                max_retries=3,
                created_at=now,
                priority=0,
                timeout_seconds=300,
            )
            assert job.status == status

    def test_tags_accept_object_and_string_array(self) -> None:
        """GET /jobs/{id} tags is JSON: object with bool values, or a string array."""
        now = datetime.now(timezone.utc)
        base = {
            "id": "job_123",
            "organization_id": "org_1",
            "queue_name": "emails",
            "status": "pending",
            "payload": {},
            "retry_count": 0,
            "max_retries": 3,
            "created_at": now,
            "priority": 0,
            "timeout_seconds": 300,
        }
        object_tags = Job.model_validate({**base, "tags": {"urgent": True}})
        assert object_tags.tags == {"urgent": True}
        array_tags = Job.model_validate({**base, "tags": ["urgent", "billing"]})
        assert array_tags.tags == ["urgent", "billing"]
        none_tags = Job.model_validate({**base, "tags": None})
        assert none_tags.tags is None

    def test_payload_and_result_accept_any_json(self) -> None:
        """GET /jobs/{id} payload/result is serde_json::Value, not only objects."""
        now = datetime.now(timezone.utc)
        base = {
            "id": "job_123",
            "organization_id": "org_1",
            "queue_name": "emails",
            "status": "completed",
            "retry_count": 0,
            "max_retries": 3,
            "created_at": now,
            "priority": 0,
            "timeout_seconds": 300,
        }
        array_payload = Job.model_validate({**base, "payload": ["a", "b"]})
        assert array_payload.payload == ["a", "b"]
        string_result = Job.model_validate({**base, "payload": {}, "result": "ok"})
        assert string_result.result == "ok"
        list_result = Job.model_validate({**base, "payload": {}, "result": [1, 2]})
        assert list_result.result == [1, 2]


class TestClaimedJob:
    """Tests for ClaimedJob."""

    def test_payload_accepts_non_object_json(self) -> None:
        """POST /jobs/claim payload is serde_json::Value."""
        job = ClaimedJob.model_validate(
            {
                "id": "job_1",
                "queue_name": "emails",
                "payload": ["item"],
                "retry_count": 0,
                "max_retries": 3,
                "timeout_seconds": 30,
            }
        )
        assert job.payload == ["item"]

    def test_parses_lease_id(self) -> None:
        """Test lease_id fencing token is parsed from the claim response."""
        job = ClaimedJob.model_validate(
            {
                "id": "job_123",
                "queue_name": "test",
                "payload": {"key": "value"},
                "retry_count": 0,
                "max_retries": 3,
                "timeout_seconds": 300,
                "lease_id": "lease-abc",
            }
        )
        assert job.lease_id == "lease-abc"

    def test_lease_id_defaults_to_none(self) -> None:
        """Test lease_id is None when absent (legacy server)."""
        job = ClaimedJob.model_validate(
            {
                "id": "job_123",
                "queue_name": "test",
                "payload": {},
                "retry_count": 0,
                "max_retries": 3,
                "timeout_seconds": 300,
            }
        )
        assert job.lease_id is None


class TestCompleteJobParams:
    """Tests for CompleteJobParams."""

    def test_result_accepts_non_object_json(self) -> None:
        """POST /jobs/{id}/complete result is serde_json::Value."""
        params = CompleteJobParams(worker_id="w1", result="ok")
        assert params.result == "ok"
        params = CompleteJobParams(worker_id="w1", result=["a"])
        assert params.result == ["a"]


class TestClaimJobsParams:
    """Tests for ClaimJobsParams."""

    def test_defaults(self) -> None:
        """Test default values."""
        params = ClaimJobsParams(
            queue_name="test",
            worker_id="worker_1",
        )
        assert params.limit == 1
        assert params.lease_duration_secs == 30

    def test_custom_values(self) -> None:
        """Test custom values."""
        params = ClaimJobsParams(
            queue_name="test",
            worker_id="worker_1",
            limit=10,
            lease_duration_secs=60,
        )
        assert params.limit == 10
        assert params.lease_duration_secs == 60

    def test_limit_bounds(self) -> None:
        """Test limit validation."""
        with pytest.raises(PydanticValidationError):
            ClaimJobsParams(queue_name="q", worker_id="w", limit=0)
        with pytest.raises(PydanticValidationError):
            ClaimJobsParams(queue_name="q", worker_id="w", limit=101)

    def test_lease_duration_bounds(self) -> None:
        """Test lease_duration_secs validation."""
        with pytest.raises(PydanticValidationError):
            ClaimJobsParams(queue_name="q", worker_id="w", lease_duration_secs=4)
        with pytest.raises(PydanticValidationError):
            ClaimJobsParams(queue_name="q", worker_id="w", lease_duration_secs=3601)


class TestJobSummary:
    """Tests for JobSummary list/DLQ shape."""

    def test_maps_attempt_from_list_json(self) -> None:
        """GET /jobs sends attempt, not retry_count."""
        job = JobSummary.model_validate(
            {
                "id": "job_1",
                "queue_name": "emails",
                "status": "pending",
                "priority": 0,
                "attempt": 2,
                "max_retries": 5,
                "created_at": "2024-01-01T00:00:00Z",
            }
        )
        assert job.retry_count == 2
        assert job.max_retries == 5

    def test_maps_job_type_from_list_json(self) -> None:
        """GET /jobs summaries send job_type from payload.job_type."""
        job = JobSummary.model_validate(
            {
                "id": "job_1",
                "queue_name": "emails",
                "status": "pending",
                "priority": 0,
                "attempt": 0,
                "max_retries": 3,
                "job_type": "send_email",
                "created_at": "2024-01-01T00:00:00Z",
            }
        )
        assert job.job_type == "send_email"

    def test_maps_last_error_from_list_json(self) -> None:
        """GET /jobs and /jobs/dlq summaries send last_error."""
        job = JobSummary.model_validate(
            {
                "id": "job_1",
                "queue_name": "emails",
                "status": "deadletter",
                "priority": 0,
                "attempt": 3,
                "max_retries": 3,
                "job_type": "send_email",
                "last_error": "Connection refused",
                "created_at": "2024-01-01T00:00:00Z",
            }
        )
        assert job.last_error == "Connection refused"


class TestPurgeDlqParams:
    """POST /jobs/dlq/purge is {queue_name?, older_than?, limit?, confirm}."""

    def test_to_payload_sends_confirm_and_older_than(self) -> None:
        payload = PurgeDlqParams(queue_name="emails", older_than_days=7).to_payload()
        assert payload["confirm"] is True
        assert payload["queue_name"] == "emails"
        assert "older_than_days" not in payload
        assert "older_than" in payload

    def test_rejects_job_ids(self) -> None:
        with pytest.raises(PydanticValidationError):
            PurgeDlqParams.model_validate({"queue_name": "emails", "job_ids": ["j1"]})

    def test_confirm_false_raises(self) -> None:
        with pytest.raises(ValueError, match="confirm"):
            PurgeDlqParams(confirm=False).to_payload()


class TestLeaseFencingParams:
    """Tests for lease_id on complete/fail/heartbeat params."""

    def test_complete_params_include_lease_id(self) -> None:
        """Test CompleteJobParams serializes lease_id when set."""
        params = CompleteJobParams(
            worker_id="worker_1",
            result={"ok": True},
            lease_id="lease-abc",
        )
        data = params.model_dump(exclude_none=True, mode="json")
        assert data["lease_id"] == "lease-abc"

    def test_complete_params_omit_none_lease_id(self) -> None:
        """Test CompleteJobParams omits lease_id when None."""
        params = CompleteJobParams(worker_id="worker_1")
        data = params.model_dump(exclude_none=True, mode="json")
        assert "lease_id" not in data

    def test_fail_params_include_lease_id(self) -> None:
        """Test FailJobParams serializes lease_id when set."""
        params = FailJobParams(
            worker_id="worker_1",
            error="boom",
            lease_id="lease-abc",
        )
        data = params.model_dump(exclude_none=True)
        assert data["lease_id"] == "lease-abc"

    def test_fail_params_omit_none_lease_id(self) -> None:
        """Test FailJobParams omits lease_id when None."""
        params = FailJobParams(worker_id="worker_1", error="boom")
        data = params.model_dump(exclude_none=True)
        assert "lease_id" not in data

    def test_heartbeat_params_include_lease_id(self) -> None:
        """Test JobHeartbeatParams serializes lease_id when set."""
        params = JobHeartbeatParams(
            worker_id="worker_1",
            lease_duration_secs=60,
            lease_id="lease-abc",
        )
        data = params.model_dump(exclude_none=True)
        assert data["lease_id"] == "lease-abc"

    def test_heartbeat_params_omit_none_lease_id(self) -> None:
        """Test JobHeartbeatParams omits lease_id when None."""
        params = JobHeartbeatParams(worker_id="worker_1")
        data = params.model_dump(exclude_none=True)
        assert "lease_id" not in data


class TestBulkEnqueueParams:
    """Tests for BulkEnqueueParams."""

    def test_minimal(self) -> None:
        """Test minimal params."""
        params = BulkEnqueueParams(
            queue_name="test",
            jobs=[BulkJobItem(payload={"n": 1})],
        )
        assert params.queue_name == "test"
        assert len(params.jobs) == 1

    def test_max_jobs(self) -> None:
        """Test max jobs limit."""
        jobs = [BulkJobItem(payload={"n": i}) for i in range(100)]
        params = BulkEnqueueParams(queue_name="test", jobs=jobs)
        assert len(params.jobs) == 100

        # Too many
        jobs = [BulkJobItem(payload={"n": i}) for i in range(101)]
        with pytest.raises(PydanticValidationError):
            BulkEnqueueParams(queue_name="test", jobs=jobs)


class TestRegisterWorkerParams:
    """Tests for RegisterWorkerParams."""

    def test_defaults(self) -> None:
        """Test default values."""
        params = RegisterWorkerParams(
            queue_name="test",
            hostname="worker-1.local",
        )
        assert params.max_concurrency == 5

    def test_max_concurrency_bounds(self) -> None:
        """Test max_concurrency validation."""
        with pytest.raises(PydanticValidationError):
            RegisterWorkerParams(queue_name="q", hostname="h", max_concurrency=0)
        with pytest.raises(PydanticValidationError):
            RegisterWorkerParams(queue_name="q", hostname="h", max_concurrency=101)

    def test_worker_id_optional(self) -> None:
        """Test worker_id defaults to None and is omitted from the payload."""
        params = RegisterWorkerParams(queue_name="q", hostname="h")
        assert params.worker_id is None
        assert "worker_id" not in params.model_dump(exclude_none=True)

    def test_worker_id_accepted(self) -> None:
        """Test a stable worker_id survives to the payload."""
        params = RegisterWorkerParams(queue_name="q", hostname="h", worker_id="pod-7.worker_1-a")
        assert params.model_dump(exclude_none=True)["worker_id"] == "pod-7.worker_1-a"

    def test_worker_id_charset_and_length(self) -> None:
        """Test worker_id validation."""
        with pytest.raises(PydanticValidationError):
            RegisterWorkerParams(queue_name="q", hostname="h", worker_id="")
        with pytest.raises(PydanticValidationError):
            RegisterWorkerParams(queue_name="q", hostname="h", worker_id="not valid!")
        with pytest.raises(PydanticValidationError):
            RegisterWorkerParams(queue_name="q", hostname="h", worker_id="x" * 129)


class TestCreateScheduleParams:
    """Tests for CreateScheduleParams."""

    def test_minimal(self) -> None:
        """Test minimal params."""
        params = CreateScheduleParams(
            name="Daily Job",
            cron_expression="0 9 * * *",
            queue_name="tasks",
            payload_template={"action": "run"},
        )
        assert params.name == "Daily Job"
        assert params.timezone == "UTC"

    def test_full_params(self) -> None:
        """Test all params."""
        params = CreateScheduleParams(
            name="Daily Job",
            description="Runs every day",
            cron_expression="0 9 * * *",
            timezone="America/New_York",
            queue_name="tasks",
            payload_template={"action": "run"},
            priority=10,
            max_retries=5,
            timeout_seconds=600,
            tags={"env": "prod"},
            metadata={"owner": "team-a"},
        )
        assert params.timezone == "America/New_York"
        assert params.priority == 10

    def test_tags_accept_object_and_string_array(self) -> None:
        """GET /schedules/{id} tags is JSON: object with bool values, or a string array."""
        now = datetime.now(timezone.utc)
        base = {
            "id": "sched_1",
            "organization_id": "org_1",
            "name": "Daily Job",
            "cron_expression": "0 9 * * *",
            "timezone": "UTC",
            "queue_name": "tasks",
            "payload_template": {},
            "priority": 0,
            "max_retries": 3,
            "timeout_seconds": 300,
            "is_active": True,
            "run_count": 0,
            "created_at": now,
            "updated_at": now,
        }
        object_tags = Schedule.model_validate({**base, "tags": {"urgent": True}})
        assert object_tags.tags == {"urgent": True}
        array_tags = Schedule.model_validate({**base, "tags": ["urgent"]})
        assert array_tags.tags == ["urgent"]

    def test_payload_template_and_metadata_accept_any_json(self) -> None:
        """GET /schedules/{id} payload_template/metadata is serde_json::Value."""
        now = datetime.now(timezone.utc)
        base = {
            "id": "sched_1",
            "organization_id": "org_1",
            "name": "Daily Job",
            "cron_expression": "0 9 * * *",
            "timezone": "UTC",
            "queue_name": "tasks",
            "payload_template": {},
            "priority": 0,
            "max_retries": 3,
            "timeout_seconds": 300,
            "is_active": True,
            "run_count": 0,
            "created_at": now,
            "updated_at": now,
        }
        array_payload = Schedule.model_validate({**base, "payload_template": ["a"]})
        assert array_payload.payload_template == ["a"]
        meta = Schedule.model_validate({**base, "metadata": True})
        assert meta.metadata is True


class TestCreateWorkflowParams:
    """Tests for CreateWorkflowParams."""

    def test_simple_workflow(self) -> None:
        """Test simple workflow."""
        params = CreateWorkflowParams(
            name="Test Workflow",
            jobs=[
                WorkflowJobDefinition(
                    key="step1",
                    queue_name="tasks",
                    payload={"step": 1},
                ),
            ],
        )
        assert params.name == "Test Workflow"
        assert len(params.jobs) == 1

    def test_job_definition_payload_accepts_non_object_json(self) -> None:
        job = WorkflowJobDefinition(
            key="step1",
            queue_name="tasks",
            payload="plain-string",
        )
        assert job.payload == "plain-string"

    def test_workflow_with_dependencies(self) -> None:
        """Test workflow with job dependencies."""
        params = CreateWorkflowParams(
            name="Pipeline",
            jobs=[
                WorkflowJobDefinition(
                    key="extract",
                    queue_name="etl",
                    payload={"step": "extract"},
                ),
                WorkflowJobDefinition(
                    key="transform",
                    queue_name="etl",
                    payload={"step": "transform"},
                    depends_on=["extract"],
                ),
                WorkflowJobDefinition(
                    key="load",
                    queue_name="etl",
                    payload={"step": "load"},
                    depends_on=["transform"],
                    dependency_mode="all",
                ),
            ],
        )
        assert len(params.jobs) == 3
        assert params.jobs[1].depends_on == ["extract"]


class TestWorkflowJob:
    """GET /workflows/{id} jobs send result, error, and metadata."""

    def test_keeps_result_error_and_metadata(self) -> None:
        job = WorkflowJob.model_validate(
            {
                "id": "job_1",
                "queue": "etl",
                "status": "failed",
                "payload": "plain-string",
                "result": [1, 2, 3],
                "error": {"type": "JobError", "message": "boom"},
                "metadata": {"tag": "urgent"},
                "attempt": 1,
                "priority": 0,
            }
        )
        assert job.queue_name == "etl"
        assert job.payload == "plain-string"
        assert job.result == [1, 2, 3]
        assert job.error is not None
        assert job.error.message == "boom"
        assert job.metadata == {"tag": "urgent"}


class TestWorkflowResponse:
    """GET /workflows/{id} is a detail document; list is the summary shape."""

    def test_metadata_accepts_any_json(self) -> None:
        got = WorkflowResponse.model_validate(
            {
                "id": "wf_1",
                "name": "ETL",
                "status": "running",
                "created_at": "2024-01-01T00:00:00Z",
                "metadata": ["env", "prod"],
            }
        )
        assert got.metadata == ["env", "prod"]

    def test_maps_progress_counts_from_get_detail(self) -> None:
        got = WorkflowResponse.model_validate(
            {
                "id": "wf_1",
                "name": "ETL",
                "status": "running",
                "created_at": "2024-01-01T00:00:00Z",
                "jobs": [{"id": "job_1"}, {"id": "job_2"}],
                "progress": {
                    "total": 2,
                    "completed": 1,
                    "failed": 0,
                    "pending": 1,
                    "processing": 0,
                },
            }
        )
        assert got.total_jobs == 2
        assert got.completed_jobs == 1
        assert got.failed_jobs == 0
        assert got.progress_percent == 50.0

    def test_keeps_list_total_jobs(self) -> None:
        got = WorkflowResponse.model_validate(
            {
                "id": "wf_1",
                "name": "ETL",
                "status": "running",
                "total_jobs": 4,
                "completed_jobs": 3,
                "failed_jobs": 1,
                "progress_percent": 75.0,
                "created_at": "2024-01-01T00:00:00Z",
            }
        )
        assert got.total_jobs == 4
        assert got.completed_jobs == 3
        assert got.failed_jobs == 1
        assert got.progress_percent == 75.0


class TestCreateOutgoingWebhookParams:
    """Tests for CreateOutgoingWebhookParams."""

    def test_minimal(self) -> None:
        """Test minimal params."""
        params = CreateOutgoingWebhookParams(
            name="Notifications",
            url="https://example.com/webhook",
            events=["job.completed"],
        )
        assert params.enabled is True

    def test_multiple_events(self) -> None:
        """Test multiple events."""
        params = CreateOutgoingWebhookParams(
            name="Notifications",
            url="https://example.com/webhook",
            events=["job.completed", "job.failed", "job.created"],
        )
        assert len(params.events) == 3


class TestUpdateOutgoingWebhookParams:
    """Tests for UpdateOutgoingWebhookParams three-state secret handling."""

    def test_omitted_secret_is_not_sent(self) -> None:
        """Test an unmentioned secret stays out of the payload."""
        payload = UpdateOutgoingWebhookParams(name="Renamed").to_payload()
        assert payload == {"name": "Renamed"}
        assert "secret" not in payload

    def test_explicit_none_clears_secret(self) -> None:
        """Test an explicit None is serialised as null so the server clears it."""
        assert UpdateOutgoingWebhookParams(secret=None).to_payload() == {"secret": None}
        assert UpdateOutgoingWebhookParams.model_validate({"secret": None}).to_payload() == {
            "secret": None
        }

    def test_string_replaces_secret(self) -> None:
        """Test a string secret is sent as-is."""
        assert UpdateOutgoingWebhookParams(secret="whsec_new").to_payload() == {
            "secret": "whsec_new"
        }

    def test_false_enabled_survives(self) -> None:
        """Test falsy-but-set values are not dropped."""
        assert UpdateOutgoingWebhookParams(enabled=False).to_payload() == {"enabled": False}


class TestOutgoingWebhook:
    """Tests for the OutgoingWebhook response model."""

    def test_auto_disabled_last_status(self) -> None:
        """Test an auto-disabled webhook parses instead of raising."""
        webhook = OutgoingWebhook.model_validate(
            {
                "id": "wh_123",
                "organization_id": "org_123",
                "name": "Notifications",
                "url": "https://example.com/webhook",
                "events": ["job.completed"],
                "enabled": False,
                "failure_count": 20,
                "last_status": "auto_disabled",
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            }
        )
        assert webhook.enabled is False
        assert webhook.last_status == "auto_disabled"


class TestCreateOrganizationParams:
    """Tests for CreateOrganizationParams."""

    def test_slug_pattern(self) -> None:
        """Test slug pattern validation."""
        # Valid slugs
        CreateOrganizationParams(name="Test Org", slug="test-org")
        CreateOrganizationParams(name="Test", slug="test123")
        CreateOrganizationParams(name="Test", slug="my-org-123")

        # Invalid: uppercase
        with pytest.raises(PydanticValidationError):
            CreateOrganizationParams(name="Test", slug="Test-Org")

        # Invalid: special chars
        with pytest.raises(PydanticValidationError):
            CreateOrganizationParams(name="Test", slug="test_org")


class TestLoginParams:
    """Tests for LoginParams."""

    def test_api_key_min_length(self) -> None:
        """Test API key minimum length."""
        LoginParams(api_key="1234567890")

        with pytest.raises(PydanticValidationError):
            LoginParams(api_key="123456789")


class TestSerializationModes:
    """Tests for Pydantic serialization modes."""

    def test_model_dump_json_mode(self) -> None:
        """Test model_dump with mode='json' for datetime serialization."""
        now = datetime.now()
        params = CreateJobParams(
            queue_name="test",
            payload={"key": "value"},
            scheduled_at=now,
        )

        # Default dump
        data = params.model_dump(exclude_none=True)
        assert isinstance(data["scheduled_at"], datetime)

        # JSON mode - datetime to ISO string
        data_json = params.model_dump(exclude_none=True, mode="json")
        assert isinstance(data_json["scheduled_at"], str)

    def test_model_dump_exclude_none(self) -> None:
        """Test model_dump excludes None values."""
        params = CreateJobParams(
            queue_name="test",
            payload={},
        )
        data = params.model_dump(exclude_none=True)

        # None values should be excluded
        assert "scheduled_at" not in data
        assert "idempotency_key" not in data
        assert "tags" not in data

        # Present values included
        assert "queue_name" in data
        assert "payload" in data


class TestOutgoingWebhookDelivery:
    def test_payload_accepts_non_object_json(self) -> None:
        got = OutgoingWebhookDelivery.model_validate(
            {
                "id": "del_1",
                "webhook_id": "wh_1",
                "event": "job.completed",
                "payload": "hello",
                "status": "success",
                "attempts": 1,
                "created_at": "2024-01-01T00:00:00Z",
            }
        )
        assert got.payload == "hello"
