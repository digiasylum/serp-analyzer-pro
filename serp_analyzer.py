# serp_analyzer.py — SERP V7
# NEW: detect_content_style() — tone classification per competitor page
# NEW: fetch_backlink_signals() now integrated alongside position tracking
# All V6 features retained

import requests, re, html
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from readability import Document
from bs4 import BeautifulSoup
from utils import normalize_space, domain_of, normalize_url
import content_grader

SERPAPI_ENDPOINT = "https://serpapi.com/search.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}

_TAG_RE = re.compile(r"<[^>]+>|;[a-z\-]+:[^;\"'>]+;?\">?", re.IGNORECASE)
def _clean(text: str) -> str:
    return normalize_space(_TAG_RE.sub("", text or ""))

# ── Tone / Style Detector ─────────────────────────────────────────────────────
def detect_content_style(full_text: str, avg_sent_len: float, word_count: int) -> dict:
    """
    Pattern-based content style detection.
    Returns: style label + confidence signals.
    """
    text_lower = full_text.lower()
    signals = {}

    # Listicle signals
    list_patterns = len(re.findall(r'\b(top \d+|best \d+|\d+ ways|\d+ tips|\d+ reasons|\d+ steps)', text_lower))
    numbered_lines = len(re.findall(r'^\s*\d+[\.\)]\s', full_text, re.MULTILINE))
    signals["listicle"] = list_patterns * 3 + numbered_lines

    # How-to signals
    how_patterns = len(re.findall(r'\b(how to|step \d+|first[,\s]|next[,\s]|then[,\s]|finally[,\s]|follow these)', text_lower))
    signals["how_to"] = how_patterns * 2

    # Review signals
    review_patterns = len(re.findall(r'\b(pros and cons|verdict|rating|out of \d+|stars?|recommend|worth it|bottom line)', text_lower))
    signals["review"] = review_patterns * 3

    # Authoritative signals (longer sentences, formal tone, data references)
    formal_patterns = len(re.findall(r'\b(according to|research shows|studies indicate|data suggests|percent|statistics|evidence)', text_lower))
    auth_score = formal_patterns * 2 + (5 if avg_sent_len > 20 else 0) + (3 if word_count > 1500 else 0)
    signals["authoritative"] = auth_score

    # Conversational signals (short sentences, first/second person, contractions)
    conv_patterns = len(re.findall(r"\b(you|you'll|you're|you've|we|let's|don't|isn't|it's|that's)\b", text_lower))
    conv_score = conv_patterns + (4 if avg_sent_len < 14 else 0)
    signals["conversational"] = conv_score

    # Pick winner
    style = max(signals, key=signals.get)
    style_labels = {
        "listicle":      "📋 Listicle",
        "how_to":        "🔧 How-to Guide",
        "review":        "⭐ Review / Comparison",
        "authoritative": "📚 Authoritative / Research",
        "conversational":"💬 Conversational",
    }
    confidence = signals[style]
    if confidence == 0: style = "authoritative"
    return {
        "style":  style_labels.get(style, "📄 General"),
        "key":    style,
        "scores": signals,
    }

# ── SERP Fetching — paginated for >10 results ────────────────────────────────
# SerpAPI returns max 10 organic results per call regardless of `num`.
# For >10 we must paginate using `start` (0, 10, 20…) and merge organics.

