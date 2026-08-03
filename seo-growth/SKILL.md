---
name: seo-growth
description: A search-growth system for a portfolio of websites. Finds keywords you can actually win by diffing your sitemap against competitors' sitemaps, per market and per language. Writes complete publishable blog posts, generates deployable free-tool pages, builds the shared target list (Domain/Market/Audience/Query/Intent/Evidence/Asset/Priority/Status), audits technical SEO and AI-search readiness, tracks every metric over time so you can tell whether a fix worked, and builds a dashboard across all your domains. Use when someone says "find keywords for X", "write an SEO blog post", "what should we write next", "audit this domain", "why isn't this ranking", "track our SEO", or asks about a content plan, keyword gaps, AEO or GEO. Configured per property in portfolio.json — adding a domain is a config entry, not new code.
version: 3.0.0
author: Harsh
license: MIT
platforms: [macos, linux]
---

# SEO Growth

A loop, not a report:

```
find winnable keywords  ->  write the post  ->  check it  ->  ship
        ^                                                      |
        |                                                      v
   track what moved  <-  audit  <-  save a dated snapshot  <----
```

Everything is driven by `portfolio.json`. Adding a domain is an entry in that
file; nothing else changes. No dependencies, no API keys — Python 3 and curl.

## What it does

| Want | Run |
|---|---|
| Keywords we can win + a content plan | `python3 scripts/keywords.py --domain D --seeds "..." --competitors A,B` |
| A finished blog post | you write it — read `references/write-blog.md` first |
| Grade a post before it ships | `python3 scripts/check_post.py post.md` |
| What's technically broken | `python3 scripts/audit.py D --summary` |
| The whole portfolio, every step | `python3 scripts/run_portfolio.py` |
| The shared target list, per market | `python3 scripts/target_list.py --markets --csv targets.csv` |
| Build a free-tool page | `python3 scripts/make_tool.py --all-markets --out out/` |
| Dashboard across all domains | `python3 scripts/audit.py --dashboard` |

`run_portfolio.py` is the one to reach for by default. It audits every property,
saves a dated snapshot, diffs against last time, finds winnable keywords, writes a
content plan, and rebuilds the dashboard. Put it on a weekly cron and the loop runs
itself.

---

## 1. Finding keywords you can win

```bash
python3 scripts/keywords.py --domain www.8x.social \
  --seeds "ugc creator,ugc marketing" \
  --competitors sideshift.app,www.shortimize.com
```

**How "winnable" is decided.** Not by a guessed difficulty number. By three things
that are free and observable:

1. **Is the query real?** Google autocomplete only suggests what people actually
   type. Expanding a seed across the alphabet turns one seed into 200-350 confirmed
   queries — that's where the winnable long tail lives.
2. **Do we already cover it?** Matched against our sitemap. If yes, it's an audit
   item, not an opportunity.
3. **Has a competitor proven it?** Matched against their sitemaps. A competitor
   built a page for it and we have nothing → demand is proven and the gap is ours.
   **This is the strongest free signal there is.**

The output is a `content_plan`: clustered, one page per cluster, with the head term
as the primary keyword and the cluster's other queries as things that page should
also answer. Write one page per cluster, not one per query.

Watch for `is_category: true`. That means many queries matched one competitor page,
so it's a whole topic area rather than a single post — split it.

**Seed length matters.** Use short head terms (`ugc creator`, not `best ugc creator
platform 2026`). Long seeds return English long-tails; short ones return the real
phrasing, including in other languages.

## 2. Writing the post

**Read `references/write-blog.md` before writing.** The short version:

- Write the **finished post**. Real prose under every heading. No `[WRITE: …]`
  placeholders — if you leave them, the tool did nothing.
- Target the whole cluster, not just the primary keyword.
- Keyword in the title, the slug, and at least one H2. Roughly once per 250 words.
- Open with a blockquote that answers the query in under 45 words. That's the block
  an AI engine lifts when it cites you.
- 4+ FAQ questions as H3s ending in `?`, using the cluster's real queries.
- One internal link to the conversion path.
- **Never invent statistics, client names, or earnings figures.** Mark anything you
  can't source as `[confirm: …]`.

`examples/ugc-creator-jobs.md` in this repo is a real one that passes all 14 checks.

