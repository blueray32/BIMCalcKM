"""Unit tests for enhanced confidence calculator."""

from datetime import datetime
from uuid import uuid4

import pytest

from bimcalc.matching.confidence import (
    ConfidenceCalculator,
    ConfidenceResult,
    MatchMethod,
)
from bimcalc.matching.models import Item, MappingMemory, MappingRecord, PriceItem


@pytest.fixture
def calculator() -> ConfidenceCalculator:
    """Create confidence calculator with default settings."""
    return ConfidenceCalculator(
        size_tolerance_mm=10.0,
        angle_tolerance_deg=5.0,
        fuzzy_min_score=70,
    )


@pytest.fixture
def mapping_memory() -> MappingMemory:
    """Create empty mapping memory."""
    return MappingMemory()


class TestExactMatching:
    """Test exact matching strategies (100 confidence)."""

    def test_exact_mpn_match(self, calculator: ConfidenceCalculator) -> None:
        """Test manufacturer part number exact match returns 100."""
        item = Item(
            id=uuid4(),
            org_id="test-org",
            project_id="proj-1",
            family="Pipe Elbow",
            type_name="90° DN100",
            manufacturer_part_number="ELB-90-100-SS",
        )
        price = PriceItem(
            id=uuid4(),
            classification_code=2215,
            sku="SKU-12345",
            manufacturer_part_number="ELB-90-100-SS",
            description="Elbow 90° DN100 Stainless Steel",
        )

        result = calculator.calculate(item, price)

        assert result.score == 100
        assert result.method == MatchMethod.EXACT_MPN
        assert result.details["mpn"] == "ELB-90-100-SS"

    def test_exact_sku_match(self, calculator: ConfidenceCalculator) -> None:
        """Test SKU exact match returns 100."""
        item = Item(
            id=uuid4(),
            org_id="test-org",
            project_id="proj-1",
            family="Valve",
            type_name="Ball Valve DN50",
            vendor_sku="VALVE-BALL-50",
        )
        price = PriceItem(
            id=uuid4(),
            classification_code=2215,
            sku="VALVE-BALL-50",
            description="Ball Valve DN50",
        )

        result = calculator.calculate(item, price)

        assert result.score == 100
        assert result.method == MatchMethod.EXACT_SKU
        assert result.details["sku"] == "VALVE-BALL-50"

    def test_canonical_key_match(
        self, calculator: ConfidenceCalculator, mapping_memory: MappingMemory
    ) -> None:
        """Test canonical key memory match returns 100."""
        item_id = uuid4()
        price_id = uuid4()

        item = Item(
            id=item_id,
            org_id="test-org",
            project_id="proj-1",
            canonical_key="canonical-key-123",
            family="Duct Elbow",
            type_name="90° 400x200",
        )
        price = PriceItem(
            id=price_id,
            classification_code=2302,
            sku="DUCT-ELB-400x200",
            description="Duct Elbow 90° 400x200",
        )

        # Add mapping to memory
        mapping = MappingRecord(
            id=uuid4(),
            org_id="test-org",
            canonical_key="canonical-key-123",
            price_item_id=price_id,
            start_ts=datetime.now(),
            created_by="test-user",
            reason="manual approval",
        )
        mapping_memory.add(mapping)

        result = calculator.calculate(item, price, mapping_memory)

        assert result.score == 100
        assert result.method == MatchMethod.CANONICAL_KEY
        assert result.details["canonical_key"] == "canonical-key-123"

    def test_mpn_takes_priority_over_sku(
        self, calculator: ConfidenceCalculator
    ) -> None:
        """Test MPN match has priority over SKU match."""
        item = Item(
            id=uuid4(),
            org_id="test-org",
            project_id="proj-1",
            manufacturer_part_number="MPN-123",
            vendor_sku="SKU-456",
        )
        price = PriceItem(
            id=uuid4(),
            classification_code=2215,
            manufacturer_part_number="MPN-123",
            sku="SKU-456",
        )

        result = calculator.calculate(item, price)

        assert result.score == 100
        assert result.method == MatchMethod.EXACT_MPN  # MPN wins