def fetch_serp(api_key: str, query: str, gl: str = "in", hl: str = "en", num: int = 10) -> dict:
    """
    Fetch organic SERP results for `query`.
    Paginates transparently when num > 10 — each page costs 1 SerpAPI credit.
    Returns a single merged dict with all organic_results combined.
    """
    num = min(num, 100)
    page_size = 10  # SerpAPI hard limit per call

    if num <= page_size:
        # Single call — no pagination needed
        # Always pass num explicitly so SerpAPI doesn't default to 10
        params = {
            "engine": "google", "q": query, "api_key": api_key,
            "gl": gl, "hl": hl, "num": num,
        }
        try:
            r = requests.get(SERPAPI_ENDPOINT, params=params, timeout=30)
            r.raise_for_status()
            return r.json()
        except Exception:
            return {}

    # Multi-page: fetch pages concurrently to minimise wall time
    starts      = list(range(0, num, page_size))           # [0, 10, 20, ...]
    page_results: dict[int, dict] = {}

    def _fetch_page(start: int) -> tuple[int, dict]:
        params = {
            "engine": "google", "q": query, "api_key": api_key,
            "gl": gl, "hl": hl, "num": page_size, "start": start,
        }
        try:
            r = requests.get(SERPAPI_ENDPOINT, params=params, timeout=45)
            r.raise_for_status()
            return start, r.json()
        except Exception:
            return start, {}

    with ThreadPoolExecutor(max_workers=min(len(starts), 5)) as ex:
        futures = {ex.submit(_fetch_page, s): s for s in starts}
        for fut in as_completed(futures):
            start, data = fut.result()
            page_results[start] = data

    # Use first page as the base (contains metadata, AI overview, PAA, etc.)
    base = page_results.get(0, {})
    if not base:
        return {}

    # Merge organic_results from all pages in order, deduplicate by URL
    merged_organics: list[dict] = []
    seen_urls: set[str] = set()
    for start in sorted(page_results.keys()):
        page = page_results[start]
        for result in page.get("organic_results", []):
            url = result.get("link", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                # Re-number positions so they are continuous (1, 2, 3…)
                result["position"] = len(merged_organics) + 1
                merged_organics.append(result)

    base["organic_results"] = merged_organics[:num]
    return base

# ── SERP Features ─────────────────────────────────────────────────────────────
def extract_serp_features(serp_json: dict) -> dict:
    org = serp_json.get("organic_results", [])
    return {
        "has_paa":         bool(serp_json.get("related_questions")),
        "has_top_stories": bool(serp_json.get("top_stories")),
        "has_shopping":    bool(serp_json.get("shopping_results")),
        "has_knowledge":   bool(serp_json.get("knowledge_graph")),
        "has_ai_overview": bool(serp_json.get("ai_overview")),
        "has_sitelinks":   any(r.get("sitelinks") for r in org),
        "has_local_pack":  bool(serp_json.get("local_results")),
        "has_images":      bool(serp_json.get("images_results")),
        "has_videos":      bool(serp_json.get("video_results")),
    }

def extract_local_pack(serp_json: dict) -> dict:
    local = serp_json.get("local_results") or {}
    if not local:
        return {
            "present": False,
            "source": "SerpAPI",
            "summary": "No Local Pack detected in this search.",
            "name": "",
            "rating": None,
            "review_count": None,
            "address": "",
            "phone": "",
            "website": "",
            "categories": [],
            "open_now": None,
            "attributes": [],
            "top_competitors": [],
            "optimization_tips": ["No Local Pack is present in this SERP. Try a more localized query or verify your local listing details."],
        }

    places = []
    if isinstance(local, list):
        places = local
    elif isinstance(local, dict):
        places = local.get("places") or local.get("results") or []
        if isinstance(places, dict):
            places = [places]
    if not isinstance(places, list):
        places = []

    first = places[0] if places else local if isinstance(local, dict) else {}
    if not isinstance(first, dict):
        first = {}

    def _get(*keys):
        for k in keys:
            if isinstance(first, dict) and k in first:
                return first.get(k)
        return None

    categories = _get("categories", "category", "types") or []
    if isinstance(categories, str):
        categories = [categories]
    rating = _get("rating", "reviews_rating", "stars", "score")
    review_count = _get("review_count", "reviews", "user_ratings_total")
    open_now = _get("open_now", "open_status", "hours")
    address = _get("address", "location", "vicinity", "formatted_address") or ""
    phone = _get("phone", "telephone", "formatted_phone_number") or ""
    website = _get("website", "url", "link") or ""
    attributes = _get("attributes", "highlights") or []
    if isinstance(attributes, str):
        attributes = [attributes]

    summary = []
    if rating:
        summary.append(f"Top listing rating: {rating} stars")
    if review_count:
        summary.append(f"{review_count} review{'s' if str(review_count) != '1' else ''}")
    if categories:
        summary.append(f"Categories: {', '.join(categories[:3])}")
    if open_now is not None:
        summary.append(f"Status: {open_now}")
    if not summary:
        summary = ["Local Pack is present but not all listing fields are available."]

    top_competitors = []
    for place in places[:6]:
        if not isinstance(place, dict):
            continue
        top_competitors.append({
            "Name": place.get("title") or place.get("name") or "",
            "Rating": place.get("rating") or place.get("stars") or "—",
            "Reviews": place.get("review_count") or place.get("reviews") or "—",
            "Address": place.get("address") or place.get("vicinity") or "",
            "Website": place.get("website") or place.get("url") or "",
            "Phone": place.get("phone") or place.get("telephone") or "",
        })

    tips = []
    if not website:
        tips.append("Add a website URL to your local listing to improve click-through and trust.")
    if not phone:
        tips.append("Include a working phone number on your profile for local searchers.")
    if not address:
        tips.append("Verify your complete address and keep citations consistent across directories.")
    if not categories:
        tips.append("Choose the most accurate business categories to match local search intent.")
    if rating and isinstance(rating, (int, float)) and rating < 4.2:
        tips.append("Increase review quality and volume to improve your Local Pack competitiveness.")
    if review_count and isinstance(review_count, (int, float)) and review_count < 20:
        tips.append("Collect more reviews to strengthen your local ranking signal.")
    if open_now is None:
        tips.append("Keep your business hours updated so Google displays your availability correctly.")
    if not tips:
        tips.append("Your Local Pack listing looks solid. Maintain NAP consistency and fresh reviews.")

    return {
        "present": True,
        "source": "SerpAPI",
        "summary": " · ".join(summary),
        "name": _get("title", "name") or "",
        "rating": rating,
        "review_count": review_count,
        "address": address,
        "phone": phone,
        "website": website,
        "categories": categories,
        "open_now": open_now,
        "attributes": attributes,
        "top_competitors": top_competitors,
        "optimization_tips": tips,
    }


def _normalize_local_field(value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return value
    return []


def extract_local_pack_results(serp_json: dict, top_n=5) -> list:
    local = serp_json.get("local_results") or {}
    places = []
    if isinstance(local, list):
        places = local
    elif isinstance(local, dict):
        places = local.get("places") or local.get("results") or []
        if isinstance(places, dict):
            places = [places]
    if not isinstance(places, list):
        places = []

    rows = []
    for place in places[:top_n]:
        if not isinstance(place, dict):
            continue
        categories = _normalize_local_field(place.get("categories") or place.get("category") or place.get("types"))
        services = _normalize_local_field(place.get("services") or place.get("attributes") or place.get("highlights") or place.get("features") or place.get("service") or place.get("services_offered"))
        if not services:
            description = place.get("description") or place.get("snippet") or place.get("details")
            if isinstance(description, str):
                services = [description]
        rows.append({
            "Name": place.get("title") or place.get("name") or "",
            "Rating": place.get("rating") or place.get("stars") or "",
            "Phone": place.get("phone") or place.get("telephone") or "",
            "Website": place.get("website") or place.get("url") or place.get("link") or "",
            "Address": place.get("address") or place.get("vicinity") or place.get("formatted_address") or "",
            "Services": ", ".join(str(x) for x in services if x),
            "Categories": ", ".join(str(x) for x in categories if x),
        })
    return rows

# ── AI Overview ───────────────────────────────────────────────────────────────
def build_ai_overview(serp_json: dict, api_key: str) -> dict:
    ai_data = serp_json.get("ai_overview")
    if not ai_data:
        parts, ab = [], serp_json.get("answer_box", {})
        if isinstance(ab, dict) and (ab.get("answer") or ab.get("snippet")):
            parts.append(ab.get("answer") or ab.get("snippet"))
        snips = [o.get("snippet","") for o in serp_json.get("organic_results",[])[:3] if o.get("snippet")]
        if not parts and snips: parts.extend(snips)
        if not parts: return {"text":"No AI Overview found.","source":"N/A"}
        return {"text":normalize_space(" ".join(parts)),"source":"Fallback Synthesis"}
    full = ai_data
    if ai_data.get("page_token"):
        try:
            r = requests.get(SERPAPI_ENDPOINT,
                params={"engine":"google_ai_overview","page_token":ai_data["page_token"],"api_key":api_key},
                timeout=30); r.raise_for_status()
            full = r.json().get("ai_overview", {})
        except: return {"text":"Failed to fetch full AI Overview.","source":"Error"}
    sources  = full.get("sources", [])
    link_map = {s["title"]:s["link"] for s in sources if s.get("title") and s.get("link")}
    if "text_blocks" in full:
        parts = []
        for block in full.get("text_blocks", []):
            snippet = html.escape(block.get("snippet",""))
            for bw in block.get("snippet_highlighted_words",[]): snippet = snippet.replace(bw,f"<strong>{bw}</strong>")
            for t,lnk in link_map.items():
                if t in snippet: snippet = snippet.replace(t,f'<a href="{lnk}" target="_blank">{t}</a>')
            bt = block.get("type")
            if bt=="heading": parts.append(f"<h4>{snippet}</h4>")
            elif bt=="list":
                items=""
                for item in block.get("list",[]):
                    tt=f"<strong>{html.escape(item.get('title',''))}:</strong> " if item.get("title") else ""
                    items+=f"<li>{tt}{html.escape(item.get('snippet',''))}</li>"
                parts.append(f"<ul>{items}</ul>")
            else: parts.append(f"<p>{snippet}</p>")
        return {"text":"".join(parts),"source":"Google AI"}
    return {"text":"AI Overview found but could not be parsed.","source":"Parsing Error"}

# ── Related Keywords ──────────────────────────────────────────────────────────
def extract_related_keywords(api_key: str, query: str, serp_json: dict) -> dict:
    paa     = [q.get("question") for q in (serp_json.get("related_questions",[]) or []) if q.get("question")]
    related = [s.get("query") for s in (serp_json.get("related_searches",[]) or []) if s.get("query")]
    autocomplete = []
    try:
        r = requests.get(SERPAPI_ENDPOINT,params={"engine":"google_autocomplete","q":query,"api_key":api_key},timeout=5)
        if r.status_code==200: autocomplete=[s.get("value") for s in r.json().get("suggestions",[])]
    except: pass
    return {"people_also_ask":paa,"related_searches":related,"autocomplete":autocomplete}

# ── Intent & Audience ─────────────────────────────────────────────────────────
def detect_intent(query: str, serp_json: dict) -> str:
    q,f = query.lower(), extract_serp_features(serp_json)
    if any(w in q for w in ["buy","price","coupon","deal","order","purchase","hire","cost"]) or f["has_shopping"]: return "Transactional"
    if any(w in q for w in ["best","vs","review","top","compare","alternative"]): return "Commercial"
    if any(w in q for w in ["login","official","homepage","site","contact"]) or f["has_sitelinks"]: return "Navigational"
    return "Informational"

def get_audience_profile(intent: str) -> dict:
    return {
        "Transactional": {"audience":"Ready-to-Buy Users","stage":"Bottom of Funnel",
            "insight":"User is actively looking to purchase. Content should be direct with clear pricing and CTAs."},
        "Commercial":    {"audience":"Problem-Aware Researchers","stage":"Middle of Funnel",
            "insight":"User is comparing solutions. Provide comparisons, reviews, and case studies."},
        "Informational": {"audience":"Information Seekers","stage":"Top of Funnel",
            "insight":"User wants to learn. Content should be comprehensive and educational."},
        "Navigational":  {"audience":"Brand-Aware Users","stage":"Varies",
            "insight":"User wants a specific page. Provide a clear path to their destination."},
    }.get(intent,{"audience":"Information Seekers","stage":"Top of Funnel","insight":""})

# ── URL Parse ─────────────────────────────────────────────────────────────────
def fetch_and_parse_url(url: str) -> dict:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15); resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for bad in soup(["script","style","noscript","template","header","footer","svg","iframe","meta","link"]):
            bad.decompose()
        body = soup.body or soup
        h1s = [normalize_space(h.get_text(" ", strip=True)) for h in body.find_all("h1")]
        h2s = [normalize_space(h.get_text(" ", strip=True)) for h in body.find_all("h2")]
        h3s = [normalize_space(h.get_text(" ", strip=True)) for h in body.find_all("h3")]
        paras = [normalize_space(p.get_text(" ", strip=True)) for p in body.find_all("p") if len(normalize_space(p.get_text(" ", strip=True))) > 40]
        text_blocks = []
        for element in body.find_all(["h1","h2","h3","p"], recursive=True):
            tag = element.name
            text = normalize_space(element.get_text(" ", strip=True))
            if not text:
                continue
            if tag in ["h1","h2","h3"]:
                text_blocks.append({"type":"heading","level":int(tag[1]),"text":text})
            elif tag == "p":
                text_blocks.append({"type":"paragraph","text":text})
        full_text = normalize_space(body.get_text(" ", strip=True))
        return {
            "h1s":h1s,"h2s":h2s,"h3s":h3s,
            "full_text":full_text,
            "paras":paras[:40],
            "content_blocks":text_blocks,
            "status":"success"
        }
    except Exception:
        return {"h1s":[],"h2s":[],"h3s":[],"full_text":"","paras":[],"content_blocks":[],"status":"error"}

def analyze_serp_content(organic_results: list) -> dict:
    all_h1s,all_h2s,all_h3s,all_texts = [],[],[],[]
    organic_table_data,competitor_scores,top_urls = [],[],[]
    parsed_map = {}

    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(fetch_and_parse_url,r.get("link")):r for r in organic_results if r.get("link")}
        for fut in as_completed(futures):
            url = futures[fut].get("link")
            try: parsed_map[url] = fut.result()
            except: parsed_map[url] = {"h1s":[],"h2s":[],"h3s":[],"full_text":"","paras":[],"status":"error"}

    for result in organic_results:
        url   = result.get("link")
        pos   = result.get("position",0)
        title = _clean(result.get("title",""))
        top_urls.append(url)
        parsed = parsed_map.get(url,{"h1s":[],"h2s":[],"h3s":[],"full_text":"","paras":[],"status":"error"})

        organic_table_data.append({
            "position":pos,"title":title,"link":url,
            "h1":" | ".join(parsed.get("h1s",[])),
            "h2":" | ".join(parsed.get("h2s",[])[:3]),
        })
        if parsed["status"]=="success":
            all_h1s.extend(parsed["h1s"]); all_h2s.extend(parsed["h2s"]); all_h3s.extend(parsed["h3s"])

        # Snippet fallback
        full_text = parsed.get("full_text","")
        if not full_text or len(full_text)<200: full_text = result.get("snippet","")

        if full_text and len(full_text)>50:
            grade = content_grader.grade_content(full_text)
            if "error" not in grade:
                style_data = detect_content_style(full_text, grade["avg_sentence_length"], grade["word_count"])
                competitor_scores.append({
                    "position":pos,"title":title,"url":url,
                    "score":grade["content_score"],"verdict":grade["verdict"],
                    "word_count":grade["word_count"],"readability":grade["readability_scores"]["flesch_kincaid_grade"],
                    "gunning_fog":grade["readability_scores"]["gunning_fog"],
                    "avg_sent_len":grade["avg_sentence_length"],
                    "top_1grams":grade["ngrams"]["1-Word"][:8],
                    "top_2grams":grade["ngrams"]["2-Words"][:8],
                    "suggestions":grade["suggestions"],
                    "content_style":style_data["style"],
                    "style_key":style_data["key"],
                    # Full content for accordion
                    "h1s":parsed.get("h1s",[]),
                    "h2s":parsed.get("h2s",[]),
                    "h3s":parsed.get("h3s",[]),
                    "paras":parsed.get("paras",[]),
                    "full_text":full_text[:3000],
                })
        all_texts.extend([title,result.get("snippet","")])

    tokens  = re.findall(r'\b\w+\b'," ".join(all_texts).lower())
    phrases = Counter([" ".join(tokens[i:i+n]) for n in [2,3] for i in range(len(tokens)-n+1)]).most_common(20)
    return {
        "top_h1s":          [h for h,_ in Counter(all_h1s).most_common(5)],
        "top_h2s":          [h for h,_ in Counter(all_h2s).most_common(10)],
        "top_h3s":          [h for h,_ in Counter(all_h3s).most_common(15)],
        "semantic_terms":   [p for p,_ in phrases],
        "organic_table_data": organic_table_data,
        "top_urls":         top_urls,
        "competitor_scores":competitor_scores,
    }

