"""Integrated matching pipeline using enhanced confidence scoring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from bimcalc.matching.confidence import ConfidenceCalculator, MatchMethod

if TYPE_CHECKING:
    from bimcalc.matching.models import Item, MappingMemory, PriceItem


@dataclass
class MatchResult:
    """Result of item matching."""

    item_id: str
    price_item_id: str | None
    confidence: int
    method: MatchMethod
    auto_accepted: bool
    flags: list[str]
    reason: str
    details: dict

    @property
    def requires_review(self) -> bool:
        """Check if match requires manual review."""
        return not self.auto_accepted or len(self.flags) > 0


class AutoRouter:
    """Automatic routing decision maker."""

    def __init__(
        self,
        min_confidence_for_auto: int = 85,
        allow_auto_with_advisory: bool = False,
    ) -> None:
        """Initialize auto-router.

        Args:
            min_confidence_for_auto: Minimum confidence for auto-accept (default: 85)
            allow_auto_with_advisory: Allow auto-accept with Advisory flags (default: False)
        """
        self.min_confidence_for_auto = min_confidence_for_auto
        self.allow_auto_with_advisory = allow_auto_with_advisory

    def should_auto_accept(
        self, confidence: int, flags: list[str], method: MatchMethod
    ) -> tuple[bool, str]:
        """Determine if match should be auto-accepted.

        Auto-accept criteria:
        - Confidence >= threshold (default 85)
        - No Critical-Veto flags
        - Advisory flags allowed only if configured

        Args:
            confidence: Confidence score (0-100)
            flags: List of flag types
            method: Match method used

        Returns:
            Tuple of (should_accept, reason)
        """
        # Exact matches always auto-accept (even with flags for manual correction)
        if method in (MatchMethod.EXACT_MPN, MatchMethod.EXACT_SKU):
            return True, f"Exact match via {method.value}"

        # Canonical key matches auto-accept (previously approved)
        if method == MatchMethod.CANONICAL_KEY:
            return True, "Previously approved mapping (canonical key)"

        # Check confidence threshold
        if confidence < self.min_confidence_for_auto:
            return (
                False,
                f"Confidence {confidence} below threshold {self.min_confidence_for_auto}",
            )

        # Check for Critical-Veto flags
        critical_flags = [
            f
            for f in flags
            if f
            in [
                "UnitConflict",
                "SizeMismatch",
                "AngleMismatch",
                "MaterialConflict",
                "ClassMismatch",
            ]
        ]
        if critical_flags:
            return False, f"Critical-Veto flags present: {', '.join(critical_flags)}"

        # Check for Advisory flags
        advisory_flags = [
            f for f in flags if f in ["StalePrice", "CurrencyMismatch", "VATUnclear"]
        ]
        if advisory_flags and not self.allow_auto_with_advisory:
            return (
                False,
                f"Advisory flags present: {', '.join(advisory_flags)} (manual review required)",
            )

        # All checks passed
        return True, f"High confidence ({confidence}) with no blocking flags"


class EnhancedMatcher:
    """Enhanced matcher with multi-strategy confidence scoring."""

    def __init__(
        self,
        confidence_calculator: ConfidenceCalculator | None = None,
        auto_router: AutoRouter | None = None,
    ) -> None:
        """Initialize enhanced matcher.

        Args:
            confidence_calculator: Custom confidence calculator
            auto_router: Custom auto-router
        """
        self.calculator = confidence_calculator or ConfidenceCalculator()
        self.router = auto_router or AutoRouter()

    def match(
        self,
        item: Item,
        price: PriceItem,
        mapping_memory: MappingMemory | None = None,
        flags: list[str] | None = None,
    ) -> MatchResult:
        """Match item to price with confidence scoring and auto-routing.

        Args:
            item: BIM item to match
            price: Price item candidate
            mapping_memory: Optional mapping memory for canonical lookups
            flags: Optional pre-computed flags for this match

        Returns:
            MatchResult with confidence, method, and auto-accept decision
        """
        flags = flags or []

        # Calculate confidence
        confidence_result = self.calculator.calculate(item, price, mapping_memory)

        # Auto-routing decision
        auto_accept, reason = self.router.should_auto_accept(
            confidence_result.score, flags, confidence_result.method
        )

        return MatchResult(
            item_id=str(item.id),
            price_item_id=str(price.id) if auto_accept else None,
            confidence=confidence_result.score,
            method=confidence_result.method,
            auto_accepted=auto_accept,
            flags=flags,
            reason=reason,
            details=confidence_result.details,
        )

    def match_batch(
        self,
        item: Item,
        candidates: list[PriceItem],
        mapping_memory: MappingMemory | None = None,
        flags_map: dict[str, list[str]] | None = None,
    ) -> list[MatchResult]:
        """Match item against multiple price candidates.

        Args:
            item: BIM item to match
            candidates: List of price item candidates
            mapping_memory: Optional mapping memory
            flags_map: Optional map of price_id -> flags

        Returns:
            List of match results, sorted by confidence (highest first)
        """
        flags_map = flags_map or {}
        results = []

        for price in candidates:
            flags = flags_map.get(str(price.id), [])
            result = self.match(item, price, mapping_memory, flags)
            results.append(result)

        # Sort by confidence descending
        results.sort(key=lambda r: r.confidence, reverse=True)
        return results

    def get_best_match(
        self,
        item: Item,
        candidates: list[PriceItem],
        mapping_memory: MappingMemory | None = None,
        flags_map: dict[str, list[str]] | None = None,
    ) -> MatchResult | None:
        """Get best match for item from candidates.

        Args:
            item: BIM item to match
            candidates: List of price item candidates
            mapping_memory: Optional mapping memory
            flags_map: Optional flags map

        Returns:
            Best match result or None if no candidates
        """
        if not candidates:
            return None

        results = self.match_batch(item, candidates, mapping_memory, flags_map)
        return results[0] if results else None


class MatchingPipeline:
    """Complete matching pipeline with classification blocking."""

    def __init__(
        self,
        matcher: EnhancedMatcher | None = None,
        mapping_memory: MappingMemory | None = None,
    ) -> None:
        """Initialize matching pipeline.

        Args:
            matcher: Enhanced matcher instance
            mapping_memory: Mapping memory for canonical key lookups
        """
        self.matcher = matcher or EnhancedMatcher()
        self.mapping_memory = mapping_memory

    def match_item(
        self,
        item: Item,
        price_catalog: list[PriceItem],
        flags_map: dict[str, list[str]] | None = None,
    ) -> MatchResult | None:
        """Match single item using classification blocking and confidence scoring.

        Workflow:
        1. Block candidates by classification_code
        2. Calculate confidence for each candidate
        3. Apply business flags
        4. Auto-route or send to review

        Args:
            item: BIM item to match
            price_catalog: Full price catalog
            flags_map: Optional pre-computed flags

        Returns:
            Best match result or None
        """
        # Step 1: Classification blocking
        if item.classification_code is None:
            # No classification - must review manually
            return MatchResult(
                item_id=str(item.id),
                price_item_id=None,
                confidence=0,
                method=MatchMethod.BASIC_FUZZY,
                auto_accepted=False,
                flags=["NoClassification"],
                reason="Item has no classification code",
                details={},
            )

        # Filter candidates by classification
        candidates = [
            p
            for p in price_catalog
            if p.classification_code == item.classification_code
        ]

        if not candidates:
            # No candidates in class - escalate
            return MatchResult(
                item_id=str(item.id),
                price_item_id=None,
                confidence=0,
                method=MatchMethod.BASIC_FUZZY,
                auto_accepted=False,
                flags=["NoCandidates"],
                reason=f"No price items found for classification {item.classification_code}",
                details={"classification_code": item.classification_code},
            )

        # Step 2-4: Match against candidates
        return self.matcher.get_best_match(
            item, candidates, self.mapping_memory, flags_map
        )
