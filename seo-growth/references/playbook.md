# Playbook — what each finding means, and what to do about it

`audit.py` measures. This file is the judgement. Read the relevant section, then
tell the user what to fix and in what order.

**The rule that matters most:** never state something the audit didn't measure.
If a number isn't in the JSON, say you don't have it. A confident guess is worse
than a gap, because the user can't tell them apart.

---

## Priority order

Work down this list. Something high up makes everything below it unreliable, so
fixing in order isn't a preference — it's a dependency chain.

1. **Unknown URLs return 200 instead of 404** — breaks every other measurement
2. **Temporary redirects on permanent moves** — leaks ranking signal at the front door
3. **No FAQ schema** — the cheapest AI-search win available
4. **Translation gaps across locales** — languages competing instead of consolidating
5. **Target keyword barely used on its own page**
6. **Pages with no route to conversion**
7. **Page weight, missing alt text, caching** — real, but least urgent

---

## `soft_404: true` — unknown URLs return 200

**What it means.** Ask for a page that doesn't exist and the site says "200 OK"
instead of "404 Not Found". So `/tools`, `/glossary`, anything — they all *look*
like real pages.

**Why it's first.** Three separate problems in one bug:
- Search engines can index URLs that don't exist
- Crawl budget gets spent on empty pages instead of real ones
- Genuinely broken links fail silently, so nobody notices them

And practically: you can't trust any other audit result on a site where every URL
returns 200.

**The fix**, for Next.js App Router:

```tsx
// app/[locale]/not-found.tsx
export default function NotFound() {
  return (
    <main>
      <meta name="robots" content="noindex, follow" />
      <h1>Page not found</h1>
      <a href="/">Back to home</a>
    </main>
  );
}
```

That file alone isn't enough. The route has to *call* `notFound()`, or the
framework keeps rendering a 200:

```tsx
// app/[locale]/[...slug]/page.tsx
import { notFound } from "next/navigation";

export default async function Page({ params }) {
  const { locale, slug } = await params;
  const page = await getPage(locale, slug.join("/"));
  if (!page) notFound();   // <- this is the actual fix
  return <PageBody page={page} />;
}
```

Verify after deploying — all three must say 404:

```bash
curl -o /dev/null -s -w "%{http_code}\n" https://SITE/en/not-a-real-page
curl -o /dev/null -s -w "%{http_code}\n" https://SITE/zz
curl -o /dev/null -s -w "%{http_code}\n" https://SITE/en/blog/nope
```

---

## `entry_points` with `temporary_hops > 0`

**What it means.** A 301 or 308 says "moved permanently" and passes ranking
signal to the new URL. A 302 or 307 says "temporary" — so search engines keep the
old URL indexed and don't fully transfer signal.

Apex→www, root→default-locale, http→https are all *permanent* decisions. Serving
them as 307 tells Google they might be reversed.

**Also check `hops`.** More than one hop means an extra round trip on the very
first request a new visitor makes, and crawlers cap how many they'll follow.

**The fix.** In `next.config.ts`, `permanent: true` is the whole thing:

```ts
async redirects() {
  return [{ source: "/", destination: "/en", permanent: true }];
}
```

Host-level redirects (apex→www) are usually set in the hosting dashboard —
Vercel's Domains settings, or Cloudflare rules.

---

## `has_faq_schema: false` — no FAQ markup

**What it means.** No `FAQPage` structured data on the page.

**Why it's the best-value item.** AI search engines (ChatGPT, Perplexity, Google's
AI Overviews) quote *passages*, not pages. FAQ schema hands them a
question-and-answer pair already separated out, instead of making them guess
which part of the page answers the question. It also earns the "People also ask"
box in normal Google results.

This matters even more for a young domain: normal Google ranking rewards age and
backlinks, which a new site doesn't have yet. AI citations don't work that way —
a brand-new page can get cited immediately if the passage is clean. So this is
the surface a new site can actually win.

**The fix:**

```tsx
export function FaqSchema({ faqs }) {
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: faqs.map((f) => ({
      "@type": "Question",
      name: f.question,
      acceptedAnswer: { "@type": "Answer", text: f.answer },
    })),
  };
  return (
    <script type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }} />
  );
}
```

**One rule you must not break:** the questions and answers in the schema have to
be *visible on the page too*. Schema describing content a user can't see violates
Google's structured data policy and can earn a manual penalty. Render the FAQ,
then mark it up.

---

## `translation_complete_pct` well under 100

**What it means.** The site publishes N locales, but most pages only exist in
some of them. `slugs_in_every_locale` vs `unique_slugs` shows the gap.

**Why it matters.** hreflang is how you tell Google "this is the German version
of that English page." When the set is incomplete, the cluster is broken — so the
locale versions look like near-duplicates competing with each other rather than
one page in many languages. It's also the usual reason a site has far more
*discovered* pages than *indexed* ones.

**The fix.** Publish complete language sets, not partial ones. One page in 19
locales beats 19 pages in one locale each.

**And the part people get wrong** — see the keyword section below. Translating the
article is fine. Translating the *target keyword* is not.

---

## Target keyword barely appears on its own page

**What it means.** A page titled for a keyword that hardly uses it, and never in a
subheading. It reads as keyword-inserted rather than keyword-about.