# ── Query Fan-out ─────────────────────────────────────────────────────────────
def generate_query_fanout(query: str, related_kw: dict, serp_json: dict) -> dict:
    q = query.lower().strip()
    intent_clusters = {
        "Informational (LLM-friendly)": [f"{m} {q}" for m in ["what is","how to","guide to","explain","benefits of","types of","definition of"]],
        "Commercial / Comparison":      [f"{m} {q}" for m in ["best","top","vs","compare","alternatives to","review of"]],
        "Transactional":                [f"{m} {q}" for m in ["buy","price of","cost of","hire","cheapest","services"]],
        "Local / Geo":                  [f"{q} {m}" for m in ["in delhi","in india","near me","delhi ncr","online","india"]],
    }
    ai_angles = [
        f"What is {q} and why does it matter?",
        f"How does {q} work step by step?",
        f"What are the benefits of {q}?",
        f"What are common mistakes in {q}?",
        f"How to choose the right {q}?",
        f"What is the difference between {q} and alternatives?",
        f"Who needs {q} and when?",
        f"What questions do people ask about {q}?",
    ]
    paa          = related_kw.get("people_also_ask",[])
    autocomplete = related_kw.get("autocomplete",[])
    related      = related_kw.get("related_searches",[])
    content_clusters = {
        "Pillar Page":       [query],
        "Supporting Pages":  [f"{q} guide",f"{q} tips",f"how {q} works",f"{q} case study",f"{q} checklist"],
        "FAQ / PAA Pages":   paa[:6],
        "Long-tail":         autocomplete[:8],
        "Related Topics":    related[:6],
    }
    return {"intent_clusters":intent_clusters,"ai_angles":ai_angles,
            "content_clusters":content_clusters,"paa":paa,"autocomplete":autocomplete,"related":related}

