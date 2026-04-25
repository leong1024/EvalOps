"""
Utility functions related to processing package metadata.
"""

import importlib.metadata


def version() -> str:
    """Return the current version of the evalops.bot package."""
    return importlib.metadata.version("evalops.bot")
