# ai_seo.py — SERP V8
# Gemini-powered versions of the four features that were previously pure
# string-templates: Intent Detection, Query Fan-out, Content Brief, and
# Topical Authority. Every function here takes the SAME real scraped data
# the tool already collects (PAA, related searches, competitor headings,
# SERP features, competitor full-text) and grounds Gemini's reasoning in it,
# instead of filling generic templates.
#
# Contract: every public function here ALWAYS returns a usable result.
# If no Gemini key is set, or the call fails for any reason, it transparently
# falls back to the matching formula-based function in serp_analyzer.py and
# tags the result with source="formula" so the UI can show which one ran.

from __future__ import annotations
import serp_analyzer
import content_grader
from gemini_client import call_gemini, call_gemini_grounded, DEFAULT_MODEL
from utils import domain_of


# ═══════════════════════════════════════════════════════════════════════════
#  1. INTENT DETECTION
# ═══════════════════════════════════════════════════════════════════════════

_INTENT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "intent":       {"type": "STRING", "enum": ["Informational", "Commercial", "Transactional", "Navigational"]},
        "confidence":   {"type": "INTEGER", "description": "0-100"},
        "funnel_stage": {"type": "STRING"},
        "audience":     {"type": "STRING", "description": "Short label for who is searching this, e.g. 'Ready-to-buy homeowners comparing quotes'"},
        "insight":      {"type": "STRING", "description": "1-2 sentence content strategy insight specific to this query, not generic advice"},
        "reasoning":    {"type": "STRING", "description": "Brief reasoning grounded in the SERP evidence provided"},
    },
    "required": ["intent", "confidence", "funnel_stage", "audience", "insight", "reasoning"],
}


def get_intent_analysis(query: str, serp_json: dict, api_key: str, model: str = DEFAULT_MODEL) -> tuple[str, dict, dict]:
    """
    Returns (intent, audience_profile, meta) — same shapes app.py already expects
    from serp_analyzer.detect_intent() + get_audience_profile(), so no UI changes
    are required beyond reading meta["source"].

    audience_profile keys: audience, stage, insight  (unchanged from formula version)
    meta keys: source ("ai" or "formula"), confidence, reasoning
    """
    features = serp_analyzer.extract_serp_features(serp_json)
    snippets = [o.get("snippet", "") for o in serp_json.get("organic_results", [])[:5] if o.get("snippet")]
    paa      = [q.get("question", "") for q in (serp_json.get("related_questions", []) or [])[:5] if q.get("question")]

    user_prompt = f"""Classify the search intent behind this Google query, using the real SERP evidence below.

QUERY: "{query}"

SERP FEATURES PRESENT: {[k for k, v in features.items() if v] or "none detected"}

TOP 5 RANKING SNIPPETS:
{chr(10).join(f"- {s}" for s in snippets) or "none"}

PEOPLE ALSO ASK QUESTIONS:
{chr(10).join(f"- {q}" for q in paa) or "none"}

Classify into exactly one of: Informational, Commercial, Transactional, Navigational.
Base your funnel_stage, audience, and insight on what's ACTUALLY ranking and being asked —
not generic funnel theory. If the query is in a non-English language, reason in that
language's cultural/search context, but respond in English."""

    result = call_gemini(
        api_key=api_key,
        system_prompt="You are a senior SEO strategist analyzing real Google SERP data to classify search intent precisely.",
        user_prompt=user_prompt,
        schema=_INTENT_SCHEMA,
        model=model,
        temperature=0.3,
    )

    if result["ok"]:
        d = result["data"]
        intent = d.get("intent", "Informational")
        audience_profile = {
            "audience": d.get("audience", ""),
            "stage":    d.get("funnel_stage", ""),
            "insight":  d.get("insight", ""),
        }
        meta = {"source": "ai", "confidence": d.get("confidence", 0), "reasoning": d.get("reasoning", "")}
        return intent, audience_profile, meta

    # Fallback — formula-based, unchanged behaviour
    intent = serp_analyzer.detect_intent(query, serp_json)
    audience_profile = serp_analyzer.get_audience_profile(intent)
    meta = {"source": "formula", "confidence": None, "reasoning": f"AI unavailable ({result.get('error')})"}
    return intent, audience_profile, meta


# ═══════════════════════════════════════════════════════════════════════════
#  2. QUERY FAN-OUT / INTENT CLUSTERS
# ═══════════════════════════════════════════════════════════════════════════

