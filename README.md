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

## Model Reachability Check

```bash
python scripts/test_gemma_reachability.py
```

## Development

```bash
make cs
pytest
```
