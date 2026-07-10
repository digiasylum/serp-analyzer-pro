# url_inspector.py — SERP V6
# MERGED: Claude's canonical/OG/robots/content_blocks + your link audit + image grid + schema fixes
import requests, json
from bs4 import BeautifulSoup
from readability import Document
from utils import normalize_space, domain_of
from urllib.parse import urljoin

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"}

def _detect_content_type(soup, url: str) -> str:
    og = (soup.find("meta", property="og:type") or {}).get("content","")
    if og == "article": return "Blog Post / Article"
    if og == "product": return "Product Page"
    u = url.lower()
    if any(x in u for x in ["/blog/","/post/","/article/","/news/"]): return "Blog Post"
    if any(x in u for x in ["/product","/shop/","/store/"]): return "Product Page"
    if "/service" in u: return "Service Page"
    if any(x in u for x in ["/category","/collection","/tag/"]): return "Category / Collection"
    if any(x in u for x in ["/about","/contact","/team"]): return "About / Contact"
    return "Web Page"

def _extract_content_blocks(soup) -> list:
    blocks = []
    for tag in soup.find_all(["h1","h2","h3","h4","p","ul","ol"]):
        name = tag.name
        if name in ("h1","h2","h3","h4"):
            text = normalize_space(tag.get_text())
            if text: blocks.append({"type":"heading","level":int(name[1]),"text":text,"items":None})
        elif name == "p":
            text = normalize_space(tag.get_text())
            if text and len(text) > 30:
                blocks.append({"type":"paragraph","level":None,"text":text,"items":None})
        elif name in ("ul","ol"):
            items = [normalize_space(li.get_text()) for li in tag.find_all("li") if normalize_space(li.get_text())]
            if items: blocks.append({"type":"list","level":None,"text":"","items":items})
    return blocks

def inspect_url(url: str) -> dict:
    try:
        r = requests.get(url, headers=HEADERS, timeout=15); r.raise_for_status()
        raw_html = r.text
    except requests.RequestException as e: return {"error": f"Failed to fetch URL: {e}"}

    soup         = BeautifulSoup(raw_html, "html.parser")
    doc          = Document(raw_html)
    summary_soup = BeautifulSoup(doc.summary(), "html.parser")
    full_text    = normalize_space(summary_soup.get_text())
    base_domain  = domain_of(url)

    # Meta
    meta_title        = soup.find("title").get_text() if soup.find("title") else ""
    meta_desc_tag     = soup.find("meta", attrs={"name":"description"})
    meta_desc         = meta_desc_tag["content"] if meta_desc_tag else ""
    meta_kw_tag       = soup.find("meta", attrs={"name":"keywords"})
    meta_keywords     = meta_kw_tag["content"] if meta_kw_tag else ""
    canonical_tag     = soup.find("link", rel="canonical")
    canonical         = canonical_tag["href"] if canonical_tag else ""
    robots_tag        = soup.find("meta", attrs={"name":"robots"})
    robots            = robots_tag["content"] if robots_tag else ""
    og = {}
    for prop in ["og:title","og:description","og:image","og:type","og:url"]:
        t = soup.find("meta", property=prop)
        if t: og[prop.replace("og:","")] = t.get("content","")

    word_count   = len(full_text.split())
    h1s = [normalize_space(h.get_text()) for h in soup.find_all("h1")]
    h2s = [normalize_space(h.get_text()) for h in soup.find_all("h2")]
    h3s = [normalize_space(h.get_text()) for h in soup.find_all("h3")]
    content_type     = _detect_content_type(soup, url)
    content_blocks   = _extract_content_blocks(summary_soup)

    internal_links, external_links = [], []
    for link in soup.find_all("a", href=True):
        href = link["href"]
        abs_url   = urljoin(url, href)
        link_text = normalize_space(link.get_text())
        if not link_text or abs_url.startswith("javascript"): continue
        if base_domain in abs_url: internal_links.append({"text":link_text,"url":abs_url})
        else: external_links.append({"text":link_text,"url":abs_url})

    images = []
    for img in soup.find_all("img"):
        src = img.get("data-src") or img.get("src")
        if src: images.append({"src":urljoin(url,src),"alt":img.get("alt","")})

    # Page speed hint: warn if many large images
    large_img_count = sum(1 for img in images if any(x in img["src"] for x in [".jpg",".png",".jpeg",".webp"]))
    speed_hint = f"⚠️ {large_img_count} images detected — check compression for page speed." if large_img_count > 10 else f"✅ {large_img_count} images detected."

    schemas = []
    for tag in soup.find_all("script", {"type":"application/ld+json"}):
        try:
            if tag.string: schemas.append(json.loads(tag.string))
        except json.JSONDecodeError: continue

    return {
        "url": url, "content_type": content_type,
        "meta_title": meta_title, "meta_title_len": len(meta_title),
        "meta_description": meta_desc, "meta_description_len": len(meta_desc),
        "meta_keywords": meta_keywords, "canonical": canonical, "robots": robots, "og": og,
        "word_count": word_count, "h1s": h1s, "h2s": h2s, "h3s": h3s,
        "content_blocks": content_blocks, "full_text": full_text,
        "internal_links": internal_links, "external_links": external_links,
        "images": images, "schemas": schemas, "speed_hint": speed_hint,
    }
