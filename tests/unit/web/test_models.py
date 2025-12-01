"""Tests for bimcalc.web.models - Shared Pydantic models."""

import pytest
from pydantic import ValidationError

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
    """Tests for BulkUpdateRequest model."""

    def test_valid_approve_request(self):
        """Test valid approve request."""
        request = BulkUpdateRequest(
            match_ids=[1, 2, 3],
            action="approve"
        )
        assert request.match_ids == [1, 2, 3]
        assert request.action == "approve"
        assert request.reason is None

    def test_valid_reject_request_with_reason(self):
        """Test valid reject request with reason."""
        request = BulkUpdateRequest(
            match_ids=[4, 5],
            action="reject",
            reason="Price variance too high"
        )
        assert request.match_ids == [4, 5]
        assert request.action == "reject"
        assert request.reason == "Price variance too high"

    def test_invalid_action(self):
        """Test invalid action raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            BulkUpdateRequest(
                match_ids=[1],
                action="invalid"  # Not in Literal["approve", "reject"]
            )
        assert "action" in str(exc_info.value)

    def test_empty_match_ids(self):
        """Test empty match_ids is allowed (validated by business logic)."""
        request = BulkUpdateRequest(match_ids=[], action="approve")
        assert request.match_ids == []


class TestBulkPriceImportModels:
    """Tests for price import models."""

    def test_valid_import_request(self):
        """Test valid price import request."""
        request = BulkPriceImportRequest(
            items=[{"code": "ABC123", "price": 10.50}],
            org_id=1,
            source="crail4"
        )
        assert len(request.items) == 1
        assert request.org_id == 1
        assert request.source == "crail4"

    def test_import_response_with_errors(self):
        """Test import response with error list."""
        response = BulkPriceImportResponse(
            imported_count=10,
            errors=["Item XYZ not found", "Invalid price format"],
            run_id=42
        )
        assert response.imported_count == 10
        assert len(response.errors) == 2
        assert response.run_id == 42


class TestComplianceModels:
    """Tests for compliance rule models."""

    def test_rule_create_minimal(self):
        """Test creating rule with minimal fields."""
        rule = RuleCreate(
            title="Test Rule",
            description="This is a test compliance rule"
        )
        assert rule.title == "Test Rule"
        assert rule.severity == "medium"  # Default
        assert rule.enabled is True  # Default

    def test_rule_create_full(self):
        """Test creating rule with all fields."""
        rule = RuleCreate(
            title="Critical Rule",
            description="Must comply",
            severity="critical",
            enabled=False,
            rule_type="safety"
        )
        assert rule.severity == "critical"
        assert rule.enabled is False
        assert rule.rule_type == "safety"

    def test_rule_update_partial(self):
        """Test partial rule update (all fields optional)."""
        update = RuleUpdate(severity="high")
        assert update.severity == "high"
        assert update.title is None
        assert update.enabled is None


class TestReportingModels:
    """Tests for reporting models."""

    def test_report_template_create(self):
        """Test report template creation."""
        template = ReportTemplateCreate(
            name="Monthly Cost Report",
            description="Monthly summary",
            template_type="excel",
            config={"columns": ["item", "price", "quantity"]}
        )
        assert template.name == "Monthly Cost Report"
        assert template.template_type == "excel"
        assert "columns" in template.config

    def test_send_email_request(self):
        """Test email send request."""
        email = SendEmailRequest(
            recipients=["user@example.com", "admin@example.com"],
            subject="Report Ready",
            body="Your report is attached.",
            attachment_path="/tmp/report.xlsx"
        )
        assert len(email.recipients) == 2
        assert email.subject == "Report Ready"
        assert email.attachment_path == "/tmp/report.xlsx"

    def test_send_email_requires_recipients(self):
        """Test email requires at least one recipient."""
        with pytest.raises(ValidationError) as exc_info:
            SendEmailRequest(
                recipients=[],  # Empty list
                subject="Test",
                body="Test"
            )
        # Pydantic validates min_length=1
        assert "recipients" in str(exc_info.value)


# Model import test
def test_all_models_importable():
    """Test that all models in __all__ are importable."""
    from bimcalc.web import models

    for model_name in models.__all__:
        assert hasattr(models, model_name), f"{model_name} not found in models module"
