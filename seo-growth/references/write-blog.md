# Writing the post

Read this before writing. It's the difference between a draft that ships and one
that gets rewritten.

## The rule that matters most

**Write the finished post. Not an outline, not a template, no `[WRITE: …]`
markers.** Every heading gets real prose underneath it. If you leave placeholders,
the person has to do the work anyway and the tool did nothing.

The only thing you may leave blank is a specific number or client name you have no
source for — and when you do, say so inline: `[confirm: current creator count]`.
One or two of those in a post is fine. Twelve means you should have asked a
question first.

## Before writing, get these three things

1. **The target keyword** — from `keywords.py`, a cluster's `primary_keyword`.
2. **The cluster's other queries** — `also_answers`. The post should answer these
   too, because that's how one page covers a whole cluster instead of you writing
   four thin ones.
3. **What the business actually does** — read the homepage. A post about UGC that
   never says what the company sells converts nobody.

If the user just says "write a post about X", run `keywords.py` first. A post
aimed at a phrase nobody searches is wasted regardless of how good the writing is.

## The structure

````markdown
---
title: "<Title with the keyword in it, under 60 chars>"
description: "<Answers the query in under 155 chars>"
slug: "<keyword-as-slug>"
targetKeyword: "<the keyword>"
alsoTargets: ["<cluster query>", "<cluster query>"]
intent: "informational | commercial | tool | supply-side"
locale: "en"
status: "draft"
reviewRequired: true
---

# <Title>

> **<Two sentences. Answer the query directly, no preamble. Under 45 words.>**

<Then 2-3 sentences of real context. Why this matters to the reader, right now.>

## <H2 containing the keyword>

<150-250 words of actual prose. Concrete. One specific example.>

### <Sub-point as H3>

<100-150 words.>

## <H2 answering one of the cluster's other queries>

<150-250 words.>

## <H2 — the practical section: how to actually do it>

1. **<Step>** — <two or three sentences, specific enough to follow>
2. **<Step>** — <same>
3. **<Step>** — <same>

## How <company> helps

<80-120 words. What the product does, plainly. Then a link:
[<natural anchor text>](/en/book-call)>

## Frequently asked questions

### <Question from the cluster, verbatim if possible>

<40-70 words. Lead with the direct answer, then qualify.>

### <Question>

<40-70 words.>

### <Question>

<40-70 words.>

### <Question>

<40-70 words.>
````

## Non-negotiables

These are what `check_post.py` enforces, and they're not stylistic preferences —
each one is a specific reason posts fail:

- **Keyword in the title, the slug, and at least one H2.** Missing it from the H2s
  is the single most common defect. It's what makes a post read as
  keyword-inserted rather than keyword-about.
- **Keyword roughly once per 250 words.** Naturally. If you can't fit it in
  without the sentence sounding wrong, the sentence is wrong — rewrite it, don't
  jam the keyword in.
- **The blockquote at the top is mandatory.** That's the passage an AI engine
  lifts when it cites you. No preamble, no "in today's fast-moving landscape".
  Answer the question in the first sentence.
- **At least 3 H2s and 1 H3.** Flat structure gives an answer engine no passage
  boundaries to quote.
- **At least 4 FAQ questions**, each an H3 ending in a question mark. Phrase them
  as real people phrase them — use the cluster's actual queries.
- **One internal link to the conversion path.**
- **700+ words.** Not padding — that's roughly what it takes to cover a cluster.

## Voice

Write like a person explaining something to a colleague. Specifically:

- Short sentences. Vary the length.
- Say the thing, then qualify it. Not the other way round.
- Concrete over abstract. "50 accounts posting daily" beats "a scaled approach".
- No "in today's digital landscape", "it's no secret that", "unlock the power of",
  "game-changer", "delve into", "navigate the complexities".
- Contractions are fine. This isn't a legal document.
- Don't hedge every claim. One "usually" per paragraph, maximum.

## Things you must not do

- **Don't invent statistics.** No "73% of marketers say…" unless you have the
  source. Made-up numbers are the fastest way to destroy trust in the whole post.
- **Don't invent client names, results, or earnings figures.** If the business has
  case studies, use those. Otherwise write around it.
- **Don't promise rankings or income.** "Creators typically earn X" needs a source.
- **Don't write about competitors inaccurately.** If you mention one, only say
  what's on their public site.

## After writing

Always run the checker and show the output:

```bash
python3 scripts/check_post.py <file> 
```

If it fails, fix it and run again. Don't hand over a post that fails its own
check — that's the same mistake as handing over an audit with made-up numbers.

Then tell the user:
- where the file should live in their repo
- which cluster queries it targets
- anything you marked `[confirm: …]` that needs a human
