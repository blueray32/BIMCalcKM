"""Tests for bimcalc.web.models - Shared Pydantic models.

Tests updated for actual model definitions extracted from app_enhanced.py.
"""

import pytest
from pydantic import ValidationError
from uuid import UUID, uuid4

from bimcalc.web.models import (
    BulkUpdateRequest,
    BulkPriceImportRequest,
    BulkPriceImportResponse,
    RuleUpdate,
    RuleCreate,
    ConvertItemsRequest,
    ReportTemplateCreate,
    SendEmailRequest,
)


class TestBulkUpdateRequest:
    """Tests for BulkUpdateRequest model (app_enhanced.py:826)."""

    def test_valid_approve_request(self):
        """Test valid approve request."""
        match_id = uuid4()
        request = BulkUpdateRequest(
            match_result_ids=[match_id],
            action="approve",
            org_id="org-123",
            project_id="proj-456"
        )
        assert request.match_result_ids == [match_id]
        assert request.action == "approve"
        assert request.annotation is None
        assert request.org_id == "org-123"
        assert request.project_id == "proj-456"

    def test_valid_reject_request_with_annotation(self):
        """Test valid reject request with annotation."""
        request = BulkUpdateRequest(
            match_result_ids=[uuid4(), uuid4()],
            action="reject",
            annotation="Price variance too high",
            org_id="org-123",
            project_id="proj-456"
        )
        assert len(request.match_result_ids) == 2
        assert request.action == "reject"
        assert request.annotation == "Price variance too high"

    def test_invalid_action(self):
        """Test invalid action raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            BulkUpdateRequest(
                match_result_ids=[uuid4()],
                action="invalid",  # Not in Literal["approve", "reject"]
                org_id="org-123",
                project_id="proj-456"
            )
        assert "action" in str(exc_info.value)

    def test_requires_org_and_project(self):
        """Test that org_id and project_id are required."""
        with pytest.raises(ValidationError):
            BulkUpdateRequest(
                match_result_ids=[uuid4()],
                action="approve"
                # Missing org_id and project_id
            )


class TestBulkPriceImportModels:
    """Tests for price import models (app_enhanced.py:2464, 2474)."""

    def test_valid_import_request(self):
        """Test valid price import request."""
        request = BulkPriceImportRequest(
            org_id="org-123",
            items=[
                {"code": "ABC123", "price": 10.50},
                {"code": "XYZ789", "price": 25.00}
            ]
        )
        assert len(request.items) == 2
        assert request.org_id == "org-123"
        assert request.source == "crail4_api"  # Default
        assert request.target_scheme == "UniClass2015"  # Default
        assert request.created_by == "system"  # Default

    def test_import_request_custom_source(self):
        """Test import request with custom source."""
        request = BulkPriceImportRequest(
            org_id="org-123",
            items=[{"code": "ABC"}],
            source="manual_upload",
            target_scheme="UniClass2",
            created_by="admin@example.com"
        )
        assert request.source == "manual_upload"
        assert request.target_scheme == "UniClass2"
        assert request.created_by == "admin@example.com"

    def test_import_response_with_errors(self):
        """Test import response with error list."""
        response = BulkPriceImportResponse(
            run_id="run-12345",
            status="partial_success",
            items_received=100,
            items_loaded=85,
            items_rejected=15,
            rejection_reasons={"missing_price": 10, "invalid_code": 5},
            errors=["Item XYZ not found", "Invalid price format"]
        )
        assert response.run_id == "run-12345"
        assert response.items_loaded == 85
        assert response.items_rejected == 15
        assert len(response.errors) == 2
        assert response.rejection_reasons["missing_price"] == 10


class TestComplianceModels:
    """Tests for compliance rule models (app_enhanced.py:4901, 4908)."""

    def test_rule_create_minimal(self):
        """Test creating rule with minimal fields."""
        rule = RuleCreate(
            name="Test Rule",
            description="This is a test compliance rule",
            rule_type="safety",
            severity="high"
        )
        assert rule.name == "Test Rule"
        assert rule.rule_type == "safety"
        assert rule.severity == "high"
        assert rule.is_active is True  # Default
        assert rule.configuration == {}  # Default

    def test_rule_create_full(self):
        """Test creating rule with all fields."""
        rule = RuleCreate(
            name="Critical Rule",
            description="Must comply",
            rule_type="safety",
            severity="critical",
            is_active=False,
            configuration={"threshold": 100, "auto_flag": True}
        )
        assert rule.severity == "critical"
        assert rule.is_active is False
        assert rule.configuration["threshold"] == 100

    def test_rule_update_partial(self):
        """Test partial rule update (all fields optional)."""
        update = RuleUpdate(severity="high", is_active=False)
        assert update.severity == "high"
        assert update.is_active is False
        assert update.name is None
        assert update.description is None

    def test_rule_update_configuration(self):
        """Test updating rule configuration."""
        update = RuleUpdate(
            configuration={"enabled": True, "threshold": 50}
        )
        assert update.configuration["enabled"] is True
        assert update.configuration["threshold"] == 50


class TestDocumentModels:
    """Tests for document management models (app_enhanced.py:5087)."""

    def test_convert_items_specific_ids(self):
        """Test converting specific item IDs."""
        item1, item2 = uuid4(), uuid4()
        request = ConvertItemsRequest(item_ids=[item1, item2])
        assert len(request.item_ids) == 2
        assert item1 in request.item_ids

    def test_convert_items_all(self):
        """Test converting all items using literal 'all'."""
        request = ConvertItemsRequest(item_ids="all")
        assert request.item_ids == "all"

    def test_convert_items_invalid_literal(self):
        """Test that invalid literals are rejected."""
        with pytest.raises(ValidationError):
            ConvertItemsRequest(item_ids="some")  # Not "all"


class TestReportingModels:
    """Tests for reporting models (app_enhanced.py:5251, 5288)."""

    def test_report_template_create(self):
        """Test report template creation."""
        template = ReportTemplateCreate(
            name="Monthly Cost Report",
            org_id="org-123",
            configuration={"columns": ["item", "price", "quantity"]}
        )
        assert template.name == "Monthly Cost Report"
        assert template.org_id == "org-123"
        assert template.project_id is None  # Default
        assert "columns" in template.configuration

    def test_report_template_with_project(self):
        """Test report template scoped to project."""
        template = ReportTemplateCreate(
            name="Project Report",
            org_id="org-123",
            project_id="proj-456",
            configuration={"format": "excel"}
        )
        assert template.project_id == "proj-456"

    def test_send_email_request(self):
        """Test email send request."""
        email = SendEmailRequest(
            recipient_emails=["user@example.com", "admin@example.com"]
        )
        assert len(email.recipient_emails) == 2
        assert email.report_type == "weekly"  # Default

    def test_send_email_custom_report_type(self):
        """Test email with custom report type."""
        email = SendEmailRequest(
            recipient_emails=["user@example.com"],
            report_type="monthly"
        )
        assert email.report_type == "monthly"

    def test_send_email_empty_recipients(self):
        """Test that empty recipient list is allowed (validated by business logic)."""
        # Pydantic doesn't enforce min_length on list by default
        email = SendEmailRequest(recipient_emails=[])
        assert email.recipient_emails == []


# Model import test
def test_all_models_importable():
    """Test that all models in __all__ are importable."""
    from bimcalc.web import models

    for model_name in models.__all__:
        assert hasattr(models, model_name), f"{model_name} not found in models module"


def test_all_models_are_basemodel_subclasses():
    """Test that all exported models are BaseModel subclasses."""
    from bimcalc.web import models
    from pydantic import BaseModel

    for model_name in models.__all__:
        model_class = getattr(models, model_name)
        assert issubclass(model_class, BaseModel), f"{model_name} is not a BaseModel subclass"