_FANOUT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "intent_clusters": {
            "type": "OBJECT",
            "description": "4-6 cluster names mapped to 4-8 real sub-queries each, grounded in the provided PAA/related/competitor data — not generic templates",
            "properties": {},
        },
        "ai_angles": {
            "type": "ARRAY",
            "description": "6-10 specific questions this content should answer to appear in AI Overviews / LLM answers, grounded in the actual PAA and competitor headings",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "question": {"type": "STRING"},
                    "currently_cited_title": {"type": "STRING", "description": "If the AI Overview sources or competitor titles provided already answer this, name that page's title. Empty string if none matches — do not invent a title."},
                    "currently_cited_url":   {"type": "STRING", "description": "The matching URL from the citation candidates provided, if any. Empty string if none matches — never invent a URL."},
                },
                "required": ["question", "currently_cited_title", "currently_cited_url"],
            },
        },
        "content_clusters": {
            "type": "OBJECT",
            "properties": {
                "Pillar Page":      {"type": "ARRAY", "items": {"type": "STRING"}},
                "Supporting Pages": {"type": "ARRAY", "items": {"type": "STRING"}},
                "FAQ / PAA Pages":  {"type": "ARRAY", "items": {"type": "STRING"}},
                "Long-tail":        {"type": "ARRAY", "items": {"type": "STRING"}},
                "Related Topics":   {"type": "ARRAY", "items": {"type": "STRING"}},
            },
        },
        "entities": {
            "type": "ARRAY", "items": {"type": "STRING"},
            "description": "Key named entities/concepts that recur across top-ranking competitor content that the target content should mention",
        },
        "content_gaps": {
            "type": "ARRAY", "items": {"type": "STRING"},
            "description": "Specific subtopics/questions competitors cover (or PAA asks) that are commonly under-served — real gaps, not generic advice",
        },
    },
    "required": ["intent_clusters", "ai_angles", "content_clusters", "entities", "content_gaps"],
}


def get_query_fanout(query: str, related_kw: dict, serp_json: dict, content_result: dict | None,
                      api_key: str, model: str = DEFAULT_MODEL) -> dict:
    """
    Returns the SAME shape as serp_analyzer.generate_query_fanout() (intent_clusters,
    ai_angles, content_clusters, paa, autocomplete, related) plus two new keys
    (entities, content_gaps) and a "meta" key. Existing Tab-1 rendering code keeps
    working unchanged; new fields are additive.

    ai_angles items are objects — {question, currently_cited_title, currently_cited_url} —
    grounded against real citation candidates (AI Overview sources + top organic titles)
    so a writer can see, per angle, whether it's already being cited and by whom.
    """
    paa          = related_kw.get("people_also_ask", [])
    autocomplete = related_kw.get("autocomplete", [])
    related      = related_kw.get("related_searches", [])
    top_h2s = (content_result or {}).get("top_h2s", [])[:15]
    top_h3s = (content_result or {}).get("top_h3s", [])[:15]

    # Real citation candidates the model may reference for ai_angles — never invent titles/URLs.
    citation_candidates = []
    ai_ov = (serp_json or {}).get("ai_overview", {}) or {}
    for s in ai_ov.get("sources", []) or []:
        if s.get("title") and s.get("link"):
            citation_candidates.append(f'{s["title"]} — {s["link"]}')
    for o in (serp_json or {}).get("organic_results", [])[:10]:
        if o.get("title") and o.get("link"):
            citation_candidates.append(f'{o["title"]} — {o["link"]}')

    user_prompt = f"""Build a query fan-out and content cluster map for this seed keyword, grounded in real
Google data (not generic "how to X / best X" templates).

SEED QUERY: "{query}"

PEOPLE ALSO ASK (real Google questions):
{chr(10).join(f"- {q}" for q in paa) or "none"}

RELATED SEARCHES:
{chr(10).join(f"- {r}" for r in related) or "none"}

AUTOCOMPLETE SUGGESTIONS:
{chr(10).join(f"- {a}" for a in autocomplete) or "none"}

HEADINGS FROM TOP-RANKING COMPETITOR PAGES (H2):
{chr(10).join(f"- {h}" for h in top_h2s) or "none"}

HEADINGS FROM TOP-RANKING COMPETITOR PAGES (H3):
{chr(10).join(f"- {h}" for h in top_h3s) or "none"}

CITATION CANDIDATES (real page titles + URLs — AI Overview sources and top organic results;
use these ONLY to fill currently_cited_title/currently_cited_url when one genuinely answers
an ai_angle question; leave both blank if nothing here matches):
{chr(10).join(f"- {c}" for c in citation_candidates) or "none available"}

Using this real evidence, produce:
1. intent_clusters — group real sub-queries (from the data above, or close natural variants)
   into 4-6 clusters with clear names (e.g. "Pricing & Cost", "Local / Delhi NCR", "How it Works").
2. ai_angles — 6-10 specific questions this page should directly answer to win AI Overview
   citations. For each, check the citation candidates list: if one of those pages is already
   the likely source for that answer, fill currently_cited_title/currently_cited_url with its
   EXACT title and URL from the list above. If nothing matches, leave both as empty strings —
   never invent a citation.
3. content_clusters — a Pillar Page title, Supporting Pages, FAQ/PAA Pages, Long-tail, and
   Related Topics, using real phrasing from the data where possible.
4. entities — key named concepts/entities that show up repeatedly in competitor headings.
5. content_gaps — specific subtopics real PAA/competitors raise that are easy to under-serve.

Everything must be specific to this query and this data — no generic filler."""

    result = call_gemini(
        api_key=api_key,
        system_prompt="You are an SEO content strategist building a query fan-out map grounded strictly in the real SERP data provided. Never invent citation titles or URLs that aren't in the candidate list.",
        user_prompt=user_prompt,
        schema=_FANOUT_SCHEMA,
        model=model,
        temperature=0.5,
    )

    if result["ok"]:
        d = result["data"]
        return {
            "intent_clusters":  d.get("intent_clusters", {}) or {},
            "ai_angles":        d.get("ai_angles", []) or [],
            "content_clusters": d.get("content_clusters", {}) or {},
            "entities":         d.get("entities", []) or [],
            "content_gaps":     d.get("content_gaps", []) or [],
            "paa": paa, "autocomplete": autocomplete, "related": related,
            "meta": {"source": "ai"},
        }

    fallback = serp_analyzer.generate_query_fanout(query, related_kw, serp_json)
    # Normalize fallback ai_angles (plain strings) to the same object shape as the AI path,
    # so app.py rendering doesn't need to branch on source.
    fallback["ai_angles"] = [
        {"question": a, "currently_cited_title": "", "currently_cited_url": ""}
        for a in fallback.get("ai_angles", [])
    ]
    fallback["entities"] = []
    fallback["content_gaps"] = []
    fallback["meta"] = {"source": "formula", "reason": result.get("error")}
    return fallback