# ── Position Tracking ─────────────────────────────────────────────────────────
def classify_questions_by_type(queries: list) -> dict:
    """
    Answer-the-Public style bucketing: takes every REAL question/query already
    collected (PAA, related searches, autocomplete, AI fan-out sub-queries) and
    groups it by question type — Why / How / What / Best / Where / When /
    Who / Is-Can-Does / Other — so a writer sees intent distribution at a glance
    instead of one flat list. Deterministic and free (no AI call needed) since
    this is pure prefix classification on real data, not generation.
    """
    buckets = {
        "Why":   [], "How":   [], "What":  [], "Best / Compare": [],
        "Where": [], "When":  [], "Who":   [], "Is / Can / Does": [], "Other": [],
    }
    seen = set()
    for q in queries or []:
        q = (q or "").strip()
        if not q or q.lower() in seen:
            continue
        seen.add(q.lower())
        ql = q.lower()
        first_word = ql.split()[0] if ql.split() else ""

        if first_word == "why":
            buckets["Why"].append(q)
        elif first_word in ("how",):
            buckets["How"].append(q)
        elif first_word == "what":
            buckets["What"].append(q)
        elif first_word == "where":
            buckets["Where"].append(q)
        elif first_word == "when":
            buckets["When"].append(q)
        elif first_word in ("who", "whose"):
            buckets["Who"].append(q)
        elif any(w in ql for w in ["best ", "top ", " vs ", "versus", "compare", "alternative", "cheapest", "cost of"]):
            buckets["Best / Compare"].append(q)
        elif first_word in ("is", "are", "can", "does", "do", "will", "should"):
            buckets["Is / Can / Does"].append(q)
        else:
            buckets["Other"].append(q)

    # Drop empty buckets so the UI only shows relevant categories
    buckets = {k: v for k, v in buckets.items() if v}
    total = sum(len(v) for v in buckets.values())
    return {
        "buckets": buckets,
        "counts": {k: len(v) for k, v in buckets.items()},
        "total_questions": total,
    }


def query_position_tracker(target_url: str, organic_results: list) -> dict:
    """
    Check where target_url (or its domain) appears in organic_results.
    Returns position, all matches with type label, and found flag.
    """
    target_norm   = normalize_url(target_url)
    target_domain = domain_of(target_url)
    position, matches = None, []
    for i, result in enumerate(organic_results):
        result_url = normalize_url(result.get("link", ""))
        pos = result.get("position") or (i + 1)
        if not result_url:
            continue
        if target_norm and target_norm == result_url:
            if position is None:
                position = pos
            matches.append((pos, result.get("link",""), "Exact match"))
        elif target_domain and target_domain == domain_of(result.get("link","")):
            if position is None:
                position = pos
            matches.append((pos, result.get("link",""), "Domain match"))
    return {
        "position":    position,
        "matches":     sorted(matches, key=lambda x: x[0]),
        "target_domain": target_domain,
        "found":       position is not None,
    }


def track_multiple_keywords(
    api_key:    str,
    keywords:   list[str],
    target_url: str,
    gl:         str = "in",
    hl:         str = "en",
    num:        int = 50,
) -> list[dict]:
    """
    Track position of target_url across multiple keywords concurrently.
    Each keyword fires a separate SerpAPI call in a background thread pool.
    Returns a list of result dicts sorted by keyword, one per keyword.
    """
    results: list[dict] = []

    def _track_one(keyword: str) -> dict:
        serp = fetch_serp(api_key, keyword, gl, hl, num)
        if not serp or "organic_results" not in serp:
            return {
                "keyword":      keyword,
                "position":     None,
                "found":        False,
                "matches":      [],
                "ai_overview":  False,
                "total_results": 0,
                "error":        "SERP fetch failed",
            }
        organic = serp.get("organic_results", [])
        tracker = query_position_tracker(target_url, organic)
        ai_check  = check_ai_overview_presence(target_url, serp)
        paa_check = check_paa_presence(target_url, serp)
        features = extract_serp_features(serp)
        return {
            "keyword":         keyword,
            "position":        tracker["position"],
            "found":           tracker["found"],
            "matches":         tracker["matches"],
            "in_ai_overview":  ai_check["in_ai_overview"],
            "ai_position":     ai_check["best_position"],
            "ai_total_sources":ai_check["total_sources"],
            "in_paa":          paa_check["in_paa"],
            "paa_position":    paa_check["matches"][0]["position"] if paa_check["matches"] else None,
            "total_results":   len(organic),
            "serp_features":   features,
            "top_url":         organic[0].get("link","") if organic else "",
            "top_title":       _clean(organic[0].get("title","")) if organic else "",
        }

    # Fire all keyword checks concurrently
    max_workers = min(len(keywords), 8)
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_track_one, kw): kw for kw in keywords}
        for fut in as_completed(futures):
            try:
                results.append(fut.result())
            except Exception as e:
                results.append({
                    "keyword":  futures[fut],
                    "position": None,
                    "found":    False,
                    "matches":  [],
                    "error":    str(e),
                })

    # Return sorted alphabetically by keyword for consistent display
    results.sort(key=lambda x: x["keyword"].lower())
    return results