**How to check.** Take the page's slug and title, work out what it's targeting,
then count. Rough bar: a 1,000-word article should use its main term maybe 5–10
times naturally, and at least one `<h2>` should contain it. Both Google and AI
engines read subheadings to work out what a page covers.

**The fix.** Rewrite the H2s to include the term where it fits naturally. Don't
stuff it — a page that repeats a phrase awkwardly reads as spam to readers and to
Google.

---

## `links_to_conversion: 0`

**What it means.** A page gets search traffic and offers no route to the thing the
business actually wants (book a call, sign up, start free).

**Why it matters.** Ranking a page that can't convert is a cost, not a win. This
is also the cheapest fix on the entire list — the content already exists, it just
needs a link. Bonus: internal links pass signal, so the conversion page benefits
from the pages actually earning traffic.

---

## `real_queries` — the per-locale keyword data

**What this data is.** Real queries from Google's autocomplete, per country and
language. Autocomplete only suggests things people actually type, so a suggestion
is evidence the query exists.

**What it is not.** Search volume. Autocomplete gives none. Never present these as
volume figures, and never invent a number to fill the gap. "Real query, volume
unknown" is the honest description.

**The insight to explain to the user.** Translating an SEO page is two different
jobs:

- **Body text** — machine translation is fine
- **The target keyword** — machine translation is *wrong*

Germans don't search a translation of "what is a UGC creator." They search
**`ugc creator werden`** — the English loan word plus the German verb for
"become". Dutch is **`worden`**. Turkish is **`nedir`**. Polish is **`co to`**.

Translate the keyword literally and you build a page targeting a phrase nobody
types. The translation costs money and earns nothing, and there's no obvious
signal telling you why.

So: **look up** each market's real query instead of translating it. That's what
`--seed` does.

**Watch for hijacked terms too.** In France, a bare `ugc` seed returns UGC Les
Halles and UGC Bercy — it's a cinema chain there. In India it returns the UGC NET
exam. If the suggestions for a market look unrelated to the business, say so: that
market needs a different seed term.

---

## `no_store: true` and page weight

**`cache-control: no-store`** tells every cache and CDN never to keep the
response, so each visit and each crawl re-renders from scratch. On marketing pages
the content is identical for everyone, so that cost buys nothing. Usually an
accidental framework default.

**`html_kb` over ~150** is a heavy document *before* images, fonts and scripts.
Delays first paint on slow connections.

**`images_missing_alt`** is an accessibility problem first and an image-search
one second.

**Be precise about what these are.** They are *not* Core Web Vitals. Vitals need a
real browser or Chrome field data; this script uses plain HTTP requests. These are
the document-level causes of poor vitals. If the user wants actual vitals numbers,
point them at PageSpeed Insights.

---

## Content templates

### Blog post skeleton

```markdown
---
title: "<title with the target keyword>"
description: "<under 155 chars, answers the query directly>"
slug: "<slug built from the local keyword>"
targetKeyword: "<the real query for this market>"
locale: "<locale>"
status: draft
---

# <Title>

> **<Two sentences, under 45 words, answering the question directly.>**

<!-- That blockquote is what an AI engine lifts when it cites you. Keep it
     answer-first — no preamble, no scene-setting. -->

## What <keyword> means in practice

<Definition, then one concrete example.>

### Where teams get <keyword> wrong

<One specific failure mode.>

## How to approach <keyword>

1. **<Step>** — <one sentence>
2. **<Step>** — <one sentence>
3. **<Step>** — <one sentence>

## How <brand> handles <keyword>

<What the product does. Then link to the conversion path.>

## Frequently asked questions

### How much does <topic> cost?
<40–60 words. Lead with a range. AI engines quote numbers.>

### How long until it works?
<Realistic timeline. Don't overclaim.>

### Do I need an agency for this?
<Honest answer, including when the answer is no.>

### How does this compare to doing it in-house?
<Name the real tradeoff. A one-sided answer reads as marketing and gets filtered.>
```

**Two things to hold the line on:**

1. **Keyword in at least one H2**, and used naturally through the body.
2. **The FAQ section is not optional.** It's the AI-citation surface, and it pairs
   with the schema component above.

### Comparison / alternative page

For "`<competitor>` alternative" queries — high commercial intent, and the play
every competitor already runs.

The section that makes it work: **"When `<competitor>` is the better choice."**
Answer it honestly. A comparison page with no genuine concession reads as
marketing, and AI engines increasingly discount those. The honest version is the
one that gets cited.

### Free tool

One narrow job, free, no signup, its own page. Requirements:

- **Server-render the answer.** If the output only appears after JavaScript runs,
  it can't be ranked or cited. This is why most SaaS tool pages are invisible.
- Its own H1 and a two-sentence explanation above the widget
- FAQ block with schema
- A link to the conversion path, placed right after the user gets their result

---

## Things to refuse

- **Don't write 100% AI-generated content at volume.** It gets filtered, and it
  risks the whole domain for a short-term gain. Generate the structure; leave the
  substance to a person.
- **Don't buy links.** The downside is permanent and asymmetric.
- **Don't put schema on the page describing content that isn't visible.** Policy
  violation.
- **Don't promise rankings.** SEO is slow and depends on things outside the site.
  Say what will improve and roughly when, not what position it'll reach.
