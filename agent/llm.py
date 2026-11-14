"""Claude calls for the film pipeline.

Key: ANTHROPIC_API_KEY if set, else the "Claude:" line in the keys file named by BLENDER_AGENT_KEYS
(default F:/work/keys.txt). Never printed. Every call logs its token use and cost to
<film>/llm-log.jsonl so a whole film's AI spend can be added up.
"""
import base64
import json
import os
import sys
import time
from pathlib import Path

import anthropic

KEYS = Path(os.environ.get("BLENDER_AGENT_KEYS", "F:/work/keys.txt"))
MODEL = "claude-opus-5-5"
PRICE_IN, PRICE_OUT = 4.00, 20.00          # $ per million tokens (Opus 5.5)
BETAS = ["server-side-fallback-2026-07-01"]  # a declined request is re-run on Anthropic's recommended fallback


def _key() -> str:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return os.environ["ANTHROPIC_API_KEY"]
    for line in KEYS.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].rstrip(":").lower() == "claude":
            return parts[1]
    sys.exit(f"Set ANTHROPIC_API_KEY or add a Claude: line to {KEYS}")


_client = None


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=_key(), max_retries=4)
    return _client


def strict(schema):
    """Make a JSON schema acceptable to structured outputs: every object closed, every property required."""
    if isinstance(schema, dict):
        out = {k: strict(v) for k, v in schema.items()}
        if out.get("type") == "object" and "properties" in out:
            out["additionalProperties"] = False
            out["required"] = list(out["properties"].keys())
        return out
    if isinstance(schema, list):
        return [strict(s) for s in schema]
    return schema


def image_block(path) -> dict:
    p = Path(path)
    media = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
    return {"type": "image", "source": {"type": "base64", "media_type": media,
                                        "data": base64.standard_b64encode(p.read_bytes()).decode()}}


def ask(prompt, *, system: str, schema: dict | None = None, effort: str = "high", log: Path | None = None,
        label: str = "", max_tokens: int = 64000):
    """One streamed request. Returns parsed JSON when a schema is given, else text.

    `prompt` is a string or a list of content blocks (text + images)."""
    content = prompt if isinstance(prompt, list) else [{"type": "text", "text": prompt}]
    output_config = {"effort": effort}
    if schema is not None:
        output_config["format"] = {"type": "json_schema", "schema": strict(schema)}
    t0 = time.time()
    with client().beta.messages.stream(
        model=MODEL, max_tokens=max_tokens, betas=BETAS, fallbacks="default",
        thinking={"type": "adaptive"}, output_config=output_config,
        system=system, messages=[{"role": "user", "content": content}],
    ) as stream:
        msg = stream.get_final_message()
    if msg.stop_reason == "refusal":
        raise RuntimeError(f"{label}: request declined ({getattr(msg, 'stop_details', None)})")
    if msg.stop_reason == "max_tokens":
        raise RuntimeError(f"{label}: hit max_tokens before finishing")
    text = "".join(b.text for b in msg.content if b.type == "text")
    u = msg.usage
    cost = (u.input_tokens * PRICE_IN + u.output_tokens * PRICE_OUT) / 1e6
    entry = {"label": label, "model": msg.model, "in": u.input_tokens, "out": u.output_tokens,
             "usd": round(cost, 4), "secs": round(time.time() - t0, 1)}
    print(f"  [claude] {label}: {u.input_tokens} in / {u.output_tokens} out, ${cost:.3f}, {entry['secs']} s", flush=True)
    if log:
        with open(log, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    return json.loads(text) if schema is not None else text
