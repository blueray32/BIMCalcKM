"""Auto-routing logic for BIMCalc matching decisions.

Routes matches to auto-accept or manual review based on confidence + flags.
"""

from __future__ import annotations

from bimcalc.config import get_config
from bimcalc.models import CandidateMatch, MatchDecision, MatchResult


class AutoRouter:
    """Auto-routing decision engine (confidence + flags → decision)."""

    def __init__(self):
        """Initialize router with configuration."""
        self.config = get_config()
        self.min_confidence = self.config.matching.auto_accept_min_confidence

    def route(
        self,
        match: CandidateMatch,
        source: str = "fuzzy_match",
        created_by: str = "system",
    ) -> MatchResult:
        """Determine match decision based on confidence and flags.

        Auto-accept rule:
        - Confidence >= min_confidence (default 85) AND
        - Zero flags (Critical-Veto OR Advisory)

        All other combinations → manual review.

        Args:
            match: CandidateMatch with score and flags
            source: "mapping_memory" or "fuzzy_match"
            created_by: User email or "system"

        Returns:
            MatchResult with decision and reason

        Raises:
            ValueError: If match has no price_item
        """
        if match.price_item is None:
            raise ValueError("match.price_item is required for routing")

        confidence = match.score
        flags = match.flags

        # Check auto-accept criteria
        if confidence >= self.min_confidence and len(flags) == 0:
            decision = MatchDecision.AUTO_ACCEPTED
            reason = (
                f"High confidence ({confidence:.1f}%), no flags, "
                f"via {source.replace('_', ' ')}"
            )
        else:
            decision = MatchDecision.MANUAL_REVIEW

            # Build reason
            reasons = []
            if confidence < self.min_confidence:
                reasons.append(f"confidence {confidence:.1f}% < {self.min_confidence}%")
            if len(flags) > 0:
                flag_types = ", ".join(f.type for f in flags)
                reasons.append(f"flags: {flag_types}")

            reason = f"Manual review required: {'; '.join(reasons)}"

        return MatchResult(
            item_id=match.price_item.id,  # Note: This should be item.id in real usage
            price_item_id=match.price_item.id,
            confidence_score=confidence,
            source=source,
            flags=flags,
            decision=decision,
            reason=reason,
            created_by=created_by,
        )


def route_match(
    match: CandidateMatch, source: str = "fuzzy_match", created_by: str = "system"
) -> MatchResult:
    """Convenience function: route match to decision.

    Args:
        match: CandidateMatch with score and flags
        source: "mapping_memory" or "fuzzy_match"
        created_by: User email or "system"

    Returns:
        MatchResult with decision and reason
    """
    router = AutoRouter()
    return router.route(match, source, created_by)
