import asyncio
import json
import logging
from dataclasses import asdict, dataclass
from typing import Any

from deepeval.models.base_model import DeepEvalBaseLLM

from ..context import Context
from ..llm import invoke
from ..runtime import settings
from ..tokenization import fit_to_token_size


DEFAULT_METRICS = {
    "grounding": (
        "Evaluate whether every reported review issue is factually grounded in "
        "the supplied code diff and repository context. Penalize unsupported claims."
    ),
    "relevance": (
        "Evaluate whether the review output is actionable, concrete, and useful "
        "to a developer working on this change."
    ),
    "severity": (
        "Evaluate whether each issue's severity matches its actual risk and "
        "whether the review avoids overstating minor concerns."
    ),
    "false_positive_risk": (
        "Evaluate the risk that the review contains speculative, vague, or "
        "incorrect findings. Higher scores mean lower false-positive risk."
    ),
}


@dataclass
class MetricResult:
    score: float
    reason: str = ""
    status: str = "passed"

    def as_dict(self) -> dict[str, Any]:
        return {"score": self.score, "reason": self.reason, "status": self.status}


def _quality_gate_disabled(ctx: Context) -> bool:
    return not getattr(ctx.config, "quality_gate_enabled", True)


def _selected_metrics(ctx: Context) -> dict[str, str]:
    configured = getattr(ctx.config, "quality_gate_metrics", None) or list(DEFAULT_METRICS)
    return {name: DEFAULT_METRICS[name] for name in configured if name in DEFAULT_METRICS}


def _report_output(ctx: Context) -> str:
    return json.dumps(
        {
            "summary": ctx.report.summary,
            "issues": asdict(ctx.report).get("issues", {}),
            "processing_warnings": [
                asdict(warning) for warning in ctx.report.processing_warnings
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


def _diff_context(ctx: Context) -> str:
    parts, removed = fit_to_token_size(ctx.diff, ctx.config.max_code_tokens)
    context = "\n".join(str(part) for part in parts)
    if removed:
        context += f"\n\n[Trimmed {removed} diff part(s) for quality evaluation.]"
    graph_context = ctx.pipeline_out.get("graph_context")
    if graph_context:
        context += f"\n\nGraph context:\n{graph_context}"
    return context


class _EvalOpsDeepEvalModel(DeepEvalBaseLLM):
    """Small DeepEval model adapter that reuses EvalOps' configured Gemini runtime."""

    def __init__(self) -> None:
        self.model_name = settings().model

    def load_model(self):
        return self

    def generate(self, prompt: str, schema: Any | None = None) -> Any:
        response = invoke(prompt)
        if schema is None:
            return response
        try:
            return schema.model_validate_json(response)
        except Exception:
            return schema(**json.loads(response))

    async def a_generate(self, prompt: str, schema: Any | None = None) -> Any:
        return await asyncio.to_thread(self.generate, prompt, schema)

    def get_model_name(self) -> str:
        return self.model_name


def _measure_metric(name: str, criteria: str, ctx: Context) -> MetricResult:
    from deepeval.metrics import GEval
    from deepeval.test_case import LLMTestCase, LLMTestCaseParams

    metric = GEval(
        name=f"EvalOps {name}",
        criteria=criteria,
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
            LLMTestCaseParams.CONTEXT,
        ],
        threshold=getattr(ctx.config, "quality_gate_min_score", 0.7),
        model=_EvalOpsDeepEvalModel(),
    )
    test_case = LLMTestCase(
        input=_diff_context(ctx),
        actual_output=_report_output(ctx),
        context=[_diff_context(ctx)],
    )
    metric.measure(test_case)
    score = float(getattr(metric, "score", 0.0) or 0.0)
    reason = str(getattr(metric, "reason", "") or "")
    success_attr = getattr(metric, "success", None)
    if callable(success_attr):
        success = bool(success_attr())
    elif success_attr is None and hasattr(metric, "is_successful"):
        success = bool(metric.is_successful())
    else:
        success = bool(success_attr if success_attr is not None else score >= metric.threshold)
    return MetricResult(score=score, reason=reason, status="passed" if success else "warn")


def run_quality_gate(ctx: Context) -> dict[str, Any] | None:
    """Evaluate the final review once and attach a soft DeepEval result."""
    if _quality_gate_disabled(ctx):
        return None

    metrics = _selected_metrics(ctx)
    if not metrics:
        return None

    min_score = float(getattr(ctx.config, "quality_gate_min_score", 0.7))
    try:
        measured = {
            name: _measure_metric(name, criteria, ctx).as_dict()
            for name, criteria in metrics.items()
        }
    except Exception as exc:
        logging.warning("DeepEval quality gate failed open: %s", exc)
        result = {
            "status": "skipped",
            "mode": getattr(ctx.config, "quality_gate_mode", "soft"),
            "score": 0.0,
            "min_score": min_score,
            "reason": f"DeepEval quality gate skipped: {type(exc).__name__}: {exc}",
            "metrics": {},
        }
        ctx.pipeline_out["quality_gate"] = result
        return result

    score = sum(metric["score"] for metric in measured.values()) / len(measured)
    status = "passed" if score >= min_score else "warn"
    result = {
        "status": status,
        "mode": getattr(ctx.config, "quality_gate_mode", "soft"),
        "score": score,
        "min_score": min_score,
        "reason": _summarize_reasons(measured),
        "metrics": measured,
    }
    ctx.pipeline_out["quality_gate"] = result
    return result


def _summarize_reasons(metrics: dict[str, dict[str, Any]]) -> str:
    reasons = [
        f"{name}: {metric['reason']}"
        for name, metric in metrics.items()
        if metric.get("reason")
    ]
    if not reasons:
        return ""
    return " ".join(reasons)[:1000]
