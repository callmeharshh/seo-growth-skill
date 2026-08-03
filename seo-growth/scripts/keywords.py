#!/usr/bin/env python3
"""
Find keywords you can actually win, and say why each one is winnable.

    python3 keywords.py --domain www.8x.social \\
        --seeds "ugc creator,ugc marketing" \\
        --competitors www.shortimize.com,sideshift.app

"Winnable" is the whole point. A list of high-volume keywords is useless if you
have no chance at them. So instead of guessing difficulty, this measures three
things that are free and observable:

  1. IS IT REAL?     Google autocomplete only suggests queries people actually
                     type. Expanding a seed across the alphabet turns one seed
                     into ~200 confirmed real queries, most of them long-tail.

  2. DO WE COVER IT? Match the query against our own sitemap. If we already have
                     a page, it's not an opportunity — it's an audit item.

  3. HAS A COMPETITOR PROVEN IT? Match the query against competitors' sitemaps.
                     If a competitor built a page for it and we have nothing,
                     that is the strongest free signal there is: someone in this
                     exact niche decided the query was worth a page.

The best keywords are the ones a competitor covers and we don't. Second best are
specific long-tail queries nobody has taken. That ranking needs no paid API and
no invented volume numbers.

What this deliberately does NOT do: report search volume. Autocomplete doesn't
provide it, so every row says so rather than carrying a number I made up.
"""

import json
import re
import sys
import time
from urllib.parse import quote, urlparse

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from audit import get, DELAY  # reuse the polite curl-based fetcher

ALPHABET = "abcdefghijklmnopqrstuvwxyz"

# Words that carry no topic meaning when matching a query to a URL.
STOP = {
    "a", "an", "the", "of", "for", "to", "in", "on", "is", "are", "and", "or",
    "what", "how", "why", "when", "which", "who", "do", "does", "can", "my",
    "your", "with", "vs", "best", "top", "free", "you", "it", "that", "this",
}


def tokens(text):
    """
    Topic words only, lowercased.

    Splits on non-word characters with the Unicode flag on. The ASCII-only
    version silently shredded every accented query — "iş ilanları" became
    fragments, "schöck" became "sch" and "ck" — which broke coverage matching and
    named-entity detection in exactly the non-English markets this is for.
    """
    return {
        w for w in re.split(r"[^\w]+", text.lower(), flags=re.UNICODE)
        if w and w not in STOP and len(w) > 2 and not w.isdigit()
    }


# Autocomplete returns everything that shares a string with your seed, including
# queries about completely different subjects. "UGC" is the University Grants
# Commission in India and a Roblox feature; "ugc full form" is people looking up
# an acronym, not buying anything. Left in, these dominate the results and make
# the whole list look untrustworthy — the first run of this put "user generated
# content and web 2.0" at the top, which is an academic phrase, not a business
# query.
IRRELEVANT = [
    # different organisation entirely
    "ugc net", "ugc care", "ugc approved", "ugc exam", "ugc syllabus",
    "ugc admit", "ugc result", "ugc equivalence", "ugc guidelines", "ugc college",
    "ugc university", "ugc scholarship", "ugc phd", "ugc professor",
    # acronym lookups, not commercial intent
    "full form", "kya hai", "kya hota", "meaning in hindi", "meaning in marathi",
    "meaning in tamil", "meaning in urdu", "abbreviation", "stands for",
    # different domain entirely — "creator platform" pulls in game modding
    "roblox", "web 2.0", "web 3.0", "minecraft", "cinema", "les halles",
    "fallout", "skyrim", "creation kit", "steam workshop", "nexus mods",
    "unreal", "unity asset",
    # not a business audience
    "bio for instagram", "bio ideas", "username ideas", "account name ideas",
    "captions for", "aesthetic",
]


def is_relevant(query, exclude=()):
    q = query.lower()
    if any(bad in q for bad in IRRELEVANT):
        return False
    if any(bad.lower() in q for bad in exclude):
        return False
    return True


