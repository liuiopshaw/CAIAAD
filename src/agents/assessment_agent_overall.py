# Import the logging module for recording runtime logs, making it easier to debug and trace agent behavior
import logging
# Import the BaseAgent base class from the base_agent module of the current package (agents)
# Use a relative import (.), indicating that base_agent is in the same directory as this file
from .base_agent import BaseAgent
# Import ToolFactory from the tools module, used to uniformly create and manage the tool set used by the agent
from src.tools import ToolFactory

# Configure basic logging parameters: set the log level to WARNING, filtering out redundant INFO/DEBUG messages
# This way only warnings and higher-level logs are output, avoiding excessive unnecessary console output
logging.basicConfig(level=logging.WARNING)
# Get the logger instance for the current module; all subsequent log output goes through this logger
logger = logging.getLogger(__name__)

# Comprehensive assessment expert class (final aggregation expert)
# Inherits from BaseAgent; it does not evaluate materials directly, but aggregates the evaluation results
# of the three experts (A/B/C), performs weighted calculations and consistency analysis, and generates
# the final comprehensive evaluation report
class AssessmentAgentOverall(BaseAgent):
    """Comprehensive assessment expert agent
    Responsible for aggregating the evaluation results of each expert, performing weighted calculations,
    and generating the final material evaluation report and improvement suggestions
    """

    def __init__(self, llm):
        # Lazily import the Config configuration class to avoid circular import issues at module load time
        from src.config.config import Config
        # Call the constructor of the base class BaseAgent, passing in all core parameters of the agent
        super().__init__(
            llm=llm,
            # Role identifier: comprehensive assessment expert (final validation expert)
            # This is the last step in the multi-agent collaboration workflow, responsible for integrating all experts' opinions
            role="assessment_agent_overall",
            # Goal description: clearly tells the agent that its task is to aggregate expert results, perform weighted
            # calculations, and generate the final report; it must also provide improvement suggestions so that the
            # output contains not only evaluation conclusions but also actionable guidance
            goal="Synthesize evaluation results from various experts, perform weighted calculations, and generate the final AD candidate evaluation report, while providing improvement suggestions",
            # Specify the prompt template file (Markdown format) used by this agent
            prompt_file="assessment_agent_overall_prompt.md",
            # Read the dedicated temperature parameter for the final validation expert from the config file,
            # controlling the randomness of LLM output
            temperature=Config.ASSESSMENT_OVERALL_TEMPERATURE,
            # Maximum number of iterations set to 1:
            # Following the "less is more" principle, reduced from the original 8 iterations to 1,
            # because this agent only aggregates existing results and does not need iterative reasoning
            max_iter=1
        )

    def create_agent(self):
        """Create and return the configured Agent instance for the final validation expert

        This method overrides the parent class's create_agent, adding:
        1. Attachment of the unified assessment toolset (same as Experts A/B/C)
        2. An appended note clarifying its aggregation role

        Returns:
            Agent: The configured Agent instance for the final validation expert
        """
        # LLM selection (EAS / standard LLM with temperature / default LLM) has been unified into
        # BaseAgent._resolve_llm(); it is no longer created repeatedly here

        # Call the base class's create_agent method to complete the basic creation and configuration of the agent instance
        agent = super().create_agent()

        # Attach the toolset: use the unified assessment toolset (shared with Experts A/B/C),
        # because the final validation prompt requires verifying claimed compound identities,
        # structures, environmental-risk and availability data through actual tool calls
        try:
            from src.agents.base_agent import tools_enabled
            if tools_enabled():
                # When tools are enabled: create the unified assessment toolset
                agent.tools = ToolFactory.create_unified_assessment_tools()
            else:
                # When tools are disabled: set to an empty list
                # The agent will rely entirely on LLM knowledge and the evaluation criteria in the backstory
                agent.tools = []
        except Exception:
            # On exception, enable tools by default (conservative strategy, prioritizing functional completeness)
            agent.tools = ToolFactory.create_unified_assessment_tools()

        # Enhance the prompt to clearly state its aggregation role:
        # Append an explanation after the existing backstory so the LLM clearly knows that:
        # 1. Its core responsibility is to collect the evaluation results of AssessmentAgentA, B, and C
        # 2. It needs to perform weighted calculations and consistency analysis
        # 3. It does not need to re-evaluate the material itself, only synthesize existing opinions
        # This prevents the LLM from re-evaluating, avoiding information redundancy and resource waste
        agent.backstory += "\n\nYour core responsibility is to collect evaluation results from three experts (AssessmentAgentA, B, C), perform weighted calculations and consistency analysis, and generate the final report. You do not need to re-evaluate the material itself, but synthesize existing opinions."

        # Return the fully configured comprehensive assessment agent instance for use by upstream callers
        return agent