# ═══════════════════════════════════════════════════════════════════════════
#  3. CONTENT BRIEF / "WHAT TO WRITE" SUGGESTIONS
# ═══════════════════════════════════════════════════════════════════════════

_BRIEF_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "content_type_recommendation": {"type": "STRING", "description": "What format/type of content to write and why (e.g. comparison guide, pricing page, how-to)"},
        "recommended_word_count": {"type": "INTEGER"},
        "title_options": {
            "type": "ARRAY", "items": {"type": "STRING"},
            "description": "3-4 real, publish-ready SEO title variants covering different angles (e.g. a complete-guide angle, a listicle angle, a comparison angle, a local-intent angle if relevant). Not placeholders.",
        },
        "primary_keyword": {"type": "STRING"},
        "secondary_keywords": {
            "type": "ARRAY", "items": {"type": "STRING"},
            "description": "4-6 secondary/LSI keywords this piece should naturally cover, grounded in the real PAA/related data provided",
        },
        "missing_subtopics": {
            "type": "ARRAY", "items": {"type": "STRING"},
            "description": "Subtopics competitors cover that appear to be commonly missed or under-explained",
        },
        "suggested_outline": {
            "type": "ARRAY", "items": {"type": "STRING"},
            "description": "Ordered H2-level outline for the ideal article, grounded in competitor coverage + PAA",
        },
        "unique_angle_ideas": {
            "type": "ARRAY", "items": {"type": "STRING"},
            "description": "2-4 ways to differentiate this content from what's currently ranking",
        },
        "faqs_to_answer": {"type": "ARRAY", "items": {"type": "STRING"}},
        "tone_formality": {"type": "STRING", "description": "e.g. 'Conversational but credible', 'Formal/technical', 'Casual and playful' — specific to this audience, not generic"},
        "tone_point_of_view": {"type": "STRING", "description": "e.g. 'Second person, direct address', 'Third person, editorial'"},
        "tone_avoid": {
            "type": "ARRAY", "items": {"type": "STRING"},
            "description": "2-3 specific things to avoid for this audience/intent, e.g. 'heavy technical jargon', 'salesy CTAs before value is shown'",
        },
    },
    "required": ["content_type_recommendation", "recommended_word_count", "title_options", "primary_keyword",
                 "secondary_keywords", "missing_subtopics", "suggested_outline", "unique_angle_ideas",
                 "faqs_to_answer", "tone_formality", "tone_point_of_view", "tone_avoid"],
}


