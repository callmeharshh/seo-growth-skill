#!/usr/bin/env python3
"""
Build the shared target list, in the exact shape the brief specifies:

    Domain | Market | Audience | Query/topic | Intent | Evidence | Recommended asset | Priority | Status

    python3 target_list.py                      # every property in portfolio.json
    python3 target_list.py --only 8x.social
    python3 target_list.py --csv targets.csv    # for a spreadsheet
    python3 target_list.py --markets            # research every configured market

Two of those nine columns are Market and Audience, which is the reason this runs
per market rather than once per domain. The same seed returns different queries
and a different audience in each country, and averaging them hides the thing you
most want to see.

Concretely, on 8x.social: in the US "ugc creator" is people researching the
category. In Germany, Brazil and Turkey it is overwhelmingly people looking for
the work — werden, vagas, iş ilanları. Same domain, same seed, different market,
different audience, different asset. A single-market run reports none of that.

Rows come from three places, all measured:
  - keyword gaps      a competitor covers the query, we don't
  - open queries      real query, nobody checked covers it
  - technical findings from the audit, which are also work that needs an owner

Status starts at "proposed" for everything. It's a real column in the brief
because the list is meant to be worked, not admired.
"""

import csv
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import audit as audit_mod
import keywords as kw_mod

OUT = os.path.expanduser("~/.seo-growth")

# Which language/country pair to use per market, and what to call it.
MARKETS = {
    "us": ("en", "us", "United States"),
    "gb": ("en", "gb", "United Kingdom"),
    "br": ("pt", "br", "Brazil"),
    "tr": ("tr", "tr", "Turkey"),
    "mx": ("es", "mx", "Mexico"),
    "de": ("de", "de", "Germany"),
    "es": ("es", "es", "Spain"),
    "fr": ("fr", "fr", "France"),
    "in": ("hi", "in", "India"),
    "id": ("id", "id", "Indonesia"),
}


def audience_for(query, intent):
    """
    Who is typing this?

    The distinction that matters for a two-sided marketplace: someone asking how
    to BECOME a creator is supply, someone asking how to HIRE one is demand. They
    need different pages and they convert to different places, so guessing wrong
    wastes the whole page.
    """
    q = query.lower()
    supply = [
        "job", "jobs", "salary", "pay", "paid", "earn", "money", "apply",
        "hiring", "career", "become", "start", "beginner", "no experience",
        # the same intent in the markets 8x is opening
        "werden", "gesucht", "verdienst", "verdienen",       # de
        "vagas", "ganhar", "como ser", "como começar",       # pt
        "nedir", "nasıl olunur", "iş ilanları", "maaş",      # tr
        "trabajo", "empleo", "ganar", "cómo ser",            # es
        "kaise bane", "salary in india",                     # hi
    ]
    demand = [
        "hire", "agency", "platform", "software", "tool", "vs", "alternative",
        "pricing", "cost", "for brands", "for dtc", "campaign", "roi", "best",
    ]
    if any(w in q for w in supply):
        return "Creator (supply)"
    if any(w in q for w in demand):
        return "Brand (demand)"
    if intent in ("commercial", "tool"):
        return "Brand (demand)"
    return "Researcher (top of funnel)"


def asset_for(query, intent, audience):
    """What should we actually build for this query?"""
    q = query.lower()
    if any(w in q for w in ("calculator", "how much", "salary", "rate", "cost",
                            "verdienst", "maaş", "quanto ganha", "cuánto")):
        return "free tool"
    if " vs " in q or "alternative" in q:
        return "comparison page"
    if intent == "commercial" or audience == "Brand (demand)":
        return "landing page"
    return "blog post"


def conversion_for(audience, prop):
    if audience == "Creator (supply)":
        return prop.get("creator_path", "/en/for-creators")
    return prop.get("conversion_path", "/en/book-call")


def rows_for_market(prop, market_key, depth):
    hl, gl, label = MARKETS.get(market_key, ("en", market_key, market_key.upper()))
    domain = prop["domain"]

    res = kw_mod.research(
        domain,
        prop.get("seeds", []),
        prop.get("competitors", []),
        locale=hl,
        market=gl,
        depth=depth,
        limit=200,
        exclude=prop.get("exclude_terms", []),
    )

    rows = []
    for c in res.get("content_plan", []):
        if c.get("is_category"):
            continue  # a category needs splitting before it's a work item
        q = c["primary_keyword"]
        intent = c["intent"]
        audience = audience_for(q, intent)
        asset = asset_for(q, intent, audience)
        evidence = (
            f"Real query (Google autocomplete, {hl}-{gl}). "
            f"Cluster of {c['cluster_size']}. "
            f"Not covered by {domain}. Covered by {c['competitor_pages'][0]}."
            if c.get("competitor_pages") else
            f"Real query (Google autocomplete, {hl}-{gl}). Cluster of {c['cluster_size']}."
        )
        rows.append({
            "Domain": domain,
            "Market": label,
            "Audience": audience,
            "Query/topic": q,
            "Intent": intent,
            "Evidence": evidence,
            "Recommended asset": asset,
            "Priority": c["points"],
            "Status": "proposed",
            "_conversion": conversion_for(audience, prop),
            "_also": c.get("also_answers", [])[:5],
        })

    # Uncontested long tail, best few only — these are cheap but unproven.
    for k in res.get("keywords", []):
        if not k["verdict"].startswith("open") or k["points"] < 60:
            continue
        audience = audience_for(k["query"], k["intent"])
        rows.append({
            "Domain": domain,
            "Market": label,
            "Audience": audience,
            "Query/topic": k["query"],
            "Intent": k["intent"],
            "Evidence": f"Real query ({hl}-{gl}). No page on {domain}; none on competitors checked.",
            "Recommended asset": asset_for(k["query"], k["intent"], audience),
            "Priority": k["points"],
            "Status": "proposed",
            "_conversion": conversion_for(audience, prop),
            "_also": [],
        })

    return rows, res


