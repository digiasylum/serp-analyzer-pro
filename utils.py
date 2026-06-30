# utils.py — SERP V6
import re, requests, tldextract
from slugify import slugify as slugify_lib

def normalize_space(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())

def domain_of(url: str) -> str:
    if not url or not isinstance(url, str): return ""
    try:
        ext = tldextract.extract(url)
        return f"{ext.domain}.{ext.suffix}" if ext.domain and ext.suffix else ""
    except Exception: return ""

def slugify(text: str) -> str:
    return slugify_lib(text)

def normalize_url(url: str) -> str:
    """YOUR FIX: strip trailing slash + lowercase before comparison"""
    if not url or not isinstance(url, str): return ""
    u = url.strip().lower()
    return u.rstrip("/")

def validate_and_get_serpapi_quota(api_key: str) -> dict:
    if not api_key: return {"ok": False, "message": "API key is missing."}
    try:
        r = requests.get("https://serpapi.com/account.json", params={"api_key": api_key}, timeout=15)
        if r.status_code == 200:
            data = r.json()
            remaining = data.get("plan_searches_left", data.get("searches_left", 0))
            return {"ok": True, "message": f"Authenticated. {remaining} searches left.",
                    "quota": {"plan_name": data.get("plan_name","N/A"), "remaining_searches": remaining}}
        elif r.status_code == 401: return {"ok": False, "message": "Unauthorized. API key is invalid."}
        else: return {"ok": False, "message": f"HTTP {r.status_code}."}
    except requests.RequestException as e: return {"ok": False, "message": f"Network error: {e}"}