def pick_primary(queries):
    """
    Choose the head term of a cluster.

    The right signal is containment. "ugc creator jobs" appears inside "ugc
    creator jobs uk", "ugc creator jobs nz" and "ugc creator jobs remote", so it
    is obviously the topic and the others are variants of it.

    Scoring by length or by points both got this wrong: they picked "ugc creator
    jobs nz" as the topic and listed the actual head term as a variant, which
    would have someone write a page about New Zealand.
    """
    lowered = [q.lower() for q in queries]

    def contained_in_others(i):
        q = lowered[i]
        return sum(1 for j, other in enumerate(lowered) if j != i and q in other)

    # Most-contained wins; ties go to the shorter phrase.
    best = max(
        range(len(queries)),
        key=lambda i: (contained_in_others(i), -len(lowered[i].split())),
    )
    return queries[best]


# ---------------------------------------------------------------------------
# 1. Discover real queries
# ---------------------------------------------------------------------------

def suggest(seed, locale="en", market="us"):
    url = (
        "https://suggestqueries.google.com/complete/search?client=firefox"
        f"&hl={locale}&gl={market}&ie=UTF-8&oe=UTF-8&q={quote(seed)}"
    )
    _, _, body = get(url, timeout=12)
    try:
        data = json.loads(body)
        return [s for s in data[1] if isinstance(s, str)]
    except Exception:
        return []


# Autocomplete sometimes returns queries prefixed with invisible characters
# (word joiner U+2060, zero-width space, BOM). They survive into slugs and make
# a query look duplicated. Strip them at the source.
INVISIBLE = dict.fromkeys(
    [0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF, 0x00AD, 0x200E, 0x200F], None
)


def clean_query(q):
    return q.translate(INVISIBLE).strip()


def discover(seed, locale="en", market="us", depth=26):
    """
    Expand one seed into many real queries.

    Asking for "ugc creator" returns ~10 suggestions. Asking for "ugc creator a",
    "ugc creator b" and so on returns a different ten each time. 26 cheap calls
    turn one seed into a couple of hundred confirmed queries, which is where the
    winnable long-tail actually lives.
    """
    found = {}
    probes = [seed] + [f"{seed} {c}" for c in ALPHABET[:depth]]

    for probe in probes:
        for s in suggest(probe, locale, market):
            s = clean_query(s)
            key = s.lower().strip()
            if key and key not in found:
                found[key] = s

    return list(found.values())


# ---------------------------------------------------------------------------
# 2. What does a site already cover?
# ---------------------------------------------------------------------------

def site_paths(domain):
    """Every URL path in a domain's sitemap. Empty list if there isn't one."""
    _, _, robots = get(f"https://{domain}/robots.txt", timeout=15)
    sitemaps = re.findall(r"(?im)^sitemap:\s*(\S+)", robots) or [
        f"https://{domain}/sitemap.xml"
    ]

    paths, xml = [], ""
    for sm in sitemaps[:3]:
        _, _, body = get(sm, timeout=30)
        if "<sitemapindex" in body.lower():
            children = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body)[:20]
            for child in children:
                _, _, c = get(child, timeout=30)
                xml += c
        else:
            xml += body

    for u in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml):
        try:
            paths.append(urlparse(u).path)
        except Exception:
            continue
    return paths


def covers(query, path_tokens_list, threshold=0.75):
    """
    Does any page on this site look like it targets this query?

    Compares the query's topic words against each URL path's words. 0.75 means
    three quarters of the meaningful words must appear in one path — strict
    enough that a vaguely related post doesn't count as coverage.
    """
    q = tokens(query)
    if not q:
        return None
    for path_tokens, path in path_tokens_list:
        if len(q & path_tokens) / len(q) >= threshold:
            return path
    return None


# ---------------------------------------------------------------------------
# 3. Score winnability
# ---------------------------------------------------------------------------

