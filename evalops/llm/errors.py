"""LLM runtime exceptions."""


class LLMRuntimeError(RuntimeError):
    """Base class for EvalOps LLM runtime failures."""


class LLMContextLengthExceededError(LLMRuntimeError):
    """Raised when a provider rejects a request because the context is too large."""
