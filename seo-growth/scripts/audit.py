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
import os
import re
import subprocess
import sys
import time
from urllib.parse import quote, urlparse

UA = "seo-growth-skill/1.0 (public SEO audit)"
DELAY = 0.3  # be polite between requests

# Where saved runs live, so you can see whether a fix actually worked.
HISTORY_DIR = os.path.expanduser("~/.seo-growth")


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

    # Translation coverage only means something on a multi-language site. On a
    # single-language site the honest answer is "not applicable" — reporting 0%
    # would read as a failure when there's nothing to translate.
    n_locales = len(locale_seen)
    multilingual = n_locales >= 2
    fully = sum(1 for v in slug_locales.values() if v >= n_locales) if multilingual else None
    out["sitemap"] = {
        "url_count": len(urls),
        "locales_found": sorted(locale_seen),
        "sections": dict(sorted(sections.items(), key=lambda kv: -kv[1])[:12]),
        "unique_slugs": len(slug_locales),
        "slugs_in_every_locale": fully,
        "translation_complete_pct": (
            round(100 * fully / len(slug_locales)) if multilingual and slug_locales else None
        ),
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


# ---------------------------------------------------------------------------
# History: save a run, then compare it to the last one.
#
# This is the bit that turns an audit into a loop. A one-off audit tells you
# what's broken. Two audits tell you whether the thing you shipped worked, which
# is the actually useful question.
# ---------------------------------------------------------------------------

# The handful of numbers worth watching between runs.
def key_metrics(run):
    ps = run.get("page_summary") or {}
    sm = run.get("sitemap") or {}
    temp_hops = sum(e.get("temporary_hops", 0) for e in (run.get("entry_points") or {}).values())
    return {
        "unknown URLs 404 correctly": not run.get("soft_404", False),
        "temporary redirects": temp_hops,
        "sitemap URLs": sm.get("url_count"),
        "translated into every locale (%)": sm.get("translation_complete_pct"),
        "llms.txt present": (run.get("llms_txt") or {}).get("exists"),
        "pages with FAQ schema": ps.get("with_faq_schema"),
        "pages with no conversion link": ps.get("pages_with_no_conversion_link"),
        "images missing alt text": ps.get("total_images_missing_alt"),
        "avg page weight (KB)": ps.get("avg_html_kb"),
    }


def save_run(run):
    folder = os.path.join(HISTORY_DIR, run["domain"])
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, time.strftime("%Y-%m-%d-%H%M") + ".json")
    with open(path, "w") as f:
        json.dump(run, f, indent=2, ensure_ascii=False)
    return path


def past_runs(domain):
    folder = os.path.join(HISTORY_DIR, domain)
    if not os.path.isdir(folder):
        return []
    out = []
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(folder, name)) as f:
                out.append((name[:-5], json.load(f)))
        except Exception:
            continue  # a half-written file shouldn't break the history
    return out


def compare(old, new):
    """What changed between two runs. Returns a list of readable lines."""
    a, b = key_metrics(old), key_metrics(new)
    lines = []
    for label, new_val in b.items():
        old_val = a.get(label)
        if old_val == new_val or new_val is None:
            continue
        if isinstance(new_val, bool) or isinstance(old_val, bool):
            lines.append(f"  {label}: {old_val} -> {new_val}")
        elif isinstance(new_val, (int, float)) and isinstance(old_val, (int, float)):
            diff = new_val - old_val
            lines.append(f"  {label}: {old_val} -> {new_val} ({diff:+})")
        else:
            lines.append(f"  {label}: {old_val} -> {new_val}")
    return lines


def print_summary(run):
    """Human-readable version. The JSON is for Claude; this is for eyeballs."""
    m = key_metrics(run)
    print(f"\n{run['domain']}  ({run['checked_at']})")
    print("-" * 58)
    for label, value in m.items():
        if value is None:
            value = "not measured"
        print(f"  {label:34} {value}")

    if run.get("notes"):
        print("\n  Worth fixing:")
        for n in run["notes"]:
            print(f"    - {n}")

    rq = run.get("real_queries") or {}
    if rq:
        print("\n  Real queries by market:")
        for locale, queries in list(rq.items())[:8]:
            if queries:
                print(f"    {locale}: {', '.join(queries[:3])}")
    print()