# Words distinctive to exactly one language. Used to confirm a query belongs to
# the target market and — more importantly — to reject one that belongs to a
# different market. Google's es-MX autocomplete returns Portuguese and de-DE
# returns Italian, so without this "ugc creator como começar" was reported as a
# Spanish opportunity and "ugc creator cos è" as a German one.
EXCLUSIVE_TO = {
    "pt": ["começar", "ganhar", "vagas", "confiável", "quanto", "trabalhar", "ganha"],
    "it": ["cos", "diventare", "guadagna", "significato"],
    "de": ["werden", "gesucht", "verdienst", "verdienen", "aufträge", "bedeutung",
           "erklärung", "wieviel"],
    "tr": ["nedir", "olunur", "ilanları", "maaş", "nasıl"],
    "es": ["trabajo", "empleo", "cuánto", "cuanto", "sueldo", "gana"],
    "fr": ["devenir", "salaire", "combien"],
    "nl": ["worden", "hoeveel", "wat"],
    "pl": ["praca", "zostać", "ile"],
    "id": ["adalah", "gaji", "cara"],
    "hi": ["kaise", "bane"],
}

# Reverse index: word -> the language it belongs to.
_WORD_LANG = {w: lang for lang, words in EXCLUSIVE_TO.items() for w in words}


def query_language(query):
    """The language a query's distinctive words point at, or None."""
    words = set(re.split(r"[^\w]+", query.lower(), flags=re.UNICODE))
    hits = {_WORD_LANG[w] for w in words if w in _WORD_LANG}
    return hits.pop() if len(hits) == 1 else None


def is_localised(query, locale):
    """
    Is this query in the local language of this market?

    Order matters here. An earlier version checked for non-ASCII characters first
    and returned True immediately, so "começar" (Portuguese) counted as Spanish
    purely because of the cedilla. The foreign-language rejection has to run
    before any character-set shortcut.
    """
    if locale in ("en", ""):
        return False

    lang = query_language(query)
    if lang and lang != locale:
        return False          # belongs to a different market entirely
    if lang == locale:
        return True           # distinctive local word, confirmed

    # No distinctive word either way. Non-Latin characters are then a reasonable
    # signal the query is not English.
    return bool(re.search(r"[^\x00-\x7F]", query))


def score(query, our_page, competitor_pages, locale="en"):
    """
    Rank by how winnable the query is, and record the reason in words.

    The reason matters as much as the number. A score with no explanation is a
    number nobody can argue with, which means nobody will trust it.

    One case needs care. Competitor coverage is normally the strongest signal —
    someone in the niche decided the query was worth a page. But in a non-English
    market that logic inverts: the competitors here are English-language sites, so
    they will never have a page for "ugc creator werden" no matter how much demand
    exists. Scoring that as "unproven" buries exactly the queries a multi-locale
    site is best placed to win. Demand is already proven by autocomplete; the
    absence of a competitor means the market is open, not empty.
    """
    words = len([w for w in query.split() if w])
    specific = min(words, 6)  # longer queries are less contested
    localised = is_localised(query, locale)

    if our_page:
        return {
            "verdict": "already covered",
            "points": 0,
            "why": f"We already have a page targeting this: {our_page}",
            "action": "improve the existing page rather than writing a new one",
        }

    if competitor_pages:
        who = ", ".join(f"{d} ({p})" for d, p in competitor_pages[:2])
        return {
            # Strongest signal available for free: a competitor in this exact
            # niche decided the query was worth building a page for, and we have
            # nothing. Demand is proven and the gap is ours.
            "verdict": "GAP — competitor covers it, we don't",
            "points": 70 + specific * 5 + len(competitor_pages) * 5,
            "why": f"Real query. Not covered by us. Covered by {who}.",
            "action": "write this one first",
        }

    if localised:
        return {
            "verdict": "LOCAL GAP — real local-language query, no competitor serves it",
            "points": 80 + specific * 5,
            "why": (
                f"Real query in the local language ({locale}). We have no page. The "
                f"competitors checked are English-language sites, so they will not "
                f"compete here — demand is proven, the market is open."
            ),
            "action": "write this in the local language; highest-leverage of all",
        }

    return {
        "verdict": "open — nobody covers it",
        "points": 30 + specific * 6,
        "why": "Real query. No page on our site, none found on the competitors checked.",
        "action": "uncontested long tail; cheap to take, verify it's on-topic first",
    }


