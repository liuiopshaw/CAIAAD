#!/usr/bin/env python3
"""
Tool Call Specification Module
Defines the tool inventory and tool call validation logic required by each Agent.

Design goals:
- Centrally manage which tools each Agent needs to call
- Provide a unified result validation interface to ensure tool-returned data matches the expected format
- Support context cache reuse to avoid repeated external API calls
"""

# Logging module, used to output warning messages when validation fails
import logging
# The typing module is used for type annotations, improving code readability and IDE support
from typing import Dict, Any, List


# =============================================================================
# Lazily imported tool getter functions
# Uses the lazy import pattern to avoid circular import issues.
# Dependencies between modules are complex; importing inside functions breaks circular dependency chains.
# =============================================================================

def get_material_identifier_tool():
    """
    Get the material identifier tool instance (lazy import).

    Import inside the function to avoid module-level circular dependencies:
    tool_call_spec -> material_identifier_tool -> other modules -> tool_call_spec
    """
    from src.tools.material_identifier_tool import get_material_identifier_tool as _get_material_identifier_tool
    return _get_material_identifier_tool()

def get_structure_validator_tool():
    """
    Get the structure validator tool instance (lazy import).
    Lazy import avoids circular dependencies with the structure_validator_tool module.
    """
    from src.tools.structure_validator_tool import get_structure_validator_tool as _get_structure_validator_tool
    return _get_structure_validator_tool()

def get_materials_project_tool():
    """
    Get the Materials Project database query tool instance (lazy import).
    Materials Project is a materials science database for querying inorganic crystal structure data.
    """
    from src.tools.materials_project_tool import get_materials_project_tool as _get_materials_project_tool
    return _get_materials_project_tool()

def get_pubchem_tool():
    """
    Get the PubChem database query tool instance (lazy import).
    PubChem is the chemical molecule database of the US National Institutes of Health (NIH), used to query organic compound information.
    """
    from src.tools.pubchem_tool import get_pubchem_tool as _get_pubchem_tool
    return _get_pubchem_tool()

