"""Predictive risk scoring for QA compliance."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from bimcalc.db.models import DocumentModel, ItemModel, MatchResultModel
from bimcalc.utils.redis_cache import get_cached, set_cached

# Cache TTL for risk scores (1 hour)
RISK_CACHE_TTL = 3600


@dataclass
class RiskScore:
    """Risk assessment for an item."""

    item_id: str
    score: float  # 0-100
    level: str  # Low/Medium/High
    factors: dict[str, Any]  # Contributing factors
    recommendations: list[str]  # Actionable recommendations


class ComplianceRiskScorer:
    """Calculate QA compliance risk for items using multi-factor analysis."""

    # Classification complexity mapping
    COMPLEX_CLASSIFICATIONS = {"2601", "2602", "2603"}  # Electrical, HVAC, Plumbing
    SIMPLE_CLASSIFICATIONS = {"2801", "2802"}  # Furniture, Fittings

    async def calculate_risk(
        self,
        item: ItemModel,
        documents: list[DocumentModel],
        match: MatchResultModel | None = None,
    ) -> RiskScore:
        """Calculate composite risk score for an item.

        Args:
            item: Item to assess
            documents: Documents linked to this item
            match: Price match result (if any)

        Returns:
            RiskScore with score, level, factors, and recommendations
        """
        score = 0.0
        factors = {}

        # Factor 1: Document Coverage (40% weight)
        doc_count = len(documents)
        if doc_count == 0:
            score += 40
            factors["doc_coverage"] = {"score": 40, "status": "No documents"}
        elif doc_count <= 2:
            score += 20
            factors["doc_coverage"] = {
                "score": 20,
                "status": f"{doc_count} documents (limited)",
            }
        else:
            factors["doc_coverage"] = {
                "score": 0,
                "status": f"{doc_count} documents (good)",
            }

        # Factor 2: Classification Complexity (25% weight)
        class_code = str(item.classification_code) if item.classification_code else None
        if not class_code:
            score += 25
            factors["classification"] = {"score": 25, "status": "Unknown"}
        elif class_code in self.COMPLEX_CLASSIFICATIONS:
            score += 15
            factors["classification"] = {
                "score": 15,
                "status": f"Complex ({class_code})",
            }
        elif class_code in self.SIMPLE_CLASSIFICATIONS:
            score += 5
            factors["classification"] = {"score": 5, "status": f"Simple ({class_code})"}
        else:
            score += 10
            factors["classification"] = {
                "score": 10,
                "status": f"Standard ({class_code})",
            }

        # Factor 3: Time Since Creation        # 1. Item Age Risk
        now = datetime.now(timezone.utc)
        if item.created_at.tzinfo is None:
            # Handle naive datetime from DB (shouldn't happen with TIMESTAMP(timezone=True))
            created_at = item.created_at.replace(tzinfo=timezone.utc)
        else:
            created_at = item.created_at

        days_old = (now - created_at).days
        if days_old > 90:
            score += 20
            factors["age"] = {"score": 20, "status": f"{days_old} days old (very old)"}
        elif days_old > 60:
            score += 10
            factors["age"] = {"score": 10, "status": f"{days_old} days old (aging)"}
        else:
            factors["age"] = {"score": 0, "status": f"{days_old} days old (recent)"}

        # Factor 4: Match Confidence (15% weight)
        if match and match.confidence_score is not None:
            if match.confidence_score < 0.70:
                score += 15
                factors["match_confidence"] = {
                    "score": 15,
                    "status": f"{match.confidence_score:.0%} confidence (low)",
                }
            elif match.confidence_score < 0.85:
                score += 8
                factors["match_confidence"] = {
                    "score": 8,
                    "status": f"{match.confidence_score:.0%} confidence (medium)",
                }
            else:
                factors["match_confidence"] = {
                    "score": 0,
                    "status": f"{match.confidence_score:.0%} confidence (high)",
                }
        else:
            factors["match_confidence"] = {"score": 0, "status": "No match data"}

        # Determine risk level
        if score >= 61:
            level = "High"
        elif score >= 31:
            level = "Medium"
        else:
            level = "Low"

        # Generate actionable recommendations
        recommendations = self._generate_recommendations(factors, score)

        return RiskScore(
            item_id=str(item.id),
            score=min(score, 100.0),  # Cap at 100
            level=level,
            factors=factors,
            recommendations=recommendations,
        )

    def _generate_recommendations(self, factors: dict, score: float) -> list[str]:
        """Generate actionable recommendations based on risk factors.

        Args:
            factors: Risk factors dict
            score: Total risk score

        Returns:
            List of recommendation strings
        """
        recs = []

        # Document coverage recommendations
        doc_status = factors.get("doc_coverage", {}).get("status", "")
        if "No documents" in doc_status:
            recs.append("🔗 Link relevant quality and safety documents")
        elif "limited" in doc_status:
            recs.append("📄 Add more supporting documents")

        # Classification recommendations
        class_status = factors.get("classification", {}).get("status", "")
        if "Unknown" in class_status:
            recs.append("🏷️ Assign proper classification code")
        elif "Complex" in class_status:
            recs.append("⚠️ Complex work - ensure thorough QA review")

        # Age recommendations
        age_status = factors.get("age", {}).get("status", "")
        if "very old" in age_status:
            recs.append("⏰ Priority review - item significantly overdue")
        elif "aging" in age_status:
            recs.append("📅 Review soon - item aging without QA")

        # Match confidence recommendations
        match_status = factors.get("match_confidence", {}).get("status", "")
        if "low" in match_status:
            recs.append("💰 Verify price match accuracy")

        # Overall urgency
        if score >= 80:
            recs.insert(0, "🚨 URGENT: Immediate attention required")

        return recs


async def get_risk_score_cached(
    item: ItemModel,
    documents: list[DocumentModel],
    match: MatchResultModel | None = None,
) -> RiskScore:
    """Get risk score with caching.

    Args:
        item: Item to assess
        documents: Documents linked to item
        match: Price match result

    Returns:
        Cached or freshly calculated RiskScore
    """
    cache_key = f"risk:{item.id}"

    # Check cache
    cached = await get_cached(cache_key)
    if cached:
        return cached

    # Calculate fresh
    scorer = ComplianceRiskScorer()
    risk = await scorer.calculate_risk(item, documents, match)

    # Cache for 1 hour
    await set_cached(cache_key, risk, ttl_seconds=RISK_CACHE_TTL)

    return risk
