import logging
from importlib.metadata import version, PackageNotFoundError


def evalops_version() -> str:
    """
    Retrieve the current version of evalops.bot package.
    Returns:
        str: The version string of the evalops.bot package, or "{Dev}" if not found.
    """
    try:
        return version("evalops.bot")
    except PackageNotFoundError:
        logging.warning("Could not retrieve evalops.bot version.")
        return "{Dev}"


class Env:
    logging_level: int = 1
    verbosity: int = 1
    evalops_version: str = evalops_version()
    working_folder = "."