def get_content_brief(query: str, intent: str, competitor_scores: list, content_result: dict,
                       related_kw: dict, api_key: str, model: str = DEFAULT_MODEL) -> dict:
    """
    Editorial brief for content writers — grounded in actual competitor content excerpts
    and content-grader scores, not just n-gram counts. Covers what to write, what to call
    it, which keywords to target, and how it should sound. Returns
    {"ok": bool, "source": str, ...fields}.
    """
    comp_excerpts = []
    for c in (competitor_scores or [])[:5]:
        txt = (c.get("full_text", "") or "")[:500]
        comp_excerpts.append(f"[Rank #{c.get('position')}, score {c.get('score')}/100] {c.get('title','')}\n{txt}")

    top_h2s = (content_result or {}).get("top_h2s", [])[:12]
    paa = related_kw.get("people_also_ask", [])[:8]
    related = related_kw.get("related_searches", [])[:8]

    user_prompt = f"""Write a content brief for a writer targeting this keyword, based on what's ACTUALLY
ranking on page 1 right now. This brief needs to cover what to write, what to TITLE it, which
keywords to target, and how it should sound — a writer should be able to start immediately
from this alone.

QUERY: "{query}"    SEARCH INTENT: {intent}

TOP-RANKING PAGE EXCERPTS (title + first ~500 chars):
{chr(10).join(f"{'-'*40}{chr(10)}{e}" for e in comp_excerpts) or "none available"}

COMMON H2 HEADINGS ACROSS TOP RESULTS:
{chr(10).join(f"- {h}" for h in top_h2s) or "none"}

PEOPLE ALSO ASK:
{chr(10).join(f"- {q}" for q in paa) or "none"}

RELATED SEARCHES:
{chr(10).join(f"- {r}" for r in related) or "none"}

Based on this, tell the writer:
- What type of content to write and why, and a realistic target word count for this specific
  query (not a generic 1200+ rule).
- 3-4 real, publish-ready title options covering different angles (guide / listicle /
  comparison / local, as relevant) — not placeholders like "Title about X".
- The single primary keyword this piece should target, and 4-6 secondary/LSI keywords drawn
  from the real PAA/related data above.
- Which subtopics competitors under-serve, a suggested H2 outline, 2-4 ideas to genuinely
  differentiate from what's ranking, and FAQs to answer.
- Specific tone guidance: formality level, point of view, and 2-3 concrete things to avoid —
  grounded in this audience and intent, not generic writing advice."""

    result = call_gemini(
        api_key=api_key,
        system_prompt="You are a senior content strategist writing a brief for a content writer, grounded strictly in the competitor data provided.",
        user_prompt=user_prompt,
        schema=_BRIEF_SCHEMA,
        model=model,
        temperature=0.5,
    )

    if result["ok"]:
        d = result["data"]
        d["ok"] = True
        d["source"] = "ai"
        return d

    return {
        "ok": False,
        "source": "unavailable",
        "reason": result.get("error"),
        "content_type_recommendation": "", "recommended_word_count": 0,
        "title_options": [], "primary_keyword": "", "secondary_keywords": [],
        "missing_subtopics": [], "suggested_outline": [], "unique_angle_ideas": [],
        "faqs_to_answer": [], "tone_formality": "", "tone_point_of_view": "", "tone_avoid": [],
    }


# ═══════════════════════════════════════════════════════════════════════════
#  4. TOPICAL AUTHORITY / TOPIC CLUSTERS
# ═══════════════════════════════════════════════════════════════════════════

_TOPICAL_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "pillar_title": {"type": "STRING"},
        "pillar_description": {"type": "STRING"},
        "clusters": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "name":        {"type": "STRING"},
                    "intent":      {"type": "STRING", "enum": ["Informational", "Commercial", "Transactional", "Navigational"]},
                    "description": {"type": "STRING"},
                    "topics":      {"type": "ARRAY", "items": {"type": "STRING"}, "description": "3-6 specific real article titles/angles, not generic labels"},
                    "priority":    {"type": "INTEGER", "description": "1 (highest) to 3 (lowest)"},
                    "word_count":  {"type": "INTEGER"},
                },
                "required": ["name", "intent", "description", "topics", "priority", "word_count"],
            },
        },
    },
    "required": ["pillar_title", "pillar_description", "clusters"],
}


