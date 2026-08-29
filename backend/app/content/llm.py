"""Provider-agnostic chat completion for the content generators.

Groq, Gemini, OpenRouter and Ollama all expose an OpenAI-compatible /chat/completions endpoint, so
one small httpx client covers them. Anthropic uses its own SDK (structured outputs). Selection is
driven purely by settings so the provider can be swapped by editing .env.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

import httpx

from ..config import settings

log = logging.getLogger("llm")

PROVIDERS: dict[str, tuple[str, str]] = {
    # provider: (base_url, default model)
    "groq": ("https://api.groq.com/openai/v1", "openai/gpt-oss-120b"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "gemini-2.5-flash"),
    "openrouter": ("https://openrouter.ai/api/v1", "meta-llama/llama-3.3-70b-instruct:free"),
    "ollama": ("http://ollama:11434/v1", "qwen2.5:7b-instruct"),
    "anthropic": ("", "claude-opus-5"),
}


@dataclass
class LLMConfig:
    provider: str
    api_key: str
    model: str
    base_url: str

    @property
    def available(self) -> bool:
        if self.provider == "ollama":
            return True
        return bool(self.api_key)


def current_config() -> LLMConfig:
    provider = (settings.llm_provider or "groq").lower()
    if provider not in PROVIDERS:
        log.warning("unknown LLM_PROVIDER %r, falling back to groq", provider)
        provider = "groq"
    base, default_model = PROVIDERS[provider]
    key = settings.llm_api_key or (settings.anthropic_api_key if provider == "anthropic" else "")
    return LLMConfig(
        provider=provider, api_key=key or "", model=settings.llm_model or default_model,
        base_url=settings.llm_base_url or base,
    )


class LLMError(RuntimeError):
    pass


def _extract_json(text: str) -> dict:
    """Models occasionally wrap JSON in code fences or prose; recover the object."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
        raise


def complete_json(system: str, user: str, *, schema: dict | None = None, max_tokens: int = 6000,
                  cfg: LLMConfig | None = None) -> dict:
    """Return the model's JSON object for a system+user prompt. Raises LLMError on failure."""
    cfg = cfg or current_config()
    if not cfg.available:
        raise LLMError(f"no API key configured for provider {cfg.provider}")
    if cfg.provider == "anthropic":
        return _anthropic(system, user, schema=schema, max_tokens=max_tokens, cfg=cfg)
    return _openai_compatible(system, user, max_tokens=max_tokens, cfg=cfg)


def _openai_compatible(system: str, user: str, *, max_tokens: int, cfg: LLMConfig) -> dict:
    headers = {"Content-Type": "application/json"}
    if cfg.api_key:
        headers["Authorization"] = f"Bearer {cfg.api_key}"
    if cfg.provider == "openrouter":
        headers["HTTP-Referer"] = "https://github.com/aravindshajan6/mocker.ai"
        headers["X-Title"] = "Mocker quiz"
    # Groq (and some OpenAI-compatible gateways) reject json_object mode unless the word "json"
    # appears somewhere in the messages. Add it rather than letting the call 400.
    if "json" not in (system + user).lower():
        system = system.rstrip() + "\n\nRespond with a single JSON object."
    body = {
        "model": cfg.model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": 0.4,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    try:
        with httpx.Client(timeout=120) as client:
            resp = client.post(f"{cfg.base_url.rstrip('/')}/chat/completions", headers=headers, json=body)
    except httpx.HTTPError as e:
        raise LLMError(f"{cfg.provider} request failed: {e}") from e
    if resp.status_code == 429:
        raise LLMError(f"{cfg.provider} rate limited (429): {resp.text[:200]}")
    if resp.status_code >= 400:
        raise LLMError(f"{cfg.provider} HTTP {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise LLMError(f"{cfg.provider} unexpected response shape: {str(data)[:200]}") from e
    try:
        return _extract_json(text)
    except json.JSONDecodeError as e:
        raise LLMError(f"{cfg.provider} returned non-JSON: {text[:200]}") from e


def _anthropic(system: str, user: str, *, schema: dict | None, max_tokens: int, cfg: LLMConfig) -> dict:
    import anthropic

    client = anthropic.Anthropic(api_key=cfg.api_key)
    kwargs: dict = {}
    if schema:
        kwargs["output_config"] = {"format": {"type": "json_schema", "schema": schema}}
    try:
        resp = client.messages.create(
            model=cfg.model, max_tokens=max_tokens,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}], **kwargs,
        )
    except anthropic.RateLimitError as e:
        raise LLMError(f"anthropic rate limited: {e}") from e
    except anthropic.APIStatusError as e:
        raise LLMError(f"anthropic HTTP {e.status_code}: {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise LLMError(f"anthropic connection error: {e}") from e
    if resp.stop_reason == "refusal":
        raise LLMError("anthropic refused the request")
    text = next((b.text for b in resp.content if b.type == "text"), "{}")
    try:
        return _extract_json(text)
    except json.JSONDecodeError as e:
        raise LLMError(f"anthropic returned non-JSON: {text[:200]}") from e