def intent_of(query):
    q = query.lower()
    if re.search(r"\b(alternative|vs|versus|review|pricing|cost|price|best|top)\b", q):
        return "commercial"
    if re.search(r"\b(calculator|generator|template|tool|checker|download|free)\b", q):
        return "tool"
    if re.search(r"\b(job|jobs|salary|apply|hiring|career|werden|worden|praca|vagas)\b", q):
        return "supply-side (people wanting the work)"
    if re.match(r"^(what|how|why|when|which|who)\b", q):
        return "informational"
    return "informational"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def research(domain, seeds, competitors, locale="en", market="us", depth=26,
             limit=40, exclude=()):
    started = time.time()

    print(f"Discovering real queries for {len(seeds)} seed(s)...", file=sys.stderr)
    queries = []
    for seed in seeds:
        got = discover(seed, locale, market, depth)
        print(f"  '{seed}' -> {len(got)} real queries", file=sys.stderr)
        queries.extend(got)

    # Dedupe, then drop queries that aren't about this business at all.
    seen, unique, dropped = set(), [], []
    for q in queries:
        k = q.lower().strip()
        if k in seen:
            continue
        seen.add(k)
        if is_relevant(q, exclude):
            unique.append(q)
        else:
            dropped.append(q)
    if dropped:
        print(f"  dropped {len(dropped)} off-topic queries "
              f"(acronym lookups, different orgs, wrong audience)", file=sys.stderr)

    print(f"Reading our sitemap ({domain})...", file=sys.stderr)
    ours = [(tokens(p), p) for p in site_paths(domain)]
    print(f"  {len(ours)} pages", file=sys.stderr)

    comp_index = {}
    for c in competitors:
        print(f"Reading competitor sitemap ({c})...", file=sys.stderr)
        paths = site_paths(c)
        print(f"  {len(paths)} pages", file=sys.stderr)
        comp_index[c] = [(tokens(p), p) for p in paths]

    # ------------------------------------------------------------------
    # Demote one-off entities: people and brands.
    #
    # Autocomplete surfaces named individuals ("ugc creator academy alina
    # schöck") and specific brands. They are real queries, but a page targeting
    # someone else's name is not a content strategy. Detect them generically
    # rather than by blacklist: a token that appears in exactly one query across
    # the whole discovered set is almost always a proper noun. A real topic word
    # recurs across the long tail.
    # ------------------------------------------------------------------
    freq = {}
    for q in unique:
        for w in tokens(q):
            freq[w] = freq.get(w, 0) + 1

    def looks_like_named_entity(q):
        rare = [w for w in tokens(q) if freq.get(w, 0) <= 1 and len(w) > 3]
        return len(rare) >= 2  # two unique-to-this-query words = a name

    rows = []
    for q in unique:
        our_page = covers(q, ours)
        comp_hits = []
        for c, idx in comp_index.items():
            hit = covers(q, idx)
            if hit:
                comp_hits.append((c, hit))
        s = score(q, our_page, comp_hits, locale)
        if looks_like_named_entity(q) and s["points"] > 0:
            s = {**s,
                 "points": max(10, s["points"] - 55),
                 "action": "likely a person or brand name — verify before targeting",
                 "why": s["why"] + " Contains words unique to this query, which usually "
                        "means a named person or brand rather than a topic."}
        rows.append({
            "query": q,
            "words": len(q.split()),
            "intent": intent_of(q),
            "we_cover": our_page,
            "competitors_covering": [{"domain": d, "page": p} for d, p in comp_hits],
            **s,
            "volume": None,  # autocomplete gives none; never invent one
        })

    rows.sort(key=lambda r: (-r["points"], r["query"]))

    gaps = [r for r in rows if r["verdict"].startswith("GAP")]
    local = [r for r in rows if r["verdict"].startswith("LOCAL")]
    openq = [r for r in rows if r["verdict"].startswith("open")]
    covered = [r for r in rows if r["verdict"] == "already covered"]

    # ------------------------------------------------------------------
    # Cluster the gaps.
    #
    # Several queries usually match the SAME competitor page, because one good
    # page covers a whole cluster. Listing them separately makes four
    # opportunities out of one and would have someone write four thin posts.
    # Grouping by the page the competitor actually built turns the list into a
    # content plan: one page per cluster, primary keyword plus the variants it
    # should also answer.
    # ------------------------------------------------------------------
    clusters = {}
    for row in gaps:
        key = tuple(sorted(c["page"] for c in row["competitors_covering"]))
        clusters.setdefault(key, []).append(row)

    plan = []
    for pages, members in clusters.items():
        # Primary = the head term of the cluster, found by containment.
        primary_query = pick_primary([m["query"] for m in members])
        primary = next(m for m in members if m["query"] == primary_query)
        rest = [m for m in members if m is not primary]
        rest.sort(key=lambda r: -r["points"])

        # A very large group isn't a cluster, it's a whole category — one page
        # won't cover 69 queries. Say so rather than implying one post does it.
        oversized = len(members) > 15
        note = (
            f"{len(members)} queries matched the same competitor page, so this is a "
            f"category rather than a single post. Start with the primary keyword and "
            f"split the rest into sub-topics."
            if oversized else
            f"{len(members)} real quer{'y' if len(members) == 1 else 'ies'} in this "
            f"cluster. A competitor covers it with one page; we have none."
        )

        plan.append({
            "primary_keyword": primary["query"],
            "also_answers": [m["query"] for m in rest[:8]],
            "cluster_size": len(members),
            "is_category": oversized,
            "intent": primary["intent"],
            "competitor_pages": sorted({
                f"{c['domain']}{c['page']}"
                for m in members for c in m["competitors_covering"]
            })[:3],
            "why": note,
            # Cap the cluster bonus so a sprawling category can't outrank a tight,
            # obviously-actionable cluster.
            "points": primary["points"] + min(len(rest), 6) * 4,
        })
    # Local-language gaps are plan items too. Group them by containment so
    # "ugc creator werden" and "ugc creator werden ohne follower" become one page.
    remaining = list(local)
    while remaining:
        seed_row = max(remaining, key=lambda r: r["points"])
        seed_q = seed_row["query"].lower()
        head = " ".join(seed_q.split()[:3])
        members = [r for r in remaining if head in r["query"].lower()] or [seed_row]
        remaining = [r for r in remaining if r not in members]

        primary_query = pick_primary([m["query"] for m in members])
        primary = next(m for m in members if m["query"] == primary_query)
        rest = [m for m in members if m is not primary]

        plan.append({
            "primary_keyword": primary["query"],
            "also_answers": [m["query"] for m in rest[:8]],
            "cluster_size": len(members),
            "is_category": False,
            "is_local_language": True,
            "locale": locale,
            "intent": primary["intent"],
            "competitor_pages": [],
            "why": (
                f"Real {locale}-language query with no page on our site. The competitors "
                f"checked are English-language, so they will not compete for it. A site "
                f"already publishing in {locale} is best placed to take this."
            ),
            "points": primary["points"] + min(len(rest), 6) * 4,
        })

    plan.sort(key=lambda c: (c["is_category"], -c["points"]))

    return {
        "domain": domain,
        "checked_at": time.strftime("%Y-%m-%d %H:%M"),
        "seeds": seeds,
        "excluded_terms": list(exclude),
        "locale": locale,
        "market": market,
        "competitors_checked": competitors,
        "totals": {
            "real_queries_found": len(unique),
            "gaps_competitor_covers_we_dont": len(gaps),
            "local_gaps_no_competitor_speaks_the_language": len(local),
            "open_nobody_covers": len(openq),
            "already_covered_by_us": len(covered),
        },
        "note": (
            "Volume is not included. Autocomplete confirms a query is real, not how "
            "big it is. Winnability is scored from coverage gaps instead, which is "
            "measurable for free."
        ),
        "seconds": round(time.time() - started, 1),
        # The content plan is the actionable output: one page per cluster.
        "content_plan": plan[:15],
        "keywords": rows[:limit],
    }


