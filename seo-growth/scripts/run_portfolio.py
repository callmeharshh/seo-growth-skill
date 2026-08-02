#!/usr/bin/env python3
"""
Run the whole loop across every property in portfolio.json.

    python3 run_portfolio.py                 # everything
    python3 run_portfolio.py --only 8x.social
    python3 run_portfolio.py --skip-keywords  # audit + dashboard only, faster

For each property: audit it, save a dated snapshot, diff against the last run,
find winnable keywords, and write a content plan. Then rebuild the dashboard.

This is the file that makes it a system rather than a command you remember to
type. Put it on a weekly cron and the loop runs itself:

    0 9 * * 1  cd ~/.claude/skills/seo-growth && python3 scripts/run_portfolio.py

Output goes to ~/.seo-growth/<domain>/ as dated JSON, plus a content plan per
property. Nothing is published anywhere — it produces evidence and drafts.
"""

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


def load_portfolio():
    path = os.path.join(ROOT, "portfolio.json")
    with open(path) as f:
        data = json.load(f)
    return [p for p in data.get("properties", []) if p.get("domain")]


def run_property(prop, do_keywords=True):
    domain = prop["domain"]
    print(f"\n{'=' * 70}\n{domain}\n{'=' * 70}")

    # --- 1. audit + snapshot + diff -----------------------------------------
    print("Auditing...")
    previous = audit_mod.past_runs(domain)
    result = audit_mod.audit(
        domain,
        locales=None,
        seed=(prop.get("seeds") or [None])[0],
        conversion_path=prop.get("conversion_path", ""),
    )
    path = audit_mod.save_run(result)

    m = audit_mod.key_metrics(result)
    good = sum(1 for k, v in m.items() if v is True or (k == "temporary redirects" and v == 0))
    print(f"  saved {os.path.basename(path)}")
    for label, value in m.items():
        print(f"    {label:34} {value if value is not None else 'not measured'}")

    if previous:
        changed = audit_mod.compare(previous[-1][1], result)
        print(f"\n  Changed since {previous[-1][0]}:")
        print("\n".join(changed) if changed else "    nothing changed")
    else:
        print("\n  First run — baseline saved.")

    if result.get("notes"):
        print("\n  Worth fixing:")
        for n in result["notes"]:
            print(f"    - {n}")

    # --- 2. winnable keywords + content plan --------------------------------
    plan = None
    if do_keywords and prop.get("seeds"):
        print("\nFinding winnable keywords...")
        try:
            plan = kw_mod.research(
                domain,
                prop["seeds"],
                prop.get("competitors", []),
                locale=prop.get("default_locale", "en"),
                market=(prop.get("markets") or ["us"])[0],
                depth=int(os.environ.get("KEYWORD_DEPTH", "14")),
                limit=60,
                exclude=prop.get("exclude_terms", []),
            )
            t = plan["totals"]
            print(f"  {t['real_queries_found']} real queries · "
                  f"{t['gaps_competitor_covers_we_dont']} gaps · "
                  f"{t['open_nobody_covers']} uncontested")

            folder = os.path.join(OUT, domain)
            os.makedirs(folder, exist_ok=True)
            kp = os.path.join(folder, f"keywords-{time.strftime('%Y-%m-%d')}.json")
            with open(kp, "w") as f:
                json.dump(plan, f, indent=2, ensure_ascii=False)
            print(f"  saved {os.path.basename(kp)}")

            if plan.get("content_plan"):
                print("\n  Write these, in order:")
                for i, c in enumerate(plan["content_plan"][:5], 1):
                    print(f"    {i}. {c['primary_keyword']}")
                    print(f"       {c['cluster_size']} queries · {c['intent']}")
                    if c["competitor_pages"]:
                        print(f"       competitor has: {c['competitor_pages'][0]}")
        except Exception as e:
            print(f"  keyword research failed: {e}")

    return {"domain": domain, "audit": result, "keywords": plan}


def main():
    argv = sys.argv[1:]
    only = argv[argv.index("--only") + 1] if "--only" in argv else None
    do_keywords = "--skip-keywords" not in argv

    props = load_portfolio()
    if only:
        props = [p for p in props if only in p["domain"]]
    if not props:
        print("No matching properties in portfolio.json")
        sys.exit(1)

    started = time.time()
    print(f"Running {len(props)} propert{'y' if len(props) == 1 else 'ies'}")

    for prop in props:
        try:
            run_property(prop, do_keywords)
        except Exception as e:
            print(f"\n{prop['domain']} failed: {e}")

    print(f"\n{'=' * 70}")
    dash, err = audit_mod.build_dashboard()
    if dash:
        print(f"Dashboard: {dash}")
        print(f"Open it:   open {dash}")
    else:
        print(err)
    print(f"Done in {round(time.time() - started)}s\n")


if __name__ == "__main__":
    main()
