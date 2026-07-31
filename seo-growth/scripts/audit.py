#!/usr/bin/env python3
"""
Measure a public website's SEO setup and print the facts as JSON.

Usage:
    python3 audit.py www.8x.social
    python3 audit.py www.8x.social --locales en,de,fr,nl

This script only MEASURES. It does not decide what's good or bad — Claude does
that using references/playbook.md. Keeping those two jobs separate is the whole
idea: numbers don't argue, and judgement shouldn't be hardcoded.

Why it shells out to curl instead of using urllib: no pip installs, works on any
mac or linux, and it sidesteps Python's macOS certificate problem (urllib throws
CERTIFICATE_VERIFY_FAILED on a default macOS install — I hit that while building
this).

Only fetches public URLs. GET only. No cookies, no credentials. Waits between
requests so it never hammers a site.
"""

import json
import re
import subprocess
import sys
import time
from urllib.parse import quote, urlparse

UA = "seo-growth-skill/1.0 (public SEO audit)"
DELAY = 0.3  # be polite between requests


def get(url, timeout=20):
    """Fetch a URL. Returns (status, headers_text, body). Never raises."""
    time.sleep(DELAY)
    try:
        r = subprocess.run(
            ["curl", "-sS", "-L", "-i", "-A", UA, "--max-time", str(timeout), url],
            capture_output=True, text=True, timeout=timeout + 10,
        )
        raw = r.stdout
    except Exception:
        return 0, "", ""

    # With -L and -i, curl prints one header block per hop. Take the last.
    parts = re.split(r"\r?\n\r?\n", raw, maxsplit=0)
    headers, body = "", raw
    for i, part in enumerate(parts):
        if part.startswith("HTTP/"):
            headers = part
            body = "\n\n".join(parts[i + 1:])
    m = re.search(r"HTTP/[\d.]+ (\d{3})", headers)
    status = int(m.group(1)) if m else 0
    return status, headers, body


def redirect_chain(url):
    """Follow redirects one at a time so we can see every hop."""
    chain, current = [], url
    for _ in range(8):
        time.sleep(DELAY)
        try:
            r = subprocess.run(
                ["curl", "-sSI", "-A", UA, "--max-time", "15", current],
                capture_output=True, text=True, timeout=25,
            )
        except Exception:
            break
        head = r.stdout
        m = re.search(r"HTTP/[\d.]+ (\d{3})", head)
        loc = re.search(r"(?im)^location:\s*(\S+)", head)
        if not m:
            break
        status = int(m.group(1))
        if 300 <= status < 400 and loc:
            nxt = loc.group(1)
            if nxt.startswith("/"):
                p = urlparse(current)
                nxt = f"{p.scheme}://{p.netloc}{nxt}"
            chain.append({
                "status": status,
                "to": nxt,
                # 301/308 pass full ranking signal. 302/307 say "temporary",
                # so search engines keep the old URL indexed.
                "permanent": status in (301, 308),
            })
            if nxt == current:
                break
            current = nxt
        else:
            break
    return chain, current


def text_of(html):
    """Rough visible text, for word counts."""
    h = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", html)
    h = re.sub(r"(?s)<[^>]+>", " ", h)
    return re.sub(r"\s+", " ", h).strip()


def tag_texts(html, tag):
    found = re.findall(rf"(?is)<{tag}[^>]*>(.*?)</{tag}>", html)
    return [re.sub(r"\s+", " ", re.sub(r"(?s)<[^>]+>", "", f)).strip() for f in found]


def check_page(url, conversion_path=""):
    """Everything worth knowing about one page."""
    status, headers, html = get(url)
    if status == 0 or not html:
        return {"url": url, "status": status, "error": "could not fetch"}

    body = text_of(html)
    words = len(body.split())
    schema = sorted(set(re.findall(r'"@type"\s*:\s*"([A-Za-z]+)"', html)))
    imgs = re.findall(r"(?is)<img[^>]*>", html)

    title = (tag_texts(html, "title") or [""])[0]
    desc = re.search(r'(?is)<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']', html)
    h2s = tag_texts(html, "h2")

    return {
        "url": url,
        "status": status,
        "html_kb": round(len(html) / 1024),
        "title": title or None,
        "title_length": len(title),
        "meta_description": (desc.group(1) if desc else None),
        "h1": tag_texts(html, "h1"),
        "h2_count": len(h2s),
        "h2_samples": h2s[:6],
        "h3_count": len(re.findall(r"(?i)<h3[^>]*>", html)),
        "word_count": words,
        "schema_types": schema,
        "has_faq_schema": "FAQPage" in schema,
        "images": len(imgs),
        "images_missing_alt": sum(1 for i in imgs if not re.search(r'alt\s*=\s*["\'][^"\']+', i)),
        "hreflang_count": len(re.findall(r"(?i)hreflang=", html)),
        "canonical": bool(re.search(r'(?i)rel=["\']canonical["\']', html)),
        "no_store": bool(re.search(r"(?im)^cache-control:.*no-store", headers)),
        # Does this page give the reader any way to convert?
        "links_to_conversion": (
            len(re.findall(re.escape(conversion_path), html)) if conversion_path else None
        ),
    }


