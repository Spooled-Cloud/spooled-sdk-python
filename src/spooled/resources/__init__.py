"""
Resource modules for Spooled SDK.
"""

from spooled.resources.admin import AdminResource, AsyncAdminResource
from spooled.resources.api_keys import ApiKeysResource, AsyncApiKeysResource
from spooled.resources.auth import AsyncAuthResource, AuthResource
from spooled.resources.billing import AsyncBillingResource, BillingResource
from spooled.resources.dashboard import AsyncDashboardResource, DashboardResource
from spooled.resources.health import AsyncHealthResource, HealthResource
from spooled.resources.ingest import AsyncIngestResource, IngestResource
from spooled.resources.jobs import AsyncJobsResource, JobsResource
from spooled.resources.metrics import AsyncMetricsResource, MetricsResource
from spooled.resources.organizations import AsyncOrganizationsResource, OrganizationsResource
from spooled.resources.queues import AsyncQueuesResource, QueuesResource
from spooled.resources.schedules import AsyncSchedulesResource, SchedulesResource
from spooled.resources.webhooks import AsyncWebhooksResource, WebhooksResource
from spooled.resources.workers import AsyncWorkersResource, WorkersResource
from spooled.resources.workflows import AsyncWorkflowsResource, WorkflowsResource

__all__ = [
    # Sync resources
    "JobsResource",
    "QueuesResource",
    "WorkersResource",
    "SchedulesResource",
    "WorkflowsResource",
    "WebhooksResource",
    "ApiKeysResource",
    "OrganizationsResource",
    "BillingResource",
    "AuthResource",
    "AdminResource",
    "HealthResource",
    "DashboardResource",
    "MetricsResource",
    "IngestResource",
    # Async resources
    "AsyncJobsResource",
    "AsyncQueuesResource",
    "AsyncWorkersResource",
    "AsyncSchedulesResource",
    "AsyncWorkflowsResource",
    "AsyncWebhooksResource",
    "AsyncApiKeysResource",
    "AsyncOrganizationsResource",
    "AsyncBillingResource",
    "AsyncAuthResource",
    "AsyncAdminResource",
    "AsyncHealthResource",
    "AsyncDashboardResource",
    "AsyncMetricsResource",
    "AsyncIngestResource",
]
