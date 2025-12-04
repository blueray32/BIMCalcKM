"""Enhanced confidence calculator with multiple match strategies."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from rapidfuzz import fuzz

if TYPE_CHECKING:
    from bimcalc.matching.models import Item, MappingMemory, PriceItem


class MatchMethod(Enum):
    """Classification of match methods by reliability."""

    EXACT_MPN = "exact_mpn"  # Manufacturer part number match → 100
    EXACT_SKU = "exact_sku"  # SKU match → 100
    CANONICAL_KEY = "canonical_key"  # Mapping memory hit → 100
    ENHANCED_FUZZY = "enhanced_fuzzy"  # Multi-field weighted → 70-95
    BASIC_FUZZY = "basic_fuzzy"  # Simple string match → 50-85


class ConfidenceResult:
    """Result of confidence calculation."""

    def __init__(
        self,
        score: int,
        method: MatchMethod,
        details: dict[str, float] | None = None,
    ) -> None:
        """Initialize confidence result.

        Args:
            score: Confidence score (0-100)
            method: Match method used
            details: Detailed scoring breakdown
        """
        self.score = max(0, min(100, score))  # Clamp to 0-100
        self.method = method
        self.details = details or {}

    def __repr__(self) -> str:
        return f"ConfidenceResult(score={self.score}, method={self.method.value})"


class ConfidenceCalculator:
    """Calculate confidence scores using multiple strategies."""

    def __init__(
        self,
        size_tolerance_mm: float = 10.0,
        angle_tolerance_deg: float = 5.0,
        fuzzy_min_score: int = 70,
    ) -> None:
        """Initialize confidence calculator.

        Args:
            size_tolerance_mm: Tolerance for dimension matching (default: 10mm)
            angle_tolerance_deg: Tolerance for angle matching (default: 5°)
            fuzzy_min_score: Minimum fuzzy score to consider (default: 70)
        """
        self.size_tolerance_mm = size_tolerance_mm
        self.angle_tolerance_deg = angle_tolerance_deg
        self.fuzzy_min_score = fuzzy_min_score

    def calculate(
        self,
        item: Item,
        price: PriceItem,
        mapping_memory: MappingMemory | None = None,
    ) -> ConfidenceResult:
        """Calculate confidence score using priority-based matching.

        Priority order:
        1. Exact MPN match → 100
        2. Exact SKU match → 100
        3. Canonical key memory hit → 100
        4. Enhanced fuzzy with bonuses → 70-95

        Args:
            item: BIM item to match
            price: Price item candidate
            mapping_memory: Optional mapping memory for canonical key lookup

        Returns:
            ConfidenceResult with score and method
        """
        # Priority 1: Exact MPN match
        if item.manufacturer_part_number and price.manufacturer_part_number:
            if item.manufacturer_part_number == price.manufacturer_part_number:
                return ConfidenceResult(
                    score=100,
                    method=MatchMethod.EXACT_MPN,
                    details={"mpn": item.manufacturer_part_number},
                )

        # Priority 2: Exact SKU match
        if item.vendor_sku and price.sku:
            if item.vendor_sku == price.sku:
                return ConfidenceResult(
                    score=100,
                    method=MatchMethod.EXACT_SKU,
                    details={"sku": price.sku},
                )

        # Priority 3: Canonical key memory
        if mapping_memory and item.canonical_key:
            mapping = mapping_memory.lookup(item.org_id, item.canonical_key)
            if mapping and mapping.price_item_id == price.id:
                return ConfidenceResult(
                    score=100,
                    method=MatchMethod.CANONICAL_KEY,
                    details={"canonical_key": item.canonical_key},
                )

        # Priority 4: Enhanced fuzzy matching
        return self._calculate_enhanced_fuzzy(item, price)

    def _calculate_enhanced_fuzzy(
        self, item: Item, price: PriceItem
    ) -> ConfidenceResult:
        """Calculate enhanced fuzzy score with weighted fields and bonuses.

        Args:
            item: BIM item
            price: Price item

        Returns:
            ConfidenceResult with detailed scoring
        """
        # Multi-field weighted scoring
        weights = {
            "family": 0.30,
            "type": 0.25,
            "material": 0.15,
            "size": 0.15,
            "unit": 0.10,
            "angle": 0.05,
        }

        field_scores: dict[str, float] = {}

        # Family name fuzzy match
        if item.family and price.family:
            field_scores["family"] = fuzz.ratio(item.family, price.family)
        else:
            field_scores["family"] = 0.0

        # Type name fuzzy match
        if item.type_name and price.type_name:
            field_scores["type"] = fuzz.ratio(item.type_name, price.type_name)
        else:
            field_scores["type"] = 0.0

        # Material exact match (binary: 100 or 0)
        if item.material and price.material:
            field_scores["material"] = (
                100.0 if item.material.lower() == price.material.lower() else 0.0
            )
        else:
            field_scores["material"] = 0.0

        # Size match (within tolerance)
        field_scores["size"] = self._score_size_match(item, price)

        # Unit exact match (binary: 100 or 0)
        if item.unit and price.unit:
            field_scores["unit"] = 100.0 if item.unit == price.unit else 0.0
        else:
            field_scores["unit"] = 0.0

        # Angle match (within tolerance)
        if item.angle_deg is not None and price.angle_deg is not None:
            angle_diff = abs(item.angle_deg - price.angle_deg)
            if angle_diff <= self.angle_tolerance_deg:
                field_scores["angle"] = 100.0
            else:
                field_scores["angle"] = 0.0
        else:
            field_scores["angle"] = 0.0

        # Calculate weighted score
        weighted_score = sum(
            field_scores.get(field, 0.0) * weight for field, weight in weights.items()
        )

        # Apply exact match bonuses (up to +10 total)
        bonuses = 0.0

        # Bonus for perfect dimension match (1mm tolerance)
        if self._is_exact_size_match(item, price, tolerance=1.0):
            bonuses += 5.0

        # Bonus for material + unit alignment
        if (
            field_scores.get("material", 0.0) == 100.0
            and field_scores.get("unit", 0.0) == 100.0
        ):
            bonuses += 5.0

        final_score = int(round(min(weighted_score + bonuses, 100.0)))

        return ConfidenceResult(
            score=final_score,
            method=MatchMethod.ENHANCED_FUZZY,
            details={
                "weighted_score": round(weighted_score, 2),
                "bonuses": round(bonuses, 2),
                "field_scores": {k: round(v, 2) for k, v in field_scores.items()},
            },
        )

    def _score_size_match(self, item: Item, price: PriceItem) -> float:
        """Score size match considering width and height.

        Args:
            item: BIM item
            price: Price item

        Returns:
            Score 0-100 based on dimensional accuracy
        """
        if not any(
            [
                item.width_mm,
                item.height_mm,
                item.dn_mm,
                price.width_mm,
                price.height_mm,
                price.dn_mm,
            ]
        ):
            return 0.0

        # Check width
        width_score = 0.0
        if item.width_mm is not None and price.width_mm is not None:
            width_diff = abs(item.width_mm - price.width_mm)
            if width_diff <= self.size_tolerance_mm:
                width_score = 100.0 * (1.0 - width_diff / self.size_tolerance_mm)

        # Check height
        height_score = 0.0
        if item.height_mm is not None and price.height_mm is not None:
            height_diff = abs(item.height_mm - price.height_mm)
            if height_diff <= self.size_tolerance_mm:
                height_score = 100.0 * (1.0 - height_diff / self.size_tolerance_mm)

        # Check DN (pipe diameter)
        dn_score = 0.0
        if item.dn_mm is not None and price.dn_mm is not None:
            dn_diff = abs(item.dn_mm - price.dn_mm)
            if dn_diff <= self.size_tolerance_mm:
                dn_score = 100.0 * (1.0 - dn_diff / self.size_tolerance_mm)

        # Average available dimension scores
        scores = [s for s in [width_score, height_score, dn_score] if s > 0.0]
        return sum(scores) / len(scores) if scores else 0.0

    def _is_exact_size_match(
        self, item: Item, price: PriceItem, tolerance: float = 1.0
    ) -> bool:
        """Check if dimensions match within tight tolerance (exact match).

        Args:
            item: BIM item
            price: Price item
            tolerance: Tolerance in mm (default: 1mm)

        Returns:
            True if all available dimensions match within tolerance
        """
        checks = []

        if item.width_mm is not None and price.width_mm is not None:
            checks.append(abs(item.width_mm - price.width_mm) <= tolerance)

        if item.height_mm is not None and price.height_mm is not None:
            checks.append(abs(item.height_mm - price.height_mm) <= tolerance)

        if item.dn_mm is not None and price.dn_mm is not None:
            checks.append(abs(item.dn_mm - price.dn_mm) <= tolerance)

        # All available dimensions must match
        return all(checks) if checks else False