def get_topical_authority(brief_data: dict, api_key: str, model: str = DEFAULT_MODEL) -> dict:
    """
    Returns the SAME shape as serp_analyzer.generate_topical_authority() so Tab 2's
    rendering code works unchanged. The creative part (identifying real subtopic
    clusters grounded in scraped data) is delegated to Gemini; the deterministic part
    (content calendar, internal links, word-count totals, scoring) is still computed
    in Python via build_topical_plan_from_clusters(), so numbers stay reliable even
    when the AI call succeeds.
    """
    query        = brief_data.get("query", "").strip()
    top_h2s      = brief_data.get("top_h2s", [])[:15]
    top_h3s      = brief_data.get("top_h3s", [])[:15]
    rk           = brief_data.get("related_keywords", {})
    paa          = rk.get("people_also_ask", [])
    autocomplete = rk.get("autocomplete", [])
    related      = rk.get("related_searches", [])
    semantic     = brief_data.get("semantic_terms", [])

    user_prompt = f"""Design a topical authority content plan for this keyword, grounded in real
competitor headings and real Google demand signals — not generic funnel templates.

SEED QUERY: "{query}"

COMPETITOR H2 HEADINGS:
{chr(10).join(f"- {h}" for h in top_h2s) or "none"}

COMPETITOR H3 HEADINGS:
{chr(10).join(f"- {h}" for h in top_h3s) or "none"}

PEOPLE ALSO ASK:
{chr(10).join(f"- {q}" for q in paa) or "none"}

RELATED SEARCHES:
{chr(10).join(f"- {r}" for r in related) or "none"}

AUTOCOMPLETE:
{chr(10).join(f"- {a}" for a in autocomplete) or "none"}

Produce a pillar page title + description, and 3-6 subtopic clusters. Each cluster needs a
specific name, an intent, a description of its strategic purpose, 3-6 REAL article titles/angles
(not "Guide to X" placeholders — use the actual subtopics visible in the data above), a priority
(1=build first), and a realistic word count. Only include clusters genuinely supported by the
data — don't invent generic Local/FAQ clusters if there's no local or FAQ signal in the data."""

    result = call_gemini(
        api_key=api_key,
        system_prompt="You are an SEO content architect designing a topical authority plan strictly grounded in the real SERP data provided.",
        user_prompt=user_prompt,
        schema=_TOPICAL_SCHEMA,
        model=model,
        temperature=0.5,
    )

    if result["ok"]:
        d = result["data"]
        clusters = []
        for c in d.get("clusters", []):
            clusters.append({
                "name": c.get("name", "Cluster"),
                "intent": c.get("intent", "Informational"),
                "description": c.get("description", ""),
                "topics": [t for t in c.get("topics", []) if t] or [query or "Core Topic"],
                "priority": max(1, min(3, int(c.get("priority", 2) or 2))),
                "word_count": max(300, int(c.get("word_count", 1200) or 1200)),
            })
        if not clusters:
            # Gemini returned nothing usable — fall through to formula instead of an empty plan
            plan = serp_analyzer.generate_topical_authority(brief_data)
            plan["meta"] = {"source": "formula", "reason": "ai_returned_no_clusters"}
            return plan

        pillar = {
            "title": d.get("pillar_title") or (f"The Complete Guide to {query.title()}" if query else "The Complete Guide"),
            "type": "Pillar Page",
            "priority": 1,
            "word_count": 3000,
            "cta": "Read the full guide",
            "description": d.get("pillar_description", ""),
        }
        plan = serp_analyzer.build_topical_plan_from_clusters(query, pillar, clusters, semantic, related, autocomplete)
        plan["meta"] = {"source": "ai"}
        return plan

    plan = serp_analyzer.generate_topical_authority(brief_data)
    plan["meta"] = {"source": "formula", "reason": result.get("error")}
    return plan


# ═══════════════════════════════════════════════════════════════════════════
#  5. "NOT FOUND" RECOVERY PLAN — Position Tracker
# ═══════════════════════════════════════════════════════════════════════════

_RECOVERY_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "likely_reasons": {
            "type": "ARRAY", "items": {"type": "STRING"},
            "description": "3-5 specific, evidence-based reasons the target isn't ranking at all for this query — grounded in the gap between what's ranking and what the target page currently has (or lacks)",
        },
        "competitor_pattern_summary": {
            "type": "STRING",
            "description": "1-2 sentences on what the ranking pages have in common (format, depth, angle) that the target is missing",
        },
        "target_page_recommendation": {
            "type": "STRING",
            "description": "Whether to optimize the existing page, build a new dedicated page, or restructure — and why",
        },
        "content_recommendations": {
            "type": "ARRAY", "items": {"type": "STRING"},
            "description": "Specific, concrete content additions/changes — not generic 'improve your content' advice",
        },
        "citation_recommendations": {
            "type": "ARRAY", "items": {"type": "STRING"},
            "description": "Specific citation/backlink/partnership leads grounded in the data provided, or general categories if no citation data was available",
        },
        "quick_wins": {
            "type": "ARRAY", "items": {"type": "STRING"},
            "description": "The 1-3 fastest, highest-leverage fixes to try first",
        },
    },
    "required": ["likely_reasons", "competitor_pattern_summary", "target_page_recommendation",
                 "content_recommendations", "citation_recommendations", "quick_wins"],
}