def print_summary(r):
    t = r["totals"]
    print(f"\nWinnable keywords for {r['domain']}  ({r['locale']}-{r['market']})")
    print("=" * 74)
    print(f"  {t['real_queries_found']} real queries found from {len(r['seeds'])} seed(s)")
    print(f"  {t['gaps_competitor_covers_we_dont']} competitor gaps  ·  "
          f"{t.get('local_gaps_no_competitor_speaks_the_language', 0)} local-language gaps  ·  "
          f"{t['open_nobody_covers']} uncontested  ·  "
          f"{t['already_covered_by_us']} we already cover")
    print(f"  competitors checked: {', '.join(r['competitors_checked']) or 'none'}")
    print()

    plan = r.get("content_plan") or []
    if plan:
        print("CONTENT PLAN — one page per cluster, highest-leverage first")
        print("-" * 74)
        for i, c in enumerate(plan[:8], 1):
            tag = "  (broad category — split it)" if c.get("is_category") else ""
            print(f"  {i}. {c['primary_keyword']}   [{c['points']}]{tag}")
            print(f"     {c['intent']} · {c['cluster_size']} quer"
                  f"{'y' if c['cluster_size'] == 1 else 'ies'} in this cluster")
            if c["also_answers"]:
                print(f"     also answers: {', '.join(c['also_answers'][:4])}")
            print(f"     competitor has: {c['competitor_pages'][0]}")
            print()

    loc = [k for k in r["keywords"] if k["verdict"].startswith("LOCAL")]
    if loc:
        print(f"LOCAL-LANGUAGE GAPS ({r['locale']}) — real queries no English competitor serves")
        print("-" * 74)
        for k in loc[:10]:
            print(f"  [{k['points']:>3}] {k['query']}  ({k['intent']})")
        print()

    openq = [k for k in r["keywords"] if k["verdict"].startswith("open")]
    if openq:
        print("UNCONTESTED — nobody checked has a page for these")
        print("-" * 74)
        for k in openq[:10]:
            print(f"  [{k['points']:>3}] {k['query']}  ({k['intent']})")
        print()

    print("Volume: not measured. Autocomplete proves a query is real, not its size.")
    print("Next:  ask Claude to write the top one, or run with --json to pipe it.\n")


def main():
    argv = sys.argv[1:]

    def opt(name, default=None):
        f = f"--{name}"
        return argv[argv.index(f) + 1] if f in argv else default

    domain = opt("domain")
    if not domain:
        print(__doc__)
        sys.exit(1)

    seeds = [s.strip() for s in (opt("seeds") or "").split(",") if s.strip()]
    if not seeds:
        print("Need --seeds, e.g. --seeds \"ugc creator,ugc marketing\"")
        sys.exit(1)

    competitors = [c.strip() for c in (opt("competitors") or "").split(",") if c.strip()]

    result = research(
        domain.replace("https://", "").replace("http://", "").rstrip("/"),
        seeds,
        competitors,
        locale=opt("locale", "en"),
        market=opt("market", "us"),
        depth=int(opt("depth", "26")),
        limit=int(opt("limit", "40")),
        exclude=[e.strip() for e in (opt("exclude") or "").split(",") if e.strip()],
    )

    if "--json" in argv:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print_summary(result)


if __name__ == "__main__":
    main()
