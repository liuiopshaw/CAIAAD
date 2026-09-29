#!/usr/bin/env python3
"""Safety assessment task for the safety agent."""

from .base_task import BaseTask, load_task_text
from crewai import Task


class SafetyTask(BaseTask):
    """Task for safety evaluation of AD therapeutic candidates."""

    # Default task text, used when the locale YAML file is absent.
    # load_task_text remains the override mechanism: when the YAML exists,
    # its values take precedence over these defaults.
    DEFAULT_DESCRIPTION = (
        "Evaluate the safety of each AD therapeutic candidate. For every "
        "candidate, score the five safety dimensions — cytotoxicity (30%), organ "
        "damage (25%), in-vivo toxicity (20%), environmental risk (15%), and "
        "structural stability (10%) — on a 1-10 scale. Base all scores on "
        "actual data, never fabricate toxicity results, and state explicitly "
        "when evidence is insufficient."
    )
    DEFAULT_EXPECTED_OUTPUT = (
        "JSON with per-dimension scores (cytotoxicity, organ_damage, "
        "in_vivo_toxicity, environmental_risk, structural_stability; each 1-10), "
        "the composite biosafety score (1-10), scoring rationale, the main "
        "safety risks, and evidence sources (literature/database/inference)."
    )

    def __init__(self, agent):
        task_text = load_task_text('safety_task')
        super().__init__(agent=agent,
                         expected_output=task_text.get('expected_output') or self.DEFAULT_EXPECTED_OUTPUT,
                         description=task_text.get('description') or self.DEFAULT_DESCRIPTION)

    def create_task(self, agent, context_task=None, user_requirement=None):
        task_text = load_task_text('safety_task')
        desc = task_text.get('description') or self.DEFAULT_DESCRIPTION
        if user_requirement:
            prefix = task_text.get('user_requirement_prefix', 'User requirement: ')
            desc = f"{desc}\n{prefix}{user_requirement}"
        task = Task(agent=agent,
                    expected_output=task_text.get('expected_output') or self.DEFAULT_EXPECTED_OUTPUT,
                    description=desc)
        if context_task:
            task.context = [context_task] if not isinstance(context_task, list) else context_task
        return task
