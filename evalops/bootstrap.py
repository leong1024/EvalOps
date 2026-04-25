"""Bootstrap module for initializing the EvalOps application environment."""

import os
import sys
import io
import logging
from datetime import datetime
from pathlib import Path

from .utils.git_platform.gitlab import is_running_in_gitlab_ci
from .utils.git_platform.github import is_running_in_github_action
from .constants import HOME_ENV_PATH, EXECUTABLE, PROJECT_EVALOPS_FOLDER, DEFAULT_MAX_CONCURRENT_TASKS
from .env import Env
from .prompts import configure_template_paths
from .runtime import LLMConfigError, configure, settings
from .ui import ui


def setup_logging(log_level: int = logging.INFO):
    """Setup custom CLI logging format with colored output."""

    class CustomFormatter(logging.Formatter):
        def format(self, record):
            dt = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
            message, level_name = record.getMessage(), record.levelname
            if record.levelno == logging.WARNING:
                message = ui.yellow(message)
                level_name = ui.yellow(level_name)
            if record.levelno >= logging.ERROR:
                message = ui.red(message)
                level_name = ui.red(level_name)

            formatted_message = f"{dt} {level_name}: {message}"
            if record.exc_info:
                formatted_message += "\n" + self.formatException(record.exc_info)
            return formatted_message

    handler = logging.StreamHandler()
    handler.setFormatter(CustomFormatter())
    logging.basicConfig(level=log_level, handlers=[handler])


def bootstrap(verbosity: int = 1):
    """Bootstrap the application with the environment configuration."""
    log_levels_by_verbosity = {
        0: logging.CRITICAL,
        1: logging.INFO,
        2: logging.INFO,
        3: logging.DEBUG,
    }
    Env.verbosity = verbosity
    Env.logging_level = log_levels_by_verbosity.get(verbosity, logging.INFO)
    setup_logging(Env.logging_level)
    logging.info(
        f"Bootstrapping EvalOps v{Env.evalops_version}... " + ui.gray(f"[verbosity={verbosity}]")
    )

    # cp1251 is used on Windows when redirecting output
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    try:
        configure(
            dot_env_file=HOME_ENV_PATH,
            PROMPT_TEMPLATES_PATH=[PROJECT_EVALOPS_FOLDER, Path(__file__).parent / "tpl"],
        )
        configure_template_paths(settings().prompt_templates_path)
        if settings().max_concurrent_tasks is None:
            settings().max_concurrent_tasks = DEFAULT_MAX_CONCURRENT_TASKS

    except LLMConfigError as e:
        msg = str(e).strip()
        if not msg.endswith((".", "!", "?")):
            msg += "."
        if is_running_in_github_action():
            ref = os.getenv("GITHUB_WORKFLOW_REF", "")
            if ref:
                # example value: 'owner/repo/.github/workflows/ai-code-review.yml@refs/pull/1/merge'
                ref = ref.split("@")[0]
                ref = ref.split(".github/workflows/")[-1]
                ref = f" (.github/workflows/{ref})"
            msg += (
                f"\nPlease check your GitHub Action secrets "
                f"and `env` configuration section of the corresponding workflow step{ref}.\n"
                f"See https://github.com/<your-org>/<your-repo>/blob/main/documentation/github_setup.md "
                f"for details."
            )
        elif is_running_in_gitlab_ci():
            # @TODO add link to GitLab setup article
            msg += (
                "\nPlease check your GitLab CI/CD Variables "
                "and `variables` configuration section of the corresponding job."
            )
        else:
            msg += (
                f"\nPlease run '{EXECUTABLE} setup' "
                "to configure LLM API access (API keys, model, etc)."
            )
        print(ui.red(msg))
        raise SystemExit(2)
    except Exception as e:
        logging.error(f"Unexpected configuration error: {e}")
        raise SystemExit(3)