# ---------------------------------------------------------------------------
# Dashboard: one HTML file built from every saved run.
#
# No framework, no build step, no hosting. It writes a single file you can open
# by double-clicking or drop on any static host. That felt like the right shape:
# the whole point of this tool is that it works without setting anything up.
# ---------------------------------------------------------------------------

def build_dashboard(out_path=None):
    domains = []
    if os.path.isdir(HISTORY_DIR):
        for name in sorted(os.listdir(HISTORY_DIR)):
            runs = past_runs(name)
            if runs:
                domains.append((name, runs))

    if not domains:
        return None, "No saved runs yet. Run an audit with --save first."

    rows = []
    for domain, runs in domains:
        stamp, latest = runs[-1]
        m = key_metrics(latest)
        changes = compare(runs[-2][1], latest) if len(runs) >= 2 else []
        problems = len(latest.get("notes") or [])

        # Health here is deliberately simple: how many of the checks that
        # returned an answer are currently in a good state. No weighting, no
        # hidden formula — you can recount it by hand from the table.
        checks = [
            m["unknown URLs 404 correctly"] is True,
            m["temporary redirects"] == 0,
            m["llms.txt present"] is True,
            (m["pages with no conversion link"] or 0) == 0,
            (m["translated into every locale (%)"] or 100) >= 90,
            (m["pages with FAQ schema"] or 0) > 0,
        ]
        passed = sum(1 for c in checks if c)
        rows.append({
            "domain": domain, "stamp": stamp, "m": m, "changes": changes,
            "problems": problems, "passed": passed, "total": len(checks),
            "runs": len(runs),
            "history": [(s, key_metrics(r)) for s, r in runs],
        })

    def cell(value, good=None):
        """A number plus a word. Never colour on its own."""
        if value is None:
            return '<td class="muted">not measured</td>'
        if isinstance(value, bool):
            return (f'<td class="{"ok" if value else "bad"}">'
                    f'{"yes" if value else "NO"}</td>')
        cls = "" if good is None else ("ok" if good else "bad")
        return f'<td class="{cls}">{value}</td>'

    body = []
    for r in rows:
        m = r["m"]
        body.append(f"""
      <tr>
        <td class="dom"><strong>{r['domain']}</strong><br>
          <span class="muted">{r['stamp']} · {r['runs']} run(s)</span></td>
        <td><strong>{r['passed']}/{r['total']}</strong> checks passing</td>
        {cell(m['unknown URLs 404 correctly'])}
        {cell(m['temporary redirects'], m['temporary redirects'] == 0)}
        {cell(m['translated into every locale (%)'])}
        {cell(m['pages with FAQ schema'])}
        {cell(m['llms.txt present'])}
        {cell(m['images missing alt text'])}
        <td>{'<br>'.join(c.strip() for c in r['changes']) if r['changes']
             else '<span class="muted">no change</span>'}</td>
      </tr>""")

    notes_blocks = []
    for domain, runs in domains:
        notes = (runs[-1][1].get("notes") or [])
        if not notes:
            continue
        items = "".join(f"<li>{n}</li>" for n in notes)
        notes_blocks.append(f"<h3>{domain}</h3><ul>{items}</ul>")

    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SEO health — {len(rows)} domain(s)</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font: 15px/1.55 system-ui, -apple-system, sans-serif;
         margin: 0; padding: 32px 20px; max-width: 1200px; margin-inline: auto; }}
  h1 {{ font-size: 22px; margin: 0 0 4px; }}
  h2 {{ font-size: 16px; margin: 36px 0 10px; }}
  h3 {{ font-size: 14px; margin: 18px 0 6px; }}
  .muted {{ opacity: .6; font-size: 12px; }}
  .wrap {{ overflow-x: auto; }}
  table {{ border-collapse: collapse; width: 100%; min-width: 900px; font-size: 13px; }}
  th, td {{ text-align: left; padding: 9px 10px; border-top: 1px solid #8884;
            vertical-align: top; }}
  th {{ font-size: 11px; text-transform: uppercase; letter-spacing: .04em; opacity: .6; }}
  .dom {{ min-width: 190px; }}
  /* Colour is a second signal only — every cell also says yes/NO or a number. */
  .ok  {{ color: #0a7f28; font-weight: 600; }}
  .bad {{ color: #b3261e; font-weight: 600; }}
  ul {{ margin: 4px 0; padding-left: 20px; }} li {{ margin: 3px 0; }}
  footer {{ margin-top: 40px; font-size: 12px; opacity: .65; }}
  code {{ font-size: 12px; }}
</style></head><body>

<h1>SEO health</h1>
<p class="muted">{len(rows)} domain(s) · generated {time.strftime('%Y-%m-%d %H:%M')} ·
   built from saved runs in ~/.seo-growth</p>

<div class="wrap">
<table>
  <thead><tr>
    <th>Domain</th><th>Status</th><th>404s correct</th><th>Temp redirects</th>
    <th>Translated %</th><th>FAQ pages</th><th>llms.txt</th><th>Missing alt</th>
    <th>Changed since last run</th>
  </tr></thead>
  <tbody>{''.join(body)}</tbody>
</table>
</div>

{'<h2>What to fix</h2>' + ''.join(notes_blocks) if notes_blocks else ''}

<footer>
  <p><strong>How to read this.</strong> "Status" counts how many of six checks are
  currently in a good state — no weighting, you can recount it from the row.
  Blank cells mean the check could not be measured, which is not the same as
  passing.</p>
  <p><strong>Refresh it:</strong>
  <code>python3 audit.py &lt;domain&gt; --save</code> then
  <code>python3 audit.py --dashboard</code></p>
  <p>Measured from public pages only. Search volume, backlinks and real Core Web
  Vitals are not included — those need a browser or a paid API.</p>
</footer>
</body></html>"""

    path = out_path or os.path.join(HISTORY_DIR, "dashboard.html")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(html)
    return path, None


def main():
    argv = sys.argv[1:]

    def opt(name):
        flag = f"--{name}"
        return argv[argv.index(flag) + 1] if flag in argv else None

    def has(name):
        return f"--{name}" in argv

    # Flag values look like positional args, so drop anything that follows a flag.
    value_flags = {"--locales", "--seed", "--conversion"}
    positional, skip = [], False
    for a in argv:
        if skip:
            skip = False
            continue
        if a in value_flags:
            skip = True
            continue
        if not a.startswith("--"):
            positional.append(a)

    # --dashboard needs no domain: it renders whatever has been saved so far.
    if has("dashboard"):
        path, err = build_dashboard(opt("out"))
        if err:
            print(err)
            sys.exit(1)
        print(f"Dashboard written to {path}\n\nOpen it with:  open {path}")
        return

    if not positional:
        print(__doc__)
        sys.exit(1)

    domain = positional[0].replace("https://", "").replace("http://", "").rstrip("/")

    # --history just reads what's already saved. No network needed.
    if has("history"):
        runs = past_runs(domain)
        if not runs:
            print(f"No saved runs for {domain} yet. Run with --save first.")
            return
        print(f"\n{len(runs)} saved run(s) for {domain}:\n")
        for stamp, run in runs:
            m = key_metrics(run)
            print(f"  {stamp}  404s ok: {m['unknown URLs 404 correctly']}  "
                  f"temp redirects: {m['temporary redirects']}  "
                  f"FAQ pages: {m['pages with FAQ schema']}")
        if len(runs) >= 2:
            print(f"\nChange from {runs[-2][0]} to {runs[-1][0]}:")
            changed = compare(runs[-2][1], runs[-1][1])
            print("\n".join(changed) if changed else "  nothing changed")
        print()
        return

    locales = (opt("locales") or "").split(",") if opt("locales") else None
    result = audit(
        domain,
        locales=[l for l in (locales or []) if l] or None,
        seed=opt("seed"),
        conversion_path=opt("conversion") or "",
    )

    if has("save"):
        previous = past_runs(domain)
        path = save_run(result)
        if has("summary"):
            print_summary(result)
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        print(f"\nSaved to {path}")
        if previous:
            stamp, last = previous[-1]
            changed = compare(last, result)
            print(f"\nChanged since {stamp}:")
            print("\n".join(changed) if changed else "  nothing changed")
        else:
            print("\nFirst saved run — this is the baseline. Run again after you ship a fix.")
        print()
        return

    if has("summary"):
        print_summary(result)
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
