"""
Constants used throughout the EvalOps project.
"""

from pathlib import Path
from .env import Env

PROJECT_EVALOPS_FOLDER = ".evalops"
PROJECT_CONFIG_FILE_NAME = "config.toml"
# Standard project config file path relative to the current project root
PROJECT_CONFIG_FILE_PATH = Path(".evalops") / PROJECT_CONFIG_FILE_NAME
PROJECT_CONFIG_BUNDLED_DEFAULTS_FILE = Path(__file__).resolve().parent / PROJECT_CONFIG_FILE_NAME
HOME_ENV_PATH = Path("~/.evalops/.env").expanduser()
JSON_REPORT_FILE_NAME = "code-review-report.json"
GITHUB_MD_REPORT_FILE_NAME = "code-review-report.md"
EXECUTABLE = "evalops"
TEXT_ICON_URL = "https://raw.githubusercontent.com/<your-org>/<your-repo>/main/press-kit/logo/evalops-bot-1_64top.png"  # noqa: E501
HTML_TEXT_ICON = f'<a href="https://github.com/<your-org>/<your-repo>"><img src="{TEXT_ICON_URL}" align="left" width=64 height=50 title="EvalOps v{Env.evalops_version}"/></a>'  # noqa: E501
HTML_CR_COMMENT_MARKER = "<!-- EVALOPS_COMMENT:CODE_REVIEW_REPORT -->"
REFS_VALUE_ALL = "!all"
DEFAULT_MAX_CONCURRENT_TASKS = 40
