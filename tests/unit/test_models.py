"""Unit tests for BIMCalc Pydantic models.

Tests data validation, field constraints, and model behavior.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from bimcalc.models import (
    CandidateMatch,
    Flag,
    FlagSeverity,
    Item,
    MappingEntry,
    MatchDecision,
    MatchResult,
    PriceItem,
    ReportRow,
)


class TestItem:
    """Test Item model validation."""

    def test_item_with_required_fields(self):
        """Test Item creation with minimum required fields."""
        item = Item(
            org_id="test-org",
            project_id="proj-1",
            family="Pipe Elbow",
            type_name="90° DN100",
        )

        assert item.org_id == "test-org"
        assert item.project_id == "proj-1"
        assert item.family == "Pipe Elbow"
        assert item.type_name == "90° DN100"
        assert isinstance(item.id, UUID)
        assert isinstance(item.created_at, datetime)

    def test_item_with_classification(self):
        """Test Item with classification fields."""
        item = Item(
            org_id="test-org",
            project_id="proj-1",
            family="Valve",
            type_name="Ball Valve",
            classification_code=2215,
            canonical_key="abc123def456",
        )

        assert item.classification_code == 2215
        assert item.canonical_key == "abc123def456"

    def test_item_with_explicit_overrides(self):
        """Test Item with explicit classification overrides."""
        item = Item(
            org_id="test-org",
            project_id="proj-1",
            family="Equipment",
            type_name="Boiler",
            omniclass_code=2301,
            uniformat_code=2350,
        )

        assert item.omniclass_code == 2301
        assert item.uniformat_code == 2350

    def test_item_with_physical_attributes(self):
        """Test Item with dimensions and material."""
        item = Item(
            org_id="test-org",
            project_id="proj-1",
            family="Duct",
            type_name="Rectangular",
            width_mm=400.0,
            height_mm=200.0,
            material="galvanized_steel",
            unit="m",
            quantity=Decimal("25.5"),
        )

        assert item.width_mm == 400.0
        assert item.height_mm == 200.0
        assert item.material == "galvanized_steel"
        assert item.unit == "m"
        assert item.quantity == Decimal("25.5")

    def test_item_with_angle(self):
        """Test Item with angle_deg for elbows/bends."""
        item = Item(
            org_id="test-org",
            project_id="proj-1",
            family="Elbow",
            type_name="90°",
            angle_deg=90.0,
        )

        assert item.angle_deg == 90.0

    def test_item_optional_fields_default_none(self):
        """Test optional fields default to None."""
        item = Item(
            org_id="test-org",
            project_id="proj-1",
            family="Test",
            type_name="Test",
        )

        assert item.classification_code is None
        assert item.canonical_key is None
        assert item.width_mm is None
        assert item.material is None


class TestPriceItem:
    """Test PriceItem model validation."""

    def test_price_item_with_required_fields(self):
        """Test PriceItem with minimum required fields."""
        price = PriceItem(
            classification_code=2215,
            sku="ELB-90-100",
            description="Pipe Elbow 90° DN100",
            unit="ea",
            unit_price=Decimal("45.50"),
        )

        assert price.classification_code == 2215
        assert price.sku == "ELB-90-100"
        assert price.description == "Pipe Elbow 90° DN100"
        assert price.unit == "ea"
        assert price.unit_price == Decimal("45.50")
        assert price.currency == "EUR"  # Default
        assert isinstance(price.id, UUID)

    def test_price_item_negative_price_rejected(self):
        """Test negative unit_price is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            PriceItem(
                classification_code=2215,
                sku="TEST",
                description="Test",
                unit="ea",
                unit_price=Decimal("-10.00"),
            )

        assert "unit_price must be non-negative" in str(exc_info.value)

    def test_price_item_with_physical_attributes(self):
        """Test PriceItem with dimensions and material."""
        price = PriceItem(
            classification_code=2302,
            sku="DUCT-400x200",
            description="Rectangular Duct",
            unit="m",
            unit_price=Decimal("25.00"),
            width_mm=400.0,
            height_mm=200.0,
            material="galvanized_steel",
        )

        assert price.width_mm == 400.0
        assert price.height_mm == 200.0
        assert price.material == "galvanized_steel"

    def test_price_item_with_vat(self):
        """Test PriceItem with VAT rate."""
        price = PriceItem(
            classification_code=2215,
            sku="TEST",
            description="Test",
            unit="ea",
            unit_price=Decimal("100.00"),
            vat_rate=Decimal("0.23"),
        )

        assert price.vat_rate == Decimal("0.23")

    def test_price_item_with_vendor_info(self):
        """Test PriceItem with vendor metadata."""
        price = PriceItem(
            classification_code=2215,
            sku="TEST",
            description="Test",
            unit="ea",
            unit_price=Decimal("50.00"),
            vendor_id="acme-supplies",
            vendor_note="12-week lead time",
            last_updated=datetime(2024, 1, 15),
        )

        assert price.vendor_id == "acme-supplies"
        assert price.vendor_note == "12-week lead time"
        assert price.last_updated == datetime(2024, 1, 15)


