#!/usr/bin/env python3
"""Manufacturing Agent — production QC & precise-tunability scoring."""

from .base_agent import BaseAgent
from src.tools import ToolFactory


class ManufacturingAgent(BaseAgent):
    """Manufacturing quality-control scoring agent.

    Assesses whether an AD therapeutic's preparation is controllable, scalable,
    and precisely tunable in composition and dose: chemical composition
    definability, process controllability, batch consistency, dose precision,
    and scale-up feasibility.
    """

    def __init__(self, llm):
        from src.config.config import Config
        super().__init__(
            llm=llm,
            role="manufacturing",
            goal="Score manufacturing QC & precise tunability (manufacturability) of AD "
                 "therapeutics: composition definability, synthesis/process "
                 "controllability, batch-to-batch consistency, dose precision, and "
                 "scale-up feasibility, following the shared rubric anchors.",
            prompt_file="manufacturing_prompt.md",
            temperature=Config.MANUFACTURING_TEMPERATURE,
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
