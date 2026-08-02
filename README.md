# seo-growth — a search-growth system as a Claude skill

Finds keywords you can actually win, writes the post, checks it, tracks whether it
worked. Across every domain you own.

Not an audit tool. The audit is one of four steps.

## The loop

```
find winnable keywords  ->  write the post  ->  check it  ->  ship
        ^                                                      |
        |                                                      v
   track what moved  <-  audit  <-  save a dated snapshot  <----
```

## Install

```bash
git clone https://github.com/callmeharshh/seo-growth-skill.git
cp -r seo-growth-skill/seo-growth ~/.claude/skills/
```

No dependencies. No API keys. Python 3 and curl. Restart Claude Code and ask it
"what should we write next for 8x.social".

## One command for the whole portfolio

```bash
python3 scripts/run_portfolio.py
```

For every property in `portfolio.json`: audit it, save a dated snapshot, diff
against last run, find winnable keywords, write a content plan, rebuild the
dashboard. On a weekly cron the loop runs itself:

```
0 9 * * 1  cd ~/.claude/skills/seo-growth && python3 scripts/run_portfolio.py
```

Adding your 11th domain is an entry in `portfolio.json`. Nothing else changes.

## The interesting part: how "winnable" is decided

Not with a guessed difficulty score. With three things that are free and
observable:

1. **Is the query real?** Google autocomplete only suggests what people actually
   type. Expanding one seed across the alphabet returns 200-350 confirmed queries.
2. **Do we already cover it?** Matched against your sitemap.
3. **Has a competitor proven it?** Matched against theirs. **A competitor built a
   page for it and you have none** — that is the strongest free signal available.

Real output for 8x.social, in 50 seconds:

```
260 real queries · 88 gaps · 128 uncontested · 44 already covered

CONTENT PLAN — one page per cluster, highest-leverage first
  1. ugc creator jobs   [110]
     supply-side · 6 queries in this cluster
     also answers: ugc creator jobs for beginners, ugc creator jobs no experience,
                   ugc creator jobs remote, ugc creator jobs nz
     competitor has: www.shortimize.com/blog/ugc-creator-jobs
```

Clustered, so you write one page per topic rather than six thin ones. The head term
is found by containment — "ugc creator jobs" is inside "ugc creator jobs uk", so it
is obviously the topic.

## It writes the whole post

Claude writes it, following `references/write-blog.md`. Complete prose, no
`[WRITE: …]` placeholders. `examples/ugc-creator-jobs.md` is a real one: 1,142
words, targets the full cluster, and passes every check.

Then a script grades it:

```bash
python3 scripts/check_post.py examples/ugc-creator-jobs.md
```

```
1142 words · target keyword "ugc creator jobs" used 14x · 6 H2s / 7 H3s
  [PASS] Keyword in at least one H2
  [PASS] Answer-first opening
  [PASS] FAQ section
  ...
  14/14 checks passed — ready to publish.
```

That split is deliberate. A model asked to write *and* grade its own work will tell
you the work is fine. A script that counts words won't. It exits 1 on failure, so it
drops into a pre-commit hook.

## Tracking whether a fix worked

```bash
python3 scripts/audit.py site.com --save   # baseline
# ship a fix
python3 scripts/audit.py site.com --save   # prints what moved
```

```
Changed since 2026-08-02-1947:
  unknown URLs 404 correctly: False -> True
  temporary redirects: 4 -> 0 (-4)
  pages with FAQ schema: 3 -> 6 (+3)
```

`--dashboard` writes one self-contained 5KB HTML file covering every domain, with a
filter and a "changed since last run" column.

## What it found on 8x.social

- unknown URLs return 200 instead of 404, so `/en/tools` and `/llms.txt` look real
  and aren't
- 18 of 219 pages exist in all 19 locales — about 8%
- apex to www to /en is two redirects, both 307 rather than 301
- FAQ schema on some pages, not others
- 343 images with no alt text

## Files

```
seo-growth/
├── SKILL.md                    what Claude does with each command
├── portfolio.json              your domains, competitors, seed topics
├── scripts/
│   ├── keywords.py             winnable keywords + content plan
│   ├── check_post.py           grades a post, exits 1 on failure
│   ├── audit.py                technical + AI-search audit, snapshots, dashboard
│   └── run_portfolio.py        the whole loop across every property
├── references/
│   ├── write-blog.md           how to write a post that passes
│   └── playbook.md             what each finding means, and the bigger plays
└── examples/
    └── ugc-creator-jobs.md     a real post, 14/14 checks
```

## What it can't do

- **No search volume.** Autocomplete proves a query is real, not how big it is. It
  reports "volume unknown" rather than inventing a number.
- **Coverage matching is token overlap on URL paths.** Good enough to find gaps, not
  a substitute for opening the competitor page. Spot-check before writing.
- **Speed numbers are document weight and response time, not Core Web Vitals.**
  Vitals need a real browser.
- **No backlink data.** Needs a paid API.

## Safety

Public URLs only, GET only, no credentials, honest User-Agent, delay between
requests. Reads only. Every generated post is a draft marked `reviewRequired: true`.

---

MIT. Built by Harsh, with AI assistance — which felt right for a tool meant to run
inside an AI coding agent.
