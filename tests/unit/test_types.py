"""Unit tests for Pydantic types/models."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError as PydanticValidationError

from spooled.types.auth import (
    LoginParams,
)
from spooled.types.jobs import (
    BulkEnqueueParams,
    BulkJobItem,
    ClaimJobsParams,
    CreateJobParams,
    Job,
)
from spooled.types.organizations import (
    CreateOrganizationParams,
)
from spooled.types.schedules import (
    CreateScheduleParams,
)
from spooled.types.webhooks import (
    CreateOutgoingWebhookParams,
)
from spooled.types.workers import (
    RegisterWorkerParams,
)
from spooled.types.workflows import (
    CreateWorkflowParams,
    WorkflowJobDefinition,
)


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
        for status in ["pending", "scheduled", "processing", "completed", "failed", "deadletter", "cancelled"]:
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
