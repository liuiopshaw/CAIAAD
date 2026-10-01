#!/usr/bin/env python3
"""
DrugBank API wrapper for pharmacology, gut metabolism,
and drug-microbiome interaction data.
"""

import logging
import httpx
from typing import Optional
from src.config.config import Config

logger = logging.getLogger(__name__)


class DrugBankTool:
    """Query DrugBank for pharmacological data relevant to caiaad interactions.

    Query modes:
    - gut_metabolism: Gut microbiota metabolism pathways for a compound
    - drug_microbiome: Known drug-microbiome interaction records
      Used by the mechanism agent for mechanism analogy
    """

    BASE_URL = "https://api.drugbank.com/v1"
    TIMEOUT = 30
    MAX_RETRIES = 2

    def run(self, query: str, query_type: str = "gut_metabolism") -> dict:
        if query_type == "gut_metabolism":
            return self.query_gut_metabolism(query)
        elif query_type == "drug_microbiome":
            return self.query_drug_microbiome(query)
        else:
            return {"error": f"Unknown query_type: {query_type}"}

    def _make_request(self, endpoint: str) -> Optional[dict]:
        headers = {
            "Authorization": f"Bearer {Config.DRUGBANK_API_KEY}",
            "Accept": "application/json"
        }
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                response = httpx.get(
                    f"{self.BASE_URL}/{endpoint}",
                    headers=headers,
                    timeout=self.TIMEOUT
                )
                if response.status_code == 200:
                    return response.json()
                logger.warning(f"DrugBank API returned {response.status_code} (attempt {attempt + 1})")
            except httpx.TimeoutException:
                logger.warning(f"DrugBank timeout (attempt {attempt + 1})")
            except Exception as e:
                logger.error(f"DrugBank request failed: {e}")
        return None

    def query_gut_metabolism(self, compound_name: str) -> dict:
        result = {
            "compound": compound_name,
            "gut_bacteria_metabolizers": [],
            "metabolites_produced": [],
            "enzyme_targets": [],
            "source": "DrugBank"
        }
        if not Config.DRUGBANK_API_KEY:
            return result
        search_result = self._make_request(f"search?q={compound_name}&type=compound")
        if not search_result:
            return result
        hits = search_result.get("hits", [])
        if not hits:
            return result
        compound_id = hits[0].get("drugbank_id", "")
        if not compound_id:
            return result
        detail = self._make_request(f"compounds/{compound_id}")
        if not detail:
            return result
        for pathway in detail.get("metabolism", {}).get("pathways", []):
            for enzyme in pathway.get("enzymes", []):
                location = enzyme.get("location", "").lower()
                notes = enzyme.get("notes", "").lower()
                organism = enzyme.get("organism", "").lower()
                if any(kw in location + notes + organism
                       for kw in ["gut", "microbiota", "bacterial", "intestinal"]):
                    result["gut_bacteria_metabolizers"].append({
                        "bacterium": enzyme.get("organism", "unknown"),
                        "enzyme": enzyme.get("name", "unknown"),
                        "reaction": enzyme.get("reaction", "unknown"),
                        "metabolite": enzyme.get("product", "unknown")
                    })
        return result

    def query_drug_microbiome(self, compound_name: str) -> dict:
        result = {
            "compound": compound_name,
            "interacting_bacteria": [],
            "effect_on_bacteria": None,
            "bacterial_metabolism": None,
            "clinical_relevance": None,
            "source": "DrugBank"
        }
        if not Config.DRUGBANK_API_KEY:
            return result
        search_result = self._make_request(f"search?q={compound_name}&type=compound")
        if not search_result:
            return result
        hits = search_result.get("hits", [])
        if not hits:
            return result
        compound_id = hits[0].get("drugbank_id", "")
        detail = self._make_request(f"compounds/{compound_id}")
        if not detail:
            return result
        microbiome = detail.get("microbiome_interactions", {})
        if microbiome:
            result["interacting_bacteria"] = microbiome.get("bacteria", [])
            result["effect_on_bacteria"] = microbiome.get("effect")
            result["bacterial_metabolism"] = microbiome.get("metabolism")
            result["clinical_relevance"] = microbiome.get("clinical_significance")
        return result