## 3. Checking it

```bash
python3 scripts/check_post.py draft.md
```

Always run this and show the output. It exits 1 on a blocking failure, so it works
in a pre-commit hook.

The reason this is a separate script rather than you self-assessing: a model asked
to write *and* grade its own work will say the work is fine. A script that counts
words has no such problem. Don't hand over a post that fails its own check.

## 4. Auditing and tracking

```bash
python3 scripts/audit.py www.8x.social --conversion /en/book-call --summary
python3 scripts/audit.py www.8x.social --save      # baseline, then diff next time
python3 scripts/audit.py www.8x.social --history   # the timeline
python3 scripts/audit.py --dashboard               # all domains, one HTML file
```

Checks 404 handling, redirect chains and whether permanent moves are served as
permanent, sitemap and per-locale translation coverage, FAQ/Article/Organization
schema, on-page structure, conversion links, and `llms.txt`.

**Always suggest `--save`.** One audit says what's broken. Two say whether the fix
worked, which is the question that matters. `run_portfolio.py` does this for every
property automatically.

Fix in the order `references/playbook.md` gives — it's a dependency chain, not a
preference. Soft-404s make every other number unreliable, so that goes first.

---

## 5. The target list, and why it runs per market

```bash
python3 scripts/target_list.py --markets --csv targets.csv
```

Outputs exactly the nine columns the brief specifies: Domain, Market, Audience,
Query/topic, Intent, Evidence, Recommended asset, Priority, Status.

Two of those are **Market** and **Audience**, which is why this runs per market
rather than once per domain. The same seed returns a different audience in each
country. On 8x.social: in the US "ugc creator" is category research; in Germany,
Brazil and Turkey it is overwhelmingly people looking for the work — *werden*,
*vagas*, *iş ilanları*. Same domain, same seed, different audience, different
asset, different conversion path. A single-market run reports none of it.

For a two-sided marketplace that distinction decides the page: supply-side queries
route to creator signup, demand-side to the sales conversion.

## 6. Free tools

```bash
python3 scripts/make_tool.py --all-markets --out out/tools
```

Writes a real, deployable, self-contained HTML page per market. The answer is
rendered in the HTML before JavaScript runs — a tool whose output only appears
after JS cannot be ranked or cited, and that is why most SaaS tool pages are
invisible. Ships with FAQPage + WebApplication schema and a conversion link.

**It verifies the target keyword against autocomplete first and refuses to build a
page for a keyword nobody searches.** That guard exists because a Turkish
calculator was drafted around a keyword that turned out not to be real. Turkey
wants an explainer, not a calculator — different market, different asset.

## How to actually use this in conversation

**"What should we write next?"** → `run_portfolio.py`, then read the content plan,
then offer to write the top cluster. Don't stop at the list; the list is not the
deliverable.

**"Write a post about X"** → run `keywords.py` first. A post aimed at a phrase
nobody searches is wasted no matter how well written. If X turns out to be already
covered, say so and offer the nearest gap instead.

**"Audit this site"** → `audit.py --summary`, report the 3-5 things that matter in
priority order, each with the command that verifies it, then offer to generate the
fix.

**Anything about a portfolio, or more than one domain** → `run_portfolio.py` and the
dashboard.

## Being honest about the numbers

The hard boundaries, and they matter more than the features:

- **No search volume. Ever.** Autocomplete proves a query is real, not how big it
  is. Say "volume unknown". Never a number.
- **Coverage matching is token overlap on URL paths.** Good enough to find gaps,
  not a substitute for looking. Spot-check the competitor page before writing.
- **Page weight and response time are not Core Web Vitals.** Vitals need a real
  browser. These are the document-level causes.
- **`audit.py` samples ~6 pages.** Page-level counts are "of the sample". Sitemap
  facts are complete.
- **No backlink data.** Needs a paid API.

If a number isn't in the output, say you don't have it. A guess the user can't
distinguish from a measurement poisons everything else in the report.

## Constraints

Public URLs only, GET only, no cookies or credentials, honest User-Agent, delay
between requests. It reads; it never changes a site it's auditing.

Nothing publishes automatically. Every generated post is a draft with
`reviewRequired: true`, and you say what a human still needs to confirm.