def get_recovery_plan(query: str, target_url: str, serp_json: dict, target_page_data: dict | None,
                       bl_data: dict | None, api_key: str, model: str = DEFAULT_MODEL) -> dict:
    """
    For when the target doesn't appear in the SERP at all — a diagnostic "why not,
    and what to do about it" plan, grounded in what's actually ranking instead of
    generic SEO advice. Distinct from get_content_brief (which improves something
    already ranking): this is for getting on the map in the first place.

    Returns {"ok": bool, "source": str, ...fields}. Falls back to a lightweight
    formula-based diagnostic (no Gemini needed) if no key/failure.
    """
    organic = (serp_json or {}).get("organic_results", [])[:8]
    competitor_summaries = [
        f'#{o.get("position", i+1)}: "{o.get("title","")}" — {(o.get("snippet","") or "")[:150]} ({o.get("link","")})'
        for i, o in enumerate(organic)
    ]

    if target_page_data and "error" not in (target_page_data or {}):
        target_summary = (
            f"Page found at {target_url}:\n"
            f"Title: {target_page_data.get('meta_title','(none)')}\n"
            f"Meta description: {target_page_data.get('meta_description','(none)')}\n"
            f"Word count: {target_page_data.get('word_count', 0)}\n"
            f"H1s: {target_page_data.get('h1s', [])}\n"
            f"H2s: {target_page_data.get('h2s', [])[:10]}"
        )
    else:
        target_summary = f"No page data available for {target_url} on this topic — it may not have a dedicated page for this query, or wasn't inspected."

    citation_note = "Not scanned — enable Citation Gap Scout for citation-specific leads."
    if bl_data and bl_data.get("link_gap"):
        top_citations = [d["domain"] for d in bl_data["link_gap"][:8]]
        citation_note = f"Domains cited by these top-ranking competitors: {', '.join(top_citations)}"

    user_prompt = f"""This target is NOT appearing anywhere in the top {len(organic) or 'N'} Google results
for this query. Diagnose why, grounded strictly in the evidence below — no generic SEO advice.

QUERY: "{query}"
TARGET: {target_url}

TOP-RANKING COMPETITORS RIGHT NOW:
{chr(10).join(competitor_summaries) or "none available"}

TARGET PAGE STATUS:
{target_summary}

CITATION SIGNAL:
{citation_note}

Diagnose: what pattern do the ranking pages share that the target lacks? Is this a missing-page
problem, a thin-content problem, a wrong-page-targeting problem, or a citation/authority problem?
Give specific, concrete recommendations — not "improve your SEO". End with the 1-3 fastest wins
to try first."""

    result = call_gemini(
        api_key=api_key,
        system_prompt="You are a senior SEO consultant diagnosing why a specific page isn't ranking at all, grounded strictly in the real competitor and page data provided. Be concrete and specific, never generic.",
        user_prompt=user_prompt,
        schema=_RECOVERY_SCHEMA,
        model=model,
        temperature=0.4,
    )

    if result["ok"]:
        d = result["data"]
        d["ok"] = True
        d["source"] = "ai"
        return d

    has_page = bool(target_page_data and "error" not in (target_page_data or {}))
    reasons = []
    recs = []
    if not has_page:
        reasons.append("No dedicated page was found/inspected for this query — Google may have nothing relevant to rank.")
        recs.append(f"Create a dedicated page specifically targeting \"{query}\".")
    else:
        wc = target_page_data.get("word_count", 0)
        if wc and wc < 500:
            reasons.append(f"Target page is thin ({wc} words) compared to typical top-10 depth.")
            recs.append("Expand the page significantly — cover subtopics competitors address that this page doesn't.")
        if not target_page_data.get("h1s"):
            reasons.append("Target page has no clear H1 matching the query intent.")
            recs.append(f"Add a clear H1 that reflects \"{query}\" directly.")
    if not reasons:
        reasons.append("Page exists with reasonable depth but still isn't ranking — likely an authority/citation gap rather than a content gap.")
        recs.append("Focus on earning citations/backlinks from the same types of sites currently linked to by top-ranking competitors.")

    return {
        "ok": True, "source": "formula",
        "likely_reasons": reasons,
        "competitor_pattern_summary": "Connect a Gemini API key for a detailed pattern analysis of what's currently ranking.",
        "target_page_recommendation": "Create a new dedicated page." if not has_page else "Expand and refocus the existing page.",
        "content_recommendations": recs,
        "citation_recommendations": ["Run Citation Gap Scout in this tab for specific outreach leads."],
        "quick_wins": recs[:2] or ["Create a dedicated, well-structured page targeting this exact query."],
    }


# ═══════════════════════════════════════════════════════════════════════════
#  6. "HOW DO WE MOVE UP?" IMPROVEMENT PLAN — Position Tracker (found, not top)
# ═══════════════════════════════════════════════════════════════════════════

