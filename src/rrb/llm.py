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


_client = None


def _anthropic_call(prompt: str) -> str:
    global _client
    import anthropic

    if _client is None:
        _client = anthropic.Anthropic()
    msg = _client.messages.create(
        model="claude-sonnet-5",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    # a truncated or empty rewrite would break the citation contract
    if msg.stop_reason == "max_tokens" or not msg.content:
        raise RuntimeError(f"unusable rewrite (stop_reason={msg.stop_reason})")
    return msg.content[0].text


def maybe_rewrite(brief, _call=None) -> str:
    """Return polished markdown when a key is present, else the draft.

    The extractive draft is always citation-faithful, so any rewrite failure
    falls back to it rather than aborting a batch run.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return brief.markdown
    call = _call or _anthropic_call
    try:
        return call(PROMPT.format(draft=brief.markdown))
    except Exception as exc:
        import sys

        print(f"rewrite failed, keeping draft: {exc}", file=sys.stderr)
        return brief.markdown
