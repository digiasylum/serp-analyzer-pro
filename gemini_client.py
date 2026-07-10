# gemini_client.py — SERP V8
# Thin wrapper around the Gemini API (v1beta generateContent REST endpoint).
# No SDK dependency — uses `requests`, same as the rest of this codebase.
#
# Design contract: call_gemini() NEVER raises. It always returns
# {"ok": True, "data": <parsed json>} or {"ok": False, "error": "<reason>"}.
# Every caller in ai_seo.py is expected to check "ok" and fall back to the
# formula-based function in serp_analyzer.py when it's False — a missing key,
# an expired quota, or a network blip should degrade the tool, not break it.

from __future__ import annotations
import json
import requests

GEMINI_ENDPOINT_TMPL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_MODEL = "gemini-2.5-flash"   # stable production tier; override per-call if needed
TIMEOUT = 45


def call_gemini(
    api_key: str,
    system_prompt: str,
    user_prompt: str,
    schema: dict | None = None,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.4,
) -> dict:
    """
    Call Gemini and return parsed JSON.

    - api_key: the user's Gemini API key (never hardcode one).
    - schema: a Gemini-flavoured JSON schema (types are UPPERCASE strings like
      "OBJECT", "STRING", "ARRAY", "INTEGER"). When provided, responseMimeType
      is forced to application/json so parsing is reliable.
    """
    if not api_key:
        return {"ok": False, "error": "missing_api_key"}

    url = GEMINI_ENDPOINT_TMPL.format(model=model)
    generation_config: dict = {
        "temperature": temperature,
        "maxOutputTokens": 8192,
    }
    if schema:
        generation_config["responseMimeType"] = "application/json"
        generation_config["responseSchema"] = schema

    payload = {
        "systemInstruction": {"role": "system", "parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": generation_config,
    }

    try:
        r = requests.post(url, params={"key": api_key}, json=payload, timeout=TIMEOUT)
    except requests.RequestException as e:
        return {"ok": False, "error": f"network_error: {e}"}

    if r.status_code == 400:
        return {"ok": False, "error": f"bad_request: {r.text[:200]}"}
    if r.status_code in (401, 403):
        return {"ok": False, "error": "invalid_api_key"}
    if r.status_code == 429:
        return {"ok": False, "error": "rate_limited"}
    if r.status_code >= 500:
        return {"ok": False, "error": f"gemini_server_error_{r.status_code}"}
    try:
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        return {"ok": False, "error": f"http_error: {e}"}
    except json.JSONDecodeError:
        return {"ok": False, "error": "invalid_response_json"}

    candidates = data.get("candidates", [])
    if not candidates:
        block_reason = data.get("promptFeedback", {}).get("blockReason", "unknown")
        return {"ok": False, "error": f"no_candidates_{block_reason}"}

    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts if "text" in p)
    if not text:
        finish_reason = candidates[0].get("finishReason", "unknown")
        return {"ok": False, "error": f"empty_response_{finish_reason}"}

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"parse_error: {e}"}

    return {"ok": True, "data": parsed}


def call_gemini_grounded(api_key: str, prompt: str, model: str = DEFAULT_MODEL, temperature: float = 0.3) -> dict:
    """
    Calls Gemini with the `google_search` grounding tool enabled — the model runs
    live Google searches itself and answers with citations to what it actually used.

    This is NOT a SerpAPI replacement: it doesn't expose a ranked list of organic
    results, PAA, or AI Overview data — it's a RAG-style grounded answer with
    whatever sources the model chose to cite while responding. Useful for a distinct
    signal: whether a domain gets cited when Gemini itself answers a query directly,
    as opposed to what Google's own SERP/AI Overview shows.

    Returns {"ok": True, "text": str, "citations": [{"title","url"}, ...]} or
    {"ok": False, "error": str}. Deliberately skips responseSchema/JSON mode —
    grounding + structured output don't combine reliably, so citations are read
    straight from groundingMetadata instead of parsed model text.
    """
    if not api_key:
        return {"ok": False, "error": "missing_api_key"}

    url = GEMINI_ENDPOINT_TMPL.format(model=model)
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}],
        "generationConfig": {"temperature": temperature, "maxOutputTokens": 2048},
    }

    try:
        r = requests.post(url, params={"key": api_key}, json=payload, timeout=TIMEOUT)
    except requests.RequestException as e:
        return {"ok": False, "error": f"network_error: {e}"}

    if r.status_code == 400:
        return {"ok": False, "error": f"bad_request: {r.text[:200]}"}
    if r.status_code in (401, 403):
        return {"ok": False, "error": "invalid_api_key"}
    if r.status_code == 429:
        return {"ok": False, "error": "rate_limited"}
    if r.status_code >= 500:
        return {"ok": False, "error": f"gemini_server_error_{r.status_code}"}
    try:
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        return {"ok": False, "error": f"http_error: {e}"}
    except json.JSONDecodeError:
        return {"ok": False, "error": "invalid_response_json"}

    candidates = data.get("candidates", [])
    if not candidates:
        block_reason = data.get("promptFeedback", {}).get("blockReason", "unknown")
        return {"ok": False, "error": f"no_candidates_{block_reason}"}

    cand = candidates[0]
    parts = cand.get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts if "text" in p)

    citations = []
    grounding_meta = cand.get("groundingMetadata", {}) or {}
    for chunk in grounding_meta.get("groundingChunks", []) or []:
        web = chunk.get("web", {}) or {}
        if web.get("uri"):
            citations.append({"title": web.get("title", ""), "url": web.get("uri", "")})

    if not text and not citations:
        finish_reason = cand.get("finishReason", "unknown")
        return {"ok": False, "error": f"empty_response_{finish_reason}"}

    return {"ok": True, "text": text, "citations": citations}


def validate_gemini_key(api_key: str, model: str = DEFAULT_MODEL) -> dict:
    """Lightweight validation call — mirrors utils.validate_and_get_serpapi_quota()."""
    if not api_key:
        return {"ok": False, "message": "API key is missing."}

    result = call_gemini(
        api_key=api_key,
        system_prompt="You are a health-check endpoint. Reply only with valid JSON.",
        user_prompt='Reply with exactly: {"status": "ok"}',
        schema={
            "type": "OBJECT",
            "properties": {"status": {"type": "STRING"}},
            "required": ["status"],
        },
        model=model,
        temperature=0,
    )
    if result["ok"]:
        return {"ok": True, "message": f"Gemini API key authenticated ({model})."}

    err = result.get("error", "unknown_error")
    if err == "invalid_api_key":
        return {"ok": False, "message": "Unauthorized. Gemini API key is invalid."}
    if err == "rate_limited":
        return {"ok": False, "message": "Key appears valid but is currently rate-limited."}
    if err.startswith("network_error"):
        return {"ok": False, "message": f"Network error reaching Gemini: {err}"}
    return {"ok": False, "message": f"Could not validate key ({err})."}
