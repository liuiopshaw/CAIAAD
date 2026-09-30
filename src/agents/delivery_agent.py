#!/usr/bin/env python3
"""Delivery Agent — target-tissue delivery evaluation."""

from .base_agent import BaseAgent
from src.tools import ToolFactory


class DeliveryAgent(BaseAgent):
    """Target-tissue delivery efficiency scoring agent.

    Assesses whether an AD therapeutic effectively reaches its site of action
    (barrier penetration & bioavailability, targeting & designability, exposure
    durability). Scoring follows the shared rubric anchors.
    """

    def __init__(self, llm):
        from src.config.config import Config
        super().__init__(
            llm=llm,
            role="delivery",
            goal="Score target-tissue delivery efficiency (delivery_efficiency) of AD therapeutics: "
                 "barrier penetration & bioavailability, targeting & designability, and exposure "
                 "durability, following the shared rubric anchors.",
            prompt_file="delivery_prompt.md",
            temperature=Config.DELIVERY_TEMPERATURE,
            max_iter=1
        )

    def create_agent(self):
        agent = super().create_agent()
        try:
            from src.agents.base_agent import tools_enabled
            if tools_enabled():
                agent.tools = ToolFactory.create_unified_assessment_tools()
            else:
                agent.tools = []
        except Exception:
            agent.tools = ToolFactory.create_unified_assessment_tools()
        return agent