_IMPROVEMENT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "position_gap_summary": {
            "type": "STRING",
            "description": "1-2 sentences on the core gap between the target and the pages ranking above it",
        },
        "structural_gaps": {
            "type": "ARRAY", "items": {"type": "STRING"},
            "description": "Specific headings/subtopics the pages above cover that the target page doesn't — named directly from their real H2/H3s, not generic",
        },
        "content_depth_comparison": {
            "type": "STRING",
            "description": "How the target's word count/depth compares to the pages above, and what that implies",
        },
        "style_readability_notes": {
            "type": "STRING",
            "description": "Concrete comparison of writing style/readability between target and pages above (e.g. sentence length, tone, structure), grounded in the scores provided",
        },
        "citation_gap_recommendations": {
            "type": "ARRAY", "items": {"type": "STRING"},
            "description": "Specific citation/backlink leads grounded in the data provided, or general categories if none available",
        },
        "priority_actions": {
            "type": "ARRAY", "items": {"type": "STRING"},
            "description": "3-6 specific actions ordered by expected impact, each concrete enough to hand to a writer/developer directly",
        },
        "estimated_effort": {
            "type": "STRING", "enum": ["Quick edit (hours)", "Moderate rewrite (days)", "Major overhaul (weeks)"],
        },
    },
    "required": ["position_gap_summary", "structural_gaps", "content_depth_comparison",
                 "style_readability_notes", "citation_gap_recommendations", "priority_actions", "estimated_effort"],
}


def get_improvement_plan(query: str, target_url: str, target_position: int,
                          pages_above_content: dict, target_page_data: dict | None,
                          bl_data: dict | None, api_key: str, model: str = DEFAULT_MODEL) -> dict:
    """
    For when the target IS ranking, but not at the top — a gap-closing plan built by
    actually scraping the pages currently outranking it (real headings, word counts,
    readability scores, detected content style via serp_analyzer.analyze_serp_content()),
    not just comparing titles/snippets. Distinct from get_recovery_plan (for "not found
    at all") and get_content_brief (for planning new content from scratch).

    pages_above_content: output of serp_analyzer.analyze_serp_content() scoped to just
    the organic results ranking above target_position.

    Returns {"ok": bool, "source": str, ...fields}.
    """
    comp_lines = []
    for c in (pages_above_content or {}).get("competitor_scores", [])[:5]:
        comp_lines.append(
            f'#{c.get("position")} "{c.get("title","")}" ({c.get("url","")})\n'
            f'  Word count: {c.get("word_count",0)} | Content score: {c.get("score","?")}/100 | '
            f'Style: {c.get("content_style","")} | Readability grade: {c.get("readability","?")}\n'
            f'  H1: {c.get("h1s",[])[:2]}\n'
            f'  H2s: {c.get("h2s",[])[:10]}'
        )

    target_grade = None
    if target_page_data and "error" not in (target_page_data or {}) and target_page_data.get("full_text"):
        target_grade = content_grader.grade_content(target_page_data["full_text"])

    if target_page_data and "error" not in (target_page_data or {}):
        target_summary = (
            f"Title: {target_page_data.get('meta_title','(none)')}\n"
            f"Word count: {target_page_data.get('word_count', 0)}\n"
            f"H1s: {target_page_data.get('h1s', [])}\n"
            f"H2s: {target_page_data.get('h2s', [])[:12]}"
        )
        if target_grade and "error" not in target_grade:
            target_summary += (
                f"\nContent score: {target_grade['content_score']}/100 | "
                f"Readability grade: {target_grade['readability_scores']['flesch_kincaid_grade']} | "
                f"Avg sentence length: {target_grade['avg_sentence_length']}"
            )
    else:
        target_summary = f"Target page at {target_url} was not inspected — enable 'Inspect target page links' for a detailed structural comparison."

    citation_note = "Not scanned — enable Citation Gap Scout for citation-specific leads."
    if bl_data and bl_data.get("link_gap"):
        top_citations = [d["domain"] for d in bl_data["link_gap"][:8]]
        citation_note = f"Domains cited by the pages ranking above you: {', '.join(top_citations)}"

    user_prompt = f"""The target is ranking at position #{target_position} for this query — not in the
top spots. Build a specific gap-closing plan by comparing it against the pages ACTUALLY
outranking it right now (real scraped content below, not guesses).

QUERY: "{query}"
TARGET: {target_url} (currently #{target_position})

PAGES CURRENTLY RANKING ABOVE THE TARGET (real scraped headings, word counts, scores):
{chr(10).join(f"{'-'*40}{chr(10)}{c}" for c in comp_lines) or "none available"}

TARGET PAGE (current state):
{target_summary}

CITATION SIGNAL:
{citation_note}

Compare the target directly against the pages above it. Identify SPECIFIC structural gaps
(name real headings/subtopics they cover that the target doesn't), a content depth comparison,
concrete style/readability differences, citation leads, and 3-6 priority actions ordered by
expected impact — specific enough to hand directly to a writer or developer. Give an overall
effort estimate."""

    result = call_gemini(
        api_key=api_key,
        system_prompt="You are a senior SEO strategist building a gap-closing plan by comparing a target page directly against the real pages currently outranking it. Be specific and grounded — cite real headings and numbers from the data given, never generic advice.",
        user_prompt=user_prompt,
        schema=_IMPROVEMENT_SCHEMA,
        model=model,
        temperature=0.4,
    )

    if result["ok"]:
        d = result["data"]
        d["ok"] = True
        d["source"] = "ai"
        return d

    # Formula fallback — deterministic comparison using the same scraped data, no Gemini needed
    comp_scores = (pages_above_content or {}).get("competitor_scores", [])
    avg_wc = round(sum(c.get("word_count", 0) for c in comp_scores) / len(comp_scores)) if comp_scores else 0
    avg_score = round(sum(c.get("score", 0) for c in comp_scores) / len(comp_scores)) if comp_scores else 0
    target_wc = target_page_data.get("word_count", 0) if target_page_data else 0
    target_score = target_grade.get("content_score", 0) if (target_grade and "error" not in target_grade) else 0

    gaps, actions = [], []
    if avg_wc and target_wc and target_wc < avg_wc * 0.7:
        gaps.append(f"Target is significantly shorter ({target_wc} words) than the average of pages above it ({avg_wc} words).")
        actions.append(f"Expand target content toward ~{avg_wc} words, covering the missing subtopics below.")
    top_missing_h2s = list(dict.fromkeys(
        h for c in comp_scores for h in c.get("h2s", [])[:5]
        if h not in (target_page_data.get("h2s", []) if target_page_data else [])
    ))[:8]
    if top_missing_h2s:
        gaps.append("Headings covered by pages above but missing from target: " + "; ".join(top_missing_h2s[:5]))
        actions.append("Add sections covering: " + ", ".join(top_missing_h2s[:3]))
    if target_score and avg_score and target_score < avg_score:
        gaps.append(f"Target content score ({target_score}/100) is below the average of pages above it ({avg_score}/100).")

    return {
        "ok": True, "source": "formula",
        "position_gap_summary": f"Target ranks #{target_position}; comparing structure and depth against the {len(comp_scores)} pages currently above it." if comp_scores else "Limited comparison data available.",
        "structural_gaps": gaps or ["Connect a Gemini API key for a detailed structural comparison."],
        "content_depth_comparison": f"Target: {target_wc} words vs. average {avg_wc} words for pages above." if avg_wc else "Word count comparison unavailable.",
        "style_readability_notes": "Connect a Gemini API key for style/readability comparison.",
        "citation_gap_recommendations": ["Run Citation Gap Scout for specific outreach leads."],
        "priority_actions": actions or ["Connect a Gemini API key, or inspect the target page, for specific recommendations."],
        "estimated_effort": "Moderate rewrite (days)",
    }


