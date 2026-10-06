"""CRM provider port and adapters (CLAUDE.md §30)."""

from colt_integrations.crm.fake import FakeCRMProvider
from colt_integrations.crm.port import CRMProvider, CrmSyncResult

__all__ = ["CRMProvider", "CrmSyncResult", "FakeCRMProvider"]