class TestFlag:
    """Test Flag model."""

    def test_flag_critical_veto(self):
        """Test Critical-Veto flag creation."""
        flag = Flag(
            type="UnitConflict",
            severity=FlagSeverity.CRITICAL_VETO,
            message="Item unit 'm' does not match price unit 'ea'",
        )

        assert flag.type == "UnitConflict"
        assert flag.severity == FlagSeverity.CRITICAL_VETO
        assert flag.severity.value == "Critical-Veto"
        assert "does not match" in flag.message

    def test_flag_advisory(self):
        """Test Advisory flag creation."""
        flag = Flag(
            type="StalePrice",
            severity=FlagSeverity.ADVISORY,
            message="Price is over 1 year old",
        )

        assert flag.type == "StalePrice"
        assert flag.severity == FlagSeverity.ADVISORY
        assert flag.severity.value == "Advisory"


class TestMatchResult:
    """Test MatchResult model validation."""

    def test_match_result_auto_accepted(self):
        """Test auto-accepted match result."""
        result = MatchResult(
            item_id=uuid4(),
            price_item_id=uuid4(),
            confidence_score=95.5,
            source="mapping_memory",
            decision=MatchDecision.AUTO_ACCEPTED,
            reason="High confidence, no flags, via canonical key",
            created_by="system",
        )

        assert result.confidence_score == 95.5
        assert result.source == "mapping_memory"
        assert result.decision == MatchDecision.AUTO_ACCEPTED
        assert len(result.flags) == 0

    def test_match_result_manual_review(self):
        """Test match requiring manual review."""
        flag = Flag(
            type="UnitConflict",
            severity=FlagSeverity.CRITICAL_VETO,
            message="Unit mismatch",
        )

        result = MatchResult(
            item_id=uuid4(),
            price_item_id=uuid4(),
            confidence_score=75.0,
            source="fuzzy_match",
            flags=[flag],
            decision=MatchDecision.MANUAL_REVIEW,
            reason="Critical-Veto flag present",
            created_by="system",
        )

        assert result.confidence_score == 75.0
        assert result.decision == MatchDecision.MANUAL_REVIEW
        assert len(result.flags) == 1
        assert result.flags[0].type == "UnitConflict"

    def test_match_result_confidence_validation(self):
        """Test confidence_score must be 0-100."""
        with pytest.raises(ValidationError) as exc_info:
            MatchResult(
                item_id=uuid4(),
                price_item_id=uuid4(),
                confidence_score=150.0,  # Invalid
                source="fuzzy_match",
                decision=MatchDecision.AUTO_ACCEPTED,
                reason="Test",
                created_by="system",
            )

        assert "confidence_score must be between 0 and 100" in str(exc_info.value)

    def test_match_result_no_price_item(self):
        """Test match result with no price match."""
        result = MatchResult(
            item_id=uuid4(),
            price_item_id=None,
            confidence_score=0.0,
            source="fuzzy_match",
            decision=MatchDecision.REJECTED,
            reason="No candidates above threshold",
            created_by="system",
        )

        assert result.price_item_id is None
        assert result.decision == MatchDecision.REJECTED


