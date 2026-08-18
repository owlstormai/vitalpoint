import os

PROMPT = """You are rewriting a renewal risk brief for readability.

Rules — non-negotiable:
- Every claim must keep its citation (title, date) exactly as given.
- Do not add facts, numbers, or judgments not present in the draft.
- Keep every section heading. Keep quotes verbatim.
- If unsure, keep the original sentence.

Draft brief:
{draft}
"""


def _anthropic_call(prompt: str) -> str:
    import anthropic

    client = anthropic.Anthropic()
    msg = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


def maybe_rewrite(brief, _call=None) -> str:
    """Return polished markdown when a key is present, else the draft."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return brief.markdown
    call = _call or _anthropic_call
    return call(PROMPT.format(draft=brief.markdown))
