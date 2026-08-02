#!/usr/bin/env python3
"""
Grade a blog post before it ships.

    python3 check_post.py draft.md
    python3 check_post.py draft.md --keyword "ugc creator jobs"

Claude writes the post. This grades it. That split matters: a model asked to
write AND self-assess will tell you its own work is fine. A script that counts
words doesn't care whose feelings it hurts.

Checks the things that actually decide whether a post ranks and gets cited:
keyword in the title, in the URL, in at least one H2, and repeated enough in the
body; an answer-first opening an AI engine can lift; nested headings; an FAQ
block; a link to the conversion path; and no leftover placeholders.

Exits 1 if anything fails, so it works in a pre-commit hook or CI.
"""

import re
import sys


def parse(md):
    fm = {}
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?", md, re.S)
    body = md[m.end():] if m else md
    if m:
        for line in m.group(1).split("\n"):
            if ":" in line and not line.startswith(" "):
                k, v = line.split(":", 1)
                fm[k.strip()] = v.strip().strip("\"'")
    return fm, body


def visible_text(body):
    """Body prose without code blocks, so counts reflect what a reader sees."""
    t = re.sub(r"(?s)```.*?```", " ", body)
    t = re.sub(r"(?s)<!--.*?-->", " ", t)
    t = re.sub(r"^#{1,6}\s*", "", t, flags=re.M)
    return re.sub(r"\s+", " ", t)


def count(text, phrase):
    """Occurrences of a phrase, whitespace-flexible, case-insensitive."""
    pat = r"\s+".join(re.escape(w) for w in phrase.lower().split())
    return len(re.findall(pat, text.lower()))


def grade(md, keyword=None):
    fm, body = parse(md)
    text = visible_text(body)
    words = len(text.split())

    kw = keyword or fm.get("targetKeyword") or ""
    head = kw.split()[0] if kw else ""

    h1s = re.findall(r"^#\s+(.+)$", body, re.M)
    h2s = re.findall(r"^##\s+(.+)$", body, re.M)
    h3s = re.findall(r"^###\s+(.+)$", body, re.M)

    body_hits = count(text, kw) if kw else 0
    # Rough target: mention the keyword about once per 250 words, min 4.
    expected = max(4, round(words / 250))

    results = []

    def check(label, passed, detail, fatal=True):
        results.append({"label": label, "passed": bool(passed), "detail": detail,
                        "fatal": fatal})

    check("Has a target keyword",
          bool(kw),
          f'targetKeyword: "{kw}"' if kw else
          "No targetKeyword in front matter and none passed with --keyword")

    check("Keyword in the title",
          kw and (count(fm.get("title", ""), kw) or (head and head.lower() in fm.get("title", "").lower())),
          f'title: "{fm.get("title", "")}"')

    check("Keyword in the URL slug",
          kw and head and head.lower() in fm.get("slug", "").lower(),
          f'slug: "{fm.get("slug", "")}"')

    check("Exactly one H1",
          len(h1s) == 1,
          f"{len(h1s)} H1(s): {h1s[:2]}")

    check("Keyword in at least one H2",
          kw and any(head.lower() in h.lower() for h in h2s) if h2s else False,
          f"{len(h2s)} H2s. " + ("Found in a heading." if kw and any(head.lower() in h.lower() for h in h2s)
                                 else "Not in any H2 — this is the most common reason a post reads as keyword-stuffed rather than keyword-about."))

    check("Keyword used enough in the body",
          body_hits >= expected,
          f'"{kw}" appears {body_hits}x in {words} words (target {expected}+)')

    check("Answer-first opening",
          bool(re.search(r"^>\s*\*?\*?\S", body, re.M)),
          "A blockquote in the first screen is what an AI engine lifts when it cites you."
          if not re.search(r"^>\s*\*?\*?\S", body, re.M) else "Present.")

    check("Nested headings",
          len(h2s) >= 3 and len(h3s) >= 1,
          f"{len(h2s)} H2s, {len(h3s)} H3s")

    check("FAQ section",
          bool(re.search(r"(?i)^##+\s*(frequently asked|faq)", body, re.M)),
          "Needed for FAQPage schema and the 'People also ask' surface.")

    check("Enough FAQ questions",
          len(re.findall(r"(?m)^###\s+.*\?", body)) >= 3,
          f"{len(re.findall(r'(?m)^###\\s+.*\\?', body))} question-shaped H3s (want 3+)",
          fatal=False)

    check("Long enough to be useful",
          words >= 700,
          f"{words} words", fatal=False)

    check("Links to a conversion path",
          bool(re.search(r"\]\(/[a-z]", body)),
          "No internal link found. A post that can't convert is a cost.",
          fatal=False)

    check("No leftover placeholders",
          not re.search(r"\[WRITE|\[TODO|\[INSERT|lorem ipsum|XXX", body, re.I),
          "Found an unfilled placeholder — this is a draft, not a post."
          if re.search(r"\[WRITE|\[TODO|\[INSERT", body, re.I) else "Clean.")

    check("Marked for review",
          "reviewRequired" in fm or fm.get("status") == "draft",
          "Front matter should say status: draft or reviewRequired: true "
          "so nothing publishes by accident.",
          fatal=False)

    return results, {"words": words, "keyword": kw, "body_hits": body_hits,
                     "h2": len(h2s), "h3": len(h3s)}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        sys.exit(1)

    keyword = None
    if "--keyword" in sys.argv:
        keyword = sys.argv[sys.argv.index("--keyword") + 1]

    path = args[0]
    try:
        md = open(path).read()
    except OSError as e:
        print(f"Can't read {path}: {e}")
        sys.exit(1)

    results, stats = grade(md, keyword)
    failed = [r for r in results if not r["passed"]]
    fatal = [r for r in failed if r["fatal"]]

    print(f"\n{path}")
    print(f"  {stats['words']} words · target keyword \"{stats['keyword']}\" "
          f"used {stats['body_hits']}x · {stats['h2']} H2s / {stats['h3']} H3s")
    print("-" * 68)
    for r in results:
        mark = "PASS" if r["passed"] else ("FAIL" if r["fatal"] else "warn")
        print(f"  [{mark}] {r['label']}")
        if not r["passed"]:
            print(f"         {r['detail']}")

    passed = len(results) - len(failed)
    print("-" * 68)
    print(f"  {passed}/{len(results)} checks passed", end="")
    if fatal:
        print(f" — {len(fatal)} blocking issue(s). Fix before publishing.\n")
        sys.exit(1)
    if failed:
        print(f" — {len(failed)} warning(s), nothing blocking.\n")
    else:
        print(" — ready to publish.\n")


if __name__ == "__main__":
    main()
