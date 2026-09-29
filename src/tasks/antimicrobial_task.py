#!/usr/bin/env python3
"""Antimicrobial evaluation task for the antimicrobial agent."""

from .base_task import BaseTask, load_task_text


class AntimicrobialTask(BaseTask):
    """Task for selective antibacterial performance evaluation."""

    # Default task text, used when the locale YAML file is absent.
    # load_task_text remains the override mechanism: when the YAML exists,
    # its values take precedence over these defaults.
    DEFAULT_DESCRIPTION = (
        "Evaluate the selective antibacterial performance of each AD therapeutic "
        "candidate for Alzheimer's disease therapy via gut microbiota modulation. "
        "For every candidate, score the four antimicrobial dimensions — bactericidal potency "
        "(40%), pathogen-probiotic selectivity (35%), spectrum breadth (15%), and "
        "resistance risk (10%) — on a 1-10 scale. Distinguish in-vitro evidence "
        "from in-vivo evidence, base all scores on actual data, and state "
        "explicitly when evidence is insufficient."
    )
    DEFAULT_EXPECTED_OUTPUT = (
        "JSON with per-dimension scores (potency, selectivity, spectrum, "
        "resistance_risk; each 1-10), the composite antibacterial score (1-10), "
        "scoring rationale, an in_vitro_vs_in_vivo evidence note, and a brief "
        "statement of relevance to AD therapy via gut microbiota modulation."
    )

    def __init__(self, agent):
        task_text = load_task_text('antimicrobial_task')
        super().__init__(
            agent=agent,
            expected_output=task_text.get('expected_output') or self.DEFAULT_EXPECTED_OUTPUT,
            description=task_text.get('description') or self.DEFAULT_DESCRIPTION
        )

    def create_task(self, agent, context_task=None, user_requirement=None):
        task_text = load_task_text('antimicrobial_task')
        desc = task_text.get('description') or self.DEFAULT_DESCRIPTION
        if user_requirement:
            prefix = task_text.get('user_requirement_prefix', 'User requirement: ')
            desc = f"{desc}\n{prefix}{user_requirement}"

        from crewai import Task
        task = Task(
            agent=agent,
            expected_output=task_text.get('expected_output') or self.DEFAULT_EXPECTED_OUTPUT,
            description=desc
        )
        if context_task:
            task.context = [context_task] if not isinstance(context_task, list) else context_task
        return task