class TestEnhancedFuzzyMatching:
    """Test enhanced fuzzy matching with weighted scoring."""

    def test_perfect_match_all_fields(self, calculator: ConfidenceCalculator) -> None:
        """Test perfect match on all fields yields high score."""
        item = Item(
            id=uuid4(),
            org_id="test-org",
            project_id="proj-1",
            family="Pipe Elbow",
            type_name="90° DN100 Stainless Steel",
            material="stainless_steel",
            unit="ea",
            dn_mm=100.0,
            angle_deg=90.0,
        )
        price = PriceItem(
            id=uuid4(),
            classification_code=2215,
            family="Pipe Elbow",
            type_name="90° DN100 Stainless Steel",
            material="stainless_steel",
            unit="ea",
            dn_mm=100.0,
            angle_deg=90.0,
        )

        result = calculator.calculate(item, price)

        assert result.method == MatchMethod.ENHANCED_FUZZY
        assert result.score >= 90  # Should be very high (90+ is excellent)
        assert "field_scores" in result.details
        # Should get material+unit bonus
        assert result.details["bonuses"] >= 5.0

    def test_material_mismatch_lowers_score(
        self, calculator: ConfidenceCalculator
    ) -> None:
        """Test material mismatch reduces confidence score."""
        item = Item(
            id=uuid4(),
            org_id="test-org",
            project_id="proj-1",
            family="Pipe Elbow",
            type_name="90° DN100",
            material="stainless_steel",
            unit="ea",
        )
        price = PriceItem(
            id=uuid4(),
            classification_code=2215,
            family="Pipe Elbow",
            type_name="90° DN100",
            material="carbon_steel",  # Different material
            unit="ea",
        )

        result = calculator.calculate(item, price)

        assert result.method == MatchMethod.ENHANCED_FUZZY
        # Material weight is 15%, so mismatch reduces score
        assert result.details["field_scores"]["material"] == 0.0

    def test_unit_mismatch_lowers_score(self, calculator: ConfidenceCalculator) -> None:
        """Test unit mismatch reduces confidence score."""
        item = Item(
            id=uuid4(),
            org_id="test-org",
            project_id="proj-1",
            family="Cable Tray",
            type_name="Ladder Type 200x50",
            unit="m",
        )
        price = PriceItem(
            id=uuid4(),
            classification_code=2601,
            family="Cable Tray",
            type_name="Ladder Type 200x50",
            unit="ea",  # Different unit
        )

        result = calculator.calculate(item, price)

        assert result.method == MatchMethod.ENHANCED_FUZZY
        assert result.details["field_scores"]["unit"] == 0.0

    def test_size_within_tolerance_scores_high(
        self, calculator: ConfidenceCalculator
    ) -> None:
        """Test dimensions within tolerance score well."""
        item = Item(
            id=uuid4(),
            org_id="test-org",
            project_id="proj-1",
            family="Duct",
            width_mm=400.0,
            height_mm=200.0,
        )
        price = PriceItem(
            id=uuid4(),
            classification_code=2302,
            family="Duct",
            width_mm=405.0,  # 5mm difference (within 10mm tolerance)
            height_mm=198.0,  # 2mm difference (within 10mm tolerance)
        )

        result = calculator.calculate(item, price)

        assert result.method == MatchMethod.ENHANCED_FUZZY
        # Size should score high (within tolerance)
        assert result.details["field_scores"]["size"] > 50.0

    def test_size_outside_tolerance_scores_zero(
        self, calculator: ConfidenceCalculator
    ) -> None:
        """Test dimensions outside tolerance score zero."""
        item = Item(
            id=uuid4(),
            org_id="test-org",
            project_id="proj-1",
            family="Duct",
            width_mm=400.0,
            height_mm=200.0,
        )
        price = PriceItem(
            id=uuid4(),
            classification_code=2302,
            family="Duct",
            width_mm=450.0,  # 50mm difference (outside 10mm tolerance)
            height_mm=250.0,  # 50mm difference (outside 10mm tolerance)
        )

        result = calculator.calculate(item, price)

        assert result.method == MatchMethod.ENHANCED_FUZZY
        # Size should score zero (outside tolerance)
        assert result.details["field_scores"]["size"] == 0.0

    def test_exact_dimension_bonus(self, calculator: ConfidenceCalculator) -> None:
        """Test bonus for exact dimension match (1mm tolerance)."""
        item = Item(
            id=uuid4(),
            org_id="test-org",
            project_id="proj-1",
            family="Duct",
            type_name="Rectangular 400x200",
            material="galvanized_steel",
            unit="m",
            width_mm=400.0,
            height_mm=200.0,
        )
        price = PriceItem(
            id=uuid4(),
            classification_code=2302,
            family="Duct",
            type_name="Rectangular 400x200",
            material="galvanized_steel",
            unit="m",
            width_mm=400.0,  # Exact match
            height_mm=200.0,  # Exact match
        )

        result = calculator.calculate(item, price)

        # Should get exact dimension bonus (+5)
        assert result.details["bonuses"] >= 5.0

    def test_material_and_unit_bonus(self, calculator: ConfidenceCalculator) -> None:
        """Test bonus for material and unit both matching."""
        item = Item(
            id=uuid4(),
            org_id="test-org",
            project_id="proj-1",
            family="Pipe",
            material="copper",
            unit="m",
        )
        price = PriceItem(
            id=uuid4(),
            classification_code=2211,
            family="Pipe",
            material="copper",
            unit="m",
        )

        result = calculator.calculate(item, price)

        # Should get material+unit bonus (+5)
        assert result.details["bonuses"] >= 5.0

    def test_angle_within_tolerance(self, calculator: ConfidenceCalculator) -> None:
        """Test angle matching within tolerance."""
        item = Item(
            id=uuid4(),
            org_id="test-org",
            project_id="proj-1",
            family="Elbow",
            angle_deg=90.0,
        )
        price = PriceItem(
            id=uuid4(),
            classification_code=2215,
            family="Elbow",
            angle_deg=92.0,  # 2° difference (within 5° tolerance)
        )

        result = calculator.calculate(item, price)

        # Angle should match
        assert result.details["field_scores"]["angle"] == 100.0

    def test_angle_outside_tolerance(self, calculator: ConfidenceCalculator) -> None:
        """Test angle mismatch outside tolerance."""
        item = Item(
            id=uuid4(),
            org_id="test-org",
            project_id="proj-1",
            family="Elbow",
            angle_deg=90.0,
        )
        price = PriceItem(
            id=uuid4(),
            classification_code=2215,
            family="Elbow",
            angle_deg=45.0,  # 45° difference (outside 5° tolerance)
        )

        result = calculator.calculate(item, price)

        # Angle should not match
        assert result.details["field_scores"]["angle"] == 0.0