def batch_position_tracker(
    api_key: str,
    keywords: list,
    target_url: str,
    gl: str = "in",
    hl: str = "en",
    num: int = 50,
) -> list:
    """
    Track position for MULTIPLE keywords in parallel.
    Each keyword fires one concurrent SerpAPI call (max 5 workers).
    Returns results in the same order as the keywords list.
    """
    from datetime import datetime as _dt

    def _track_one(keyword):
        try:
            serp = fetch_serp(api_key, keyword, gl, hl, num)
            if not serp or "organic_results" not in serp:
                return {
                    "keyword": keyword, "position": None, "found": False,
                    "matched_url": "", "match_type": "error",
                    "error": "SERP fetch failed",
                    "checked_at": _dt.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            organic = serp.get("organic_results", [])
            tracker = query_position_tracker(target_url, organic)
            matched_url = tracker["matches"][0][1] if tracker["matches"] else ""
            match_type  = tracker["matches"][0][2] if tracker["matches"] else "Not found"
            ai_check  = check_ai_overview_presence(target_url, serp)
            paa_check = check_paa_presence(target_url, serp)
            # Snippet from the matched result
            snippet = ""
            for r in organic:
                if matched_url and matched_url in r.get("link",""):
                    snippet = r.get("snippet","")
                    break
            return {
                "keyword":         keyword,
                "position":        tracker["position"],
                "found":           tracker["found"],
                "matched_url":     matched_url,
                "match_type":      match_type,
                "in_ai_overview":  ai_check["in_ai_overview"],
                "ai_position":     ai_check["best_position"],
                "ai_total_sources":ai_check["total_sources"],
                "in_paa":          paa_check["in_paa"],
                "paa_position":    paa_check["matches"][0]["position"] if paa_check["matches"] else None,
                "paa_question":    paa_check["matches"][0]["question"] if paa_check["matches"] else "",
                "snippet":         snippet,
                "total_scanned":   len(organic),
                "checked_at":      _dt.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        except Exception as exc:
            return {
                "keyword": keyword, "position": None, "found": False,
                "matched_url": "", "match_type": "error",
                "error": str(exc),
                "checked_at": _dt.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

    results_map = {}
    with ThreadPoolExecutor(max_workers=min(len(keywords), 5)) as ex:
        future_map = {ex.submit(_track_one, kw): kw for kw in keywords}
        for fut in as_completed(future_map):
            kw = future_map[fut]
            results_map[kw] = fut.result()

    return [results_map.get(kw, {"keyword":kw,"position":None,"found":False}) for kw in keywords]


def check_ai_overview_presence(target_url: str, serp_json: dict) -> dict:
    """
    Not just whether you're cited — WHERE. Returns citation position within the
    AI Overview's source list (1 = cited first) and the actual snippet text the
    citation supports, when Google's response makes that traceable.
    """
    target_domain = domain_of(target_url)
    ai_data = serp_json.get("ai_overview", {}) or {}
    sources = ai_data.get("sources", []) or []
    total = len(sources)

    matches = []
    matched_titles = set()
    for idx, s in enumerate(sources, start=1):
        if target_domain and target_domain == domain_of(s.get("link", "")):
            matches.append({"position": idx, "title": s.get("title", ""), "link": s.get("link", "")})
            if s.get("title"):
                matched_titles.add(s["title"])

    context_snippets = []
    if matched_titles:
        for block in ai_data.get("text_blocks", []) or []:
            snippet = block.get("snippet", "")
            if snippet and any(t in snippet for t in matched_titles):
                context_snippets.append(snippet)
            for item in block.get("list", []) or []:
                item_snip = item.get("snippet", "")
                if (item.get("title") in matched_titles) or (item_snip and any(t in item_snip for t in matched_titles)):
                    context_snippets.append(item_snip or item.get("title", ""))

    return {
        "in_ai_overview":  len(matches) > 0,
        "total_sources":   total,
        "matches":         matches,                                   # [{position, title, link}, ...]
        "best_position":   matches[0]["position"] if matches else None,
        "context_snippets":[c for c in dict.fromkeys(context_snippets)][:3],  # dedup, keep order
        "ai_source_urls":  [m["link"] for m in matches],              # kept for backward-compat
    }


def check_paa_presence(target_url: str, serp_json: dict) -> dict:
    """
    Checks whether target_url/domain is the CITED SOURCE behind a People Also Ask
    answer. Google attaches a source link+title to most (not all) PAA entries —
    when it's your page, that's a very concrete "you're already answering this
    question" signal, distinct from just ranking in the top 10.
    """
    target_domain = domain_of(target_url)
    target_norm   = normalize_url(target_url)
    paa = serp_json.get("related_questions", []) or []

    matches = []
    for idx, q in enumerate(paa, start=1):
        link = q.get("link", "")
        if not link:
            continue
        is_match = (target_norm and normalize_url(link) == target_norm) or \
                   (target_domain and target_domain == domain_of(link))
        if is_match:
            matches.append({
                "position": idx,
                "question": q.get("question", ""),
                "snippet":  q.get("snippet", ""),
                "title":    q.get("title", ""),
                "link":     link,
            })

    return {
        "in_paa":              len(matches) > 0,
        "total_paa_questions": len(paa),
        "matches":             matches,   # [{position, question, snippet, title, link}, ...]
    }


def get_interlinking_signals(target_url: str, organic_results: list) -> list:
    target_domain = domain_of(target_url)
    return [{"ranked_page":r.get("link",""),
             "links_to_target": bool(target_domain) and target_domain == domain_of(r.get("link",""))}
            for r in organic_results[:5] if r.get("link")]

# ── Backlink Scout ────────────────────────────────────────────────────────────
def fetch_backlink_signals(organic_results: list, target_url: str) -> dict:
    """
    IMPORTANT — this is a CITATION scan, not a real backlink index.
    It inspects each top-ranking competitor page's own OUTBOUND external links
    (who they cite/reference/link out to) — that's the only signal obtainable by
    scraping pages directly. True inbound backlink data (who links TO a page)
    requires a paid crawl index like Ahrefs, Majestic, or Moz, which this tool
    doesn't have access to. Treat "citation_gap" as outreach/partnership leads
    worth investigating, not verified backlinks — and treat "pages_citing_you"
    as confirmation that a competitor's page currently references your domain.
    """
    from url_inspector import inspect_url
    target_domain = domain_of(target_url)
    all_referring: dict = {}
    pages_citing_you: list = []

    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = {ex.submit(inspect_url,r.get("link","")): r for r in organic_results[:6] if r.get("link")}
        for fut in as_completed(futures):
            comp_url = futures[fut].get("link","")
            try:
                data = fut.result()
                if "error" in data: continue
                for ext in data.get("external_links",[]):
                    ext_dom = domain_of(ext["url"])
                    if not ext_dom:
                        continue
                    if ext_dom == target_domain:
                        # This competitor page already cites/links to you —
                        # not an outreach target, so track it separately.
                        pages_citing_you.append(comp_url)
                        continue
                    if ext_dom not in all_referring:
                        all_referring[ext_dom] = {"count": 0, "pages": [], "anchor_texts": []}
                    all_referring[ext_dom]["count"] += 1
                    all_referring[ext_dom]["pages"].append(comp_url)
                    if ext.get("text"):
                        all_referring[ext_dom]["anchor_texts"].append(ext["text"][:60])
            except Exception:
                continue

    sorted_refs = sorted(all_referring.items(), key=lambda x: x[1]["count"], reverse=True)
    citation_gap = [
        {"domain": dom, "count": info["count"],
         "sample_page": info["pages"][0] if info["pages"] else "",
         "anchor": info["anchor_texts"][0] if info["anchor_texts"] else ""}
        for dom, info in sorted_refs
    ][:30]

    return {
        "total_referring_domains": len(all_referring),
        "link_gap": citation_gap,
        "common_refs": list(dict.fromkeys(pages_citing_you))[:10],  # dedup, preserve order
        "your_referrer_count": len(set(pages_citing_you)),
    }

# ── CTAs & Brief ─────────────────────────────────────────────────────────────
def ctas_for_intent(intent: str) -> list:
    return {"Informational":["Download full guide","Subscribe for updates","Explore related tutorials"],
            "Commercial":["Compare plans","Get pricing","See demo","Download buyer's guide"],
            "Transactional":["Start free trial","Buy now","Get instant quote","Talk to sales"],
            "Navigational":["Visit homepage","Log in / Sign up","Contact support"]}.get(intent,["Get started"])

def generate_v1_style_markdown_brief(data: dict) -> str:
    query,intent = data.get("query",""),data.get("intent","N/A")
    ctas    = ctas_for_intent(intent)
    h2_md   = "\n".join([f"- {h}" for h in data.get("top_h2s",[])])
    h3_md   = "\n".join([f"- {h}" for h in data.get("top_h3s",[])])
    faq_md  = "\n".join([f"- {q}" for q in data.get("related_keywords",{}).get("people_also_ask",[])])
    ent_md  = ", ".join(data.get("semantic_terms",[]))
    urls_md = "\n".join([f"- {u}" for u in data.get("top_urls",[]) if u])
    ai_text = BeautifulSoup(data.get("ai_overview",{}).get("text",""),"html.parser").get_text()
    ai_md   = f"\n\n> **AI Overview:**\n> {ai_text}\n" if ai_text and "No AI" not in ai_text else ""
    return f"""### Content Brief: {query}
**Intent:** {intent}
**Suggested CTAs:** {", ".join(ctas)}
***
#### Outline (H2)
{h2_md or "No common H2s found."}
#### Suggested H3s
{h3_md or "No common H3s found."}
***
#### FAQs (from People Also Ask)
{faq_md or "No PAA questions found."}
***
#### Entities / Terms to Include
{ent_md or "No specific terms extracted."}
***
#### Reference URLs
{urls_md or "No URLs found."}
{ai_md}"""


def generate_topical_authority(brief_data: dict) -> dict:
    query        = brief_data.get("query", "").strip()
    intent       = brief_data.get("intent", "Informational")
    top_h2s      = brief_data.get("top_h2s", [])
    top_h3s      = brief_data.get("top_h3s", [])
    paa          = brief_data.get("related_keywords", {}).get("people_also_ask", [])
    autocomplete = brief_data.get("related_keywords", {}).get("autocomplete", [])
    related      = brief_data.get("related_keywords", {}).get("related_searches", [])
    semantic     = brief_data.get("semantic_terms", [])
    fanout       = brief_data.get("fanout", {})
    fo_clusters  = fanout.get("intent_clusters", {})
    ai_angles    = fanout.get("ai_angles", [])

    def _normalize_titles(items):
        seen = set(); output = []
        for item in items:
            if item and item not in seen:
                seen.add(item); output.append(item)
        return output

    info_queries = _normalize_titles(fo_clusters.get("Informational (LLM-friendly)", []))
    comm_queries = _normalize_titles(fo_clusters.get("Commercial / Comparison", []))
    trans_queries = _normalize_titles(fo_clusters.get("Transactional", []))
    local_queries = _normalize_titles(fo_clusters.get("Local / Geo", []))
    faq_queries  = _normalize_titles(paa[:6])
    ai_queries   = _normalize_titles(ai_angles[:6])

    def _headline_matches(source, terms):
        return [h for h in source if any(t in h.lower() for t in terms)]

    clusters = []
    info_h2s = _headline_matches(top_h2s, ["what","how","why","guide","benefits","steps","types","introduction"])
    comm_h2s = _headline_matches(top_h2s, ["best","vs","compare","review","alternative","top","choose","select"])
    trans_h2s = _headline_matches(top_h2s, ["price","cost","buy","order","package","plan","service","offer"])

    if info_queries or info_h2s:
        topics = _normalize_titles(info_queries[:4] + info_h2s[:3])[:5]
        if topics:
            clusters.append({
                "name": "Educational / How-to",
                "intent": "Informational",
                "description": "Build a strong foundation with practical guides, explainers, and process-focused pages.",
                "topics": topics,
                "priority": 1,
                "word_count": 1800,
            })
    if comm_queries or comm_h2s:
        topics = _normalize_titles(comm_queries[:4] + comm_h2s[:3])[:5]
        if topics:
            clusters.append({
                "name": "Comparisons & Reviews",
                "intent": "Commercial",
                "description": "Target buyers with comparisons, reviews, and side-by-side evaluations.",
                "topics": topics,
                "priority": 1,
                "word_count": 2000,
            })
    if trans_queries or trans_h2s:
        topics = _normalize_titles(trans_queries[:4] + trans_h2s[:3])[:4]
        if topics:
            clusters.append({
                "name": "Pricing & Services",
                "intent": "Transactional",
                "description": "Capture purchase-ready traffic with pricing, plans, and service-focused pages.",
                "topics": topics,
                "priority": 2,
                "word_count": 1300,
            })
    if local_queries:
        clusters.append({
            "name": "Local & Geographic",
            "intent": "Navigational",
            "description": "Cover geo-specific variations and local search demand with location-aware pages.",
            "topics": local_queries[:4],
            "priority": 2,
            "word_count": 1200,
        })
    if faq_queries:
        clusters.append({
            "name": "FAQ & People Also Ask",
            "intent": "Informational",
            "description": "Answer common questions clearly to win featured snippets and voice-search results.",
            "topics": faq_queries[:5],
            "priority": 3,
            "word_count": 900,
        })
    if ai_queries:
        clusters.append({
            "name": "AI & LLM Optimized Pages",
            "intent": "Informational",
            "description": "Create content aligned with AI answer patterns for stronger inclusion in answer boxes.",
            "topics": ai_queries[:5],
            "priority": 3,
            "word_count": 1500,
        })

    if not clusters:
        fallback = [query] if query else ["Core Topic Overview"]
        clusters.append({
            "name": "Core Topic Coverage",
            "intent": "Informational",
            "description": "Start with a core pillar and then expand into supporting topics.",
            "topics": fallback,
            "priority": 1,
            "word_count": 1800,
        })

    pillar = {
        "title": f"The Complete Guide to {query.title()}" if query else "The Complete Guide",
        "type": "Pillar Page",
        "priority": 1,
        "word_count": 3000,
        "cta": "Read the full guide",
        "description": f"Comprehensive overview of {query}. Links to supporting pages and covers core search intent.",
    }

    return build_topical_plan_from_clusters(query, pillar, clusters, semantic, related, autocomplete)


def build_topical_plan_from_clusters(
    query: str, pillar: dict, clusters: list, semantic: list, related: list, autocomplete: list
) -> dict:
    """
    Deterministic plan-builder shared by the formula-based generate_topical_authority()
    and the Gemini-powered ai_seo.get_topical_authority(). Takes a pillar + a list of
    subtopic clusters (however they were produced) and turns them into a content plan,
    internal-link map, publishing calendar, and coverage/authority scores.

    Each cluster dict needs: name, intent, description, topics (list[str]), priority (1-3),
    word_count (int).
    """
    content_plan = [pillar]
    seen_titles = set()
    for cluster in clusters:
        for topic in cluster["topics"]:
            if topic in seen_titles:
                continue
            seen_titles.add(topic)
            content_plan.append({
                "title": topic,
                "type": "Guide / Tutorial" if cluster["priority"] == 1 else "Landing Page" if cluster["priority"] == 2 else "FAQ / Answer Page",
                "priority": cluster["priority"],
                "word_count": cluster["word_count"],
                "cluster": cluster["name"],
                "reason": f"Supports the {cluster['name']} bucket and strengthens topical depth.",
            })
    pillar["cluster"] = "Pillar"
    pillar["type"] = "Pillar Page"

    internal_links = []
    for article in content_plan[1:]:
        internal_links.append({
            "from": pillar["title"],
            "to": article["title"],
            "anchor_text": article["title"],
        })
    for cluster in clusters:
        if len(cluster["topics"]) > 1:
            source = cluster["topics"][0]
            for target in cluster["topics"][1:]:
                internal_links.append({
                    "from": source,
                    "to": target,
                    "anchor_text": f"Read more about {target}",
                })

    calendar = []
    sorted_plan = sorted(content_plan[1:], key=lambda x: (x["priority"], x["title"]))
    week_labels = ["Week 1 — Foundation","Week 2 — Core Supporting Pages",
                   "Week 3 — FAQ & Depth","Week 4 — Comparisons, Local & AI"]
    articles_per_week = max(1, len(sorted_plan) // 4)
    for idx, article in enumerate(sorted_plan):
        week_idx = min(3, idx // articles_per_week)
        calendar.append({
            "week": week_labels[week_idx],
            "title": article["title"],
            "cluster": article["cluster"],
            "priority": article["priority"],
        })

    # Intent-based coverage checks (works for both formula cluster names and
    # free-form AI-generated cluster names, since both always set "intent").
    cluster_intents = {c.get("intent", "") for c in clusters}
    has_informational = "Informational" in cluster_intents
    has_commercial    = "Commercial" in cluster_intents
    has_transactional = "Transactional" in cluster_intents
    has_local         = "Navigational" in cluster_intents or any(
        "local" in c.get("name", "").lower() or "geo" in c.get("name", "").lower() for c in clusters
    )
    has_faq = any("faq" in c.get("name", "").lower() or "paa" in c.get("name", "").lower()
                  or "question" in c.get("name", "").lower() for c in clusters)

    coverage_score = round((len(clusters) / 6) * 100)
    authority_score = sum([
        30 if has_informational else 0,
        20 if has_commercial else 0,
        20 if has_transactional else 0,
        15 if has_faq else 0,
        15 if has_local else 0,
    ])
    coverage_score = min(coverage_score, 100)
    authority_score = min(authority_score, 100)

    gap_recommendations = []
    if not has_informational: gap_recommendations.append("Add a deep how-to or explainer pillar for the core topic.")
    if not has_commercial: gap_recommendations.append("Add a comparison or review page to capture buyer research traffic.")
    if not has_transactional: gap_recommendations.append("Add a pricing, services, or product page to capture transactional intent.")
    if not has_faq: gap_recommendations.append("Add FAQ pages that answer People Also Ask queries directly.")
    if not has_local: gap_recommendations.append("Add local or geo-specific landing pages if your audience is location-based.")
    if not gap_recommendations:
        gap_recommendations.append("Your topical authority plan is comprehensive. Follow the content plan and internal linking map next.")

    authority_map = []
    for cluster in clusters:
        authority_map.append({
            "name": cluster["name"],
            "focus": cluster["description"],
            "type": cluster["intent"],
            "topics": cluster["topics"][:4],
            "priority": "High" if cluster["priority"] == 1 else "Medium" if cluster["priority"] == 2 else "Tactical",
        })

    return {
        "pillar": pillar,
        "subtopic_clusters": clusters,
        "content_plan": content_plan,
        "internal_links": internal_links,
        "authority_map": authority_map,
        "calendar": calendar,
        "coverage_score": coverage_score,
        "authority_score": authority_score,
        "gap_recommendations": gap_recommendations,
        "total_articles": len(content_plan),
        "total_words": sum(a["word_count"] for a in content_plan),
        "top_terms": semantic[:12],
        "related_searches": related[:6],
        "autocomplete_suggestions": autocomplete[:6],
    }

# ── Content vs Competitor Comparison ─────────────────────────────────────────
# compare_with_competitors() takes the user's graded content + competitor_scores
# already in session. Zero extra API calls. Pure Python math.

def compare_with_competitors(user_grade: dict, competitor_scores: list) -> dict:
    """
    user_grade       — output of content_grader.grade_content()
    competitor_scores — list already in brief_data["competitor_scores"]

    Returns a full comparison report dict.
    """
    if not competitor_scores:
        return {"error": "No competitor data. Run a SERP analysis in Tab 1 first."}
    if "error" in user_grade:
        return {"error": user_grade["error"]}

    comps = competitor_scores  # shorthand

    # ── User metrics ──────────────────────────────────────────────────────────
    u_score   = user_grade["content_score"]
    u_words   = user_grade["word_count"]
    u_fk      = user_grade["readability_scores"]["flesch_kincaid_grade"]
    u_fog     = user_grade["readability_scores"]["gunning_fog"]
    u_sent    = user_grade["avg_sentence_length"]
    u_1grams  = set(row.split(" (")[0].strip() for row in user_grade["ngrams"]["1-Word"])
    u_2grams  = set(row.split(" (")[0].strip() for row in user_grade["ngrams"]["2-Words"])
    u_style   = detect_content_style(
                    " ".join(row.split(" (")[0] for row in user_grade["ngrams"]["1-Word"]),
                    u_sent, u_words)["style"]

    # ── Competitor aggregates ─────────────────────────────────────────────────
    avg_score = round(sum(c["score"]        for c in comps) / len(comps), 1)
    avg_words = round(sum(c["word_count"]   for c in comps) / len(comps))
    avg_fk    = round(sum(c["readability"]  for c in comps) / len(comps), 1)
    avg_fog   = round(sum(c.get("gunning_fog", 0) for c in comps) / len(comps), 1)
    avg_sent  = round(sum(c["avg_sent_len"] for c in comps) / len(comps), 1)

    best      = max(comps, key=lambda x: x["score"])
    top3      = sorted(comps, key=lambda x: x["position"])[:3]

    # ── Metric gap table ──────────────────────────────────────────────────────
    def _status(user_val, avg_val, higher_is_better=True, threshold=0.1):
        diff = (user_val - avg_val) / max(abs(avg_val), 0.01)
        if higher_is_better:
            if diff > threshold:   return "✅ Winning"
            if diff > -threshold:  return "⚠️ Close"
            return "❌ Behind"
        else:
            # lower is better (e.g. FK grade, Fog)
            if diff < -threshold:  return "✅ Winning"
            if diff < threshold:   return "⚠️ Close"
            return "❌ Behind"

    metric_gaps = [
        {
            "metric":   "Content Score",
            "yours":    u_score,
            "avg_comp": avg_score,
            "best_comp":best["score"],
            "gap_to_avg":  round(u_score - avg_score, 1),
            "gap_to_best": round(u_score - best["score"], 1),
            "status":   _status(u_score, avg_score, higher_is_better=True),
            "unit": "/100",
        },
        {
            "metric":   "Word Count",
            "yours":    u_words,
            "avg_comp": avg_words,
            "best_comp":best["word_count"],
            "gap_to_avg":  u_words - avg_words,
            "gap_to_best": u_words - best["word_count"],
            "status":   _status(u_words, avg_words, higher_is_better=True),
            "unit": " words",
        },
        {
            "metric":   "FK Reading Grade",
            "yours":    u_fk,
            "avg_comp": avg_fk,
            "best_comp":min(c["readability"] for c in comps),
            "gap_to_avg":  round(u_fk - avg_fk, 1),
            "gap_to_best": round(u_fk - min(c["readability"] for c in comps), 1),
            "status":   _status(u_fk, avg_fk, higher_is_better=False),
            "unit": " grade",
            "note": "Lower = easier to read",
        },
        {
            "metric":   "Gunning Fog",
            "yours":    u_fog,
            "avg_comp": avg_fog,
            "best_comp":min(c.get("gunning_fog",0) for c in comps),
            "gap_to_avg":  round(u_fog - avg_fog, 1),
            "gap_to_best": round(u_fog - min(c.get("gunning_fog",0) for c in comps), 1),
            "status":   _status(u_fog, avg_fog, higher_is_better=False),
            "unit": "",
            "note": "Lower = simpler language",
        },
        {
            "metric":   "Avg Sentence Length",
            "yours":    u_sent,
            "avg_comp": avg_sent,
            "best_comp":min(c["avg_sent_len"] for c in comps),
            "gap_to_avg":  round(u_sent - avg_sent, 1),
            "gap_to_best": round(u_sent - min(c["avg_sent_len"] for c in comps), 1),
            "status":   _status(u_sent, avg_sent, higher_is_better=False),
            "unit": " words",
            "note": "Lower = punchier sentences",
        },
    ]

    # ── Keyword gap ───────────────────────────────────────────────────────────
    # Collect all competitor 1-grams and 2-grams from top 3
    comp_1grams_all = []
    comp_2grams_all = []
    for c in top3:
        for kw in c.get("top_1grams", []):
            word = kw.split(" (")[0].strip()
            comp_1grams_all.append(word)
        for kw in c.get("top_2grams", []):
            phrase = kw.split(" (")[0].strip()
            comp_2grams_all.append(phrase)

    comp_1gram_set = set(comp_1grams_all)
    comp_2gram_set = set(comp_2grams_all)

    # Keywords competitors use you don't (opportunity gaps)
    missing_1grams = [w for w in comp_1grams_all
                      if w not in u_1grams and comp_1grams_all.count(w) >= 2]
    missing_1grams = list(dict.fromkeys(missing_1grams))[:15]  # dedupe, top 15

    missing_2grams = [p for p in comp_2grams_all
                      if p not in u_2grams and comp_2grams_all.count(p) >= 2]
    missing_2grams = list(dict.fromkeys(missing_2grams))[:12]

    # Keywords you use competitors don't (your differentiators)
    unique_1grams = [w for w in u_1grams if w not in comp_1gram_set][:10]
    unique_2grams = [p for p in u_2grams if p not in comp_2gram_set][:8]

    # ── Style match ───────────────────────────────────────────────────────────
    comp_styles = [c.get("content_style","—") for c in top3]
    dominant_style = max(set(comp_styles), key=comp_styles.count) if comp_styles else "—"
    style_match    = u_style == dominant_style

    # ── Publish readiness score ───────────────────────────────────────────────
    readiness  = 0
    actions    = []

    # Score comparison (30 pts)
    if u_score >= avg_score:
        readiness += 30
    elif u_score >= avg_score * 0.85:
        readiness += 18
        actions.append(f"⚠️ Content score ({u_score}) is below competitor average ({avg_score}). Improve readability and add missing keywords.")
    else:
        readiness += 5
        actions.append(f"❌ Content score ({u_score}) is significantly below competitor average ({avg_score}). Major revision needed.")

    # Word count (25 pts)
    if u_words >= avg_words:
        readiness += 25
    elif u_words >= avg_words * 0.8:
        readiness += 14
        actions.append(f"⚠️ Word count ({u_words:,}) is below competitor average ({avg_words:,}). Add {avg_words - u_words:,} more words.")
    else:
        readiness += 0
        actions.append(f"❌ Word count ({u_words:,}) is far below competitors ({avg_words:,} avg). Add at least {avg_words - u_words:,} words.")

    # Readability (20 pts)
    if u_fk <= avg_fk + 1:
        readiness += 20
    elif u_fk <= avg_fk + 3:
        readiness += 12
        actions.append(f"⚠️ Your reading grade ({u_fk}) is higher than competitor average ({avg_fk}). Shorten sentences.")
    else:
        readiness += 4
        actions.append(f"❌ Content is much harder to read (grade {u_fk}) than competitors (avg {avg_fk}). Simplify significantly.")

    # Missing keywords (15 pts)
    if len(missing_1grams) <= 3:
        readiness += 15
    elif len(missing_1grams) <= 8:
        readiness += 8
        actions.append(f"⚠️ {len(missing_1grams)} competitor keywords missing from your content. Add: {', '.join(missing_1grams[:5])}.")
    else:
        readiness += 2
        actions.append(f"❌ {len(missing_1grams)} important keywords from top competitors are missing. Top gaps: {', '.join(missing_1grams[:5])}.")

    # Style match (10 pts)
    if style_match:
        readiness += 10
    else:
        readiness += 3
        actions.append(f"⚠️ Your writing style ({u_style}) differs from the dominant competitor style ({dominant_style}). Consider aligning.")

    readiness = min(readiness, 100)

    if readiness >= 80:
        verdict       = "✅ Ready to Publish"
        verdict_color = "#4ade80"
        verdict_note  = "Your content is competitive. Publish and monitor rankings."
    elif readiness >= 55:
        verdict       = "⚠️ Needs Work"
        verdict_color = "#f59e0b"
        verdict_note  = "Fix the flagged issues below before publishing."
    else:
        verdict       = "❌ Not Ready"
        verdict_color = "#f87171"
        verdict_note  = "Significant gaps vs competitors. Revise before publishing."

    if not actions:
        actions = ["✅ Your content looks competitive across all measured dimensions."]

    # ── Per-competitor scorecard ──────────────────────────────────────────────
    scorecards = []
    for c in sorted(comps, key=lambda x: x["position"])[:6]:
        scorecards.append({
            "position":   c["position"],
            "title":      c["title"],
            "url":        c["url"],
            "their_score":c["score"],
            "your_score": u_score,
            "you_win":    u_score > c["score"],
            "their_words":c["word_count"],
            "your_words": u_words,
            "their_fk":   c["readability"],
            "your_fk":    u_fk,
            "style":      c.get("content_style","—"),
        })

    return {
        "user_score":      u_score,
        "user_words":      u_words,
        "user_fk":         u_fk,
        "user_fog":        u_fog,
        "user_style":      u_style,
        "avg_score":       avg_score,
        "avg_words":       avg_words,
        "avg_fk":          avg_fk,
        "best_title":      best["title"],
        "best_score":      best["score"],
        "best_words":      best["word_count"],
        "metric_gaps":     metric_gaps,
        "missing_1grams":  missing_1grams,
        "missing_2grams":  missing_2grams,
        "unique_1grams":   unique_1grams,
        "unique_2grams":   unique_2grams,
        "dominant_style":  dominant_style,
        "style_match":     style_match,
        "readiness":       readiness,
        "verdict":         verdict,
        "verdict_color":   verdict_color,
        "verdict_note":    verdict_note,
        "actions":         actions,
        "scorecards":      scorecards,
        "top3_positions":  [c["position"] for c in top3],
    }
