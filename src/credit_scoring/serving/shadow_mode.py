"""A/B testing shadow mode for model comparison.

Shadow mode scores every request through both the production (champion)
model and a challenger model. The champion drives the decision; the
challenger runs silently for comparison. Results are logged for offline
analysis.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class ShadowResult:
    """Result from a single shadow comparison."""

    application_id: str
    champion_pd: float
    challenger_pd: float
    champion_score: int
    challenger_score: int
    champion_decision: str
    challenger_decision: str
    champion_latency_ms: float
    challenger_latency_ms: float
    agreement: bool
    timestamp: datetime


class ShadowModeRouter:
    """Routes scoring requests through both champion and challenger models.

    The champion model drives the actual decision. The challenger model
    runs in the background for comparison. All results are logged for
    offline A/B analysis.

    Usage:
        router = ShadowModeRouter(champion_scorer, challenger_scorer)
        result, shadow = router.score(features)
        # result is from champion (used for decision)
        # shadow contains comparison data
    """

    def __init__(
        self,
        champion_scorer,
        challenger_scorer,
        shadow_traffic_pct: float = 1.0,
    ):
        """Initialize shadow mode.

        Args:
            champion_scorer: Production CreditScoreCalculator.
            challenger_scorer: Challenger CreditScoreCalculator.
            shadow_traffic_pct: Fraction of requests to shadow score (0.0-1.0).
        """
        self.champion = champion_scorer
        self.challenger = challenger_scorer
        self.shadow_traffic_pct = shadow_traffic_pct
        self._rng = np.random.default_rng(42)

        # In-memory log for demo (production would use a database or message queue)
        self.shadow_log: list[ShadowResult] = []

    def score(self, features: pd.DataFrame, application_id: str = "") -> tuple[dict, ShadowResult | None]:
        """Score through champion (always) and challenger (shadow).

        Returns:
            Tuple of (champion_result, shadow_result).
            shadow_result is None if this request was not shadowed.
        """
        # Champion always runs
        t0 = time.monotonic()
        champion_result = self.champion.score_single(features)
        champion_ms = (time.monotonic() - t0) * 1000

        # Challenger runs based on traffic percentage
        shadow = None
        if self._rng.random() < self.shadow_traffic_pct:
            try:
                t1 = time.monotonic()
                challenger_result = self.challenger.score_single(features)
                challenger_ms = (time.monotonic() - t1) * 1000

                shadow = ShadowResult(
                    application_id=application_id,
                    champion_pd=float(champion_result["pd"]),
                    challenger_pd=float(challenger_result["pd"]),
                    champion_score=int(champion_result["credit_score"]),
                    challenger_score=int(challenger_result["credit_score"]),
                    champion_decision=champion_result["decision"],
                    challenger_decision=challenger_result["decision"],
                    champion_latency_ms=round(champion_ms, 2),
                    challenger_latency_ms=round(challenger_ms, 2),
                    agreement=champion_result["decision"] == challenger_result["decision"],
                    timestamp=datetime.now(UTC),
                )
                self.shadow_log.append(shadow)

            except Exception as e:
                logger.warning("Challenger scoring failed: %s", e)

        return champion_result, shadow

    def get_comparison_report(self) -> dict:
        """Generate summary report comparing champion vs challenger.

        Returns metrics useful for deciding whether to promote the challenger.
        """
        if not self.shadow_log:
            return {"status": "no_data", "n_comparisons": 0}

        n = len(self.shadow_log)
        agreement_rate = sum(1 for s in self.shadow_log if s.agreement) / n

        champ_pds = np.array([s.champion_pd for s in self.shadow_log])
        chall_pds = np.array([s.challenger_pd for s in self.shadow_log])
        champ_scores = np.array([s.champion_score for s in self.shadow_log])
        chall_scores = np.array([s.challenger_score for s in self.shadow_log])
        champ_latencies = np.array([s.champion_latency_ms for s in self.shadow_log])
        chall_latencies = np.array([s.challenger_latency_ms for s in self.shadow_log])

        pd_correlation = float(np.corrcoef(champ_pds, chall_pds)[0, 1])
        pd_mean_diff = float(np.mean(chall_pds - champ_pds))
        score_mean_diff = float(np.mean(chall_scores - champ_scores))

        # Decision disagreement breakdown
        disagreements = [s for s in self.shadow_log if not s.agreement]
        upgrade_count = sum(
            1 for s in disagreements if s.challenger_decision == "approved" and s.champion_decision != "approved"
        )
        downgrade_count = sum(
            1 for s in disagreements if s.challenger_decision == "declined" and s.champion_decision != "declined"
        )

        return {
            "status": "active",
            "n_comparisons": n,
            "decision_agreement_rate": round(agreement_rate, 4),
            "pd_correlation": round(pd_correlation, 4),
            "pd_mean_difference": round(pd_mean_diff, 6),
            "credit_score_mean_difference": round(score_mean_diff, 2),
            "champion_avg_latency_ms": round(float(champ_latencies.mean()), 2),
            "challenger_avg_latency_ms": round(float(chall_latencies.mean()), 2),
            "disagreement_breakdown": {
                "total": len(disagreements),
                "challenger_more_lenient": upgrade_count,
                "challenger_more_strict": downgrade_count,
                "other": len(disagreements) - upgrade_count - downgrade_count,
            },
            "recommendation": _promotion_recommendation(agreement_rate, pd_correlation),
        }


def _promotion_recommendation(agreement_rate: float, pd_correlation: float) -> str:
    """Suggest whether the challenger should be promoted."""
    if agreement_rate >= 0.95 and pd_correlation >= 0.98:
        return "SAFE TO PROMOTE: High agreement, strong correlation."
    elif agreement_rate >= 0.90:
        return "REVIEW NEEDED: Good agreement but check disagreement cases."
    elif agreement_rate >= 0.80:
        return "CAUTION: Moderate disagreement. Run longer before promoting."
    else:
        return "DO NOT PROMOTE: Significant behavioral differences detected."
