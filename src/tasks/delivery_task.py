#!/usr/bin/env python3
"""Delivery-efficiency evaluation task for the delivery scoring agent."""

from .base_task import BaseTask, load_task_text
from crewai import Task


class DeliveryTask(BaseTask):
    """Task for target-tissue delivery-efficiency evaluation of AD therapeutics."""

    # Default task text, used when the locale YAML file is absent.
    # load_task_text remains the override mechanism: when the YAML exists,
    # its values take precedence over these defaults.
    DEFAULT_DESCRIPTION = (
        "Evaluate the target-tissue delivery efficiency of each AD therapeutic "
        "candidate. For every candidate, score the three delivery dimensions — "
        "barrier penetration & bioavailability (50%), targeting & designability "
        "(30%), and exposure durability & dosing convenience (20%) — on a 1-10 "
        "scale, relative to its site of action (CNS targets via blood-brain "
        "barrier penetration, or peripheral targets). Base all "
        "scores on actual data and state explicitly when evidence is insufficient."
    )
    DEFAULT_EXPECTED_OUTPUT = (
        "JSON containing the per-dimension scores, the composite "
        "delivery_efficiency score (1-10), the main delivery bottleneck, a "
        "designability note, and a brief statement of relevance to AD therapy."
    )

    def __init__(self, agent):
        task_text = load_task_text('delivery_task')
        super().__init__(agent=agent,
                         expected_output=task_text.get('expected_output') or self.DEFAULT_EXPECTED_OUTPUT,
                         description=task_text.get('description') or self.DEFAULT_DESCRIPTION)

    def create_task(self, agent, context_task=None, user_requirement=None):
        task_text = load_task_text('delivery_task')
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
