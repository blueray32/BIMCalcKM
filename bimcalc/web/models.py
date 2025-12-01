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

from pydantic import BaseModel, Field
from typing import List, Literal, Optional, Dict, Any


# ============================================================================
# Matching & Review Models
# ============================================================================

class BulkUpdateRequest(BaseModel):
    """Request for bulk match updates (approve/reject)."""

    match_ids: List[int] = Field(..., description="List of match IDs to update")
    action: Literal["approve", "reject"] = Field(..., description="Action to perform")
    reason: Optional[str] = Field(None, description="Reason for rejection (optional)")


# ============================================================================
# Price Import Models
# ============================================================================

class BulkPriceImportRequest(BaseModel):
    """Request for bulk price import."""

    items: List[Dict[str, Any]] = Field(..., description="List of price items to import")
    org_id: int = Field(..., description="Organization ID")
    source: Optional[str] = Field(None, description="Price source identifier")


class BulkPriceImportResponse(BaseModel):
    """Response for bulk price import operation."""

    imported_count: int = Field(..., description="Number of items successfully imported")
    errors: List[str] = Field(default_factory=list, description="List of error messages")
    run_id: Optional[int] = Field(None, description="Import run ID if created")


# ============================================================================
# Compliance & Intelligence Models
# ============================================================================

class RuleUpdate(BaseModel):
    """Update an existing compliance rule."""

    title: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[Literal["critical", "high", "medium", "low"]] = None
    enabled: Optional[bool] = None


class RuleCreate(BaseModel):
    """Create a new compliance rule."""

    title: str = Field(..., min_length=1, max_length=255)
    description: str
    severity: Literal["critical", "high", "medium", "low"] = "medium"
    enabled: bool = True
    rule_type: Optional[str] = None


# ============================================================================
# Item Management Models
# ============================================================================

class ConvertItemsRequest(BaseModel):
    """Request to convert items between schedules and pricebooks."""

    item_ids: List[int] = Field(..., description="Items to convert")
    target_type: Literal["schedule", "pricebook"] = Field(..., description="Target item type")
    org_id: Optional[int] = Field(None, description="Organization ID")


# ============================================================================
# Reporting Models
# ============================================================================

class ReportTemplateCreate(BaseModel):
    """Create a custom report template."""

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    template_type: Literal["excel", "pdf", "csv"] = "excel"
    config: Dict[str, Any] = Field(default_factory=dict, description="Template configuration")


class SendEmailRequest(BaseModel):
    """Request to send an email report."""

    recipients: List[str] = Field(..., min_length=1, description="Email recipients")
    subject: str = Field(..., min_length=1)
    body: str
    attachment_path: Optional[str] = Field(None, description="Path to attachment file")


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    # Matching & Review
    "BulkUpdateRequest",
    # Price Import
    "BulkPriceImportRequest",
    "BulkPriceImportResponse",
    # Compliance
    "RuleUpdate",
    "RuleCreate",
    # Item Management
    "ConvertItemsRequest",
    # Reporting
    "ReportTemplateCreate",
    "SendEmailRequest",
]
