"""Shared Pydantic models for BIMCalc web API.

This module contains all request/response models used across the web UI.
Models are extracted from app_enhanced.py for better organization and reusability.

Usage:
    from bimcalc.web.models import BulkUpdateRequest

    @router.post("/matches/bulk-update")
    async def bulk_update(request: BulkUpdateRequest):
        ...
"""

from __future__ import annotations

from pydantic import BaseModel
from typing import List, Literal, Optional, Dict
from uuid import UUID


# ============================================================================
# Matching & Review Models
# ============================================================================


class BulkUpdateRequest(BaseModel):
    """Request for bulk match updates (approve/reject).

    Extracted from app_enhanced.py:826
    Used by: POST /api/matches/bulk-update
    """

    match_result_ids: List[UUID]
    action: Literal["approve", "reject"]
    annotation: Optional[str] = None
    org_id: str
    project_id: str


# ============================================================================
# Price Import Models
# ============================================================================


class BulkPriceImportRequest(BaseModel):
    """Request schema for Crail4 -> BIMCalc bulk imports.

    Extracted from app_enhanced.py:2464
    Used by: POST /api/price-items/bulk-import
    """

    org_id: str
    items: list[dict]
    source: str = "crail4_api"
    target_scheme: str = "UniClass2015"
    created_by: str = "system"


class BulkPriceImportResponse(BaseModel):
    """Response schema for bulk price imports.

    Extracted from app_enhanced.py:2474
    Used by: POST /api/price-items/bulk-import
    """

    run_id: str
    status: str
    items_received: int
    items_loaded: int
    items_rejected: int
    rejection_reasons: dict
    errors: list[str]


# ============================================================================
# Compliance & Intelligence Models
# ============================================================================


class RuleUpdate(BaseModel):
    """Update an existing compliance rule.

    Extracted from app_enhanced.py:4901
    Used by: PUT /api/projects/{project_uuid}/intelligence/rules/{rule_id}
    """

    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    configuration: Optional[Dict] = None
    severity: Optional[str] = None


class RuleCreate(BaseModel):
    """Create a new compliance rule.

    Extracted from app_enhanced.py:4908
    Used by: POST /api/projects/{project_uuid}/intelligence/rules
    """

    name: str
    description: str
    rule_type: str
    severity: str
    is_active: bool = True
    configuration: Dict = {}


# ============================================================================
# Document Management Models
# ============================================================================


class ConvertItemsRequest(BaseModel):
    """Request to convert extracted items to project estimate items.

    Extracted from app_enhanced.py:5087
    Used by: POST /api/projects/{project_uuid}/documents/{document_id}/convert
    """

    item_ids: List[UUID] | Literal["all"]


# ============================================================================
# Reporting Models
# ============================================================================


class ReportTemplateCreate(BaseModel):
    """Create a custom report template.

    Extracted from app_enhanced.py:5251
    Used by: POST /api/reports/templates
    """

    name: str
    org_id: str
    project_id: str | None = None
    configuration: dict


class SendEmailRequest(BaseModel):
    """Request to send a project report via email.

    Extracted from app_enhanced.py:5288
    Used by: POST /api/projects/{project_uuid}/email/send-report
    """

    recipient_emails: list[str]
    report_type: str = "weekly"


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    # Matching & Review
    "BulkUpdateRequest",
    # Price Import
    "BulkPriceImportRequest",
    "BulkPriceImportResponse",
    # Compliance & Intelligence
    "RuleUpdate",
    "RuleCreate",
    # Document Management
    "ConvertItemsRequest",
    # Reporting
    "ReportTemplateCreate",
    "SendEmailRequest",
]


# Future models to extract (as routers are created):
# - ProjectCreate, ProjectUpdate (from projects routes)
# - AnalyticsRequest (from analytics routes)
# - ComplianceCheckRequest (from compliance routes)
# - ClassificationMappingRequest (from classifications routes)
# - Crail4ConfigRequest (from crail4 routes)
# - ScenarioCompareRequest (from scenarios routes)
# - Additional models discovered during router extraction
