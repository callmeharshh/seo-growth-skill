---
name: seo-growth
description: Audit any public website's SEO and AI-search setup, then generate the fix. Point it at a domain and it checks 404 handling, redirects, sitemap and translation coverage, FAQ/schema markup, keyword usage, conversion links, and finds real per-market search queries via Google autocomplete. Use when someone says "audit this domain", "check the SEO on X", "why isn't this site ranking", "find keywords for X", "write an SEO post about X", or asks about AEO/GEO/AI search visibility. Works on any number of domains — nothing is hardcoded to one site.
version: 1.0.0
author: Harsh
license: MIT
platforms: [macos, linux]
---

# SEO Growth

Point this at a domain. It measures what's actually there, tells you the few
things worth fixing in order, and writes the file that fixes them.

Built around one split: **the script measures, you judge.** `audit.py` only
reports numbers. `references/playbook.md` holds what those numbers mean. That way
the facts can't be argued with, and the advice isn't frozen into a scoring
formula nobody can inspect.

## How to run it

```bash
python3 scripts/audit.py <domain> [--conversion /path] [--seed "keyword"] [--locales en,de,fr]
```

Real example:

```bash
python3 scripts/audit.py www.8x.social --conversion /en/book-call --seed "ugc creator"
```

No dependencies, no API keys, no install. Python 3 and curl, both already on any
mac or linux.

| Flag | What it does |
|---|---|
| `--conversion` | The path that counts as converting (`/en/book-call`). Checks whether pages actually link to it. |
| `--seed` | A short head term (`ugc creator`, not `best ugc creator platform 2026`). Finds the real query in every market. Short seeds return native phrasing; long ones return English long-tails. |
| `--locales` | Limit which locales to check. Defaults to whatever the sitemap has. |
| `--summary` | Human-readable output instead of JSON. Use when the person wants to read it themselves. |
| `--save` | Save the run, and print what changed since the last one. This is the loop. |
| `--history` | Show every saved run for a domain and the change between the last two. No network. |
| `--dashboard` | Build one HTML file covering every saved domain. No domain argument needed. |

## What to do with the output

**1. Run the audit.** If the user gave you a domain and nothing else, just run it —
don't interrogate them first. Guess `--conversion` from the site if it's obvious
(`/book-call`, `/signup`, `/pricing`, `/demo`) and say what you guessed.

**2. Read `references/playbook.md`.** It has a priority order and it's a
dependency chain, not a preference. Soft-404s make every other number unreliable,
so that goes first regardless of what else you found.

**3. Report the 3–5 things that matter.** Not everything. For each one:

- what's wrong, in one sentence
- why it costs them something
- the command or file that fixes it

Every claim has to trace to a number in the JSON. If it's not measured, say you
don't have it. **Do not fill gaps with plausible-sounding figures** — the user
can't tell your guess from your measurement, so a guess poisons the whole report.

**4. Offer to generate the fix.** Not a description of the fix — the file, with
the path it belongs at. Templates are in the playbook. This is the point of the
skill: they asked for an audit, they get a file they can commit.

**5. If they want content in more than one language**, use the `real_queries`
data. Read the keyword section of the playbook first — translating the target
keyword is the mistake this skill exists to prevent.

**6. If they ask "what else should we do?"** rather than "what's broken?", they've
moved past repair work. The playbook's *Bigger plays* section covers that: filling
gaps in existing content, comparison pages, free tools, templated pages, off-site
citations, brand-name defence. Suggest in that order — each is cheaper than the
next.

**7. If they want to see it rather than read it**, run `--dashboard`. It writes a
single self-contained HTML file covering every domain that's been saved, with one
row each and a "changed since last run" column. No server, no build — they open
the file. Tell them the path.

**8. Always suggest `--save` on the first run.** A single audit says what's broken.
Two audits say whether the fix worked, which is the question that actually
matters. One run is a baseline; the value shows up on the second.

## Talking about the numbers honestly

The audit fetches public pages over plain HTTP. That bounds what it can know, and
the boundaries matter:

- **Autocomplete gives real queries, never volume.** Say "real query, volume
  unknown". Never a number.
- **Page weight and response time are not Core Web Vitals.** Vitals need a real
  browser. These are the document-level causes of bad vitals. Point at PageSpeed
  Insights for actual vitals.
- **It samples about 6 pages, not the whole site.** Page-level counts are "of the
  sample". Sitemap-level facts (URL count, locale coverage) are complete.
- **Backlinks aren't measured at all.** That needs a paid API.

## Constraints

Public URLs only. GET only. No cookies or credentials sent, an honest
User-Agent, and a delay between requests so it never hammers a site. It reads;
it never changes anything.

Nothing gets published automatically. Generated files are drafts — say so, and
say what a human still needs to check.

## Running it across a portfolio

Every domain is just an argument, so a loop is the whole feature:

```bash
for d in site-one.com site-two.com site-three.com; do
  python3 scripts/audit.py "$d" > "audit-$d.json"
done
```

Two things that get genuinely useful at that point:

**Track it over time.** That's what `--save` is for:

```bash
python3 scripts/audit.py site.com --save          # baseline
# ...ship a fix...
python3 scripts/audit.py site.com --save          # prints what changed
python3 scripts/audit.py site.com --history       # the whole timeline
```

Runs are stored as dated JSON in `~/.seo-growth/<domain>/`. The interesting
question isn't "what's our score" — it's "what changed since we shipped that fix,
and did it work?"

**See the whole portfolio at once.**

```bash
for d in site-one.com site-two.com site-three.com; do
  python3 scripts/audit.py "$d" --save
done
python3 scripts/audit.py --dashboard   # -> ~/.seo-growth/dashboard.html
```

One row per domain, side by side, with what changed since the last run. It's a
plain HTML file, so it opens locally or drops onto any static host.

**Run it on competitors too.** Same script, same checks, so "they're better at
this" becomes a measured difference instead of a hunch. It also shows what a
healthy site in your space looks like, which is a better target than a generic
best practice.