class TestScoreClamping:
    """Test score clamping and edge cases."""

    def test_score_clamped_to_100(self, calculator: ConfidenceCalculator) -> None:
        """Test score never exceeds 100."""
        item = Item(
            id=uuid4(),
            org_id="test-org",
            project_id="proj-1",
            family="Perfect Match",
            type_name="Perfect Type",
            material="stainless_steel",
            unit="ea",
        )
        price = PriceItem(
            id=uuid4(),
            classification_code=2215,
            family="Perfect Match",
            type_name="Perfect Type",
            material="stainless_steel",
            unit="ea",
        )

        result = calculator.calculate(item, price)

        # Even with bonuses, score should not exceed 100
        assert result.score <= 100

    def test_missing_fields_handled_gracefully(
        self, calculator: ConfidenceCalculator
    ) -> None:
        """Test missing fields don't cause errors."""
        item = Item(
            id=uuid4(),
            org_id="test-org",
            project_id="proj-1",
            family="Minimal Item",
            # No type, material, dimensions, etc.
        )
        price = PriceItem(
            id=uuid4(),
            classification_code=2215,
            family="Minimal Price",
            # No type, material, dimensions, etc.
        )

        # Should not raise exception
        result = calculator.calculate(item, price)

        assert isinstance(result, ConfidenceResult)
        assert 0 <= result.score <= 100


class TestConfidenceResult:
    """Test ConfidenceResult model."""

    def test_confidence_result_repr(self) -> None:
        """Test string representation of result."""
        result = ConfidenceResult(score=95, method=MatchMethod.ENHANCED_FUZZY)
        repr_str = repr(result)

        assert "95" in repr_str
        assert "enhanced_fuzzy" in repr_str

    def test_score_clamping_in_constructor(self) -> None:
        """Test score is clamped in constructor."""
        # Test upper bound
        result_high = ConfidenceResult(score=150, method=MatchMethod.EXACT_MPN)
        assert result_high.score == 100

        # Test lower bound
        result_low = ConfidenceResult(score=-10, method=MatchMethod.BASIC_FUZZY)
        assert result_low.score == 0
