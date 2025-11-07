"""Fuzzy ranking using RapidFuzz for BIMCalc.

Ranks pre-filtered candidates by string similarity (RapidFuzz token_sort_ratio).
"""

from __future__ import annotations

from rapidfuzz import fuzz

from bimcalc.config import get_config
from bimcalc.models import CandidateMatch, Item, PriceItem


class FuzzyRanker:
    """RapidFuzz string similarity ranker."""

    def __init__(self):
        """Initialize ranker with configuration."""
        self.config = get_config()
        self.min_score = self.config.matching.fuzzy_min_score

    def rank(self, item: Item, candidates: list[PriceItem]) -> list[CandidateMatch]:
        """Rank candidates by fuzzy string similarity.

        Ranking logic:
        1. Construct search strings (family + type + material)
        2. Compute RapidFuzz token_sort_ratio (0-100)
        3. Filter: Keep only scores >= min_score
        4. Sort: Descending by score

        Args:
            item: BIM item
            candidates: Pre-filtered candidates from CandidateGenerator

        Returns:
            List of CandidateMatch (price_item + score), sorted descending

        Raises:
            ValueError: If item.family or item.type_name is None
        """
        if not item.family or not item.family.strip():
            raise ValueError("item.family is required for fuzzy ranking")

        # Construct item search string
        item_parts = [item.family]
        if item.type_name:
            item_parts.append(item.type_name)
        if item.material:
            item_parts.append(item.material)

        item_text = " ".join(item_parts).strip()

        # Rank each candidate
        ranked = []

        for candidate in candidates:
            # Construct price search string
            price_parts = [candidate.description]
            if candidate.material:
                price_parts.append(candidate.material)

            price_text = " ".join(price_parts).strip()

            # Compute RapidFuzz token_sort_ratio (0-100)
            score = fuzz.token_sort_ratio(item_text, price_text)

            # Filter by min score
            if score >= self.min_score:
                ranked.append(
                    CandidateMatch(
                        price_item=candidate,
                        score=score,
                        flags=[],  # Flags computed separately by FlagsEngine
                    )
                )

        # Sort descending by score
        ranked.sort(key=lambda x: x.score, reverse=True)

        return ranked


def rank_candidates(item: Item, candidates: list[PriceItem]) -> list[CandidateMatch]:
    """Convenience function: rank candidates.

    Args:
        item: BIM item
        candidates: Pre-filtered candidates

    Returns:
        List of CandidateMatch, sorted descending by score
    """
    ranker = FuzzyRanker()
    return ranker.rank(item, candidates)
