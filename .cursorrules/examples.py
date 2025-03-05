"""Example module demonstrating Python coding standards.

This module provides examples of proper code style, documentation, and type annotations
for this project. Use these examples as templates for your own code.
"""

from typing import Dict, List, Optional, Tuple, Any
import logging


# Configure logging
logger = logging.getLogger(__name__)


def example_function(param1: str, param2: Optional[int] = None) -> Dict[str, Any]:
    """Perform a sample operation on input parameters.

    This function demonstrates proper function definition with type annotations,
    docstrings, and implementation following project standards.

    Args:
        param1: A string input to process
        param2: An optional integer parameter with a default value of None

    Returns:
        A dictionary containing the processed results

    Raises:
        ValueError: If param1 is empty
    """
    if not param1:
        logger.error("Empty param1 provided")
        raise ValueError("param1 cannot be empty")

    # Log debug information
    logger.debug("Processing with param1=%s, param2=%s", param1, param2)

    # Default value for optional parameter
    value = param2 if param2 is not None else 0

    # Create and return result
    result = {
        "original": param1,
        "modified": f"{param1}_{value}",
        "length": len(param1),
        "value": value,
    }

    logger.info("Successfully processed input: %s", param1)
    return result


class ExampleClass:
    """A sample class demonstrating class structure and documentation.

    This class shows how to properly structure and document a Python class
    including initialization, properties, and methods.
    """

    def __init__(self, name: str, values: Optional[List[int]] = None):
        """Initialize the ExampleClass.

        Args:
            name: The name identifier for this instance
            values: Optional list of integer values, defaults to empty list
        """
        self.name = name
        self.values = values if values is not None else []
        logger.info("Created new ExampleClass: %s", self.name)

    def process_values(self) -> Tuple[int, float]:
        """Process the stored values and return statistics.

        Returns:
            A tuple containing (count, average) of the values

        Raises:
            ValueError: If no values are stored
        """
        if not self.values:
            logger.warning("No values available for processing in %s", self.name)
            raise ValueError("No values to process")

        count = len(self.values)
        average = sum(self.values) / count

        logger.debug("Processed %d values with average %f", count, average)
        return count, average