def technical_rows(prop, audit_result):
    """Audit findings are work too, so they belong in the same list."""
    domain = prop["domain"]
    rows = []
    for note in audit_result.get("notes", []):
        low = note.lower()
        if "404" in low:
            q, pri = "Unknown URLs return 200 instead of 404", 95
        elif "temporary redirect" in low:
            q, pri = "Permanent moves served as temporary redirects", 80
        elif "llms" in low:
            q, pri = "No llms.txt for answer engines", 55
        else:
            q, pri = note[:70], 50
        rows.append({
            "Domain": domain,
            "Market": "All",
            "Audience": "Search crawler / answer engine",
            "Query/topic": q,
            "Intent": "technical",
            "Evidence": note,
            "Recommended asset": "technical fix",
            "Priority": pri,
            "Status": "proposed",
            "_conversion": "",
            "_also": [],
        })

    sm = audit_result.get("sitemap", {})
    pct = sm.get("translation_complete_pct")
    if pct is not None and pct < 90:
        rows.append({
            "Domain": domain,
            "Market": "All",
            "Audience": "Search crawler / answer engine",
            "Query/topic": f"Only {pct}% of pages exist in every locale",
            "Intent": "technical",
            "Evidence": (
                f"{sm.get('slugs_in_every_locale')} of {sm.get('unique_slugs')} slugs are "
                f"published in all {len(sm.get('locales_found', []))} locales. Incomplete "
                f"hreflang clusters mean locales compete instead of consolidating."
            ),
            "Recommended asset": "technical fix",
            "Priority": 85,
            "Status": "proposed",
            "_conversion": "",
            "_also": [],
        })
    return rows


COLUMNS = ["Domain", "Market", "Audience", "Query/topic", "Intent",
           "Evidence", "Recommended asset", "Priority", "Status"]


def print_table(rows, limit=25):
    print(f"\n{'PRI':>4}  {'MARKET':<14} {'AUDIENCE':<30} {'ASSET':<16} QUERY / TOPIC")
    print("-" * 118)
    for r in rows[:limit]:
        print(f"{r['Priority']:>4}  {r['Market']:<14} {r['Audience']:<30} "
              f"{r['Recommended asset']:<16} {r['Query/topic'][:44]}")
    if len(rows) > limit:
        print(f"\n  ... {len(rows) - limit} more rows. Use --csv to get all of them.")


def main():
    argv = sys.argv[1:]

    def opt(n, d=None):
        return argv[argv.index(f"--{n}") + 1] if f"--{n}" in argv else d

    with open(os.path.join(ROOT, "portfolio.json")) as f:
        props = [p for p in json.load(f).get("properties", []) if p.get("domain")]

    only = opt("only")
    if only:
        props = [p for p in props if only in p["domain"]]
    if not props:
        print("No matching properties in portfolio.json")
        sys.exit(1)

    depth = int(opt("depth", "8"))
    all_rows = []

    for prop in props:
        domain = prop["domain"]
        markets = (prop.get("markets") or ["us"]) if "--markets" in argv else [
            (prop.get("markets") or ["us"])[0]
        ]

        print(f"\n{'=' * 70}\n{domain}  —  {len(markets)} market(s)\n{'=' * 70}",
              file=sys.stderr)

        print("Auditing...", file=sys.stderr)
        a = audit_mod.audit(domain, locales=None, seed=None,
                            conversion_path=prop.get("conversion_path", ""))
        audit_mod.save_run(a)
        all_rows.extend(technical_rows(prop, a))

        for mk in markets:
            print(f"Researching market: {mk}...", file=sys.stderr)
            try:
                rows, _ = rows_for_market(prop, mk, depth)
                all_rows.extend(rows)
                print(f"  {len(rows)} target(s)", file=sys.stderr)
            except Exception as e:
                print(f"  failed: {e}", file=sys.stderr)

    all_rows.sort(key=lambda r: -r["Priority"])

    csv_path = opt("csv")
    if csv_path:
        with open(csv_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
            w.writeheader()
            w.writerows(all_rows)
        print(f"\nWrote {len(all_rows)} rows to {csv_path}")

    out = os.path.join(OUT, f"target-list-{time.strftime('%Y-%m-%d')}.json")
    os.makedirs(OUT, exist_ok=True)
    with open(out, "w") as f:
        json.dump(all_rows, f, indent=2, ensure_ascii=False)

    print_table(all_rows)

    # The split that only shows up when you research per market.
    supply = [r for r in all_rows if r["Audience"] == "Creator (supply)"]
    demand = [r for r in all_rows if r["Audience"] == "Brand (demand)"]
    print(f"\n  {len(all_rows)} targets · {len(supply)} creator-supply · "
          f"{len(demand)} brand-demand")
    by_market = {}
    for r in supply:
        by_market[r["Market"]] = by_market.get(r["Market"], 0) + 1
    if by_market:
        print("  creator-supply demand by market: " +
              ", ".join(f"{k} {v}" for k, v in sorted(by_market.items(), key=lambda x: -x[1])))
    print(f"\n  Saved: {out}\n")


if __name__ == "__main__":
    main()