class TestMappingEntry:
    """Test MappingEntry (SCD Type-2) model."""

    def test_mapping_entry_active(self):
        """Test active mapping entry (end_ts is None)."""
        mapping = MappingEntry(
            org_id="test-org",
            canonical_key="abc123",
            price_item_id=uuid4(),
            created_by="engineer@example.com",
            reason="manual match",
        )

        assert mapping.org_id == "test-org"
        assert mapping.canonical_key == "abc123"
        assert mapping.end_ts is None
        assert mapping.is_active is True
        assert isinstance(mapping.start_ts, datetime)

    def test_mapping_entry_closed(self):
        """Test closed mapping entry (end_ts set)."""
        now = datetime.utcnow()
        mapping = MappingEntry(
            org_id="test-org",
            canonical_key="abc123",
            price_item_id=uuid4(),
            start_ts=datetime(2024, 1, 1),
            end_ts=now,
            created_by="system",
            reason="superseded",
        )

        assert mapping.end_ts == now
        assert mapping.is_active is False

    def test_mapping_entry_with_custom_start(self):
        """Test mapping with custom start timestamp."""
        start = datetime(2024, 6, 1, 12, 0, 0)
        mapping = MappingEntry(
            org_id="test-org",
            canonical_key="xyz789",
            price_item_id=uuid4(),
            start_ts=start,
            created_by="user@example.com",
            reason="initial match",
        )

        assert mapping.start_ts == start


class TestCandidateMatch:
    """Test CandidateMatch model."""

    def test_candidate_match_with_high_score(self):
        """Test candidate with high similarity score."""
        price = PriceItem(
            classification_code=2215,
            sku="TEST",
            description="Test Item",
            unit="ea",
            unit_price=Decimal("50.00"),
        )

        candidate = CandidateMatch(
            price_item=price,
            score=87.5,
        )

        assert candidate.score == 87.5
        assert candidate.price_item.sku == "TEST"
        assert len(candidate.flags) == 0

    def test_candidate_match_with_flags(self):
        """Test candidate with risk flags."""
        price = PriceItem(
            classification_code=2215,
            sku="TEST",
            description="Test",
            unit="ea",
            unit_price=Decimal("50.00"),
        )

        flag = Flag(
            type="SizeMismatch",
            severity=FlagSeverity.CRITICAL_VETO,
            message="Dimensions differ by >10mm",
        )

        candidate = CandidateMatch(
            price_item=price,
            score=75.0,
            flags=[flag],
        )

        assert len(candidate.flags) == 1
        assert candidate.flags[0].type == "SizeMismatch"


class TestReportRow:
    """Test ReportRow model."""

    def test_report_row_with_match(self):
        """Test report row with matched price."""
        row = ReportRow(
            item_id=uuid4(),
            family="Pipe Elbow",
            type_name="90° DN100",
            quantity=Decimal("10"),
            unit="ea",
            canonical_key="abc123",
            sku="ELB-90-100",
            description="Pipe Elbow 90° DN100 Steel",
            unit_price=Decimal("45.50"),
            currency="EUR",
            vat_rate=Decimal("0.23"),
            total_price=Decimal("455.00"),
            total_price_with_vat=Decimal("559.65"),
            matched_by="engineer@example.com",
            match_reason="manual match",
        )

        assert row.family == "Pipe Elbow"
        assert row.quantity == Decimal("10")
        assert row.unit_price == Decimal("45.50")
        assert row.total_price == Decimal("455.00")
        assert row.total_price_with_vat == Decimal("559.65")

    def test_report_row_without_match(self):
        """Test report row for unmatched item."""
        row = ReportRow(
            item_id=uuid4(),
            family="Unknown Item",
            type_name="Unknown",
            quantity=Decimal("5"),
            unit="ea",
            canonical_key=None,
            sku=None,
            description=None,
            unit_price=None,
            matched_by=None,
            match_reason=None,
        )

        assert row.sku is None
        assert row.unit_price is None
        assert row.total_price is None


class TestEnums:
    """Test enum values."""

    def test_flag_severity_enum(self):
        """Test FlagSeverity enum values."""
        assert FlagSeverity.CRITICAL_VETO.value == "Critical-Veto"
        assert FlagSeverity.ADVISORY.value == "Advisory"

    def test_match_decision_enum(self):
        """Test MatchDecision enum values."""
        assert MatchDecision.AUTO_ACCEPTED.value == "auto-accepted"
        assert MatchDecision.MANUAL_REVIEW.value == "manual-review"
        assert MatchDecision.REJECTED.value == "rejected"
