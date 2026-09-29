#!/usr/bin/env python3
"""Ranker Agent — Multi-material cross-comparison with Cj fusion."""

import logging
from .base_agent import BaseAgent
from src.tools.material_compare import MaterialCompare

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class RankerAgent(BaseAgent):
    """Cross-material comparison and ranking agent.

    Aggregates manufacturing, delivery, and safety evaluation scores, applies
    consistency coefficient Cj fusion, and produces comparison matrix, radar
    chart data, rankings, and recommendations.
    """

    def __init__(self, llm):
        from src.config.config import Config
        super().__init__(
            llm=llm,
            role="ranker",
            goal="Aggregate multi-dimensional evaluation scores, fuse with consistency "
                 "coefficient Cj, generate cross-material comparison matrix, radar chart "
                 "data, rankings, and AD therapeutic potential recommendations.",
            prompt_file="ranker_prompt.md",
            temperature=Config.RANKER_TEMPERATURE,
            max_iter=1
        )
        self.material_compare = MaterialCompare()

    def create_agent(self):
        agent = super().create_agent()
        agent.tools = []
        return agent

    def calculate_comprehensive_score(self, manufacturing_score: float, delivery_score: float,
                                       safety_score: float) -> float:
        """S_j = W̄_j × C_j

        C_j = 1 − (1/3) × Σ(W_ij − W̄_j)² / W̄_j
        """
        scores = [manufacturing_score, delivery_score, safety_score]
        avg = sum(scores) / 3
        variance = sum((s - avg) ** 2 for s in scores) / 3
        if avg > 0:
            c_j = 1 - variance / avg
            c_j = max(c_j, 0.5)  # floor at 0.5 to avoid over-penalization
        else:
            c_j = 0
        return round(avg * c_j, 2)

    def compare(self, evaluations: list) -> dict:
        """Run full comparison pipeline."""
        return self.material_compare.run(evaluations)
