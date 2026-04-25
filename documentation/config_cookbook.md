
# <a href="https://github.com/Nayjest/EvalOps"><img src="https://raw.githubusercontent.com/Nayjest/EvalOps/main/press-kit/logo/evalops-bot-1_64top.png" align="left" width=64 height=50 title="EvalOps: AI Code Reviewer"></a>Configuration Cookbook

This document provides a comprehensive guide on how to configure and tune [EvalOps AI Code Reviewer](https://pypi.org/project/evalops.bot/) using project-specific configuration.

## Project-specific configuration
When run locally or via GitHub/GitLab actions, [EvalOps](https://pypi.org/project/evalops.bot/)
looks for `.evalops/config.toml` file in the root directory of reviewed project / repository.  
Then it merges project-specific configuration (if exists) with the
[bundled configuration defaults](https://github.com/Nayjest/EvalOps/blob/main/evalops/config.toml).  
This allows you to customize the behavior of the AI code review tool according to your project's needs.


## How to add custom code review rule?
```toml
[prompt_vars]
requirements = """
- Issue descriptions should be written on Ukrainian language
  (Опис виявлених проблем має бути Українською мовою)
"""
# this instruction affects only summary text generation, not the issue detection itself
summary_requirements = """
- Rate the code quality of introduced changes on a scale from 1 to 100, where 1 is the worst and 100 is the best.
"""
```

## Where can I see all available configuration options?
Check **bundled configuration defaults** here:  
https://github.com/Nayjest/EvalOps/blob/main/evalops/config.toml

## How do I configure advanced language model settings?

EvalOps uses the [ai-microcore](https://github.com/Nayjest/ai-microcore) package for vendor-agnostic LLM inference.  
All language model settings are configured via OS environment variables or `.env` files.

**Default configuration file:** `~/.evalops/.env`  
*(Created automatically via `evalops setup`)*

This file is used for local setups and applies across all projects unless overridden.

In the CI workflows you typically can define OS environment variables in the workflow file itself. For passing API keys securely, use GitHub / GitLab secrets functionality within the workflow.

For the full list of supported configuration options, see:
- ai-microcore configuration guide:  
  https://github.com/Nayjest/ai-microcore?tab=readme-ov-file#%EF%B8%8F-configuring
- ai-microcore configuration schema:  
  https://github.com/Nayjest/ai-microcore/blob/main/microcore/configuration.py
