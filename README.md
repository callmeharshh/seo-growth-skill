# seo-growth — a Claude skill

Point Claude at any domain. It audits the site's SEO and AI-search setup, tells
you the few things worth fixing in order, and writes the file that fixes them.

Built for the 8x assignment: one reusable thing that works on every domain instead
of a separate research process per site.

## Install (30 seconds)

```bash
git clone https://github.com/callmeharshh/seo-growth-skill.git
cp -r seo-growth-skill/seo-growth ~/.claude/skills/
```

That's it. Restart Claude Code and it's available.

To check it loaded:

```bash
ls ~/.claude/skills/seo-growth
```

No dependencies. No API keys. No signup. Python 3 and curl, which you already
have.

## Use it

Just ask Claude in plain English:

```
audit the SEO on www.8x.social
```

```
check 8x.social and find me the real German and Dutch keywords for "ugc creator"
```

```
audit sideshift.app and compare it to 8x.social
```

Or run the script directly:

```bash
cd ~/.claude/skills/seo-growth

# readable report
python3 scripts/audit.py www.8x.social --conversion /en/book-call --summary

# save it, and see what changed since last time
python3 scripts/audit.py www.8x.social --conversion /en/book-call --save

# the whole timeline for a domain
python3 scripts/audit.py www.8x.social --history

# a dashboard covering every domain you've saved
python3 scripts/audit.py --dashboard
```

## What it checks

| | |
|---|---|
| **404 handling** | Do URLs that don't exist actually return 404, or a fake 200? |
| **Redirects** | Every hop, and whether permanent moves are served as permanent |
| **Sitemap** | URL count, which locales exist, what sections the site has |
| **Translation coverage** | How many pages exist in *every* locale vs only some |
| **Schema** | FAQ, Article, Organization markup — the AI-citation surface |
| **On-page** | Titles, descriptions, H1/H2 structure, word counts, alt text |
| **Conversion** | Do content pages actually link to the thing you want people to do? |
| **Real keywords** | The actual query people type, per market, from Google autocomplete |
| **llms.txt** | The emerging convention for AI crawlers |

## How it's put together

```
seo-growth/
├── SKILL.md                  what Claude does with the results
├── scripts/audit.py          measures a domain, prints JSON
└── references/playbook.md    what each finding means + content templates
```

The split is the point: **the script measures, Claude judges.** Numbers can't be
argued with, and the advice isn't frozen into a scoring formula nobody can see
inside. Change your mind about what matters? Edit the playbook — no code change.

## The one non-obvious thing in here

Translating an SEO page is two different jobs.

**Body text** — machine translation is fine.
**The target keyword** — machine translation is *wrong*.

Germans don't search a translation of "what is a UGC creator". They search
`ugc creator werden` — the English loan word plus the German verb for "become".
Dutch is `worden`. Turkish is `nedir`. Polish is `co to`.

Translate the keyword literally and you've built a page targeting a phrase nobody
types. You pay for the translation and get nothing, and there's no obvious signal
telling you why.

So the skill **looks up** each market's real query instead of translating it. That
data comes from Google's own autocomplete — free, no key, and it only ever
suggests things people actually type.

## Tracking whether a fix actually worked

One audit tells you what's broken. Two tell you whether the thing you shipped
worked, which is the question that actually matters.

```bash
python3 scripts/audit.py site.com --save     # baseline
# ship a fix
python3 scripts/audit.py site.com --save     # prints what moved
```

```
Changed since 2026-07-31-2212:
  unknown URLs 404 correctly: False -> True
  temporary redirects: 4 -> 0 (-4)
  pages with FAQ schema: 3 -> 6 (+3)
  images missing alt text: 343 -> 120 (-223)
```

Runs are saved as dated JSON in `~/.seo-growth/<domain>/`. `--history` shows the
whole timeline.

## The dashboard

```bash
for d in 8x.social shortimize.com sideshift.app; do
  python3 scripts/audit.py "$d" --save
done
python3 scripts/audit.py --dashboard
```

Writes one self-contained HTML file — `~/.seo-growth/dashboard.html`. One row per
domain, side by side:

```
Domain               Status              404s  Temp     Translated  FAQ    Changed
                                              redirects    %       pages  since last
www.8x.social        2/6 checks passing   NO      4          8       3     no change
sideshift.app        3/6 checks passing   yes     0         n/a      0     no change
www.shortimize.com   4/6 checks passing   yes     0         n/a      1     no change
```

Under the table, a "what to fix" list per domain with the exact verification
command.

No server, no build step, no dependencies — it's a 4KB HTML file. Open it by
double-clicking, or drop it on any static host if you want it shared.

"Status" is deliberately dumb: how many of six checks are currently in a good
state. No weighting, no hidden formula — you can recount it from the row. A blank
cell means the check couldn't be measured, which is not the same as passing.

## Across a portfolio

Every domain is just an argument, so a loop covers all of them:

```bash
for d in site-one.com site-two.com site-three.com; do
  python3 scripts/audit.py "$d" --save --summary
done
```

Run it on competitors too — same checks, so comparisons are measured rather than
guessed.

## What it can't do

Worth being straight about the edges:

- **Autocomplete gives real queries but no search volume.** It reports "volume
  unknown" instead of making a number up.
- **Page weight and response time are not Core Web Vitals.** Vitals need a real
  browser — these are the document-level causes of bad vitals. Use PageSpeed
  Insights for the real thing.
- **It samples ~6 pages**, not the whole site. Sitemap-level facts are complete;
  page-level counts are "of the sample".
- **No backlink data.** That needs a paid API.

## Safety

Public URLs only, GET only, no cookies or credentials, honest User-Agent, and a
delay between requests so it never hammers a site. It reads and never writes
anything to the site it's auditing. Generated content is always a draft.

---

MIT. Built by Harsh, with AI assistance — which felt like the right way to build
a tool that's meant to be used from inside an AI coding agent.
