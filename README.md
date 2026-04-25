# EvalOps

EvalOps is a Gemini-assisted code review CLI for local changes and pull requests.
It reviews git diffs, writes structured reports, and can publish review summaries back
to GitHub or GitLab.

## What It Does

- Reviews changed files with Gemini and extracts actionable issues.
- Generates a short review summary.
- Runs a DeepEval quality gate over the final review output.
- Optionally enriches reviews with repository graph context.
- Saves machine-readable and Markdown reports.

EvalOps is currently pinned to `gemma-4-31b-it`.

## Requirements

- Python 3.11+
- Git
- A Gemini API key in `GOOGLE_API_KEY`

## Install

For local development:

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

On macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Configure

Set your Gemini API key before running reviews:

```bash
evalops setup
```

Or set it directly in your shell:

```bash
export GOOGLE_API_KEY="your-gemini-api-key"
```

PowerShell:

```powershell
$env:GOOGLE_API_KEY="your-gemini-api-key"
```

## Run A Review

From the repository you want to review:

```bash
evalops review
```

EvalOps reviews the current git diff against the base branch. You do not need to
commit first; staged and unstaged changes are included.

Useful commands:

```bash
evalops --help
evalops files
evalops review --filters "*.py,src/*"
evalops review --all
```

## Review Outputs

Each review writes:

- `code-review-report.json` for structured pipeline data.
- `code-review-report.md` for human-readable output and PR/MR comments.

The report includes detected issues, summary text, processing warnings, and DeepEval
quality metadata under `pipeline_out.quality_gate`.

## Quality Gate

DeepEval quality scoring is enabled by default as a soft gate. It evaluates the final
review output against the reviewed diff using these default metrics:

- `grounding`
- `relevance`
- `severity`
- `false_positive_risk`

Soft gate results are shown in reports but do not block the review.

Override the defaults in `.evalops/config.toml`:

```toml
quality_gate_enabled = true
quality_gate_mode = "soft"
quality_gate_min_score = 0.7
quality_gate_metrics = ["grounding", "relevance", "severity", "false_positive_risk"]
```

## Graph Context

Graphify repository context is optional and disabled by default. To enable it, install
the graph extra and turn it on in `.evalops/config.toml`:

```bash
pip install -e ".[dev,graph]"
```

```toml
graph_context_enabled = true
```

Graph artifacts are stored under `.evalops/graphify/`, refreshed automatically when
the repository HEAD changes, and ignored if unavailable.

## CI Setup

Generate GitHub Actions or GitLab CI review workflows:

```bash
evalops deploy
```

Then add the required repository secret:

- `GOOGLE_API_KEY`

Optional issue tracker integrations can use:

- `LINEAR_API_KEY`
- `JIRA_URL`
- `JIRA_USER`
- `JIRA_TOKEN`

## Model Reachability Check

```bash
python scripts/test_gemma_reachability.py
```

## Development

```bash
pytest
make cs
```