def keyword_in_page(page, keyword):
    """How often does the page actually say its own target keyword?"""
    if not keyword or "error" in page:
        return None
    head = keyword.split()[0].lower()
    status, _, html = get(page["url"])
    body = text_of(html).lower()
    return {
        "keyword": keyword,
        "in_body": len(re.findall(re.escape(head), body)),
        "in_h2": sum(1 for h in page.get("h2_samples", []) if head in h.lower()),
        "word_count": page.get("word_count"),
    }


def real_queries(seed, locale, country):
    """
    Real search queries from Google's autocomplete. Free, no API key.

    Autocomplete only suggests things people actually type, so a suggestion is
    proof the query exists. It gives no volume — so this returns queries, never
    invented numbers.

    Per-locale is the useful part: seeding "ugc creator" at hl=de returns
    "ugc creator werden", which is NOT a translation of the English phrase.
    """
    url = (
        "https://suggestqueries.google.com/complete/search?client=firefox"
        f"&hl={locale}&gl={country}&ie=UTF-8&oe=UTF-8&q={quote(seed)}"
    )
    _, _, body = get(url, timeout=12)
    try:
        data = json.loads(body)
        return [s for s in data[1] if s.lower() != seed.lower()][:6]
    except Exception:
        return []


def audit(domain, locales=None, seed=None, conversion_path=""):
    out = {"domain": domain, "checked_at": time.strftime("%Y-%m-%d %H:%M"), "notes": []}

    # --- 1. Do unknown URLs 404 properly? -----------------------------------
    # A correct site says 404. Some frameworks return 200 with a generic page,
    # which means search engines can index URLs that don't exist.
    fake = f"https://{domain}/this-page-does-not-exist-9k2x"
    fake_status, _, fake_body = get(fake)
    out["fake_url_returns"] = fake_status
    out["soft_404"] = fake_status == 200
    if out["soft_404"]:
        out["notes"].append(
            f"Unknown URLs return {fake_status} instead of 404. Verify: "
            f'curl -o /dev/null -s -w "%{{http_code}}" {fake}'
        )

    # --- 2. robots.txt -------------------------------------------------------
    r_status, _, robots = get(f"https://{domain}/robots.txt")
    is_html = robots.strip().lower().startswith(("<!doctype", "<html"))
    out["robots"] = {
        "status": r_status,
        "served_as_text": r_status == 200 and not is_html,
        "declares_sitemap": bool(re.search(r"(?im)^sitemap:", robots)) if not is_html else False,
    }

    # --- 3. sitemap ----------------------------------------------------------
    _, _, sm = get(f"https://{domain}/sitemap.xml", timeout=30)
    urls = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", sm)
    sections, locale_seen, slug_locales = {}, set(), {}
    for u in urls:
        try:
            path = urlparse(u).path
        except Exception:
            continue
        segs = [s for s in path.split("/") if s]
        loc = segs[0] if segs and re.fullmatch(r"[a-z]{2}", segs[0]) else None
        rest = segs[1:] if loc else segs
        if loc:
            locale_seen.add(loc)
        key = rest[0] if rest else "(homepage)"
        sections[key] = sections.get(key, 0) + 1
        slug = "/".join(rest) or "(homepage)"
        slug_locales[slug] = slug_locales.get(slug, 0) + 1

    n_locales = len(locale_seen)
    fully = sum(1 for v in slug_locales.values() if v >= n_locales) if n_locales else 0
    out["sitemap"] = {
        "url_count": len(urls),
        "locales_found": sorted(locale_seen),
        "sections": dict(sorted(sections.items(), key=lambda kv: -kv[1])[:12]),
        "unique_slugs": len(slug_locales),
        "slugs_in_every_locale": fully,
        "translation_complete_pct": round(100 * fully / len(slug_locales)) if slug_locales else None,
    }

    # --- 4. how do people actually arrive? ----------------------------------
    apex = domain.replace("www.", "", 1)
    entries = {}
    for label, u in [
        ("apex", f"https://{apex}"),
        ("root", f"https://{domain}/"),
        ("http", f"http://{domain}/"),
    ]:
        chain, final = redirect_chain(u)
        temp = [h for h in chain if not h["permanent"]]
        entries[label] = {
            "hops": len(chain),
            "temporary_hops": len(temp),
            "chain": [f"{h['status']} -> {h['to']}" for h in chain],
            "final": final,
        }
        if temp:
            out["notes"].append(
                f"{label}: {len(temp)} temporary redirect(s) (302/307) on a permanent move. "
                "Should be 301/308 so ranking signal transfers."
            )
    out["entry_points"] = entries

    # --- 5. llms.txt (for AI search engines) --------------------------------
    l_status, _, llms = get(f"https://{domain}/llms.txt")
    out["llms_txt"] = {
        "status": l_status,
        "exists": l_status == 200 and not llms.strip().lower().startswith(("<!doctype", "<html")),
    }

    # --- 6. sample some real pages ------------------------------------------
    # Which locale is the DEFAULT one? Don't guess alphabetically — that picked
    # "ar" on 8x.social and audited the Arabic site by mistake. The root redirect
    # is authoritative: https://site/ -> /en means the default locale is "en".
    default_locale = ""
    root_final = entries.get("root", {}).get("final", "")
    m = re.search(r"https?://[^/]+/([a-z]{2})(?:/|$)", root_final)
    if m and m.group(1) in locale_seen:
        default_locale = m.group(1)
    elif "en" in locale_seen:
        default_locale = "en"
    elif locale_seen:
        default_locale = sorted(locale_seen)[0]
    out["default_locale"] = default_locale or None

    prefix = f"/{default_locale}" if default_locale else ""
    candidates = [f"https://{domain}{prefix}"]
    for u in urls:
        if len(candidates) >= 6:
            break
        # On a localised site, only sample the default locale so the numbers are
        # comparable. On a single-language site there's no prefix to match, so
        # take any real page — otherwise we'd only ever check the homepage.
        if u in candidates:
            continue
        if prefix:
            if f"{prefix}/" in u:
                candidates.append(u)
        elif urlparse(u).path.strip("/"):
            candidates.append(u)
    out["pages"] = [check_page(u, conversion_path) for u in candidates]

    ok = [p for p in out["pages"] if "error" not in p]
    if ok:
        out["page_summary"] = {
            "checked": len(ok),
            "with_faq_schema": sum(1 for p in ok if p["has_faq_schema"]),
            "avg_html_kb": round(sum(p["html_kb"] for p in ok) / len(ok)),
            "total_images_missing_alt": sum(p["images_missing_alt"] for p in ok),
            "pages_with_no_store": sum(1 for p in ok if p["no_store"]),
            "pages_with_no_conversion_link": (
                sum(1 for p in ok if p.get("links_to_conversion") == 0)
                if conversion_path else None
            ),
        }

    # --- 7. real queries per market -----------------------------------------
    if seed:
        market = {"en": "us", "de": "de", "fr": "fr", "es": "es", "it": "it", "nl": "nl",
                  "pt": "br", "pl": "pl", "tr": "tr", "ru": "ru", "ja": "jp", "ko": "kr",
                  "hi": "in", "id": "id", "ar": "ae", "zh": "tw", "sl": "si", "bg": "bg",
                  "el": "gr"}
        want = locales or sorted(locale_seen) or ["en"]
        out["real_queries"] = {
            lo: real_queries(seed, lo, market.get(lo, "us")) for lo in want[:10]
        }

    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        sys.exit(1)

    def opt(name):
        flag = f"--{name}"
        return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else None

    domain = args[0].replace("https://", "").replace("http://", "").rstrip("/")
    locales = (opt("locales") or "").split(",") if opt("locales") else None
    result = audit(
        domain,
        locales=[l for l in (locales or []) if l] or None,
        seed=opt("seed"),
        conversion_path=opt("conversion") or "",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
