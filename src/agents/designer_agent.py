# Import the logging module for recording runtime log information of the agent
import logging
# Import the BaseAgent base class; DesignerAgent inherits from it to reuse common agent creation logic
from src.agents.base_agent import BaseAgent
# Import the ToolFactory class, used to create the toolset required for material design
from src.tools import ToolFactory

# Set the global logging level of the logging module to WARNING,
# so that only warning- and error-level logs are output, avoiding INFO/DEBUG flooding
logging.basicConfig(level=logging.WARNING)
# Get the logger instance for the current module; log output carries the module name for easier troubleshooting
logger = logging.getLogger(__name__)

# AD therapeutic design expert agent class
# Responsible for designing innovative Alzheimer's disease therapeutic candidates based on user requirements
class DesignerAgent(BaseAgent):
    """Designer Agent
       Dedicated to AD therapeutic design tasks:
       - Generate therapeutic candidate designs based on user requirements
       - Query compound/target information from databases such as PubChem and UniProt
       - Output structured design results (modality, composition, mechanism hypothesis, etc.)"""

    def __init__(self, llm):
        """Initialize the designer agent

        Args:
            llm: Language model instance, passed in externally (usually from the Crew configuration or main program)
        """
        # Lazily import the Config class to avoid circular import issues at module load time
        from src.config.config import Config
        # Call the constructor of the parent class BaseAgent, passing configuration parameters specific to the design agent
        super().__init__(
            llm=llm,
            role="designer",  # Agent role name: material design expert
            goal="Design innovative Alzheimer's disease (AD) therapeutic candidates — small molecules, nano formulations, and biologics — with explicit AD mechanism hypotheses, strictly following modality classification and structural description specifications",
            # Specify the prompt template file dedicated to the design agent
            prompt_file="designer_prompt.md",
            # Read the temperature parameter dedicated to material design from Config;
            # a higher temperature can increase the diversity/creativity of design solutions
            temperature=Config.DESIGNER_TEMPERATURE,
            # max_iter=1: performance optimization, limited to only 1 iteration
            # The original value was 8; reducing the iteration count significantly lowers API call costs and speeds up responses
            max_iter=1
        )

    def create_agent(self):
        """Create and return a configured designer Agent instance

        This method overrides the parent class's create_agent, adding:
        1. Attachment of tools dedicated to therapeutic design
        2. Enhancement of the backstory (adding design output and tool usage requirements)
        (the LLM passed to the constructor is used as-is; LLM selection
        is centralized in BaseAgent._resolve_llm())

        Returns:
            Agent: The fully configured material design Agent instance
        """
        # LLM selection (EAS / standard LLM with temperature / default LLM) has been
        # unified into BaseAgent._resolve_llm(); it is no longer created repeatedly here

        # Call the parent class's create_agent() method to create the base Agent instance
        agent = super().create_agent()
        # Attach tools: decide whether to enable tool calls based on the environment
        # On some compatible-mode endpoints, tool calls may return 500 errors, so a conditional check is needed
        try:
            from src.agents.base_agent import tools_enabled
            if tools_enabled():
                # When tools are enabled: create the toolset dedicated to material design,
                # including Materials Project query, structure validation, and other tools
                agent.tools = ToolFactory.create_material_design_tools()
            else:
                # When tools are disabled: set to an empty list; the agent will rely entirely on LLM knowledge
                agent.tools = []
        except Exception:
            # On exception, enable tools by default (conservative strategy)
            agent.tools = ToolFactory.create_material_design_tools()

        # Enhance the backstory: append additional design output requirements and tool usage strategy after the original prompt
        agent.backstory += (
            "\n\nWhen outputting design results, include the following detailed information whenever possible:\n"
            "- Modality classification (small_molecule / nano_formulation / biologic / other) for every candidate\n"
            "- Modality-specific composition and structural description\n"
            "- SMILES (small molecules) or UniProt accession (biologics) — only when verified; otherwise NA, never invent\n"
            "- Explicit AD mechanism hypothesis (mechanism of action, target & pathway, delivery strategy)\n"
            "\nTool Usage Strategy (Rate Limiting & Reuse):\n"
            "- Prioritize reusing already-obtained compound or material query results; avoid duplicate database searches\n"
            "- Only call Materials Project or PubChem when essential information is missing, using minimal field sets\n"
            "- Limit result counts to avoid large-scale data retrieval\n"
        )

        return agent
