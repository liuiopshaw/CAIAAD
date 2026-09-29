#!/usr/bin/env python3
"""
Cross-material comparison tool. Aggregates multi-dimensional scores
and produces comparison matrix, radar chart data, and rankings.
"""

import logging

logger = logging.getLogger(__name__)


class MaterialCompare:
    """Generate cross-material comparison matrix and rankings.

    Takes manufacturing, delivery, and safety scores for multiple materials
    and produces standardized comparison output including radar chart data.
    """

    def run(self, evaluations: list, mode: str = "full_matrix") -> dict:
        """Main entry point.

        Args:
            evaluations: list of dicts, each containing:
                - material_name (str)
                - manufacturing_score (float)
                - delivery_score (float)
                - safety_score (float)
                - comprehensive_score (float)
                - manufacturing_details (dict)
                - delivery_details (dict)
                - safety_details (dict)
                - selectivity_ratio (float | None)
                - mechanism_summary (str | None)
            mode: 'full_matrix', 'ranking_only', 'radar_data'

        Returns:
            dict with comparison matrix, rankings, and radar chart data
        """
        if not evaluations:
            return {"error": "No evaluations provided", "source": "MaterialCompare"}

        # Sort by comprehensive score descending
        ranked = sorted(evaluations, key=lambda x: x.get("comprehensive_score", 0), reverse=True)

        matrix = self._build_comparison_matrix(ranked)
        rankings = self._build_rankings(ranked)
        radar_data = self._build_radar_data(ranked)
        recommendations = self._build_recommendations(ranked)

        return {
            "comparison_matrix": matrix,
            "rankings": rankings,
            "radar_chart_data": radar_data,
            "recommendations": recommendations,
            "best_material": ranked[0]["material_name"] if ranked else None,
            "total_materials_compared": len(evaluations),
            "source": "MaterialCompare"
        }

    def _build_comparison_matrix(self, ranked: list) -> list:
        """Build row-based comparison matrix."""
        matrix = []
        for entry in ranked:
            matrix.append({
                "material": entry["material_name"],
                "manufacturing_score": round(entry.get("manufacturing_score", 0), 2),
                "delivery_score": round(entry.get("delivery_score", 0), 2),
                "safety_score": round(entry.get("safety_score", 0), 2),
                "comprehensive_score": round(entry.get("comprehensive_score", 0), 2),
                "selectivity_ratio": entry.get("selectivity_ratio"),
                "key_strength": self._identify_key_strength(entry),
                "key_weakness": self._identify_key_weakness(entry)
            })
        return matrix

    def _build_rankings(self, ranked: list) -> list:
        """Build ranked list with score breakdowns."""
        rankings = []
        for i, entry in enumerate(ranked):
            rankings.append({
                "rank": i + 1,
                "material": entry["material_name"],
                "overall_score": round(entry.get("comprehensive_score", 0), 2),
                "manufacturing_score": round(entry.get("manufacturing_score", 0), 2),
                "delivery_score": round(entry.get("delivery_score", 0), 2),
                "safety_score": round(entry.get("safety_score", 0), 2)
            })
        return rankings

    def _build_radar_data(self, ranked: list) -> dict:
        """Build radar chart compatible data structure."""
        dimensions = [
            "manufacturing_potency",
            "manufacturing_selectivity",
            "delivery_efficiency",
            "delivery_affinity",
            "safety"
        ]
        datasets = []
        for entry in ranked[:5]:  # Top 5 materials
            manufacturing = entry.get("manufacturing_details", {})
            delivery = entry.get("delivery_details", {})
            safety = entry.get("safety_details", {})

            datasets.append({
                "label": entry["material_name"],
                "data": [
                    manufacturing.get("potency_score", 0),
                    manufacturing.get("selectivity_score", 0),
                    delivery.get("activity_strength_score", 0),
                    delivery.get("substrate_affinity_score", 0),
                    safety.get("overall_safety_score", 0) or
                    entry.get("safety_score", 0)
                ]
            })
        return {"dimensions": dimensions, "datasets": datasets}

    def _build_recommendations(self, ranked: list) -> list:
        """Generate human-readable recommendations."""
        recommendations = []
        if not ranked:
            return recommendations

        best = ranked[0]
        recommendations.append(
            f"Best overall recommendation: {best['material_name']} "
            f"(comprehensive score {best.get('comprehensive_score', 0):.1f}/10)"
        )

        # Check selectivity champion
        selectivity_best = max(ranked, key=lambda x: x.get("selectivity_ratio") or 0)
        if selectivity_best.get("selectivity_ratio"):
            recommendations.append(
                f"Best manufacturing selectivity: {selectivity_best['material_name']} "
                f"(selectivity ratio {selectivity_best['selectivity_ratio']:.1f})"
            )

        # Check delivery champion
        delivery_best = max(ranked, key=lambda x: x.get("delivery_score", 0))
        recommendations.append(
            f"Best delivery: {delivery_best['material_name']} "
            f"(delivery score {delivery_best.get('delivery_score', 0):.1f}/10)"
        )

        # Check safety champion
        safety_best = max(ranked, key=lambda x: x.get("safety_score", 0))
        recommendations.append(
            f"Best safety: {safety_best['material_name']} "
            f"(safety score {safety_best.get('safety_score', 0):.1f}/10)"
        )

        return recommendations

    def _identify_key_strength(self, entry: dict) -> str:
        scores = {
            "manufacturing": entry.get("manufacturing_score", 0),
            "delivery": entry.get("delivery_score", 0),
            "safety": entry.get("safety_score", 0)
        }
        best_dim = max(scores, key=scores.get)
        return f"Best in {best_dim} ({scores[best_dim]:.1f})"

    def _identify_key_weakness(self, entry: dict) -> str:
        scores = {
            "manufacturing": entry.get("manufacturing_score", 0),
            "delivery": entry.get("delivery_score", 0),
            "safety": entry.get("safety_score", 0)
        }
        worst_dim = min(scores, key=scores.get)
        return f"Needs improvement in {worst_dim} ({scores[worst_dim]:.1f})"