# Configure the logger for this module
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class ToolCallSpec:
    """
    Base class for tool call specifications.

    Provides tool result validation methods shared by all Agents.
    Each validation method checks whether the tool-returned result meets the expected format and content requirements.
    Subclasses can inherit these validation methods and add Agent-specific validation logic.
    """

    @staticmethod
    def validate_material_identifier_result(result: Dict[str, Any]) -> bool:
        """
        Validate the completeness and validity of the material identifier tool result.

        Validation steps:
        1. Confirm the result is a dict
        2. Check that all required fields exist
        3. Confirm the validation status passed (is_verified is True)

        Args:
            result: The result dictionary returned by the material identifier tool

        Returns:
            bool: Whether validation passed. True means the result format is correct and the content is valid
        """
        # Step 1: basic type check - the result must be a dict
        if not isinstance(result, dict):
            return False

        # Step 2: check that all required fields exist
        # query: original query string, material_type: material type (metal/organic)
        # identifier: material identifier (e.g. chemical formula), identifier_type: identifier type
        # validation_status: validation status, is_verified: whether verification passed
        required_fields = ["query", "material_type", "identifier", "identifier_type", "validation_status", "is_verified"]
        for field in required_fields:
            if field not in result:
                # Log a warning when a required field is missing, helping developers locate data issues
                logger.warning(f"Material identifier result missing required field: {field}")
                return False

        # Step 3: confirm the material identification passed validation
        # is_verified being True means the tool has confirmed the material identifier is valid
        # Use .get() to safely retrieve the value, defaulting to False to avoid KeyError
        if result.get("is_verified", False) is not True:
            logger.warning(f"Material identifier validation failed: {result.get('query', 'Unknown')}")
            return False

        return True

    @staticmethod
    def validate_structure_validator_result(result: Dict[str, Any]) -> bool:
        """
        Validate the completeness and validity of the structure validator tool result.

        Validation steps:
        1. Confirm the result is a dict
        2. Check that all required fields exist
        3. Confirm the structure is valid (valid is True)
        4. Confirm the validation confidence is "high" (high confidence)

        Args:
            result: The result dictionary returned by the structure validator tool

        Returns:
            bool: Whether validation passed
        """
        # Basic type check
        if not isinstance(result, dict):
            return False

        # Check required fields:
        # query: queried material chemical formula, valid: whether the structure is valid
        # type: material type, source: data source, reason: reason for the validation conclusion
        # validation_confidence: validation confidence (high/medium/low)
        required_fields = ["query", "valid", "type", "source", "reason", "validation_confidence"]
        for field in required_fields:
            if field not in result:
                logger.warning(f"Structure validation result missing required field: {field}")
                return False

        # Confirm the structure was judged valid
        if result.get("valid", False) is not True:
            logger.warning(f"Material structure validation failed: {result.get('query', 'Unknown')}")
            return False

        # Confirm the validation confidence is "high" (only high confidence is considered reliable)
        # If the confidence is "low" or "medium", the data source is not authoritative enough or uncertainty exists
        if result.get("validation_confidence", "low") != "high":
            logger.warning(f"Material structure validation confidence insufficient: {result.get('query', 'Unknown')}")
            return False

        return True

    @staticmethod
    def validate_materials_project_result(result: Dict[str, Any]) -> bool:
        """
        Validate the completeness and validity of the Materials Project tool result.

        Materials Project is dedicated to querying data such as electronic structure and
        thermodynamic properties of inorganic crystalline materials (e.g. metal alloys, ceramics).

        Validation steps:
        1. Confirm the result is a dict
        2. Check for an error field (i.e. the API returned an error)
        3. Confirm the data field exists and is non-empty

        Args:
            result: The result dictionary returned by the Materials Project tool

        Returns:
            bool: Whether validation passed
        """
        # Basic type check
        if not isinstance(result, dict):
            return False

        # Check whether the API returned an error
        # If result contains an "error" key, the external API call failed
        if "error" in result:
            logger.warning(f"Materials Project tool returned error: {result['error']}")
            return False

        # Confirm the returned result contains a data field
        # The data field is usually a list of dicts, each element representing a matched material entry
        if "data" not in result:
            logger.warning("Materials Project result missing data field")
            return False

        # Confirm the data field is non-empty (i.e. data was actually found)
        # Empty data means no matching material, which is also a validation failure
        if not result["data"]:
            logger.warning("Materials Project returned empty data")
            return False

        return True

    @staticmethod
    def validate_pubchem_result(result: Dict[str, Any]) -> bool:
        """
        Validate the completeness and validity of the PubChem tool result.

        PubChem is used to query organic compound information; the returned structure contains PropertyTable.Properties.

        Validation steps:
        1. Confirm the result is a dict
        2. Check for an error field
        3. Check the structural integrity of PropertyTable -> Properties level by level
        4. Confirm the Properties data is non-empty

        Args:
            result: The result dictionary returned by the PubChem tool

        Returns:
            bool: Whether validation passed
        """
        # Basic type check
        if not isinstance(result, dict):
            return False

        # Check whether the API returned an error
        if "error" in result:
            logger.warning(f"PubChem tool returned error: {result['error']}")
            return False

        # Check the top-level structure of the PubChem result: it must contain PropertyTable
        # PropertyTable is the standard response structure of the PubChem API
        if "PropertyTable" not in result:
            logger.warning("PubChem result missing PropertyTable field")
            return False

        # Check whether PropertyTable contains the Properties field
        # Properties is a list where each element is a dict of compound properties
        if "Properties" not in result["PropertyTable"]:
            logger.warning("PubChem result missing Properties field")
            return False

        # Confirm the Properties list is non-empty
        # Empty Properties means no compound data was found
        if not result["PropertyTable"]["Properties"]:
            logger.warning("PubChem returned empty Properties data")
            return False

        return True

