# Import the logging module for recording runtime log messages
import logging
# Import the os module for reading environment variables
import os
# Import the Agent class from the crewai framework as the base class for all custom agents
from crewai import Agent
# Import the custom prompt loading utility, used to read prompt templates from external .md files
from src.utils.prompt_loader import load_prompt

# Configure the global logging level to WARNING,
# so only WARNING and above are emitted, avoiding DEBUG/INFO log flooding
logging.basicConfig(level=logging.WARNING)
# Get the logger instance for the current module; using __name__ tags logs with
# the module name, making it easier to trace their source
logger = logging.getLogger(__name__)

# Define the global Memory-first usage guidance text, appended to the end of each
# agent's backstory. It instructs the LLM to look for existing information in the
# context/memory first, reducing duplicate external tool calls and lowering API costs
MEMORY_GUIDANCE_EN = """

## Tool Usage Optimization Strategy ##
1. **Memory First**: Check context or memory for existing information before calling external tools
2. **Avoid Duplicate Queries**: Reuse results if material/chemical info was queried by previous tasks
3. **Minimize Tool Calls**: Only query necessary information, avoid overusing tools
4. **Result Reuse**: Pass organized query results to downstream tasks for reuse
"""


def tools_enabled() -> bool:
    """Determine whether agent tool calling is enabled.

    Controlled solely by the ENABLE_TOOLS environment variable:
    "true" (default) enables tools, anything else disables them.
    """
    return os.getenv("ENABLE_TOOLS", "true").lower() == "true"


class BaseAgent:
    """ Base class for all custom agents, providing common agent creation
        functionality. It encapsulates shared logic such as prompt loading,
        temperature parameter, and maximum iteration count."""

    # Default maximum iteration count is 10, preventing the agent from falling into
    # infinite loops or excessive tool calls. Used when a subclass does not
    # explicitly specify max_iter
    DEFAULT_MAX_ITER = 10

    def __init__(self, llm, role, goal, prompt_file, temperature=None, max_iter=None, prompt_params=None):
        # Main LLM instance, passed in externally (usually from the Crew configuration);
        # all agents share the same base LLM
        self.llm = llm
        # Agent role name (e.g. "Material_Design_Expert"), used for CrewAI's role field
        self.role = role
        # Agent goal description, used for CrewAI's goal field, guiding the LLM's behavior
        self.goal = goal
        # Path to the prompt template file, pointing to a .md file under the prompts directory
        self.prompt_file = prompt_file
        # LLM temperature parameter (controls output randomness); None means use the
        # default temperature. Subclasses can use this parameter to set different
        # creativity levels for different agents
        self.temperature = temperature
        # Maximum iteration count: prefer the passed-in max_iter, falling back to
        # DEFAULT_MAX_ITER when not provided
        self.max_iter = max_iter or self.DEFAULT_MAX_ITER
        # Parameterized substitution dictionary, used to replace {key} placeholders
        # in the backstory. For example, {"EXPERT_ID": "A"} replaces {EXPERT_ID}
        # in the prompt with "A"
        self.prompt_params = prompt_params or {}

    def _resolve_llm(self):
        """Resolve the LLM instance this agent should use.

        The externally provided ``self.llm`` is used as-is; per-agent
        ``temperature`` values are kept on the subclass constructors so a
        custom LLM can be wired in by the caller when needed.

        Returns:
            The resolved LLM instance
        """
        return self.llm

    def create_agent(self):
        """Create and return a configured CrewAI Agent instance

        This method is responsible for:
        1. Resolving the LLM via _resolve_llm()
        2. Loading the prompt template and performing parameterized substitution
        3. Appending the Memory-first usage guidance
        4. Assembling the final Agent object

        Returns:
            Agent: the fully configured CrewAI Agent instance
        """
        # Resolve the LLM used by this agent
        agent_llm = self._resolve_llm()

        # Load the backstory (prompt template) from a .md file, returning the full
        # text content
        backstory = load_prompt(self.prompt_file)

        # Parameterized substitution: if self.prompt_params is not empty, iterate
        # over all key-value pairs and replace the {key} placeholders in the
        # backstory with the corresponding value. For example {EXPERT_ID} -> "A",
        # allowing the same template to generate different prompts for different experts
        if self.prompt_params:
            for key, value in self.prompt_params.items():
                backstory = backstory.replace(f"{{{key}}}", value)

        # Append the Memory-first usage guidance text to the end of the backstory,
        # instructing each agent to obtain existing information from the
        # context/memory first, reducing unnecessary tool calls
        backstory += MEMORY_GUIDANCE_EN

        # Create and return the CrewAI Agent instance with all configuration
        # parameters:
        # - role: agent role name
        # - goal: agent goal description
        # - backstory: the complete prompt composed of the prompt template +
        #   parameter substitution + Memory guidance
        # - verbose=False: disable verbose output to avoid excessive console messages
        # - allow_delegation=False: disallow task delegation; base-class agents
        #   execute tasks directly
        # - llm: the configured LLM instance
        # - max_iter: maximum iteration limit, preventing excessive tool calls
        return Agent(
            role=self.role,
            goal=self.goal,
            backstory=backstory,
            verbose=False,
            allow_delegation=False,
            llm=agent_llm,
            max_iter=self.max_iter
        )
