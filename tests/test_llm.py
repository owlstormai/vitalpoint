from rrb.llm import maybe_rewrite


class _FakeBrief:
    markdown = "# Renewal Risk Brief — X\n- **usage_decline** — down 30%."
    citations = []


def test_no_key_returns_original(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    b = _FakeBrief()
    assert maybe_rewrite(b) is b.markdown


def test_rewrite_uses_injected_client(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    def fake_call(prompt: str) -> str:
        assert "every claim must keep its citation" in prompt.lower()
        return "REWRITTEN\n" + _FakeBrief.markdown

    out = maybe_rewrite(_FakeBrief(), _call=fake_call)
    assert out.startswith("REWRITTEN")
