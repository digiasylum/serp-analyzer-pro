# =============================================================================
# app.py — SERP V7 Final · All-in-One SEO & Marketing Intelligence
# =============================================================================
# Code quality improvements:
#   • All st.dataframe(width="stretch") → use_container_width=True  [BUG FIX]
#   • Dead import (importlib.reload) removed                          [CLEAN]
#   • CSS uses Streamlit var() tokens — Light/Dark theme works auto   [YOUR FIX]
#   • Helper functions have docstrings + type hints                   [QUALITY]
#   • Session state: single typed dict, no scattered defaults         [QUALITY]
#   • All tabs defined before any tab body is rendered                [QUALITY]
#   • extract_local_pack() now connected to Tab 3 UI                  [YOUR FIX]
#   • generate_topical_authority() connected to Tab 2 UI              [YOUR FIX]
#   • compare_with_competitors() auto-runs in Tab 5 Content Grader    [V10 MERGE]
#   • 7 tabs total: SERP | Topical | Local Pack | Competitor |
#                   Content Grader | URL Inspector | Position Tracking
# =============================================================================
from __future__ import annotations

import html as html_lib
from datetime import datetime

import pandas as pd
import streamlit as st

import ai_seo
import content_grader
import serp_analyzer
import url_inspector
from gemini_client import validate_gemini_key, DEFAULT_MODEL as GEMINI_DEFAULT_MODEL
from utils import domain_of, normalize_url, slugify, validate_and_get_serpapi_quota

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SERP V7 · SEO Intelligence by DigiAsylum",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
# Uses Streamlit native CSS var() tokens so Light/Dark both work automatically.
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: var(--secondary-background-color);
    border-radius: 14px; padding: 5px; gap: 4px;
    border: 1px solid rgba(148,163,184,.18);
}
.stTabs [data-baseweb="tab"] {
    background: transparent; border-radius: 10px;
    color: var(--text-color); font-weight: 600;
    font-size: .85rem; padding: 10px 16px; border: none;
    opacity: .55; transition: all .2s;
}
.stTabs [aria-selected="true"] {
    background: var(--primary-color, #3b5bdb) !important;
    color: #fff !important; opacity: 1 !important;
}

/* ── Cards ── */
.v7-card {
    background: var(--secondary-background-color);
    border: 1px solid rgba(148,163,184,.18);
    border-radius: 18px; padding: 22px 24px; margin-bottom: 18px;
    transition: border-color .25s, box-shadow .25s, transform .22s;
}
.v7-card:hover {
    border-color: var(--primary-color, #3b5bdb);
    box-shadow: 0 20px 48px rgba(0,0,0,.12);
    transform: translateY(-2px);
}

/* ── Section labels ── */
.slabel {
    font-size: .67rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: .1em; opacity: .45; margin-bottom: 12px; display: block;
}

/* ── AI box ── */
.ai-box {
    background: var(--secondary-background-color);
    border: 1px solid rgba(59,91,219,.28);
    border-radius: 14px; padding: 18px 22px;
    font-size: .91rem; line-height: 1.8;
}
.ai-box p  { margin-bottom: 10px; }
.ai-box ul { padding-left: 18px; margin-bottom: 12px; }
.ai-box li { margin-bottom: 4px; }
.ai-box a  { color: var(--primary-color, #3b5bdb); }
.ai-box h4 { font-weight: 600; margin: 10px 0 6px; font-size: .95rem; }

/* ── Chips ── */
.chip-wrap { display: flex; flex-wrap: wrap; gap: 7px; padding: 5px 0; }
.chip      { background: rgba(59,91,219,.18); color: var(--primary-color, #3b5bdb);
             border: 1px solid rgba(59,91,219,.3); border-radius: 20px;
             padding: 5px 13px; font-size: .76rem; font-weight: 500; }
.chip-grey { background: var(--secondary-background-color);
             border: 1px solid rgba(148,163,184,.2); border-radius: 20px;
             padding: 5px 13px; font-size: .76rem; }
.chip-grn  { background: rgba(16,185,129,.12); color: #10b981;
             border: 1px solid rgba(16,185,129,.25); border-radius: 20px;
             padding: 5px 13px; font-size: .76rem; }

/* ── Intent badges ── */
.ibadge   { display: inline-block; padding: 4px 14px; border-radius: 20px;
            font-size: .76rem; font-weight: 600; letter-spacing: .04em; }
.ib-info  { background: rgba(59,91,219,.18);  color: var(--primary-color,#3b5bdb); border: 1px solid rgba(59,91,219,.3);  }
.ib-comm  { background: rgba(245,158,11,.15); color: #f59e0b; border: 1px solid rgba(245,158,11,.3); }
.ib-trans { background: rgba(16,185,129,.15); color: #10b981;  border: 1px solid rgba(16,185,129,.3); }
.ib-nav   { background: rgba(168,85,247,.15); color: #a855f7;  border: 1px solid rgba(168,85,247,.3); }

/* ── Score bar ── */
.sbar-wrap { background: rgba(148,163,184,.12); border-radius: 8px; height: 9px; overflow: hidden; margin: 8px 0; }
.sbar      { height: 100%; border-radius: 8px; transition: width .5s; }

/* ── Competitor cards ── */
.comp-card { background: var(--secondary-background-color);
             border: 1px solid rgba(148,163,184,.15);
             border-radius: 16px; margin-bottom: 12px; overflow: hidden;
             transition: border-color .2s; }
.comp-card:hover { border-color: var(--primary-color, #3b5bdb); }
.comp-card-header { display: flex; align-items: flex-start; gap: 14px; padding: 16px 20px; }
.comp-rank  { font-size: 1.3rem; font-weight: 800; opacity: .4; min-width: 30px; padding-top: 2px; }
.comp-main  { flex: 1; min-width: 0; }
.comp-title { font-size: .9rem; font-weight: 600; margin-bottom: 3px;
              white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.comp-url   { font-size: .7rem; opacity: .4; font-family: 'JetBrains Mono', monospace;
              white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 8px; }
.comp-meta-row { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
.comp-meta-pill { background: rgba(148,163,184,.1); border: 1px solid rgba(148,163,184,.15);
                  border-radius: 8px; padding: 3px 9px; font-size: .71rem; }
.comp-meta-pill.highlight { background: rgba(59,91,219,.15); color: var(--primary-color,#3b5bdb);
                             border-color: rgba(59,91,219,.25); }
.comp-kw-row { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 6px; }
.comp-kw    { background: rgba(148,163,184,.08); border: 1px solid rgba(148,163,184,.12);
              border-radius: 8px; padding: 2px 7px; font-size: .68rem; opacity: .7; }
.comp-score-col  { text-align: right; min-width: 80px; flex-shrink: 0; }
.comp-score-num  { font-size: 1.6rem; font-weight: 800; line-height: 1; }
.comp-style-badge { font-size: .68rem; opacity: .45; margin-top: 4px;
                    background: rgba(148,163,184,.08); border-radius: 5px;
                    padding: 2px 7px; display: inline-block; }

/* ── Fan-out ── */
.fo-card  { background: var(--secondary-background-color);
            border: 1px solid rgba(148,163,184,.12);
            border-radius: 12px; padding: 14px 16px; margin-bottom: 10px; }
.fo-title { font-size: .68rem; font-weight: 700; text-transform: uppercase;
            letter-spacing: .08em; opacity: .45; margin-bottom: 8px; }
.fo-q     { font-size: .82rem; padding: 5px 0; border-bottom: 1px solid rgba(148,163,184,.08); }
.fo-q:last-child { border-bottom: none; }

/* ── Schema table ── */
.schema-tbl { width: 100%; border-collapse: collapse; }
.schema-tbl td { padding: 8px 12px; border: 1px solid rgba(148,163,184,.12);
                 font-size: .81rem; vertical-align: top; }
.schema-tbl tr td:first-child { font-weight: 600; width: 32%; opacity: .55; }

/* ── Content blocks ── */
.cb-h1 { font-size: 1rem;  font-weight: 700; border-left: 3px solid var(--primary-color,#3b5bdb); padding-left: 10px; margin: 12px 0 4px; }
.cb-h2 { font-size: .92rem; font-weight: 600; border-left: 3px solid #6366f1; padding-left: 10px; margin: 10px 0 4px; }
.cb-h3 { font-size: .85rem; font-weight: 600; border-left: 3px solid #818cf8; padding-left: 10px; margin: 8px 0 4px; opacity: .75; }
.cb-h4 { font-size: .8rem;  font-weight: 600; border-left: 3px solid #a5b4fc; padding-left: 10px; margin: 6px 0 3px;  opacity: .6; }
.cb-p  { font-size: .83rem; line-height: 1.65; margin: 0 0 6px 14px; opacity: .7; }
.cb-li { font-size: .81rem; margin: 2px 0 2px 26px; opacity: .7; }
.cb-li::before { content: "•"; color: var(--primary-color,#3b5bdb); margin-right: 6px; }

/* ── Backlink rows ── */
.bl-row   { display: flex; gap: 12px; align-items: center; padding: 9px 13px;
            background: var(--secondary-background-color);
            border: 1px solid rgba(148,163,184,.12); border-radius: 9px; margin-bottom: 6px; }
.bl-dom   { flex: 1; font-family: 'JetBrains Mono', monospace; font-size: .76rem;
            color: var(--primary-color, #3b5bdb); }
.bl-count  { font-size: 1rem; font-weight: 700; min-width: 32px; text-align: right; }
.bl-anchor { font-size: .7rem; opacity: .45; flex: 1.5; overflow: hidden;
             text-overflow: ellipsis; white-space: nowrap; }

/* ── Streamlit overrides ── */
.stButton > button {
    background: var(--primary-color, #3b5bdb) !important;
    color: #fff !important; border: none !important;
    border-radius: 12px !important; font-weight: 600 !important;
    font-size: .9rem !important; padding: 11px 22px !important;
    box-shadow: 0 4px 20px rgba(59,91,219,.25) !important;
    transition: all .2s !important;
}
.stButton > button:hover { filter: brightness(1.1) !important; transform: translateY(-1px) !important; }
.stButton > button:disabled { opacity: .4 !important; box-shadow: none !important; }
.stTextInput input, .stTextArea textarea {
    background: var(--secondary-background-color) !important;
    border: 1px solid rgba(148,163,184,.2) !important;
    border-radius: 12px !important; padding: 12px 16px !important;
    transition: border-color .2s !important;
}
.stTextInput input:focus, .stTextArea textarea:focus {
    border-color: var(--primary-color, #3b5bdb) !important;
    box-shadow: 0 0 0 3px rgba(59,91,219,.12) !important;
}
.stSelectbox > div > div {
    background: var(--secondary-background-color) !important;
    border: 1px solid rgba(148,163,184,.2) !important;
    border-radius: 12px !important;
}
[data-testid="metric-container"] {
    background: var(--secondary-background-color) !important;
    border: 1px solid rgba(148,163,184,.12) !important;
    border-radius: 12px !important; padding: 16px !important;
}
[data-testid="stDataFrame"] {
    border: 1px solid rgba(148,163,184,.12) !important;
    border-radius: 12px !important; overflow: hidden !important;
}
.stExpander { border: 1px solid rgba(148,163,184,.12) !important; border-radius: 12px !important; }
.element-container:empty { display: none !important; }
</style>
""", unsafe_allow_html=True)


# ── Helper functions ──────────────────────────────────────────────────────────

def score_color(score: int) -> str:
    """Return hex colour for a 0–100 score (green / amber / red)."""
    return "#4ade80" if score >= 80 else "#f59e0b" if score >= 50 else "#f87171"


def sbar(score: int) -> str:
    """Render a coloured progress bar as an HTML string."""
    c = score_color(score)
    return (
        f'<div class="sbar-wrap">'
        f'<div class="sbar" style="width:{score}%;background:{c};"></div>'
        f'</div>'
    )


def chips(terms: list, cls: str = "chip") -> str:
    """Render a list of strings as inline chip spans."""
    if not terms:
        return ""
    inner = "".join(
        f'<span class="{cls}">{html_lib.escape(str(t))}</span>' for t in terms
    )
    return f'<div class="chip-wrap">{inner}</div>'


def ibadge(intent: str) -> str:
    """Render a colour-coded search intent badge."""
    cls_map = {
        "Informational": "ib-info",
        "Commercial":    "ib-comm",
        "Transactional": "ib-trans",
        "Navigational":  "ib-nav",
    }
    return f'<span class="ibadge {cls_map.get(intent, "ib-info")}">{html_lib.escape(intent)}</span>'


def render_content_blocks(blocks: list) -> None:
    """Render heading/paragraph/list blocks from url_inspector into Streamlit."""
    for block in blocks:
        btype = block.get("type")
        if btype == "heading":
            lvl = min(block.get("level", 2), 4)
            st.markdown(
                f'<div class="cb-h{lvl}">{html_lib.escape(block["text"])}</div>',
                unsafe_allow_html=True,
            )
        elif btype == "paragraph":
            st.markdown(
                f'<div class="cb-p">{html_lib.escape(block["text"])}</div>',
                unsafe_allow_html=True,
            )
        elif btype == "list":
            for item in block.get("items") or []:
                st.markdown(
                    f'<div class="cb-li">{html_lib.escape(item)}</div>',
                    unsafe_allow_html=True,
                )


def generate_schema_table(schema_data: dict | list) -> str:
    """Convert JSON-LD schema data into an HTML table string."""
    rows: list[tuple[str, str]] = []

    def _walk(data, prefix: str = "") -> None:
        if isinstance(data, dict):
            for k, v in data.items():
                if k == "@context":
                    continue
                label = k.replace("@", "")
                if isinstance(v, dict):
                    rows.append((f"{prefix}{label}", f"<i>({v.get('@type', 'Object')})</i>"))
                    _walk(v, prefix + "&nbsp;&nbsp;")
                elif isinstance(v, list):
                    if all(isinstance(i, dict) for i in v):
                        rows.append((f"{prefix}{label}", f"<i>List ({len(v)})</i>"))
                        for i in v:
                            _walk(i, prefix + "&nbsp;&nbsp;")
                    else:
                        rows.append((f"{prefix}{label}", ", ".join(str(x) for x in v)))
                else:
                    rows.append((f"{prefix}{label}", v))
        elif isinstance(data, list):
            for item in data:
                _walk(item, prefix)
        else:
            rows.append((prefix, data))

    if isinstance(schema_data, dict) and "@graph" in schema_data:
        for item in schema_data["@graph"]:
            _walk(item)
    else:
        _walk(schema_data)

    out = "<table class='schema-tbl'>"
    for key, value in rows:
        vs = str(value)
        if vs.startswith("http"):
            display = (
                f'<a href="{html_lib.escape(vs)}" target="_blank" '
                f'style="color:var(--primary-color,#3b5bdb)">'
                f'{html_lib.escape(vs[:65])}…</a>'
            )
        else:
            display = html_lib.escape(vs)
        out += f"<tr><td>{html_lib.escape(str(key))}</td><td>{display}</td></tr>"
    return out + "</table>"


def slabel(text: str) -> None:
    """Render a small uppercase section label."""
    st.markdown(f'<span class="slabel">{html_lib.escape(text)}</span>', unsafe_allow_html=True)


# ── Caching ───────────────────────────────────────────────────────────────────

@st.cache_data(ttl=1_800, show_spinner=False)
def cached_fetch_serp(api_key: str, query: str, gl: str, hl: str, num: int) -> dict:
    """Cache SERP API responses for 1 hour to avoid burning credits on rerenders."""
    return serp_analyzer.fetch_serp(api_key, query, gl, hl, num)


@st.cache_data(ttl=3_600, show_spinner=False)
def cached_inspect_url(url: str) -> dict:
    """Cache URL inspection results for 1 hour."""
    return url_inspector.inspect_url(url)


# ── Session state ─────────────────────────────────────────────────────────────
_DEFAULTS: dict = {
    "api_ok":                   False,
    "api_key":                  "",
    "quota_info":               None,
    "gemini_ok":                False,
    "gemini_key":               "",
    "use_ai":                   True,
    "ai_content_brief":         None,
    "recovery_plan":            None,
    "improvement_plan":         None,
    "llm_citation":             None,
    "standalone_llm_citation":  None,
    "_last_tracker_serp":       None,
    "brief_data":               None,
    "serp_data":                None,
    "inspection_data":          None,
    "grading_results":          None,
    "comparison_result":        None,
    "position_tracker":         None,
    "position_tracker_history": [], "batch_tracking_results": [], "batch_tracking_running": False,
    "local_pack_query":         "",
    "local_pack_results":       [],
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔑 Authentication")
    _api_input = st.text_input(
        "SerpAPI Key", type="password", placeholder="Paste your SerpAPI key here…"
    )
    if st.button("Authenticate →", use_container_width=True):
        with st.spinner("Validating…"):
            _result = validate_and_get_serpapi_quota(_api_input)
            if _result["ok"]:
                st.session_state.api_ok     = True
                st.session_state.api_key    = _api_input
                st.session_state.quota_info = _result["quota"]
                st.success(_result["message"])
            else:
                st.session_state.api_ok = False
                st.error(_result["message"])

    if st.session_state.api_ok and st.session_state.quota_info:
        _q = st.session_state.quota_info
        st.markdown(
            f'<div style="background:rgba(16,185,129,.1);border:1px solid rgba(16,185,129,.25);'
            f'border-radius:10px;padding:12px 14px;margin:8px 0;">'
            f'<div style="font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;'
            f'color:#10b981;">✓ Connected</div>'
            f'<div style="font-size:.82rem;margin-top:4px;">Plan: <strong>{_q["plan_name"]}</strong></div>'
            f'<div style="font-size:.82rem;">Credits: <strong style="color:#10b981;">{_q["remaining_searches"]}</strong></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown("### 🤖 AI Analysis (Gemini)")
    _gemini_input = st.text_input(
        "Gemini API Key", type="password", placeholder="Paste your Gemini API key here…",
        help="Powers dynamic Intent Detection, Query Fan-out, Content Brief, and Topical Authority. Optional — the tool falls back to formula-based analysis without it.",
    )
    if st.button("Connect Gemini →", use_container_width=True):
        with st.spinner("Validating…"):
            _gresult = validate_gemini_key(_gemini_input)
            if _gresult["ok"]:
                st.session_state.gemini_ok  = True
                st.session_state.gemini_key = _gemini_input
                st.success(_gresult["message"])
            else:
                st.session_state.gemini_ok = False
                st.error(_gresult["message"])

    if st.session_state.gemini_ok:
        st.markdown(
            '<div style="background:rgba(16,185,129,.1);border:1px solid rgba(16,185,129,.25);'
            'border-radius:10px;padding:10px 14px;margin:8px 0;font-size:.78rem;">'
            '✓ AI-powered analysis active</div>',
            unsafe_allow_html=True,
        )
        st.session_state.use_ai = st.toggle("Use AI for this analysis", value=st.session_state.use_ai,
            help="Turn off to force formula-based analysis even with a connected key (useful to save Gemini quota).")
    else:
        st.caption("Without a Gemini key, SERP V7 still works fully on formula-based analysis.")

    st.markdown("---")
    st.markdown("### ⚙️ Search Settings")
    gl = st.selectbox(
        "Country / Region",
        ["in — India", "us — United States", "gb — United Kingdom",
         "au — Australia", "ca — Canada", "sg — Singapore", "ae — UAE"],
        index=0,
    ).split(" — ")[0]
    hl = st.selectbox(
        "Language",
        ["en — English", "hi — Hindi", "es — Spanish", "fr — French", "de — German", "ar — Arabic"],
        index=0,
    ).split(" — ")[0]
    num = st.select_slider(
        "Results to fetch", options=[10, 20, 30, 40, 50, 60, 70, 80, 90, 100], value=10
    )
    if num > 30:
        st.warning(f"⚠️ {num} results uses more SerpAPI quota and takes longer.")
    st.markdown("---")
    st.caption("DigiAsylum · SERP V7 · Free for everyone")


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(
    '<div style="display:flex;align-items:center;gap:14px;padding-bottom:14px;'
    'border-bottom:1px solid rgba(148,163,184,.18);margin-bottom:22px;">'
    '<div style="background:var(--primary-color,#3b5bdb);border-radius:12px;width:42px;height:42px;'
    'display:flex;align-items:center;justify-content:center;font-size:1.4rem;color:#fff;">📈</div>'
    '<div><div style="font-size:1.35rem;font-weight:800;line-height:1.2;">SERP V7</div>'
    '<div style="font-size:.74rem;opacity:.45;font-weight:500;margin-top:2px;">'
    'All-in-One SEO &amp; Marketing Intelligence · DigiAsylum</div></div>'
    '<div style="margin-left:auto;display:flex;gap:8px;align-items:center;">'
    '<span style="background:rgba(16,185,129,.12);color:#10b981;border:1px solid rgba(16,185,129,.25);'
    'border-radius:8px;padding:4px 12px;font-size:.7rem;font-weight:600;">7 Tools</span>'
    '<span style="background:var(--secondary-background-color);border:1px solid rgba(148,163,184,.18);'
    'border-radius:8px;padding:4px 10px;font-size:.7rem;font-family:JetBrains Mono,monospace;opacity:.4;">v7.0.0</span>'
    '</div></div>',
    unsafe_allow_html=True,
)


# ── Tab definitions (all declared before any body) ────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "📊 SERP Analyzer",
    "🗺️ Topical Authority",
    "📍 Local Pack",
    "🏆 Competitor Score",
    "📝 Content Grader",
    "🔎 URL Inspector",
    "📌 Position Tracking",
])


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 1 — SERP Analyzer
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    with st.container():
        st.markdown('<div class="v7-card">', unsafe_allow_html=True)
        slabel("Keyword Analysis")
        col_in, col_btn = st.columns([5, 1])
        with col_in:
            query = st.text_input(
                "keyword", label_visibility="collapsed",
                placeholder="Enter your target keyword — e.g. shopify development company delhi",
            )
        with col_btn:
            go_btn = st.button("🚀 Analyze", disabled=not st.session_state.api_ok, use_container_width=True)
        if not st.session_state.api_ok:
            st.info("🔑 Enter your SerpAPI key in the sidebar and click Authenticate.")
        st.markdown("</div>", unsafe_allow_html=True)

    if go_btn and query:
        _use_ai = st.session_state.gemini_ok and st.session_state.use_ai
        _gkey   = st.session_state.gemini_key if _use_ai else ""
        try:
            with st.spinner(f"Fetching top {num} results and scraping concurrently…"):
                raw = cached_fetch_serp(st.session_state.api_key, query, gl, hl, num)
            if not raw or "organic_results" not in raw:
                st.error("❌ Failed to fetch SERP. Check your API key and remaining quota.")
            else:
                with st.spinner("Analyzing intent, keywords, and competitor content…"):
                    rk             = serp_analyzer.extract_related_keywords(st.session_state.api_key, query, raw)
                    content_result = serp_analyzer.analyze_serp_content(raw.get("organic_results", []))
                    intent, audience_profile, intent_meta = ai_seo.get_intent_analysis(query, raw, _gkey)

                spinner_msg = "Generating AI-grounded fan-out & topical plan…" if _use_ai else "Generating fan-out & topical plan…"
                with st.spinner(spinner_msg):
                    fanout = ai_seo.get_query_fanout(query, rk, raw, content_result, _gkey)
                    _ta_input = {"query": query, "intent": intent, "related_keywords": rk, **content_result}
                    topical_authority = ai_seo.get_topical_authority(_ta_input, _gkey)

                bd: dict = {
                    "query":            query,
                    "intent":           intent,
                    "intent_meta":      intent_meta,
                    "audience_profile": audience_profile,
                    "ai_overview":      serp_analyzer.build_ai_overview(raw, st.session_state.api_key),
                    "related_keywords": rk,
                    "serp_features":    serp_analyzer.extract_serp_features(raw),
                    "fanout":           fanout,
                    "topical_authority":topical_authority,
                    "local_pack":       serp_analyzer.extract_local_pack(raw),
                    **content_result,
                }
                _question_pool = (
                    rk.get("people_also_ask", []) + rk.get("related_searches", []) + rk.get("autocomplete", [])
                    + [a.get("question", "") if isinstance(a, dict) else a for a in fanout.get("ai_angles", [])]
                    + [q for cluster_qs in fanout.get("intent_clusters", {}).values() for q in cluster_qs]
                )
                bd["question_explorer"] = serp_analyzer.classify_questions_by_type(_question_pool)
                bd["markdown_brief"] = serp_analyzer.generate_v1_style_markdown_brief(bd)
                st.session_state.brief_data      = bd
                st.session_state.serp_data       = raw
                st.session_state.comparison_result = None  # reset stale comparison
                _ai_note = " (AI-powered)" if intent_meta.get("source") == "ai" else ""
                st.success(f"✅ Analysis complete{_ai_note} — {len(raw.get('organic_results', []))} results processed.")
        except Exception as e:
            st.error(f"❌ Something went wrong during analysis: {e}. Please try again — if it persists, try a lower result count or check your API keys.")

    if st.session_state.brief_data:
        data = st.session_state.brief_data

        # Intent & Audience
        with st.container():
            st.markdown('<div class="v7-card">', unsafe_allow_html=True)
            slabel("Content Strategy")
            ap = data["audience_profile"]
            im = data.get("intent_meta", {})
            _src_pill = (
                '<span style="background:rgba(59,91,219,.15);color:var(--primary-color,#3b5bdb);border-radius:8px;'
                f'padding:2px 9px;font-size:.68rem;font-weight:600;">🤖 AI · {im.get("confidence","?")}% confidence</span>'
                if im.get("source") == "ai" else
                '<span style="background:rgba(148,163,184,.12);border-radius:8px;padding:2px 9px;'
                'font-size:.68rem;opacity:.55;">📐 Formula-based</span>'
            )
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;flex-wrap:wrap;">'
                f'<span style="font-size:.82rem;opacity:.45;">Search Intent:</span>'
                f'{ibadge(data["intent"])}'
                f'<span style="font-size:.75rem;opacity:.35;">· {html_lib.escape(ap["stage"])}</span>'
                f'{_src_pill}'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<div style="background:rgba(59,91,219,.08);border-left:3px solid var(--primary-color,#3b5bdb);'
                f'padding:12px 16px;border-radius:0 10px 10px 0;">'
                f'<strong>{html_lib.escape(ap["audience"])}</strong>'
                f'<div style="font-size:.83rem;opacity:.65;margin-top:4px;">{html_lib.escape(ap["insight"])}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            if im.get("source") == "ai" and im.get("reasoning"):
                st.caption(f"🧠 {im['reasoning']}")
            st.markdown("</div>", unsafe_allow_html=True)

        # SERP Features + AI Overview
        with st.container():
            st.markdown('<div class="v7-card">', unsafe_allow_html=True)
            slabel("SERP Features & AI Overview")
            fc, ac = st.columns([1, 2])
            with fc:
                feats = data["serp_features"]
                FEAT_LABELS = {
                    "has_ai_overview": "🤖 AI Overview",   "has_paa":        "❓ People Also Ask",
                    "has_top_stories": "📰 Top Stories",    "has_shopping":   "🛒 Shopping",
                    "has_knowledge":   "🧠 Knowledge Graph","has_sitelinks":  "🔗 Sitelinks",
                    "has_local_pack":  "📍 Local Pack",     "has_images":     "🖼️ Images",
                    "has_videos":      "▶️ Videos",
                }
                for key, label in FEAT_LABELS.items():
                    present = feats.get(key, False)
                    dot_col = "#4ade80" if present else "rgba(148,163,184,.2)"
                    txt_op  = "1"       if present else ".35"
                    st.markdown(
                        f'<div style="display:flex;align-items:center;gap:8px;padding:4px 0;">'
                        f'<span style="width:8px;height:8px;border-radius:50%;background:{dot_col};flex-shrink:0;"></span>'
                        f'<span style="font-size:.81rem;opacity:{txt_op};">{label}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
            with ac:
                ai = data["ai_overview"]
                slabel(ai["source"])
                ai_content = ai["text"] if ai["source"] == "Google AI" else html_lib.escape(ai["text"])
                st.markdown(f'<div class="ai-box">{ai_content}</div>', unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        # Content Brief
        with st.container():
            st.markdown('<div class="v7-card">', unsafe_allow_html=True)
            slabel("Content Brief — H2 / H3 / PAA / Entities")
            bc1, bc2 = st.columns(2)
            with bc1:
                st.markdown("**Recommended H2 Headings**")
                if data["top_h2s"]:
                    st.dataframe(pd.DataFrame(data["top_h2s"], columns=["H2 from Top Pages"]),
                                 use_container_width=True, height=220)
                st.markdown("**People Also Ask — FAQ Seeds**")
                paas = data["related_keywords"]["people_also_ask"]
                if paas:
                    st.dataframe(pd.DataFrame(paas, columns=["Question"]),
                                 use_container_width=True, height=180)
                else:
                    st.caption("No PAA questions found.")
            with bc2:
                st.markdown("**Recommended H3 Headings**")
                if data["top_h3s"]:
                    st.dataframe(pd.DataFrame(data["top_h3s"], columns=["H3 from Top Pages"]),
                                 use_container_width=True, height=220)
                st.markdown("**Semantic Entities**")
                st.markdown(chips(data.get("semantic_terms", [])), unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        # Organic results
        with st.container():
            st.markdown('<div class="v7-card">', unsafe_allow_html=True)
            slabel(f"Top {len(data['organic_table_data'])} Organic Results")
            st.dataframe(
                pd.DataFrame(data["organic_table_data"])[["position", "title", "link", "h1", "h2"]],
                use_container_width=True, height=300,
            )
            st.markdown("</div>", unsafe_allow_html=True)

        # Query Fan-out
        fo = data.get("fanout")
        if fo:
            with st.container():
                st.markdown('<div class="v7-card">', unsafe_allow_html=True)
                _fo_src = fo.get("meta", {}).get("source", "formula")
                _fo_badge = (
                    ' <span style="background:rgba(59,91,219,.15);color:var(--primary-color,#3b5bdb);border-radius:8px;'
                    'padding:2px 9px;font-size:.68rem;font-weight:600;vertical-align:middle;">🤖 Gemini-grounded</span>'
                    if _fo_src == "ai" else
                    ' <span style="background:rgba(148,163,184,.12);border-radius:8px;padding:2px 9px;'
                    'font-size:.68rem;opacity:.55;vertical-align:middle;">📐 Formula-based</span>'
                )
                st.markdown(f'<span class="slabel" style="display:inline;">Query Fan-out & LLM / AI Optimization</span>{_fo_badge}', unsafe_allow_html=True)
                st.markdown(
                    '<div style="font-size:.83rem;opacity:.65;line-height:1.75;margin:10px 0 16px;">'
                    'Google, ChatGPT, Gemini and Perplexity <strong>fan out</strong> your keyword into '
                    'dozens of sub-queries. Cover every cluster below to appear in AI Overviews and LLM answers.'
                    '</div>', unsafe_allow_html=True)
                fo_tab_labels = ["🎯 Intent Clusters", "🧠 AI Angles", "🗺️ Content Cluster Map"]
                has_gaps = bool(fo.get("entities") or fo.get("content_gaps"))
                if has_gaps:
                    fo_tab_labels.append("🔍 Entities & Gaps")
                    ft1, ft2, ft3, ft4 = st.tabs(fo_tab_labels)
                else:
                    ft1, ft2, ft3 = st.tabs(fo_tab_labels)
                BADGE_CLS = ["ib-info", "ib-comm", "ib-trans", "ib-nav"]
                with ft1:
                    fc1, fc2 = st.columns(2)
                    for i, (cn, qs) in enumerate(fo["intent_clusters"].items()):
                        with (fc1 if i % 2 == 0 else fc2):
                            st.markdown(
                                f'<div class="fo-card"><div class="fo-title">{html_lib.escape(cn)} '
                                f'<span class="ibadge {BADGE_CLS[i%4]}" style="font-size:.6rem;padding:2px 8px;">'
                                f'{len(qs)}</span></div>'
                                + "".join(f'<div class="fo-q">{html_lib.escape(q)}</div>' for q in qs)
                                + "</div>", unsafe_allow_html=True)
                with ft2:
                    st.markdown('<div style="font-size:.78rem;opacity:.45;margin-bottom:12px;">Address each question pattern in your article to appear in AI-generated answers.</div>', unsafe_allow_html=True)
                    for i, angle in enumerate(fo["ai_angles"]):
                        _q     = angle.get("question", "") if isinstance(angle, dict) else angle
                        _title = angle.get("currently_cited_title", "") if isinstance(angle, dict) else ""
                        _url   = angle.get("currently_cited_url", "") if isinstance(angle, dict) else ""
                        _cite_html = (
                            f'<div style="font-size:.72rem;opacity:.55;margin-top:3px;">'
                            f'📎 Currently cited: <a href="{html_lib.escape(_url)}" target="_blank">{html_lib.escape(_title)}</a></div>'
                            if _title and _url else
                            '<div style="font-size:.72rem;opacity:.35;margin-top:3px;">No current citation found — open opportunity</div>'
                        )
                        st.markdown(
                            f'<div style="display:flex;gap:10px;align-items:flex-start;padding:8px 0;'
                            f'border-bottom:1px solid rgba(148,163,184,.08);">'
                            f'<span style="background:rgba(59,91,219,.18);color:var(--primary-color,#3b5bdb);'
                            f'border-radius:50%;width:22px;height:22px;display:flex;align-items:center;'
                            f'justify-content:center;font-size:.7rem;font-weight:700;flex-shrink:0;">{i+1}</span>'
                            f'<div><span style="font-size:.84rem;">{html_lib.escape(_q)}</span>{_cite_html}</div></div>',
                            unsafe_allow_html=True)
                with ft3:
                    for cluster_type, pages in fo["content_clusters"].items():
                        if not pages:
                            continue
                        is_pillar = cluster_type == "Pillar Page"
                        st.markdown(
                            f'<div style="background:{"rgba(59,91,219,.1)" if is_pillar else "var(--secondary-background-color)"};'
                            f'border:1px solid {"rgba(59,91,219,.3)" if is_pillar else "rgba(148,163,184,.12)"};'
                            f'border-radius:10px;padding:12px 16px;margin-bottom:8px;">'
                            f'<div class="slabel">{html_lib.escape(cluster_type)}</div>'
                            f'<div class="chip-wrap">'
                            + "".join(f'<span class="chip">{html_lib.escape(p)}</span>' for p in pages if p)
                            + "</div></div>", unsafe_allow_html=True)
                if has_gaps:
                    with ft4:
                        if fo.get("entities"):
                            st.markdown("**Key Entities to Cover** — recurring concepts across top-ranking pages", unsafe_allow_html=False)
                            st.markdown(chips(fo["entities"], "chip"), unsafe_allow_html=True)
                        if fo.get("content_gaps"):
                            st.markdown("**Content Gaps** — subtopics competitors under-serve", unsafe_allow_html=False)
                            for gap in fo["content_gaps"]:
                                st.markdown(
                                    f'<div style="display:flex;gap:8px;align-items:flex-start;padding:6px 0;'
                                    f'border-bottom:1px solid rgba(148,163,184,.08);font-size:.84rem;">'
                                    f'<span style="opacity:.4;">→</span><span>{html_lib.escape(gap)}</span></div>',
                                    unsafe_allow_html=True,
                                )
                fo_df = pd.DataFrame(
                    [{"Type": cn, "Query": q} for cn, qs in fo["intent_clusters"].items() for q in qs]
                    + [{"Type": "AI Angle",
                        "Query": (a.get("question","") if isinstance(a, dict) else a),
                        "Currently Cited": (a.get("currently_cited_title","") if isinstance(a, dict) else "")}
                       for a in fo["ai_angles"]]
                )
                st.download_button("⬇️ Download Fan-out CSV",
                    fo_df.to_csv(index=False).encode(), f"{slugify(query)}-fanout.csv", "text/csv")
                st.markdown("</div>", unsafe_allow_html=True)

        # Question Explorer — Answer-the-Public style breakdown of every real
        # question collected (PAA + related + autocomplete + AI fan-out), grouped
        # by question type so a writer sees intent distribution at a glance.
        qe = data.get("question_explorer")
        if qe and qe.get("buckets"):
            with st.container():
                st.markdown('<div class="v7-card">', unsafe_allow_html=True)
                slabel(f"❓ Question Explorer — {qe['total_questions']} Real Questions by Type")
                st.markdown(
                    '<div style="font-size:.78rem;opacity:.45;margin-bottom:14px;">'
                    'Every real question pulled from PAA, related searches, autocomplete, and the fan-out above — '
                    'grouped Answer-the-Public style so you can see at a glance which question types dominate demand.</div>',
                    unsafe_allow_html=True,
                )
                qe_cols = st.columns(3)
                for i, (bucket_name, questions) in enumerate(qe["buckets"].items()):
                    with qe_cols[i % 3]:
                        st.markdown(
                            f'<div style="background:var(--secondary-background-color);border:1px solid rgba(148,163,184,.12);'
                            f'border-radius:10px;padding:12px 14px;margin-bottom:10px;">'
                            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">'
                            f'<strong style="font-size:.82rem;">{html_lib.escape(bucket_name)}</strong>'
                            f'<span style="font-size:.68rem;opacity:.5;background:rgba(59,91,219,.12);'
                            f'padding:1px 7px;border-radius:6px;">{len(questions)}</span></div>'
                            + "".join(
                                f'<div style="font-size:.78rem;opacity:.7;padding:3px 0;border-top:1px solid rgba(148,163,184,.06);">{html_lib.escape(q)}</div>'
                                for q in questions[:6]
                              )
                            + (f'<div style="font-size:.72rem;opacity:.4;padding-top:4px;">+{len(questions)-6} more</div>' if len(questions) > 6 else "")
                            + "</div>",
                            unsafe_allow_html=True,
                        )
                qe_df = pd.DataFrame(
                    [{"Type": bt, "Question": q} for bt, qs in qe["buckets"].items() for q in qs]
                )
                st.download_button("⬇️ Download Question Explorer CSV",
                    qe_df.to_csv(index=False).encode(), f"{slugify(query)}-question-explorer.csv", "text/csv")
                st.markdown("</div>", unsafe_allow_html=True)

        # Keyword Opportunities
        with st.container():
            st.markdown('<div class="v7-card">', unsafe_allow_html=True)
            slabel("Keyword Opportunities")
            kc1, kc2 = st.columns(2)
            with kc1:
                st.markdown("**Autocomplete Suggestions**")
                ac_list = data["related_keywords"]["autocomplete"]
                if ac_list:
                    st.dataframe(pd.DataFrame(ac_list, columns=["Suggestion"]),
                                 use_container_width=True, height=180)
                else:
                    st.caption("No autocomplete data found.")
            with kc2:
                st.markdown("**Related Searches**")
                rs_list = data["related_keywords"]["related_searches"]
                if rs_list:
                    st.dataframe(pd.DataFrame(rs_list, columns=["Query"]),
                                 use_container_width=True, height=180)
                else:
                    st.caption("No related searches found.")
            st.markdown("</div>", unsafe_allow_html=True)

        # Brief download
        with st.container():
            st.markdown('<div class="v7-card">', unsafe_allow_html=True)
            slabel("Download Content Brief")
            brief_md = data.get("markdown_brief", "")
            with st.expander("📄 Preview Brief"):
                st.markdown(brief_md)
            with st.expander("📋 Raw Markdown"):
                st.code(brief_md, language="markdown")
            st.download_button("⬇️ Download Brief (.md)",
                brief_md.encode(), f"{slugify(query)}-brief.md", "text/markdown")
            st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 2 — Topical Authority
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    if not st.session_state.brief_data:
        with st.container():
            st.markdown('<div class="v7-card">', unsafe_allow_html=True)
            st.info("🗺️ Run a SERP analysis in Tab 1 to build your topical authority plan.")
            st.markdown("</div>", unsafe_allow_html=True)
    else:
        ta   = st.session_state.brief_data.get("topical_authority", {})
        q_ta = st.session_state.brief_data.get("query", "")

        # Snapshot metrics
        with st.container():
            st.markdown('<div class="v7-card">', unsafe_allow_html=True)
            _ta_src = ta.get("meta", {}).get("source", "formula")
            _ta_badge = (
                '<span style="background:rgba(59,91,219,.15);color:var(--primary-color,#3b5bdb);border-radius:8px;'
                'padding:2px 9px;font-size:.68rem;font-weight:600;">🤖 Gemini-grounded</span>'
                if _ta_src == "ai" else
                '<span style="background:rgba(148,163,184,.12);border-radius:8px;padding:2px 9px;'
                'font-size:.68rem;opacity:.55;">📐 Formula-based</span>'
            )
            st.markdown(f'<span class="slabel" style="display:inline;">Topical Authority Snapshot</span> {_ta_badge}', unsafe_allow_html=True)
            auth_score   = ta.get("authority_score", 0)
            auth_color   = score_color(auth_score)
            auth_verdict = "Strong" if auth_score >= 70 else "Developing" if auth_score >= 40 else "Thin"
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("Authority Score",    f"{auth_score}/100")
            s2.metric("Topic Coverage",     f"{ta.get('coverage_score', 0)}%")
            s3.metric("Articles Suggested", ta.get("total_articles", 0))
            s4.metric("Est. Total Words",   f"{ta.get('total_words', 0):,}")
            st.markdown(
                f'{sbar(auth_score)}'
                f'<div style="font-size:.8rem;opacity:.55;margin-top:4px;">'
                f'Topical Authority: <strong style="color:{auth_color};">{auth_verdict}</strong></div>',
                unsafe_allow_html=True)
            top_terms = ta.get("top_terms", [])
            if top_terms:
                st.markdown(chips(top_terms[:15], "chip"), unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        # Gap recommendations
        with st.container():
            st.markdown('<div class="v7-card">', unsafe_allow_html=True)
            slabel("Coverage Gap Recommendations")
            for rec in ta.get("gap_recommendations", []):
                rec_color = "#4ade80" if rec.startswith("✅") else "#f59e0b" if rec.startswith("⚠") else "#f87171"
                st.markdown(
                    f'<div style="font-size:.84rem;color:{rec_color};padding:4px 0;'
                    f'border-bottom:1px solid rgba(148,163,184,.08);">{html_lib.escape(rec)}</div>',
                    unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        # Authority Map
        with st.container():
            st.markdown('<div class="v7-card">', unsafe_allow_html=True)
            slabel("Authority Map — Pillar & Clusters")
            pillar = ta.get("pillar", {})
            if pillar:
                st.markdown(
                    f'<div style="background:rgba(59,91,219,.12);border:2px solid rgba(59,91,219,.35);'
                    f'border-radius:14px;padding:16px 20px;margin-bottom:16px;">'
                    f'<div style="font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;'
                    f'color:var(--primary-color,#3b5bdb);margin-bottom:6px;">🏛️ PILLAR PAGE — Publish First</div>'
                    f'<div style="font-size:1rem;font-weight:700;">{html_lib.escape(pillar.get("title",""))}</div>'
                    f'<div style="font-size:.78rem;opacity:.55;margin-top:4px;">'
                    f'{pillar.get("word_count",0):,} words · {html_lib.escape(pillar.get("type",""))}</div>'
                    f'<div style="font-size:.78rem;opacity:.45;margin-top:4px;">'
                    f'{html_lib.escape(pillar.get("description",""))}</div></div>',
                    unsafe_allow_html=True)

            # Cluster cards — support both your authority_map format and subtopic_clusters
            auth_map = ta.get("authority_map") or ta.get("subtopic_clusters", [])
            INTENT_COLORS = {
                "Informational": ("rgba(59,91,219,.15)",  "rgba(59,91,219,.3)"),
                "Commercial":    ("rgba(245,158,11,.12)", "rgba(245,158,11,.3)"),
                "Transactional": ("rgba(16,185,129,.12)", "rgba(16,185,129,.3)"),
                "Navigational":  ("rgba(168,85,247,.12)", "rgba(168,85,247,.3)"),
            }
            cols = st.columns(2)
            for i, item in enumerate(auth_map):
                name   = item.get("name") or item.get("focus", "—")
                focus  = item.get("focus") or item.get("description", "")
                topics = item.get("topics") or item.get("articles", [])
                intent = item.get("intent", "Informational")
                bg, border = INTENT_COLORS.get(intent, ("rgba(148,163,184,.08)", "rgba(148,163,184,.18)"))
                topic_html = "".join(
                    f'<div style="font-size:.76rem;opacity:.6;padding:3px 0;'
                    f'border-bottom:1px solid rgba(148,163,184,.06);">→ {html_lib.escape(str(t)[:70])}</div>'
                    for t in (topics or [])[:5])
                with cols[i % 2]:
                    st.markdown(
                        f'<div style="background:{bg};border:1px solid {border};'
                        f'border-radius:12px;padding:14px 16px;margin-bottom:10px;">'
                        f'<div style="font-size:.7rem;font-weight:700;text-transform:uppercase;'
                        f'letter-spacing:.07em;opacity:.55;margin-bottom:6px;">{html_lib.escape(name)}</div>'
                        f'<div style="font-size:.8rem;opacity:.5;margin-bottom:10px;">{html_lib.escape(str(focus)[:100])}</div>'
                        f'{topic_html}</div>',
                        unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        # Content Plan
        with st.container():
            st.markdown('<div class="v7-card">', unsafe_allow_html=True)
            slabel("Content Plan & Priority Order")
            plan_data = ta.get("content_plan", [])
            if plan_data:
                PRI_COLORS = {"🔴 High": "#fca5a5", "🟡 Medium": "#fcd34d", "🟢 Low": "#6ee7b7"}
                for pri_label in ["🔴 High", "🟡 Medium", "🟢 Low"]:
                    group = [a for a in plan_data if a.get("priority_label") == pri_label]
                    if not group:
                        continue
                    pri_col = PRI_COLORS.get(pri_label, "#94a3b8")
                    st.markdown(
                        f'<div style="font-size:.72rem;font-weight:700;text-transform:uppercase;'
                        f'letter-spacing:.08em;color:{pri_col};margin:14px 0 8px;">'
                        f'{pri_label} Priority — {len(group)} article{"s" if len(group)!=1 else ""}</div>',
                        unsafe_allow_html=True)
                    for a in group:
                        st.markdown(
                            f'<div style="display:flex;align-items:center;gap:12px;padding:10px 14px;'
                            f'background:var(--secondary-background-color);border:1px solid rgba(148,163,184,.1);'
                            f'border-radius:10px;margin-bottom:6px;">'
                            f'<div style="flex:1;min-width:0;">'
                            f'<div style="font-size:.85rem;font-weight:600;">{html_lib.escape(a.get("title",""))}</div>'
                            f'<div style="font-size:.72rem;opacity:.45;margin-top:2px;">'
                            f'{html_lib.escape(a.get("type","Article"))} · {html_lib.escape(a.get("cluster",""))} · CTA: {html_lib.escape(a.get("cta",""))}</div></div>'
                            f'<div style="text-align:right;flex-shrink:0;">'
                            f'<div style="font-size:.85rem;font-weight:700;color:var(--primary-color,#3b5bdb);">{a.get("word_count",0):,}</div>'
                            f'<div style="font-size:.68rem;opacity:.4;">words</div></div></div>',
                            unsafe_allow_html=True)
                plan_df = pd.DataFrame([{
                    "Priority": a.get("priority_label",""),
                    "Title":    a.get("title",""),
                    "Type":     a.get("type",""),
                    "Cluster":  a.get("cluster",""),
                    "Words":    a.get("word_count",0),
                    "CTA":      a.get("cta",""),
                } for a in plan_data])
                with st.expander("📊 View as table"):
                    st.dataframe(plan_df, use_container_width=True, height=300)
                st.download_button("⬇️ Download Content Plan CSV",
                    plan_df.to_csv(index=False).encode(),
                    f"{slugify(q_ta)}-content-plan.csv", "text/csv")
            else:
                st.caption("No content plan available. Run SERP analysis first.")
            st.markdown("</div>", unsafe_allow_html=True)

        # Internal Linking Guide
        with st.container():
            st.markdown('<div class="v7-card">', unsafe_allow_html=True)
            slabel("Internal Linking Guide")
            st.markdown(
                '<div style="font-size:.83rem;opacity:.55;margin-bottom:12px;">'
                'Every supporting article links <em>up</em> to the pillar. '
                'The pillar links <em>down</em> to top spokes. '
                'Same-cluster articles cross-link each other.</div>',
                unsafe_allow_html=True)
            links_data = ta.get("internal_links", [])
            LINK_TYPE_COLORS = {
                "Supporting article → Pillar": "#4ade80",
                "Pillar → Top spoke":          "var(--primary-color,#3b5bdb)",
                "Cross-link":                  "#f59e0b",
            }
            if links_data:
                for link in links_data[:25]:
                    reason  = link.get("reason","")
                    key     = next((k for k in LINK_TYPE_COLORS if k in reason), "Cross-link")
                    t_color = LINK_TYPE_COLORS[key]
                    st.markdown(
                        f'<div style="display:flex;align-items:flex-start;gap:10px;padding:8px 12px;'
                        f'border-bottom:1px solid rgba(148,163,184,.07);">'
                        f'<div style="flex:1;min-width:0;">'
                        f'<span style="font-size:.78rem;font-weight:600;">{html_lib.escape(link.get("from","")[:50])}</span>'
                        f'<span style="font-size:.72rem;opacity:.4;margin:0 6px;">→</span>'
                        f'<span style="font-size:.78rem;color:{t_color};font-weight:600;">{html_lib.escape(link.get("to","")[:50])}</span>'
                        f'<div style="font-size:.68rem;opacity:.4;margin-top:2px;">Anchor: "{html_lib.escape(link.get("anchor","")[:40])}"</div>'
                        f'</div>'
                        f'<div style="font-size:.65rem;color:{t_color};text-align:right;min-width:90px;opacity:.8;">'
                        f'{html_lib.escape(reason.split("(")[0].strip())}</div></div>',
                        unsafe_allow_html=True)
                links_df = pd.DataFrame([{
                    "From": l.get("from",""), "To": l.get("to",""),
                    "Anchor": l.get("anchor",""), "Type": l.get("reason",""),
                } for l in links_data])
                st.download_button("⬇️ Download Internal Link Map CSV",
                    links_df.to_csv(index=False).encode(),
                    f"{slugify(q_ta)}-internal-links.csv", "text/csv")
            else:
                st.caption("No internal link suggestions available.")
            st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 3 — Local Pack
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    # Standalone search
    with st.container():
        st.markdown('<div class="v7-card">', unsafe_allow_html=True)
        slabel("Local Pack Search")
        lc1, lc2 = st.columns([5, 1])
        with lc1:
            local_query = st.text_input(
                "local_kw", label_visibility="collapsed",
                value=st.session_state.local_pack_query,
                placeholder="Enter keyword to analyse the Local Pack — e.g. digital marketing agency delhi",
            )
        with lc2:
            local_btn = st.button("🔍 Search", use_container_width=True, disabled=not st.session_state.api_ok)
        if not st.session_state.api_ok:
            st.info("🔑 Authenticate in the sidebar first.")
        st.markdown("</div>", unsafe_allow_html=True)

    if local_btn and local_query:
        with st.spinner("Fetching Local Pack results…"):
            raw_local = cached_fetch_serp(st.session_state.api_key, local_query, gl, hl, 10)
            st.session_state.local_pack_query = local_query
            if raw_local and raw_local.get("local_results"):
                st.session_state.local_pack_results = (
                    serp_analyzer.extract_local_pack_results(raw_local, top_n=5)
                )
            else:
                st.session_state.local_pack_results = []
                st.info("No Local Pack results found. Try a more location-specific keyword.")

    if st.session_state.local_pack_results:
        with st.container():
            st.markdown('<div class="v7-card">', unsafe_allow_html=True)
            slabel("Top 5 Local Pack Results")
            st.dataframe(pd.DataFrame(st.session_state.local_pack_results),
                         use_container_width=True, height=340)
            st.markdown("</div>", unsafe_allow_html=True)
    elif not local_btn:
        st.info("📍 Enter a keyword above, or run a SERP analysis in Tab 1 — the Local Pack will be auto-detected.")

    # Local pack from SERP analysis
    local_pack = (st.session_state.brief_data or {}).get("local_pack", {})
    if local_pack.get("present"):
        with st.container():
            st.markdown('<div class="v7-card">', unsafe_allow_html=True)
            slabel("Local Pack — Detected in SERP Analysis")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Rating",     local_pack.get("rating") or "—")
            m2.metric("Reviews",    local_pack.get("review_count") or "—")
            m3.metric("Open Now",   local_pack.get("open_now") or "Unknown")
            completeness = sum(bool(local_pack.get(k)) for k in ["website","phone","address","categories"])
            m4.metric("Fields Complete", f"{completeness}/4")
            if local_pack.get("summary"):
                st.markdown(
                    f'<div style="font-size:.85rem;opacity:.65;margin-top:10px;">'
                    f'{html_lib.escape(local_pack["summary"])}</div>',
                    unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        with st.container():
            st.markdown('<div class="v7-card">', unsafe_allow_html=True)
            slabel("Listing Details")
            ld1, ld2, ld3, ld4 = st.columns(4)
            ld1.text_input("Business Name", local_pack.get("name",""),    disabled=True)
            ld2.text_input("Website",       local_pack.get("website",""), disabled=True)
            ld3.text_input("Phone",         local_pack.get("phone",""),   disabled=True)
            ld4.text_input("Address",       local_pack.get("address",""), disabled=True)
            st.markdown("</div>", unsafe_allow_html=True)

        if local_pack.get("categories") or local_pack.get("attributes"):
            with st.container():
                st.markdown('<div class="v7-card">', unsafe_allow_html=True)
                slabel("Categories & Attributes")
                if local_pack.get("categories"):
                    st.markdown(chips(local_pack["categories"], "chip"), unsafe_allow_html=True)
                if local_pack.get("attributes"):
                    st.markdown(chips(local_pack["attributes"], "chip-grey"), unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

        if local_pack.get("top_competitors"):
            with st.container():
                st.markdown('<div class="v7-card">', unsafe_allow_html=True)
                slabel("Top Local Competitors")
                st.dataframe(pd.DataFrame(local_pack["top_competitors"]),
                             use_container_width=True, height=260)
                st.markdown("</div>", unsafe_allow_html=True)

        if local_pack.get("optimization_tips"):
            with st.container():
                st.markdown('<div class="v7-card">', unsafe_allow_html=True)
                slabel("GBP Optimization Suggestions")
                for tip in local_pack["optimization_tips"]:
                    st.markdown(
                        f'<div style="font-size:.85rem;padding:5px 0;'
                        f'border-bottom:1px solid rgba(148,163,184,.08);">• {html_lib.escape(tip)}</div>',
                        unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 4 — Competitor Score
# ══════════════════════════════════════════════════════════════════════════════
with tab4:
    comp_scores = (st.session_state.brief_data or {}).get("competitor_scores", [])
    if not comp_scores:
        with st.container():
            st.markdown('<div class="v7-card">', unsafe_allow_html=True)
            st.info("📊 Run a SERP analysis in Tab 1 first to populate competitor data.")
            st.markdown("</div>", unsafe_allow_html=True)
    else:
        avg_score = round(sum(c["score"]       for c in comp_scores) / len(comp_scores), 1)
        avg_wc    = round(sum(c["word_count"]  for c in comp_scores) / len(comp_scores))
        avg_rd    = round(sum(c["readability"] for c in comp_scores) / len(comp_scores), 1)
        avg_fg    = round(sum(c.get("gunning_fog",0) for c in comp_scores) / len(comp_scores), 1)
        best      = max(comp_scores, key=lambda x: x["score"])

        with st.container():
            st.markdown('<div class="v7-card">', unsafe_allow_html=True)
            slabel("Benchmark Summary")
            bm1,bm2,bm3,bm4,bm5 = st.columns(5)
            bm1.metric("Pages Scored",    len(comp_scores))
            bm2.metric("Avg Score",       f"{avg_score}/100")
            bm3.metric("Avg Word Count",  avg_wc)
            bm4.metric("Avg FK Grade",    avg_rd)
            bm5.metric("Avg Gunning Fog", avg_fg)
            st.markdown(
                f'<div style="margin-top:10px;padding:10px 16px;background:rgba(16,185,129,.1);'
                f'border:1px solid rgba(16,185,129,.25);border-radius:8px;font-size:.82rem;">'
                f'🏆 Strongest: <strong>{html_lib.escape(best["title"][:70])}</strong>'
                f' — Score {best["score"]}/100 · {best["word_count"]:,} words · {best["content_style"]}</div>',
                unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        with st.container():
            st.markdown('<div class="v7-card">', unsafe_allow_html=True)
            slabel("What You Need to Write to Win")
            wn1,wn2,wn3,wn4 = st.columns(4)
            for col, title, val, sub in [
                (wn1,"Target Score",  f"≥ {min(best['score']+10,100)}", f"Best: {best['score']}"),
                (wn2,"Target Words",  f"{best['word_count']+200:,}+",   f"Best: {best['word_count']:,}"),
                (wn3,"Reading Grade", f"≤ {avg_rd}",                    f"Avg: {avg_rd}"),
                (wn4,"Writing Style", best["content_style"],             "Most common in top pages"),
            ]:
                with col:
                    st.markdown(
                        f'<div style="background:rgba(59,91,219,.08);border:1px solid rgba(59,91,219,.2);'
                        f'border-radius:12px;padding:14px;"><div class="slabel">{html_lib.escape(title)}</div>'
                        f'<div style="font-size:1.6rem;font-weight:800;color:var(--primary-color,#3b5bdb);line-height:1.2;">'
                        f'{html_lib.escape(val)}</div>'
                        f'<div style="font-size:.7rem;opacity:.45;margin-top:4px;">{html_lib.escape(sub)}</div></div>',
                        unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        with st.container():
            st.markdown('<div class="v7-card">', unsafe_allow_html=True)
            slabel("Per-Page Breakdown — expand any card to read full content")
            for c in sorted(comp_scores, key=lambda x: x["position"]):
                color   = score_color(c["score"])
                kw_html = "".join(
                    f'<span class="comp-kw">{html_lib.escape(k)}</span>'
                    for k in c.get("top_2grams",[]))
                st.markdown(
                    f'<div class="comp-card"><div class="comp-card-header">'
                    f'<div class="comp-rank">#{c["position"]}</div>'
                    f'<div class="comp-main">'
                    f'<div class="comp-title">{html_lib.escape(c["title"])}</div>'
                    f'<div class="comp-url">{html_lib.escape(c["url"])}</div>'
                    f'<div class="comp-meta-row">'
                    f'<span class="comp-meta-pill highlight">{c["word_count"]:,} words</span>'
                    f'<span class="comp-meta-pill">FK {c["readability"]:.1f}</span>'
                    f'<span class="comp-meta-pill">Fog {c.get("gunning_fog",0):.1f}</span>'
                    f'<span class="comp-meta-pill">Sent {c["avg_sent_len"]} wds</span></div>'
                    f'{sbar(c["score"])}'
                    f'<div class="comp-kw-row">{kw_html}</div></div>'
                    f'<div class="comp-score-col">'
                    f'<div class="comp-score-num" style="color:{color};">{c["score"]}</div>'
                    f'<div style="font-size:.7rem;opacity:.45;">{c["verdict"]}</div>'
                    f'<div class="comp-style-badge">{html_lib.escape(c["content_style"])}</div>'
                    f'</div></div></div>',
                    unsafe_allow_html=True)
                with st.expander(f"📖 Full content — #{c['position']} · {c['title'][:55]}"):
                    acc1, acc2 = st.columns([1,2])
                    with acc1:
                        st.markdown("**Heading Structure**")
                        for h in c.get("h1s",[]):
                            st.markdown(f'<div class="cb-h1">{html_lib.escape(h)}</div>', unsafe_allow_html=True)
                        for h in c.get("h2s",[])[:8]:
                            st.markdown(f'<div class="cb-h2">{html_lib.escape(h)}</div>', unsafe_allow_html=True)
                        for h in c.get("h3s",[])[:6]:
                            st.markdown(f'<div class="cb-h3">{html_lib.escape(h)}</div>', unsafe_allow_html=True)
                        st.markdown("---")
                        st.markdown("**Top Keywords**")
                        st.markdown(chips(c.get("top_1grams",[]), "chip-grey"), unsafe_allow_html=True)
                        st.markdown("**Top Phrases**")
                        st.markdown(chips(c.get("top_2grams",[]), "chip"), unsafe_allow_html=True)
                    with acc2:
                        st.markdown("**Scraped Content**")
                        if c.get("paras"):
                            for p in c["paras"][:12]:
                                st.markdown(f'<div class="cb-p">{html_lib.escape(p)}</div>', unsafe_allow_html=True)
                        elif c.get("full_text"):
                            st.text_area("", c["full_text"][:1500], height=280,
                                         disabled=True, label_visibility="collapsed")
                        else:
                            st.caption("Content not available for this page.")
                        st.markdown("**Readability Feedback**")
                        for s in c.get("suggestions",[]):
                            st.markdown(f'<div style="font-size:.8rem;opacity:.65;margin:3px 0;">{html_lib.escape(s)}</div>', unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        with st.container():
            st.markdown('<div class="v7-card">', unsafe_allow_html=True)
            slabel("Export")
            exp_df = pd.DataFrame([{
                "Position":      c["position"], "Title": c["title"], "URL": c["url"],
                "Score":         c["score"],    "Verdict": c["verdict"],
                "Word Count":    c["word_count"], "FK Grade": c["readability"],
                "Gunning Fog":   c.get("gunning_fog",0), "Avg Sent Len": c["avg_sent_len"],
                "Content Style": c["content_style"],
                "Top Keywords":  ", ".join(c.get("top_2grams",[])),
            } for c in comp_scores])
            st.dataframe(exp_df, use_container_width=True)
            kw_slug = slugify(st.session_state.brief_data.get("query","serp"))
            st.download_button("⬇️ Download CSV",
                exp_df.to_csv(index=False).encode(),
                f"{kw_slug}-competitors.csv", "text/csv")
            st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 5 — Content Grader + Competitor Comparison
# ══════════════════════════════════════════════════════════════════════════════
with tab5:
    _comp_available = bool((st.session_state.brief_data or {}).get("competitor_scores"))

    with st.container():
        st.markdown('<div class="v7-card">', unsafe_allow_html=True)
        slabel("Grade Your Content")
        if _comp_available:
            st.markdown(
                '<div style="font-size:.79rem;color:#10b981;background:rgba(16,185,129,.08);'
                'border:1px solid rgba(16,185,129,.2);border-radius:8px;padding:8px 12px;margin-bottom:12px;">'
                '✓ Competitor data loaded — your content will be benchmarked against live SERP results after grading.</div>',
                unsafe_allow_html=True)
        else:
            st.markdown(
                '<div style="font-size:.79rem;background:var(--secondary-background-color);'
                'border:1px solid rgba(148,163,184,.15);border-radius:8px;padding:8px 12px;margin-bottom:12px;opacity:.7;">'
                '💡 Run a SERP analysis in Tab 1 to unlock the competitor comparison below.</div>',
                unsafe_allow_html=True)
        kw_str      = st.text_input("keywords", label_visibility="collapsed",
                         placeholder="Target keywords (comma-separated) — e.g. shopify development, ecommerce agency delhi")
        content_txt = st.text_area("content", label_visibility="collapsed", height=240,
                         placeholder="Paste your drafted article or page content here (minimum 100 characters)…")
        grade_btn   = st.button("✅ Grade My Content")
        st.markdown("</div>", unsafe_allow_html=True)

    if grade_btn:
        kw_list = [k.strip() for k in kw_str.split(",") if k.strip()]
        gd = content_grader.grade_content(content_txt, kw_list)
        st.session_state.grading_results = gd
        # Auto-run comparison only if competitor data is in session
        if "error" not in gd and _comp_available:
            st.session_state.comparison_result = serp_analyzer.compare_with_competitors(
                gd, st.session_state.brief_data["competitor_scores"]
            )
        else:
            st.session_state.comparison_result = None

    if st.session_state.grading_results:
        gd = st.session_state.grading_results
        if "error" in gd:
            st.error(gd["error"])
        else:
            score = gd["content_score"]

            sc1, sc2 = st.columns([1,2])
            with sc1:
                with st.container():
                    st.markdown('<div class="v7-card">', unsafe_allow_html=True)
                    slabel("Content Score")
                    st.markdown(
                        f'<div style="font-size:4rem;font-weight:800;color:{score_color(score)};line-height:1;">{score}</div>'
                        f'<div style="font-size:.82rem;opacity:.45;margin-top:6px;">out of 100 · {gd["verdict"]}</div>',
                        unsafe_allow_html=True)
                    st.markdown(sbar(score), unsafe_allow_html=True)
                    st.markdown("</div>", unsafe_allow_html=True)
            with sc2:
                with st.container():
                    st.markdown('<div class="v7-card">', unsafe_allow_html=True)
                    slabel("Suggestions")
                    for s in gd["suggestions"]:
                        st.markdown(f'<div style="font-size:.85rem;margin:5px 0;">{html_lib.escape(s)}</div>', unsafe_allow_html=True)
                    st.markdown("</div>", unsafe_allow_html=True)

            with st.container():
                st.markdown('<div class="v7-card">', unsafe_allow_html=True)
                slabel("Readability Metrics")
                mc1,mc2,mc3,mc4 = st.columns(4)
                mc1.metric("FK Grade",     gd["readability_scores"]["flesch_kincaid_grade"])
                mc2.metric("Word Count",   gd["word_count"])
                mc3.metric("Sentences",    gd["sentence_count"])
                mc4.metric("Avg Sent Len", f"{gd['avg_sentence_length']} wds")
                with st.expander("Advanced Readability Scores"):
                    sc_d = gd["readability_scores"]
                    rc1,rc2,rc3,rc4 = st.columns(4)
                    rc1.metric("Gunning Fog",  f"{sc_d.get('gunning_fog',0):.1f}")
                    rc2.metric("SMOG",         f"{sc_d.get('smog_index',0):.1f}")
                    rc3.metric("ARI",          f"{sc_d.get('automated_readability_index',0):.1f}")
                    rc4.metric("Coleman-Liau", f"{sc_d.get('coleman_liau_index',0):.1f}")
                st.markdown("</div>", unsafe_allow_html=True)

            with st.container():
                st.markdown('<div class="v7-card">', unsafe_allow_html=True)
                slabel("Keyword Density & N-Gram Analysis")
                NG_KEYS = ["1-Word","2-Words","3-Words","4-Words","5-Words"]
                ng_tabs = st.tabs(NG_KEYS)
                for i, t in enumerate(ng_tabs):
                    with t:
                        if i == 0:
                            hm_data = []
                            for row in gd["ngrams"]["1-Word"][:15]:
                                parts = row.rsplit("(",1)
                                if len(parts) == 2:
                                    phrase = parts[0].strip()
                                    count  = int(parts[1].rstrip(")"))
                                    hm_data.append({"Keyword":phrase,"Count":count,
                                                    "Density":round(count/max(gd["word_count"],1)*100,2)})
                            if hm_data:
                                max_count = max(h["Count"] for h in hm_data) or 1
                                for row in hm_data:
                                    pct = int(row["Count"]/max_count*100)
                                    bar_col = "#4ade80" if pct>60 else "#f59e0b" if pct>30 else "#f87171"
                                    st.markdown(
                                        f'<div style="display:flex;align-items:center;gap:10px;margin:4px 0;">'
                                        f'<span style="min-width:120px;font-size:.8rem;">{html_lib.escape(row["Keyword"])}</span>'
                                        f'<div style="flex:1;background:rgba(148,163,184,.1);border-radius:5px;height:14px;overflow:hidden;">'
                                        f'<div style="width:{pct}%;background:{bar_col};height:100%;border-radius:5px;"></div></div>'
                                        f'<span style="min-width:55px;font-size:.73rem;opacity:.45;text-align:right;">'
                                        f'{row["Count"]}× ({row["Density"]}%)</span></div>',
                                        unsafe_allow_html=True)
                            else:
                                st.dataframe(pd.DataFrame(gd["ngrams"]["1-Word"], columns=["Phrase (count)"]),
                                             use_container_width=True, height=240)
                        else:
                            st.dataframe(pd.DataFrame(gd["ngrams"][NG_KEYS[i]], columns=["Phrase (count)"]),
                                         use_container_width=True, height=240)
                st.markdown("</div>", unsafe_allow_html=True)

            # ── AI Content Brief (Gemini-powered, grounded in real competitor pages) ──
            with st.container():
                st.markdown('<div class="v7-card">', unsafe_allow_html=True)
                slabel("🤖 AI Content Brief — What to Write Next")
                if not st.session_state.gemini_ok:
                    st.caption("Connect a Gemini API key in the sidebar to unlock a grounded editorial brief here.")
                elif not _comp_available:
                    st.caption("💡 Run a SERP analysis in Tab 1 first — the AI brief is grounded in real competitor pages, not generated from thin air.")
                else:
                    if st.button("Generate AI Content Brief", key="ai_brief_btn"):
                        with st.spinner("Reading competitor pages and drafting your brief…"):
                            bdata = st.session_state.brief_data
                            brief = ai_seo.get_content_brief(
                                query=bdata.get("query", ""),
                                intent=bdata.get("intent", "Informational"),
                                competitor_scores=bdata.get("competitor_scores", []),
                                content_result=bdata,
                                related_kw=bdata.get("related_keywords", {}),
                                api_key=st.session_state.gemini_key,
                            )
                            st.session_state["ai_content_brief"] = brief

                    _brief = st.session_state.get("ai_content_brief")
                    if _brief:
                        if not _brief.get("ok"):
                            st.warning(f"⚠️ Could not generate AI brief ({_brief.get('reason', 'unknown error')}). Try again in a moment.")
                        else:
                            st.markdown(
                                f'<div class="ai-box"><strong>Recommended format:</strong> '
                                f'{html_lib.escape(_brief.get("content_type_recommendation",""))}<br>'
                                f'<strong>Target length:</strong> ~{_brief.get("recommended_word_count",0):,} words</div>',
                                unsafe_allow_html=True)

                            if _brief.get("title_options"):
                                st.markdown("**Title Options**")
                                for t in _brief["title_options"]:
                                    st.markdown(
                                        f'<div style="font-size:.86rem;padding:6px 12px;background:var(--secondary-background-color);'
                                        f'border-radius:8px;margin-bottom:5px;">📝 {html_lib.escape(t)}</div>',
                                        unsafe_allow_html=True)

                            if _brief.get("primary_keyword") or _brief.get("secondary_keywords"):
                                kc1, kc2 = st.columns([1, 2])
                                with kc1:
                                    st.markdown(f"**Primary Keyword**\n\n`{_brief.get('primary_keyword','')}`")
                                with kc2:
                                    st.markdown("**Secondary Keywords**")
                                    st.markdown(chips(_brief.get("secondary_keywords", []), "chip"), unsafe_allow_html=True)

                            bc1, bc2 = st.columns(2)
                            with bc1:
                                st.markdown("**Suggested Outline**")
                                for h in _brief.get("suggested_outline", []):
                                    st.markdown(f"- {html_lib.escape(h)}", unsafe_allow_html=False)
                                st.markdown("**Missing Subtopics (competitor gaps)**")
                                for m in _brief.get("missing_subtopics", []):
                                    st.markdown(f"- {html_lib.escape(m)}", unsafe_allow_html=False)
                            with bc2:
                                st.markdown("**Ways to Differentiate**")
                                for u in _brief.get("unique_angle_ideas", []):
                                    st.markdown(f"- {html_lib.escape(u)}", unsafe_allow_html=False)
                                st.markdown("**FAQs to Answer**")
                                for f in _brief.get("faqs_to_answer", []):
                                    st.markdown(f"- {html_lib.escape(f)}", unsafe_allow_html=False)

                            if _brief.get("tone_formality") or _brief.get("tone_point_of_view") or _brief.get("tone_avoid"):
                                st.markdown("**Tone & Style**")
                                _tone_bits = []
                                if _brief.get("tone_formality"): _tone_bits.append(f"**Formality:** {html_lib.escape(_brief['tone_formality'])}")
                                if _brief.get("tone_point_of_view"): _tone_bits.append(f"**POV:** {html_lib.escape(_brief['tone_point_of_view'])}")
                                st.markdown(" · ".join(_tone_bits), unsafe_allow_html=True)
                                if _brief.get("tone_avoid"):
                                    st.caption("🚫 Avoid: " + ", ".join(_brief["tone_avoid"]))
                st.markdown("</div>", unsafe_allow_html=True)

            # ── Competitor Comparison (auto-rendered when available) ───────────
            cr = st.session_state.get("comparison_result")
            if cr and "error" not in cr:
                st.markdown(
                    '<div style="display:flex;align-items:center;gap:10px;margin:24px 0 16px;">'
                    '<span style="font-size:1rem;">⚔️</span>'
                    '<span style="font-size:1rem;font-weight:700;">Competitor Comparison Report</span>'
                    f'<span style="background:rgba(59,91,219,.15);color:var(--primary-color,#3b5bdb);'
                    f'border:1px solid rgba(59,91,219,.25);border-radius:6px;padding:2px 9px;'
                    f'font-size:.7rem;font-weight:500;">vs Top {len(cr["scorecards"])} Competitors</span></div>',
                    unsafe_allow_html=True)

                # Publish Readiness
                with st.container():
                    st.markdown('<div class="v7-card">', unsafe_allow_html=True)
                    slabel("Publish Readiness Verdict")
                    r_score = cr["readiness"]
                    v_color = cr["verdict_color"]
                    rd1, rd2 = st.columns([1,2])
                    with rd1:
                        st.markdown(
                            f'<div style="text-align:center;padding:20px 10px;">'
                            f'<div style="font-size:3.5rem;font-weight:800;color:{v_color};line-height:1;">{r_score}</div>'
                            f'<div style="font-size:.78rem;opacity:.45;margin:4px 0;">Readiness Score / 100</div>'
                            f'{sbar(r_score)}'
                            f'<div style="font-size:1rem;font-weight:700;color:{v_color};margin-top:8px;">{html_lib.escape(cr["verdict"])}</div>'
                            f'<div style="font-size:.76rem;opacity:.45;margin-top:4px;">{html_lib.escape(cr["verdict_note"])}</div>'
                            f'</div>', unsafe_allow_html=True)
                    with rd2:
                        st.markdown("**Action items before publishing:**")
                        STATUS_A_COLORS = {"✅":"#4ade80","⚠":"#f59e0b","❌":"#f87171"}
                        for action in cr["actions"]:
                            a_color = next((v for k,v in STATUS_A_COLORS.items() if action.startswith(k)), "#94a3b8")
                            st.markdown(
                                f'<div style="font-size:.83rem;color:{a_color};padding:5px 0;'
                                f'border-bottom:1px solid rgba(148,163,184,.08);">{html_lib.escape(action)}</div>',
                                unsafe_allow_html=True)
                    st.markdown("</div>", unsafe_allow_html=True)

                # Metric gap table
                with st.container():
                    st.markdown('<div class="v7-card">', unsafe_allow_html=True)
                    slabel("Metric Gap — You vs Competitor Average vs Best")
                    st.markdown(
                        '<div style="display:grid;grid-template-columns:1.4fr 1fr 1fr 1fr 1fr 1fr;'
                        'gap:8px;padding:6px 12px;font-size:.68rem;font-weight:700;text-transform:uppercase;'
                        'letter-spacing:.07em;opacity:.45;border-bottom:1px solid rgba(148,163,184,.1);">'
                        '<div>Metric</div><div style="text-align:center;">Yours</div>'
                        '<div style="text-align:center;">Avg</div><div style="text-align:center;">Best</div>'
                        '<div style="text-align:center;">Gap to Avg</div><div style="text-align:center;">Status</div>'
                        '</div>', unsafe_allow_html=True)
                    STATUS_COLORS = {"✅ Winning":"#4ade80","⚠️ Close":"#f59e0b","❌ Behind":"#f87171"}
                    for mg in cr["metric_gaps"]:
                        s_color  = STATUS_COLORS.get(mg["status"],"#94a3b8")
                        gap_val  = mg["gap_to_avg"]
                        gap_sign = "+" if gap_val > 0 else ""
                        note     = mg.get("note","")
                        st.markdown(
                            f'<div style="display:grid;grid-template-columns:1.4fr 1fr 1fr 1fr 1fr 1fr;'
                            f'gap:8px;padding:9px 12px;border-bottom:1px solid rgba(148,163,184,.06);align-items:center;">'
                            f'<div><div style="font-size:.83rem;font-weight:600;">{html_lib.escape(mg["metric"])}</div>'
                            + (f'<div style="font-size:.68rem;opacity:.4;">{html_lib.escape(note)}</div>' if note else "")
                            + f'</div>'
                            f'<div style="text-align:center;font-size:.88rem;font-weight:700;color:var(--primary-color,#3b5bdb);">{mg["yours"]}{mg["unit"]}</div>'
                            f'<div style="text-align:center;font-size:.83rem;opacity:.55;">{mg["avg_comp"]}{mg["unit"]}</div>'
                            f'<div style="text-align:center;font-size:.83rem;opacity:.55;">{mg["best_comp"]}{mg["unit"]}</div>'
                            f'<div style="text-align:center;font-size:.83rem;color:{"#4ade80" if gap_val>=0 else "#f87171"};">{gap_sign}{gap_val}{mg["unit"]}</div>'
                            f'<div style="text-align:center;font-size:.78rem;font-weight:600;color:{s_color};">{html_lib.escape(mg["status"])}</div>'
                            f'</div>', unsafe_allow_html=True)
                    st.markdown("</div>", unsafe_allow_html=True)

                # Score comparison bars
                with st.container():
                    st.markdown('<div class="v7-card">', unsafe_allow_html=True)
                    slabel("Your Score vs Each Competitor")
                    u_sc = cr["user_score"]
                    for card in cr["scorecards"]:
                        you_win   = card["you_win"]
                        bar_color = "#4ade80" if you_win else "#f87171"
                        st.markdown(
                            f'<div style="margin-bottom:14px;">'
                            f'<div style="display:flex;justify-content:space-between;font-size:.78rem;opacity:.55;margin-bottom:4px;">'
                            f'<span>#{card["position"]} {html_lib.escape(card["title"][:55])}</span>'
                            f'<span style="color:{"#4ade80" if you_win else "#f87171"};font-weight:600;">{"You win ✓" if you_win else "Behind ✗"}</span></div>'
                            f'<div style="display:flex;gap:6px;align-items:center;">'
                            f'<span style="font-size:.7rem;opacity:.4;min-width:28px;">You</span>'
                            f'<div style="flex:1;background:rgba(148,163,184,.1);border-radius:5px;height:12px;overflow:hidden;">'
                            f'<div style="width:{u_sc}%;background:var(--primary-color,#3b5bdb);height:100%;border-radius:5px;"></div></div>'
                            f'<span style="font-size:.78rem;font-weight:700;color:var(--primary-color,#3b5bdb);min-width:30px;">{u_sc}</span></div>'
                            f'<div style="display:flex;gap:6px;align-items:center;margin-top:3px;">'
                            f'<span style="font-size:.7rem;opacity:.4;min-width:28px;">#{card["position"]}</span>'
                            f'<div style="flex:1;background:rgba(148,163,184,.1);border-radius:5px;height:12px;overflow:hidden;">'
                            f'<div style="width:{card["their_score"]}%;background:{bar_color};height:100%;border-radius:5px;opacity:.7;"></div></div>'
                            f'<span style="font-size:.78rem;font-weight:700;color:{bar_color};min-width:30px;">{card["their_score"]}</span>'
                            f'</div></div>', unsafe_allow_html=True)
                    st.markdown(
                        f'<div style="font-size:.75rem;opacity:.4;padding:6px 0;border-top:1px solid rgba(148,163,184,.08);">'
                        f'Competitor average: <strong>{cr["avg_score"]}/100</strong> · Your score: <strong>{u_sc}/100</strong></div>',
                        unsafe_allow_html=True)
                    st.markdown("</div>", unsafe_allow_html=True)

                # Keyword gap
                with st.container():
                    st.markdown('<div class="v7-card">', unsafe_allow_html=True)
                    slabel("Keyword Gap Analysis")
                    kg1, kg2 = st.columns(2)
                    with kg1:
                        st.markdown(
                            f'<div style="font-size:.78rem;font-weight:600;color:#f87171;margin-bottom:8px;">'
                            f'❌ {len(cr["missing_1grams"])} keywords competitors use — you don\'t</div>',
                            unsafe_allow_html=True)
                        st.markdown(chips(cr["missing_1grams"], "chip-grey"), unsafe_allow_html=True)
                        if cr["missing_2grams"]:
                            st.markdown('<div style="font-size:.75rem;opacity:.4;margin:10px 0 6px;">Missing 2-word phrases:</div>', unsafe_allow_html=True)
                            st.markdown(chips(cr["missing_2grams"], "chip-grey"), unsafe_allow_html=True)
                    with kg2:
                        st.markdown(
                            f'<div style="font-size:.78rem;font-weight:600;color:#10b981;margin-bottom:8px;">'
                            f'✅ {len(cr["unique_1grams"])} keywords you use — competitors don\'t</div>',
                            unsafe_allow_html=True)
                        st.markdown(chips(cr["unique_1grams"], "chip-grn"), unsafe_allow_html=True)
                        if cr["unique_2grams"]:
                            st.markdown('<div style="font-size:.75rem;opacity:.4;margin:10px 0 6px;">Your unique phrases:</div>', unsafe_allow_html=True)
                            st.markdown(chips(cr["unique_2grams"], "chip-grn"), unsafe_allow_html=True)
                    st.markdown("</div>", unsafe_allow_html=True)

                # Style match
                with st.container():
                    st.markdown('<div class="v7-card">', unsafe_allow_html=True)
                    slabel("Writing Style Match")
                    sm1, sm2, sm3 = st.columns(3)
                    with sm1:
                        st.markdown(
                            f'<div style="background:rgba(59,91,219,.1);border:1px solid rgba(59,91,219,.2);'
                            f'border-radius:12px;padding:14px;text-align:center;">'
                            f'<div class="slabel">Your Style</div>'
                            f'<div style="font-size:1.05rem;font-weight:700;color:var(--primary-color,#3b5bdb);">{html_lib.escape(cr["user_style"])}</div></div>',
                            unsafe_allow_html=True)
                    with sm2:
                        st.markdown(
                            f'<div style="background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.2);'
                            f'border-radius:12px;padding:14px;text-align:center;">'
                            f'<div class="slabel">Dominant Competitor Style</div>'
                            f'<div style="font-size:1.05rem;font-weight:700;color:#f59e0b;">{html_lib.escape(cr["dominant_style"])}</div></div>',
                            unsafe_allow_html=True)
                    with sm3:
                        match       = cr["style_match"]
                        match_color = "#4ade80" if match else "#f59e0b"
                        match_label = "✅ Match" if match else "⚠️ Mismatch"
                        match_note  = "Your style aligns with top competitors." if match else "Consider aligning with the dominant competitor style."
                        st.markdown(
                            f'<div style="background:rgba(148,163,184,.06);border:1px solid rgba(148,163,184,.15);'
                            f'border-radius:12px;padding:14px;text-align:center;">'
                            f'<div class="slabel">Style Match</div>'
                            f'<div style="font-size:1.05rem;font-weight:700;color:{match_color};">{match_label}</div>'
                            f'<div style="font-size:.72rem;opacity:.45;margin-top:6px;">{match_note}</div></div>',
                            unsafe_allow_html=True)
                    st.markdown("</div>", unsafe_allow_html=True)

                # Export
                with st.container():
                    st.markdown('<div class="v7-card">', unsafe_allow_html=True)
                    slabel("Export Comparison Report")
                    exp_rows = [{"Metric":mg["metric"],"Yours":f'{mg["yours"]}{mg["unit"]}',
                                 "Avg Competitor":f'{mg["avg_comp"]}{mg["unit"]}',
                                 "Best Competitor":f'{mg["best_comp"]}{mg["unit"]}',
                                 "Gap to Avg":f'{mg["gap_to_avg"]}{mg["unit"]}',
                                 "Status":mg["status"]} for mg in cr["metric_gaps"]]
                    exp_df = pd.DataFrame(exp_rows)
                    st.dataframe(exp_df, use_container_width=True, height=220)
                    kw_slug = slugify((st.session_state.brief_data or {}).get("query","content"))
                    st.download_button("⬇️ Download Comparison CSV",
                        exp_df.to_csv(index=False).encode(),
                        f"{kw_slug}-content-comparison.csv", "text/csv")
                    st.markdown("</div>", unsafe_allow_html=True)

            elif _comp_available and not cr:
                st.info("Grade your content above — comparison will appear automatically.")


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 6 — URL Inspector
# ══════════════════════════════════════════════════════════════════════════════
with tab6:
    with st.container():
        st.markdown('<div class="v7-card">', unsafe_allow_html=True)
        slabel("On-Page SEO Inspector")
        ic1, ic2 = st.columns([5,1])
        with ic1:
            url_input = st.text_input("url", label_visibility="collapsed",
                           placeholder="Enter any URL to inspect — e.g. https://digiasylum.com/seo-services/")
        with ic2:
            inspect_btn = st.button("🔬 Inspect", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    if inspect_btn and url_input:
        with st.spinner(f"Scraping {url_input}…"):
            st.session_state.inspection_data = cached_inspect_url(url_input)

    if st.session_state.inspection_data:
        idata = st.session_state.inspection_data
        if "error" in idata:
            st.error(idata["error"])
        else:
            with st.container():
                st.markdown('<div class="v7-card">', unsafe_allow_html=True)
                slabel("Page Overview")
                m1,m2,m3,m4 = st.columns(4)
                m1.metric("Word Count",   idata["word_count"])
                m2.metric("Title Length", f"{idata['meta_title_len']} chars")
                m3.metric("Desc Length",  f"{idata['meta_description_len']} chars")
                m4.metric("Content Type", idata.get("content_type","—"))
                st.text_input("Meta Title",       idata["meta_title"],      disabled=True)
                st.text_area("Meta Description",  idata["meta_description"], height=60, disabled=True)
                cc1, cc2 = st.columns(2)
                with cc1:
                    if idata.get("canonical"):     st.text_input("Canonical URL",  idata["canonical"],     disabled=True)
                    if idata.get("robots"):        st.text_input("Robots Meta",    idata["robots"],        disabled=True)
                    if idata.get("meta_keywords"): st.text_input("Meta Keywords",  idata["meta_keywords"], disabled=True)
                with cc2:
                    for k, v in idata.get("og",{}).items():
                        st.text_input(f"OG: {k}", v, disabled=True)
                if idata.get("speed_hint"):
                    st.markdown(f'<div style="font-size:.8rem;opacity:.55;margin-top:6px;">{html_lib.escape(idata["speed_hint"])}</div>', unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

            with st.container():
                st.markdown('<div class="v7-card">', unsafe_allow_html=True)
                slabel("Heading Structure")
                hc1,hc2,hc3 = st.columns(3)
                with hc1:
                    st.markdown("**H1**")
                    if idata["h1s"]: st.dataframe(pd.DataFrame(idata["h1s"],columns=["H1"]),use_container_width=True)
                    else: st.caption("No H1 found")
                with hc2:
                    st.markdown("**H2**")
                    if idata["h2s"]: st.dataframe(pd.DataFrame(idata["h2s"],columns=["H2"]),use_container_width=True)
                    else: st.caption("No H2 found")
                with hc3:
                    st.markdown("**H3**")
                    if idata["h3s"]: st.dataframe(pd.DataFrame(idata["h3s"],columns=["H3"]),use_container_width=True)
                    else: st.caption("No H3 found")
                st.markdown("</div>", unsafe_allow_html=True)

            with st.container():
                st.markdown('<div class="v7-card">', unsafe_allow_html=True)
                slabel("Full Content Scraper")
                st.markdown('<div style="font-size:.78rem;opacity:.45;margin-bottom:12px;">Structured heading tree, paragraphs and lists extracted from the page.</div>', unsafe_allow_html=True)
                blocks = idata.get("content_blocks",[])
                if blocks: render_content_blocks(blocks)
                else: st.caption("No structured content blocks extracted.")
                with st.expander("📄 Raw Full Text"):
                    st.text_area("raw", idata.get("full_text",""), height=260,
                                 disabled=True, label_visibility="collapsed")
                st.markdown("</div>", unsafe_allow_html=True)

            with st.container():
                st.markdown('<div class="v7-card">', unsafe_allow_html=True)
                slabel("Link Analysis")
                lt1, lt2 = st.tabs([
                    f"Internal ({len(idata['internal_links'])})",
                    f"External ({len(idata['external_links'])})",
                ])
                with lt1:
                    if idata["internal_links"]: st.dataframe(pd.DataFrame(idata["internal_links"]),use_container_width=True,height=240)
                    else: st.caption("No internal links found.")
                with lt2:
                    if idata["external_links"]: st.dataframe(pd.DataFrame(idata["external_links"]),use_container_width=True,height=240)
                    else: st.caption("No external links found.")
                st.markdown("</div>", unsafe_allow_html=True)

            if idata.get("images"):
                with st.container():
                    st.markdown('<div class="v7-card">', unsafe_allow_html=True)
                    slabel(f"Images ({len(idata['images'])} found)")
                    img_html = "<div style='display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:10px;'>"
                    for img in idata["images"]:
                        alt = html_lib.escape(img["alt"] or "No ALT text")
                        img_html += (
                            f"<div style='background:var(--secondary-background-color);border:1px solid rgba(148,163,184,.12);border-radius:10px;overflow:hidden;'>"
                            f"<img src='{img['src']}' style='width:100%;height:96px;object-fit:cover;'>"
                            f"<div style='padding:5px 8px;font-size:.68rem;opacity:.45;'>{alt}</div></div>")
                    st.markdown(img_html+"</div>", unsafe_allow_html=True)
                    st.markdown("</div>", unsafe_allow_html=True)

            if idata.get("schemas"):
                with st.container():
                    st.markdown('<div class="v7-card">', unsafe_allow_html=True)
                    slabel("JSON-LD Structured Data")
                    for i, sch in enumerate(idata["schemas"]):
                        with st.expander(f"Schema #{i+1} — {sch.get('@type','Unknown')}"):
                            st.markdown(generate_schema_table(sch), unsafe_allow_html=True)
                    st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 7 — Position Tracking + Citation Gap Scout
# ══════════════════════════════════════════════════════════════════════════════#  TAB 7 — Position Tracking + Citation Gap Scout
#  FIXED: Multi-keyword batch tracking, depth slider, result num fix
# ══════════════════════════════════════════════════════════════════════════════
with tab7:

    # ── Standalone LLM Citation Check — works with ONLY a Gemini key, no SerpAPI ──
    # Everything else in this tab needs a real ranked SERP (SerpAPI), which Gemini's
    # grounding tool can't provide. This one check genuinely doesn't need SerpAPI at
    # all, so it's pulled out here as its own entry point rather than gated behind a
    # SerpAPI-based tracking run.
    with st.expander("🔮 Quick LLM Citation Check — works with just a Gemini key, no SerpAPI needed", expanded=not st.session_state.api_ok):
        st.markdown(
            '<div style="font-size:.78rem;opacity:.5;margin-bottom:10px;">'
            'Asks Gemini your query directly with live Google Search grounding on, and checks whether '
            'your domain shows up in what it actually cites. This is independent of SerpAPI — useful if '
            'you haven\'t connected a SerpAPI key yet, or just want a fast standalone check.</div>',
            unsafe_allow_html=True,
        )
        if not st.session_state.gemini_ok:
            st.caption("Connect a Gemini API key in the sidebar to use this.")
        else:
            qc1, qc2 = st.columns(2)
            with qc1:
                quick_query = st.text_input("Query", key="quick_llm_query", placeholder="e.g. best shopify agency delhi ncr")
            with qc2:
                quick_url = st.text_input("Your URL or domain", key="quick_llm_url", placeholder="e.g. https://digiasylum.com")
            if st.button("Check Gemini Citation", key="standalone_llm_citation_btn", disabled=not (quick_query and quick_url)):
                with st.spinner("Asking Gemini directly, with search grounding on…"):
                    st.session_state["standalone_llm_citation"] = ai_seo.get_llm_citation_check(
                        quick_query, quick_url, st.session_state.gemini_key
                    )
            _slc = st.session_state.get("standalone_llm_citation")
            if _slc:
                if not _slc.get("ok"):
                    st.warning(f"⚠️ Could not complete the check ({_slc.get('error', 'unknown error')}).")
                else:
                    if _slc["cited"]:
                        st.success(f"✅ Gemini cites your domain as source #{_slc['position']} of {_slc['total_citations']} in its grounded answer.")
                    elif _slc["total_citations"]:
                        st.warning(f"⚠️ Gemini answered using {_slc['total_citations']} source(s), but your domain wasn't one of them.")
                    else:
                        st.info("ℹ️ Gemini answered without citing any external sources for this query.")
                    if _slc.get("all_citations"):
                        for i, c in enumerate(_slc["all_citations"], start=1):
                            _is_you = any(m["url"] == c["url"] for m in _slc.get("matches", []))
                            st.markdown(
                                f'<div style="font-size:.82rem;padding:4px 0;'
                                f'{"font-weight:700;color:#4ade80;" if _is_you else "opacity:.7;"}">'
                                f'{i}. {"✓ " if _is_you else ""}{html_lib.escape(c.get("title","") or c.get("url",""))}</div>',
                                unsafe_allow_html=True,
                            )
                    if _slc.get("answer_excerpt"):
                        with st.expander("View Gemini's grounded answer"):
                            st.markdown(html_lib.escape(_slc["answer_excerpt"]))

    if not st.session_state.api_ok:
        st.info("ℹ️ Everything below this point needs a SerpAPI key — it reads real Google ranking data that Gemini's grounding tool can't provide. Connect one in the sidebar to unlock Position Tracking and Citation Gap Scout.")

    # ── Mode selector ─────────────────────────────────────────────────────────
    mode_col1, mode_col2 = st.columns(2)
    with mode_col1:
        track_mode = st.radio(
            "Tracking mode",
            ["Single Keyword", "Batch (Multiple Keywords)"],
            horizontal=True, label_visibility="collapsed",
        )
    with mode_col2:
        track_depth = st.select_slider(
            "Scan depth (results)",
            options=[10, 20, 30, 50, 100], value=50,
            help="How many SERP results to scan per keyword. Higher = more credits used.",
        )

    # ── Shared: Target URL ────────────────────────────────────────────────────
    with st.container():
        st.markdown('<div class="v7-card">', unsafe_allow_html=True)
        slabel("Position Tracker")
        st.markdown(
            '<div style="font-size:.82rem;opacity:.55;margin-bottom:14px;">'
            'Enter your target URL/domain and one or more keywords. '
            'Batch mode fires all keywords concurrently in background threads — '
            'no waiting for each one to finish before the next starts.</div>',
            unsafe_allow_html=True)

        tracking_url = st.text_input(
            "track_url", label_visibility="collapsed",
            placeholder="Your website URL or domain — e.g. https://digiasylum.com",
            key="pt_url",
        )

        if track_mode == "Single Keyword":
            tracking_query = st.text_input(
                "track_kw", label_visibility="collapsed",
                placeholder="Target keyword — e.g. shopify development company delhi",
                key="pt_kw",
            )
            batch_keywords = [tracking_query] if tracking_query else []
        else:
            kw_textarea = st.text_area(
                "batch_kw", label_visibility="collapsed",
                placeholder=(
                    "Enter one keyword per line:\n"
                    "shopify development company delhi\n"
                    "ecommerce agency india\n"
                    "shopify seo services\n"
                    "best shopify developer delhi"
                ),
                height=140, key="pt_kw_batch",
            )
            batch_keywords = [k.strip() for k in kw_textarea.splitlines() if k.strip()]
            if batch_keywords:
                st.markdown(
                    f'<div style="font-size:.78rem;color:#10b981;margin-top:4px;">'
                    f'✓ {len(batch_keywords)} keyword{"s" if len(batch_keywords)!=1 else ""} ready to track</div>',
                    unsafe_allow_html=True)

        tc1, tc2, tc3 = st.columns(3)
        with tc1: track_signals = st.checkbox("Capture SERP signals & AI Overview", value=True)
        with tc2: track_links   = st.checkbox("Inspect target page links",          value=False)
        with tc3: run_bl        = st.checkbox("Run Citation Gap Scout",                 value=False)

        if run_bl and len(batch_keywords) > 1:
            st.warning("⚠️ Citation Gap Scout scans competitor pages — enabling it for batch tracking will use significant quota. Recommended only for single keyword mode.")

        track_btn = st.button(
            f"📍 Track {'All' if len(batch_keywords) > 1 else ''} {len(batch_keywords)} Keyword{'s' if len(batch_keywords)!=1 else ''}",
            disabled=not st.session_state.api_ok or not batch_keywords or not tracking_url,
            key="track_btn",
        )
        with st.expander("ℹ️ How this works"):
            st.markdown(
                "**Single keyword:** Full analysis — AI Overview, SERP features, top-10 view, interlinking signals, optional Citation Gap Scout (competitor citation analysis, not a verified backlink index).  \n"
                "**Batch mode:** Fires all keywords concurrently (up to 5 at once). "
                "Returns a ranked summary table — position, AI Overview presence, match type — for each keyword. "
                "Each keyword costs 1 SerpAPI credit per 10 results scanned.  \n\n"
                f"With depth={track_depth} and {max(len(batch_keywords),1)} keyword(s): "
                f"~{max(len(batch_keywords),1) * (track_depth//10)} SerpAPI credit(s)."
            )
        if not st.session_state.api_ok:
            st.info("🔑 Authenticate in the sidebar to use Position Tracking.")
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Execute tracking ──────────────────────────────────────────────────────
    if track_btn and batch_keywords and tracking_url:

        if len(batch_keywords) == 1:
            # ── Single keyword — full analysis ────────────────────────────────
            kw = batch_keywords[0]
            with st.spinner(f"Fetching SERP for '{kw}' (scanning top {track_depth} results)…"):
                serp_resp = serp_analyzer.fetch_serp(
                    st.session_state.api_key, kw, gl, hl, track_depth
                )
                if not serp_resp or "organic_results" not in serp_resp:
                    st.error("❌ Could not fetch SERP. Check your API key and quota.")
                else:
                    st.session_state["_last_tracker_serp"] = serp_resp
                    st.session_state["recovery_plan"]    = None  # reset stale plan from a prior keyword
                    st.session_state["improvement_plan"] = None
                    st.session_state["llm_citation"]     = None
                    organic    = serp_resp.get("organic_results", [])
                    tracker    = serp_analyzer.query_position_tracker(tracking_url, organic)
                    features   = serp_analyzer.extract_serp_features(serp_resp)               if track_signals else None
                    ai_ov      = serp_analyzer.build_ai_overview(serp_resp, st.session_state.api_key) if track_signals else None
                    ai_check   = serp_analyzer.check_ai_overview_presence(tracking_url, serp_resp)    if track_signals else None
                    paa_check  = serp_analyzer.check_paa_presence(tracking_url, serp_resp)            if track_signals else None
                    interlinks = serp_analyzer.get_interlinking_signals(tracking_url, organic)
                    target_pg  = cached_inspect_url(tracking_url) if track_links else None
                    bl_data    = serp_analyzer.fetch_backlink_signals(organic, tracking_url)   if run_bl else None
                    raw_top10  = [
                        {"pos": r.get("position"),
                         "title": serp_analyzer._clean(r.get("title", "")),
                         "url": r.get("link", "")}
                        for r in organic[:10]
                    ]
                    st.session_state.position_tracker = {
                        "query": kw, "target_url": tracking_url,
                        "tracker": tracker, "features": features,
                        "ai_overview": ai_ov, "ai_check": ai_check, "paa_check": paa_check,
                        "interlinking": interlinks, "target_page_data": target_pg,
                        "raw_top10": raw_top10, "bl_data": bl_data,
                        "depth": track_depth,
                    }
                    # Add to history
                    st.session_state.position_tracker_history = [
                        {
                            "timestamp":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "query":         kw,
                            "target_url":    tracking_url,
                            "position":      tracker["position"],
                            "found":         tracker["found"],
                            "depth":         track_depth,
                            "serp_signals":  track_signals,
                            "link_audit":    track_links,
                            "backlink_scout":run_bl,
                        },
                        *st.session_state.position_tracker_history,
                    ]

        else:
            # ── Batch mode — concurrent multi-keyword tracking ────────────────
            with st.spinner(
                f"Tracking {len(batch_keywords)} keywords concurrently "
                f"(scanning top {track_depth} results each)…"
            ):
                batch_results = serp_analyzer.batch_position_tracker(
                    st.session_state.api_key,
                    batch_keywords,
                    tracking_url,
                    gl=gl, hl=hl, num=track_depth,
                )
                st.session_state.batch_tracking_results = batch_results
                # Also push to history log
                new_entries = [
                    {
                        "timestamp":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "query":         r["keyword"],
                        "target_url":    tracking_url,
                        "position":      r.get("position"),
                        "found":         r.get("found", False),
                        "depth":         track_depth,
                        "serp_signals":  track_signals,
                        "link_audit":    False,
                        "backlink_scout":False,
                    }
                    for r in batch_results
                ]
                st.session_state.position_tracker_history = (
                    new_entries + st.session_state.position_tracker_history
                )
                st.success(
                    f"✅ Batch complete — {len(batch_results)} keywords tracked across top {track_depth} results."
                )

    # ── Batch results view ────────────────────────────────────────────────────
    batch_results = st.session_state.get("batch_tracking_results", [])
    if batch_results and len(batch_keywords) != 1:
        with st.container():
            st.markdown('<div class="v7-card">', unsafe_allow_html=True)
            slabel(f"Batch Results — {len(batch_results)} Keywords · {tracking_url}")

            # Summary metrics
            found_count  = sum(1 for r in batch_results if r.get("found"))
            in_ai_count  = sum(1 for r in batch_results if r.get("in_ai_overview"))
            in_paa_count = sum(1 for r in batch_results if r.get("in_paa"))
            avg_pos      = round(
                sum(r["position"] for r in batch_results if r.get("position")) /
                max(sum(1 for r in batch_results if r.get("position")), 1), 1
            )
            bm1, bm2, bm3, bm4, bm5 = st.columns(5)
            bm1.metric("Keywords Tracked",  len(batch_results))
            bm2.metric("Found in SERP",     f"{found_count}/{len(batch_results)}")
            bm3.metric("In AI Overview",    in_ai_count)
            bm4.metric("In PAA",            in_paa_count)
            bm5.metric("Avg Position",      avg_pos if found_count else "—")

            st.markdown("<div style='margin-top:14px;'></div>", unsafe_allow_html=True)

            # Per-keyword result rows
            for r in batch_results:
                pos       = r.get("position")
                found     = r.get("found", False)
                in_ai     = r.get("in_ai_overview", False)
                in_paa    = r.get("in_paa", False)
                has_error = bool(r.get("error"))

                if has_error:
                    row_bg, row_border = "rgba(239,68,68,.08)", "rgba(239,68,68,.2)"
                    pos_label, pos_color = "Error", "#f87171"
                elif found and pos and pos <= 3:
                    row_bg, row_border = "rgba(16,185,129,.08)", "rgba(16,185,129,.25)"
                    pos_label, pos_color = f"#{pos}", "#4ade80"
                elif found and pos and pos <= 10:
                    row_bg, row_border = "rgba(59,91,219,.08)", "rgba(59,91,219,.25)"
                    pos_label, pos_color = f"#{pos}", "var(--primary-color,#3b5bdb)"
                elif found:
                    row_bg, row_border = "rgba(245,158,11,.07)", "rgba(245,158,11,.2)"
                    pos_label, pos_color = f"#{pos}", "#f59e0b"
                else:
                    row_bg, row_border = "var(--secondary-background-color)", "rgba(148,163,184,.15)"
                    pos_label, pos_color = "Not found", "#f87171"

                ai_badge = (
                    f'<span style="background:rgba(16,185,129,.15);color:#4ade80;'
                    f'border-radius:5px;padding:2px 7px;font-size:.68rem;font-weight:600;margin-left:6px;">'
                    f'AI #{r.get("ai_position")} of {r.get("ai_total_sources")}</span>'
                    if in_ai else ""
                )
                paa_badge = (
                    f'<span style="background:rgba(59,91,219,.15);color:var(--primary-color,#3b5bdb);'
                    f'border-radius:5px;padding:2px 7px;font-size:.68rem;font-weight:600;margin-left:6px;">'
                    f'PAA #{r.get("paa_position")}</span>'
                    if in_paa else ""
                )
                snippet_html = (
                    f'<div style="font-size:.72rem;opacity:.45;margin-top:3px;'
                    f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'
                    f'{html_lib.escape(r.get("snippet","")[:100])}</div>'
                    if r.get("snippet") else ""
                )

                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:14px;padding:10px 14px;'
                    f'background:{row_bg};border:1px solid {row_border};'
                    f'border-radius:10px;margin-bottom:7px;">'
                    f'<div style="min-width:60px;text-align:center;flex-shrink:0;">'
                    f'<div style="font-size:1.2rem;font-weight:800;color:{pos_color};">{pos_label}</div>'
                    f'</div>'
                    f'<div style="flex:1;min-width:0;">'
                    f'<div style="font-size:.86rem;font-weight:600;">'
                    f'{html_lib.escape(r["keyword"])}{ai_badge}{paa_badge}</div>'
                    f'{snippet_html}'
                    f'<div style="font-size:.7rem;opacity:.4;font-family:monospace;margin-top:2px;'
                    f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'
                    f'{html_lib.escape(r.get("matched_url","")[:80])}</div>'
                    f'</div>'
                    f'<div style="font-size:.68rem;opacity:.45;flex-shrink:0;text-align:right;">'
                    f'{html_lib.escape(r.get("match_type",""))}<br>'
                    f'top {r.get("total_scanned",0)} scanned</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            # Export batch results
            batch_df = pd.DataFrame([{
                "Keyword":       r["keyword"],
                "Position":      r.get("position") or "Not found",
                "Found":         "Yes" if r.get("found") else "No",
                "In AI Overview":"Yes" if r.get("in_ai_overview") else "No",
                "AI Position":   r.get("ai_position") or "",
                "AI Total Sources": r.get("ai_total_sources") or "",
                "In PAA":        "Yes" if r.get("in_paa") else "No",
                "PAA Position":  r.get("paa_position") or "",
                "PAA Question":  r.get("paa_question",""),
                "Match Type":    r.get("match_type",""),
                "Matched URL":   r.get("matched_url",""),
                "Scanned":       r.get("total_scanned",0),
                "Checked At":    r.get("checked_at",""),
            } for r in batch_results])
            st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
            st.download_button(
                "⬇️ Download Batch Results CSV",
                batch_df.to_csv(index=False).encode(),
                f"batch-position-tracking-{datetime.now().strftime('%Y%m%d-%H%M')}.csv",
                "text/csv",
            )
            st.markdown("</div>", unsafe_allow_html=True)

    # ── Single keyword detailed result ────────────────────────────────────────
    td = st.session_state.get("position_tracker")
    if td and (len(batch_keywords) == 1 or not batch_results):
        track    = td["tracker"]
        depth_used = td.get("depth", track_depth)
        pos_label = f"#{track['position']}" if track["found"] else f"Not in top {depth_used}"

        with st.container():
            st.markdown('<div class="v7-card">', unsafe_allow_html=True)
            slabel("Single Keyword Result")
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("Current Position", pos_label)
            s2.metric("Matches Found",    len(track["matches"]))
            s3.metric("Results Scanned",  depth_used)
            s4.metric("Link Audit",       "✓ Captured" if td.get("target_page_data") else "Skipped")

            if track["found"]:
                st.success(
                    f'✅ **{html_lib.escape(td["target_url"])}** '
                    f'ranks at **{pos_label}** for '
                    f'"{html_lib.escape(td["query"])}"'
                )
            elif track["matches"]:
                st.warning("⚠️ Domain found but no exact URL match. See match table below.")
            else:
                st.info(f'ℹ️ Not found in the top {depth_used} results for this keyword.')
            st.markdown("</div>", unsafe_allow_html=True)

        # ── LLM Citation Check — does Gemini itself cite you when grounded-answering? ──
        # Distinct from AI Overview/PAA above: those read Google's own SERP data via
        # SerpAPI. This asks Gemini the query directly with Google Search grounding on,
        # and checks whether the target domain shows up in what Gemini actually cited.
        if st.session_state.gemini_ok:
            with st.container():
                st.markdown('<div class="v7-card">', unsafe_allow_html=True)
                slabel("🔮 LLM Citation Check (Gemini, grounded)")
                st.markdown(
                    '<div style="font-size:.78rem;opacity:.5;margin-bottom:10px;">'
                    'A separate signal from AI Overview/PAA above — this asks Gemini the query directly '
                    '(with live Google Search grounding on) and checks whether your domain shows up in what '
                    'it actually cites. Reflects visibility in Gemini\'s own answers, not Google\'s SERP.</div>',
                    unsafe_allow_html=True,
                )
                if st.button("Check Gemini Citation", key="llm_citation_btn"):
                    with st.spinner("Asking Gemini directly, with search grounding on…"):
                        lc = ai_seo.get_llm_citation_check(td["query"], td["target_url"], st.session_state.gemini_key)
                        st.session_state["llm_citation"] = lc

                _lc = st.session_state.get("llm_citation")
                if _lc:
                    if not _lc.get("ok"):
                        st.warning(f"⚠️ Could not complete the check ({_lc.get('error', 'unknown error')}). Try again in a moment.")
                    else:
                        if _lc["cited"]:
                            st.success(f"✅ Gemini cites your domain as source #{_lc['position']} of {_lc['total_citations']} in its grounded answer.")
                        elif _lc["total_citations"]:
                            st.warning(f"⚠️ Gemini answered this using {_lc['total_citations']} source(s), but your domain wasn't one of them.")
                        else:
                            st.info("ℹ️ Gemini answered without citing any external sources for this query.")
                        if _lc.get("all_citations"):
                            st.markdown("**Sources Gemini cited:**")
                            for i, c in enumerate(_lc["all_citations"], start=1):
                                _is_you = any(m["url"] == c["url"] for m in _lc.get("matches", []))
                                st.markdown(
                                    f'<div style="font-size:.82rem;padding:4px 0;'
                                    f'{"font-weight:700;color:#4ade80;" if _is_you else "opacity:.7;"}">'
                                    f'{i}. {"✓ " if _is_you else ""}{html_lib.escape(c.get("title","") or c.get("url",""))}</div>',
                                    unsafe_allow_html=True,
                                )
                        if _lc.get("answer_excerpt"):
                            with st.expander("View Gemini's grounded answer"):
                                st.markdown(html_lib.escape(_lc["answer_excerpt"]))
                st.markdown("</div>", unsafe_allow_html=True)

        # ── Improvement Plan — only surfaces when found, but not already #1 ────
        if track["found"] and track.get("position") and track["position"] > 1:
            with st.container():
                st.markdown('<div class="v7-card">', unsafe_allow_html=True)
                slabel("📈 How do we move up?")
                st.markdown(
                    f'<div style="font-size:.78rem;opacity:.5;margin-bottom:10px;">'
                    f'Scrapes the real content, headings, and style of the {min(track["position"]-1, 5)} '
                    f'page(s) ranking above you at #{track["position"]}, and builds a specific gap-closing plan '
                    f'— not generic advice.</div>',
                    unsafe_allow_html=True,
                )
                if st.button("Generate Improvement Plan", key="improvement_plan_btn"):
                    _serp_for_plan = st.session_state.get("_last_tracker_serp", {})
                    _organic = _serp_for_plan.get("organic_results", [])
                    _pages_above = [r for r in _organic if r.get("position") and r["position"] < track["position"]][:5]
                    if not _pages_above:
                        st.warning("Couldn't find the pages ranking above you in this session — re-run tracking and try again.")
                    else:
                        with st.spinner(f"Scraping {len(_pages_above)} page(s) currently outranking you…"):
                            pages_above_content = serp_analyzer.analyze_serp_content(_pages_above)
                        with st.spinner("Building your gap-closing plan…"):
                            plan = ai_seo.get_improvement_plan(
                                query=td["query"], target_url=td["target_url"], target_position=track["position"],
                                pages_above_content=pages_above_content,
                                target_page_data=td.get("target_page_data"),
                                bl_data=td.get("bl_data"),
                                api_key=st.session_state.gemini_key if st.session_state.gemini_ok else "",
                            )
                            st.session_state["improvement_plan"] = plan

                _ip = st.session_state.get("improvement_plan")
                if _ip:
                    _ip_badge = (
                        '<span style="background:rgba(59,91,219,.15);color:var(--primary-color,#3b5bdb);border-radius:8px;'
                        'padding:2px 9px;font-size:.68rem;font-weight:600;">🤖 AI-grounded</span>'
                        if _ip.get("source") == "ai" else
                        '<span style="background:rgba(148,163,184,.12);border-radius:8px;padding:2px 9px;'
                        'font-size:.68rem;opacity:.55;">📐 Quick diagnostic</span>'
                    )
                    _effort_colors = {"Quick edit (hours)": "#4ade80", "Moderate rewrite (days)": "#f59e0b", "Major overhaul (weeks)": "#f87171"}
                    _effort = _ip.get("estimated_effort", "")
                    _effort_html = (
                        f'<span style="background:rgba(148,163,184,.12);border-radius:8px;padding:2px 9px;'
                        f'font-size:.68rem;color:{_effort_colors.get(_effort,"inherit")};margin-left:6px;">⏱ {html_lib.escape(_effort)}</span>'
                        if _effort else ""
                    )
                    st.markdown(_ip_badge + _effort_html, unsafe_allow_html=True)
                    st.markdown(f"**Gap Summary:** {html_lib.escape(_ip.get('position_gap_summary',''))}")

                    ip1, ip2 = st.columns(2)
                    with ip1:
                        st.markdown("**Structural Gaps (headings you're missing)**")
                        for g in _ip.get("structural_gaps", []):
                            st.markdown(f"- {html_lib.escape(g)}", unsafe_allow_html=False)
                        st.markdown(f"**Content Depth:** {html_lib.escape(_ip.get('content_depth_comparison',''))}")
                    with ip2:
                        st.markdown(f"**Style & Readability:** {html_lib.escape(_ip.get('style_readability_notes',''))}")
                        st.markdown("**Citation Leads**")
                        for c in _ip.get("citation_gap_recommendations", []):
                            st.markdown(f"- {html_lib.escape(c)}", unsafe_allow_html=False)

                    if _ip.get("priority_actions"):
                        st.markdown(
                            '<div class="ai-box" style="margin-top:10px;"><strong>🎯 Priority Actions:</strong><br>'
                            + "<br>".join(f"{i+1}. {html_lib.escape(a)}" for i, a in enumerate(_ip["priority_actions"]))
                            + '</div>', unsafe_allow_html=True,
                        )
                st.markdown("</div>", unsafe_allow_html=True)

        # ── Recovery Plan — only surfaces when the target wasn't found ─────────
        if not track["found"]:
            with st.container():
                st.markdown('<div class="v7-card">', unsafe_allow_html=True)
                slabel("🩺 Why aren't we ranking?")
                st.markdown(
                    '<div style="font-size:.78rem;opacity:.5;margin-bottom:10px;">'
                    'Diagnoses the gap between what\'s actually ranking and your page, '
                    'and gives specific content + citation next steps.</div>',
                    unsafe_allow_html=True,
                )
                if st.button("Generate Recovery Plan", key="recovery_plan_btn"):
                    with st.spinner("Comparing your page against what's actually ranking…"):
                        _serp_for_recovery = st.session_state.get("_last_tracker_serp", {})
                        plan = ai_seo.get_recovery_plan(
                            query=td["query"], target_url=td["target_url"],
                            serp_json=_serp_for_recovery,
                            target_page_data=td.get("target_page_data"),
                            bl_data=td.get("bl_data"),
                            api_key=st.session_state.gemini_key if st.session_state.gemini_ok else "",
                        )
                        st.session_state["recovery_plan"] = plan

                _rp = st.session_state.get("recovery_plan")
                if _rp:
                    _rp_badge = (
                        '<span style="background:rgba(59,91,219,.15);color:var(--primary-color,#3b5bdb);border-radius:8px;'
                        'padding:2px 9px;font-size:.68rem;font-weight:600;">🤖 AI-grounded</span>'
                        if _rp.get("source") == "ai" else
                        '<span style="background:rgba(148,163,184,.12);border-radius:8px;padding:2px 9px;'
                        'font-size:.68rem;opacity:.55;">📐 Quick diagnostic</span>'
                    )
                    st.markdown(_rp_badge, unsafe_allow_html=True)
                    st.markdown(f"**Pattern:** {html_lib.escape(_rp.get('competitor_pattern_summary',''))}")
                    rp1, rp2 = st.columns(2)
                    with rp1:
                        st.markdown("**Likely Reasons**")
                        for reason in _rp.get("likely_reasons", []):
                            st.markdown(f"- {html_lib.escape(reason)}", unsafe_allow_html=False)
                        st.markdown("**Content Recommendations**")
                        for c in _rp.get("content_recommendations", []):
                            st.markdown(f"- {html_lib.escape(c)}", unsafe_allow_html=False)
                    with rp2:
                        st.markdown(f"**Page Strategy:** {html_lib.escape(_rp.get('target_page_recommendation',''))}")
                        st.markdown("**Citation Leads**")
                        for c in _rp.get("citation_recommendations", []):
                            st.markdown(f"- {html_lib.escape(c)}", unsafe_allow_html=False)
                    if _rp.get("quick_wins"):
                        st.markdown(
                            '<div class="ai-box" style="margin-top:10px;"><strong>⚡ Quick Wins:</strong><br>'
                            + "<br>".join(f"• {html_lib.escape(q)}" for q in _rp["quick_wins"])
                            + '</div>', unsafe_allow_html=True,
                        )
                st.markdown("</div>", unsafe_allow_html=True)

        if track["matches"]:
            with st.container():
                st.markdown('<div class="v7-card">', unsafe_allow_html=True)
                slabel("Matching Results")
                st.dataframe(
                    pd.DataFrame([
                        {"Position": pos, "URL": url, "Match Type": mt}
                        for pos, url, mt in track["matches"]
                    ]),
                    use_container_width=True, height=180,
                )
                st.markdown("</div>", unsafe_allow_html=True)

        if td.get("raw_top10"):
            with st.container():
                st.markdown('<div class="v7-card">', unsafe_allow_html=True)
                slabel(f"Top 10 of {depth_used} Scanned")
                your_dom = domain_of(td["target_url"])
                for r in td["raw_top10"]:
                    is_you  = bool(your_dom and your_dom in domain_of(r["url"]))
                    bg      = "rgba(16,185,129,.1)"  if is_you else "var(--secondary-background-color)"
                    border  = "rgba(16,185,129,.3)"  if is_you else "rgba(148,163,184,.12)"
                    you_tag = ' ← <strong style="color:#10b981;">YOUR SITE</strong>' if is_you else ""
                    st.markdown(
                        f'<div style="display:flex;gap:12px;align-items:center;background:{bg};'
                        f'border:1px solid {border};border-radius:10px;padding:10px 14px;margin-bottom:5px;">'
                        f'<span style="font-size:.95rem;font-weight:700;opacity:.35;min-width:26px;">#{r["pos"]}</span>'
                        f'<div style="flex:1;min-width:0;">'
                        f'<div style="font-size:.84rem;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'
                        f'{html_lib.escape(r["title"])}{you_tag}</div>'
                        f'<div style="font-size:.7rem;opacity:.35;font-family:monospace;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'
                        f'{html_lib.escape(r["url"])}</div></div></div>',
                        unsafe_allow_html=True,
                    )
                st.markdown("</div>", unsafe_allow_html=True)

        if td.get("features"):
            with st.container():
                st.markdown('<div class="v7-card">', unsafe_allow_html=True)
                slabel("SERP Signal Snapshot")
                FEAT_PT = {
                    "has_ai_overview":"🤖 AI Overview",  "has_paa":"❓ PAA",
                    "has_knowledge":  "🧠 Knowledge",    "has_shopping":"🛒 Shopping",
                    "has_local_pack": "📍 Local Pack",   "has_top_stories":"📰 Top Stories",
                    "has_images":     "🖼️ Images",        "has_videos":"▶️ Videos",
                    "has_sitelinks":  "🔗 Sitelinks",
                }
                feat_cols = st.columns(3)
                for i, (key, label) in enumerate(FEAT_PT.items()):
                    p = td["features"].get(key, False)
                    with feat_cols[i % 3]:
                        st.markdown(
                            f'<div style="background:var(--secondary-background-color);'
                            f'border:1px solid rgba(148,163,184,.12);border-radius:10px;padding:10px 14px;margin-bottom:8px;">'
                            f'<strong style="font-size:.82rem;">{label}</strong>'
                            f'<div style="margin-top:4px;color:{"#4ade80" if p else "#f87171"};font-size:.8rem;">'
                            f'{"✅ Present" if p else "✗ Not found"}</div></div>',
                            unsafe_allow_html=True,
                        )
                st.markdown("</div>", unsafe_allow_html=True)

        if td.get("ai_overview"):
            ai = td["ai_overview"]
            with st.container():
                st.markdown('<div class="v7-card">', unsafe_allow_html=True)
                slabel("AI Overview Preview")
                preview = ai["text"] if ai["source"] == "Google AI" else html_lib.escape(ai["text"])
                st.markdown(f'<div class="ai-box">{preview}</div>', unsafe_allow_html=True)
                if td.get("ai_check"):
                    ac = td["ai_check"]
                    if ac["in_ai_overview"]:
                        pos_txt = f"source #{ac['best_position']} of {ac['total_sources']}" if ac.get("total_sources") else "a cited source"
                        st.success(f"✅ Your domain is cited as **{pos_txt}** in the AI Overview.")
                        if ac.get("context_snippets"):
                            st.markdown("**Where you're mentioned:**")
                            for snip in ac["context_snippets"]:
                                st.markdown(
                                    f'<div style="font-size:.82rem;background:rgba(59,91,219,.07);border-left:3px solid var(--primary-color,#3b5bdb);'
                                    f'padding:8px 12px;border-radius:0 8px 8px 0;margin:4px 0;">{html_lib.escape(snip)}</div>',
                                    unsafe_allow_html=True,
                                )
                    elif ac.get("total_sources"):
                        st.warning(f"⚠️ Not among the {ac['total_sources']} cited sources in this AI Overview. Deepen content, add schema, earn links from cited pages.")
                    else:
                        st.warning("⚠️ Not in AI Overview. Deepen content, add schema, earn links from cited pages.")
                st.markdown("</div>", unsafe_allow_html=True)

        if td.get("paa_check"):
            pc = td["paa_check"]
            with st.container():
                st.markdown('<div class="v7-card">', unsafe_allow_html=True)
                slabel("People Also Ask — Source Position")
                if pc["in_paa"]:
                    st.success(f"✅ You're the cited source for {len(pc['matches'])} of {pc['total_paa_questions']} PAA question(s).")
                    for m in pc["matches"]:
                        st.markdown(
                            f'<div style="background:var(--secondary-background-color);border:1px solid rgba(148,163,184,.12);'
                            f'border-radius:10px;padding:12px 16px;margin-bottom:8px;">'
                            f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                            f'<strong style="font-size:.86rem;">{html_lib.escape(m["question"])}</strong>'
                            f'<span style="font-size:.7rem;opacity:.5;background:rgba(59,91,219,.12);padding:2px 8px;border-radius:6px;">PAA #{m["position"]}</span>'
                            f'</div>'
                            + (f'<div style="font-size:.8rem;opacity:.65;margin-top:6px;">{html_lib.escape(m["snippet"])}</div>' if m.get("snippet") else "")
                            + '</div>',
                            unsafe_allow_html=True,
                        )
                elif pc["total_paa_questions"]:
                    st.warning(f"⚠️ Not cited as the source for any of the {pc['total_paa_questions']} PAA questions on this SERP. Add direct, concise answers matching PAA phrasing to target these.")
                else:
                    st.caption("No People Also Ask box appeared for this query.")
                st.markdown("</div>", unsafe_allow_html=True)

        if td.get("interlinking"):
            with st.container():
                st.markdown('<div class="v7-card">', unsafe_allow_html=True)
                slabel("Interlinking Signals")
                for sig in td["interlinking"]:
                    linked = sig.get("links_to_target", False)
                    st.markdown(
                        f'<div style="display:flex;gap:10px;align-items:center;padding:5px 0;'
                        f'border-bottom:1px solid rgba(148,163,184,.06);">'
                        f'<span style="color:{"#4ade80" if linked else "#f87171"};font-size:.82rem;">'
                        f'{"🔗 Links to you" if linked else "✗ Does not link"}</span>'
                        f'<span style="font-size:.76rem;opacity:.45;font-family:monospace;">'
                        f'{html_lib.escape(sig["ranked_page"][:80])}</span></div>',
                        unsafe_allow_html=True,
                    )
                st.markdown("</div>", unsafe_allow_html=True)

        if td.get("target_page_data") and "error" not in td["target_page_data"]:
            tp = td["target_page_data"]
            with st.container():
                st.markdown('<div class="v7-card">', unsafe_allow_html=True)
                slabel("Target Page Link Audit")
                c1, c2, c3 = st.columns(3)
                c1.metric("Internal Links", len(tp.get("internal_links", [])))
                c2.metric("External Links", len(tp.get("external_links", [])))
                c3.metric("Word Count",     tp.get("word_count", 0))
                with st.expander("View internal links"):
                    if tp.get("internal_links"):
                        st.dataframe(pd.DataFrame(tp["internal_links"]), use_container_width=True, height=200)
                with st.expander("View external links"):
                    if tp.get("external_links"):
                        st.dataframe(pd.DataFrame(tp["external_links"]), use_container_width=True, height=200)
                st.markdown("</div>", unsafe_allow_html=True)

        bl = td.get("bl_data")
        if bl:
            with st.container():
                st.markdown('<div class="v7-card">', unsafe_allow_html=True)
                slabel("Citation Gap Scout")
                st.markdown(
                    '<div style="font-size:.75rem;opacity:.4;margin:-6px 0 12px;">'
                    'Scans outbound links on top-ranking competitor pages — the domains they cite/reference. '
                    'This is a citation signal, not a verified backlink index (real inbound backlink data needs '
                    'a paid index like Ahrefs/Majestic/Moz). Use it for outreach leads, not as a backlink audit.</div>',
                    unsafe_allow_html=True,
                )
                sm1, sm2, sm3 = st.columns(3)
                sm1.metric("Domains Cited by Competitors", bl["total_referring_domains"])
                sm2.metric("Citation Gap Opportunities",   len(bl["link_gap"]))
                sm3.metric("Competitor Pages Citing You",  bl["your_referrer_count"])
                if bl["link_gap"]:
                    st.markdown(
                        '<div style="font-size:.78rem;opacity:.45;margin:8px 0;">'
                        'These domains are cited by your top-ranking competitors — worth exploring for guest posts, '
                        'partnerships, or directory/resource-page outreach.</div>',
                        unsafe_allow_html=True,
                    )
                    for item in bl["link_gap"][:15]:
                        st.markdown(
                            f'<div class="bl-row"><div class="bl-dom">{html_lib.escape(item["domain"])}</div>'
                            f'<div class="bl-anchor">{html_lib.escape(item.get("anchor","")[:55]) if item.get("anchor") else "—"}</div>'
                            f'<div class="bl-count">{item["count"]}×</div></div>',
                            unsafe_allow_html=True,
                        )
                    bl_slug = slugify(
                        td["target_url"].replace("https://", "").replace("http://", "").split("/")[0]
                    )
                    st.download_button(
                        "⬇️ Download Outreach List CSV",
                        pd.DataFrame(bl["link_gap"]).to_csv(index=False).encode(),
                        f"{bl_slug}-citation-gap.csv", "text/csv",
                    )
                if bl.get("common_refs"):
                    st.markdown("**Competitor pages that already cite/link to you:**")
                    for pg in bl["common_refs"]:
                        st.markdown(f'<div style="font-size:.82rem;padding:3px 0;opacity:.75;">🔗 {html_lib.escape(pg)}</div>', unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

    # ── Tracking history ──────────────────────────────────────────────────────
    if st.session_state.position_tracker_history:
        with st.container():
            st.markdown('<div class="v7-card">', unsafe_allow_html=True)
            slabel(f"Tracking History ({len(st.session_state.position_tracker_history)} checks)")
            history_df = pd.DataFrame([{
                "Timestamp":      i["timestamp"],
                "Keyword":        i["query"],
                "URL":            i["target_url"],
                "Position":       i["position"] if i.get("position") is not None else "Not found",
                "Found":          "Yes" if i.get("found") else "No",
                "Depth":          i.get("depth", "—"),
                "SERP Signals":   "Yes" if i.get("serp_signals")   else "No",
                "Link Audit":     "Yes" if i.get("link_audit")      else "No",
                "Citation Gap Scout": "Yes" if i.get("backlink_scout")  else "No",
            } for i in st.session_state.position_tracker_history])
            st.dataframe(history_df, use_container_width=True, height=260)
            col_exp, col_clear = st.columns([3,1])
            with col_exp:
                st.download_button(
                    "⬇️ Export History CSV",
                    history_df.to_csv(index=False).encode(),
                    "position-tracking-history.csv", "text/csv",
                )
            with col_clear:
                if st.button("🗑️ Clear History"):
                    st.session_state.position_tracker_history = []
                    st.session_state.batch_tracking_results   = []
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
