# EvalOps

Technical implementation of a Gemini-assisted code review CLI.

## Requirements

- Python 3.11+
- Git

## Install

```bash
pip install -e ".[dev]"
```

## Run

```bash
export GOOGLE_API_KEY="your-gemini-api-key"
evalops --help
evalops review
```

EvalOps is pinned to model `gemma-4-31b-it`.

## Quality Gate And Graph Context

DeepEval quality scoring is enabled by default as a soft gate. Results are saved in
`code-review-report.json` under `pipeline_out.quality_gate` and shown in PR/MR comments
without blocking the review.

Graphify repository context is optional and disabled by default. To enable it, install the
graph extra and set `graph_context_enabled = true` in `.evalops/config.toml`:

```bash
pip install "evalops.bot[graph]"
```

Graph artifacts are persisted under `.evalops/graphify/`, refreshed automatically when
the repository HEAD changes, and the review falls back to diff-only context if Graphify
is unavailable.

## Model Reachability Check

```bash
python scripts/test_gemma_reachability.py
```

## Development

```bash
make cs
pytest
```
