from types import SimpleNamespace

from evalops.llm import runtime


def test_invoke_parses_text_part_from_structured_content(monkeypatch):
    class FakeModel:
        def invoke(self, prompt):
            return SimpleNamespace(
                content=[
                    {"type": "thinking", "thinking": "internal reasoning"},
                    {"type": "text", "text": '[{"title": "Bug"}]'},
                ]
            )

    monkeypatch.setattr(runtime, "make_chat_model", lambda: FakeModel())

    assert runtime.invoke("prompt", parse_json=True) == [{"title": "Bug"}]


def test_text_ignores_thinking_parts_in_structured_content():
    response = SimpleNamespace(
        content=[
            {"type": "thinking", "thinking": "do not render"},
            {"type": "text", "text": "Rendered summary."},
        ]
    )

    assert runtime._text(response) == "Rendered summary."