# ═══════════════════════════════════════════════════════════════════════════
#  7. LLM CITATION CHECK — does Gemini itself cite you when grounded-answering?
# ═══════════════════════════════════════════════════════════════════════════

def get_llm_citation_check(query: str, target_url: str, api_key: str, model: str = DEFAULT_MODEL) -> dict:
    """
    Asks Gemini the query directly with Google Search grounding enabled, and checks
    whether the target domain appears among the sources Gemini actually cited in its
    grounded answer.

    This is a DIFFERENT signal from check_ai_overview_presence() / check_paa_presence()
    in serp_analyzer.py — those read Google's own SERP/AI Overview (via SerpAPI).
    This one reflects visibility in Gemini's own grounded answers specifically — a
    distinct, separate answer surface, not a replacement for real SERP position data.

    Requires a Gemini API key — there's no formula fallback for this one, since
    there's nothing to fall back to (it's not modeling anything SerpAPI already gives us).

    Returns {"ok": bool, "cited": bool, "position": int|None, "matches": [...],
             "total_citations": int, "all_citations": [...], "answer_excerpt": str, "error": str|None}
    """
    prompt = f"{query}\n\nAnswer directly and concisely based on current, real information."
    result = call_gemini_grounded(api_key, prompt, model=model)

    if not result["ok"]:
        return {
            "ok": False, "cited": False, "position": None, "matches": [],
            "total_citations": 0, "all_citations": [], "answer_excerpt": "",
            "error": result.get("error"),
        }

    target_domain = domain_of(target_url)
    citations = result.get("citations", [])
    matches = []
    for idx, c in enumerate(citations, start=1):
        if target_domain and target_domain == domain_of(c.get("url", "")):
            matches.append({"position": idx, "title": c.get("title", ""), "url": c.get("url", "")})

    return {
        "ok": True,
        "cited": len(matches) > 0,
        "position": matches[0]["position"] if matches else None,
        "matches": matches,
        "total_citations": len(citations),
        "all_citations": citations[:10],
        "answer_excerpt": (result.get("text", "") or "")[:500],
        "error": None,
    }
