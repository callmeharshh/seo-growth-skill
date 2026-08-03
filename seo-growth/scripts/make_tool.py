#!/usr/bin/env python3
"""
Generate a free-tool page — a real deployable HTML file, localised per market.

    python3 make_tool.py --locale de --out out/
    python3 make_tool.py --all-markets --out out/

The brief lists free tools as an asset the system should create, and points at a
competitor's 45-tool portfolio as the pattern. This builds the first one.

WHY AN EARNINGS CALCULATOR, SPECIFICALLY

Not copied from the reference portfolio — chosen from measured demand. Google
autocomplete confirms all four target keywords: "ugc creator salary" (en-US),
"ugc creator verdienst" (de-DE), "quanto ganha um ugc creator" (pt-BR) and
"cuanto gana un creador ugc" (es-ES/MX). People want to know if the work pays
before they start.

Note the Spanish one: "creador ugc", not "ugc creator". Spanish flips the noun
order and German does not. That is only knowable by measuring, which is the whole
argument for not translating keywords.

Turkey is deliberately absent. It has strong demand for "ugc creator nedir" and
"nasıl olunur" — explainers — but autocomplete shows no earnings query, so the
generator refuses to build a calculator there. See keyword_is_real().

That is the supply side of a two-sided marketplace, which is the side a creator
network needs. So the tool answers a real question honestly and the conversion is
"join" rather than "book a demo".

WHAT IT DOES NOT DO

It does not tell anyone what UGC pays. Nobody has trustworthy global rate data and
inventing some would be the fastest way to lose a reader's trust. Instead the user
supplies their own rate and volume, and the tool does the arithmetic they were
going to do badly in their head: monthly and annual totals, effective hourly rate,
and how long it takes to hit a target. Every number on screen traces to something
they typed.

SEO REQUIREMENTS BUILT IN

- The default answer is in the HTML before any JavaScript runs. A tool whose
  output only exists after JS cannot be ranked or cited, which is why most SaaS
  tool pages are invisible.
- FAQPage schema, with the same questions visible on the page.
- The target keyword is in the title, the H1, and the copy.
- One link to the creator conversion path.
- Self-contained: no external requests, so it drops anywhere.
"""

import json
import os
import sys

# Per-market copy. Keyword comes from the real autocomplete queries, not a
# translation of the English one.
LOCALES = {
    "en": {
        "market": "United States", "cur": "$", "hl": "en",
        "kw": "ugc creator salary",
        "title": "UGC Creator Salary Calculator: What You'd Actually Earn",
        "h1": "UGC Creator Salary Calculator",
        "lede": "Work out what UGC creator work would pay you, from your own rate and how many videos you can realistically make.",
        "answer": "A UGC creator's monthly earnings are the per-video rate multiplied by videos delivered, minus unpaid time. This calculator does that maths with your numbers.",
        "rate": "Your rate per video", "videos": "Videos per month",
        "hours": "Hours spent per video", "target": "Monthly income target",
        "monthly": "Per month", "yearly": "Per year", "hourly": "Effective hourly",
        "needed": "Videos needed to hit your target",
        "cta": "Start getting briefs with 8x", "cta_path": "/en/for-creators",
        "note": "Nothing here is a promise. It is arithmetic on the numbers you entered.",
        "faq": [
            ("How much do UGC creators actually make?",
             "It varies too much for a single honest number — rate depends on your market, the usage rights the brand buys, and how many videos you deliver. That's why this calculator asks for your rate instead of inventing one."),
            ("How many videos a month is realistic?",
             "Most people starting part-time manage between four and twelve. Filming is quick once you have a setup; briefing and revisions take the time."),
            ("Do I need followers to be paid as a UGC creator?",
             "No. Brands buy the video to run on their own channels, so follower count usually isn't part of the deal."),
            ("Should I charge more for ads usage?",
             "Yes. A video a brand runs as a paid ad for months is worth more than one organic post. Always ask which it is before quoting."),
        ],
    },
    "de": {
        "market": "Germany", "cur": "€", "hl": "de",
        "kw": "ugc creator verdienst",
        "title": "UGC Creator Verdienst Rechner: Was du wirklich verdienst",
        "h1": "UGC Creator Verdienst Rechner",
        "lede": "Berechne deinen UGC Creator Verdienst aus deinem eigenen Preis pro Video und der Anzahl Videos, die du realistisch schaffst.",
        "answer": "Der Verdienst als UGC Creator ergibt sich aus dem Preis pro Video mal der Anzahl gelieferter Videos, abzüglich unbezahlter Zeit. Dieser Rechner macht die Rechnung mit deinen Zahlen.",
        "rate": "Dein Preis pro Video", "videos": "Videos pro Monat",
        "hours": "Stunden pro Video", "target": "Monatliches Einkommensziel",
        "monthly": "Pro Monat", "yearly": "Pro Jahr", "hourly": "Effektiver Stundenlohn",
        "needed": "Videos für dein Ziel",
        "cta": "Mit 8x als UGC Creator starten", "cta_path": "/de/for-creators",
        "note": "Das ist kein Versprechen, sondern eine Rechnung mit deinen Angaben.",
        "faq": [
            ("Wie viel verdient ein UGC Creator?",
             "Das hängt zu stark vom Markt, den Nutzungsrechten und der Anzahl Videos ab, um eine ehrliche Pauschalzahl zu nennen. Deshalb fragt der Rechner nach deinem Preis, statt einen zu erfinden."),
            ("Wie viele Videos pro Monat sind realistisch?",
             "Nebenberuflich schaffen die meisten vier bis zwölf. Das Filmen geht schnell, sobald ein Setup steht — Briefing und Korrekturschleifen kosten die Zeit."),
            ("Braucht man Follower, um UGC Creator zu werden?",
             "Nein. Marken kaufen das Video für ihre eigenen Kanäle, die Reichweite deines Profils spielt meist keine Rolle."),
            ("Sollte ich für Werbenutzung mehr verlangen?",
             "Ja. Ein Video, das als bezahlte Anzeige läuft, ist mehr wert als ein organischer Post. Kläre die Nutzungsrechte vor dem Angebot."),
        ],
    },
    "pt": {
        "market": "Brazil", "cur": "R$", "hl": "pt",
        "kw": "quanto ganha um ugc creator",
        "title": "Calculadora: Quanto Ganha um UGC Creator",
        "h1": "Quanto ganha um UGC creator?",
        "lede": "Calcule quanto você ganharia como UGC creator, a partir do seu próprio valor por vídeo e de quantos vídeos consegue entregar.",
        "answer": "Quanto um UGC creator ganha é o valor por vídeo multiplicado pelos vídeos entregues, menos o tempo não pago. Esta calculadora faz essa conta com os seus números.",
        "rate": "Seu valor por vídeo", "videos": "Vídeos por mês",
        "hours": "Horas por vídeo", "target": "Meta de renda mensal",
        "monthly": "Por mês", "yearly": "Por ano", "hourly": "Valor por hora efetivo",
        "needed": "Vídeos para bater sua meta",
        "cta": "Começar como creator na 8x", "cta_path": "/pt/for-creators",
        "note": "Isto não é uma promessa. É uma conta com os números que você informou.",
        "faq": [
            ("Quanto ganha um UGC creator no Brasil?",
             "Varia demais para dar um número honesto: depende do seu mercado, dos direitos de uso que a marca compra e de quantos vídeos você entrega. Por isso a calculadora pede o seu valor em vez de inventar um."),
            ("Quantos vídeos por mês dá para fazer?",
             "Quem começa em paralelo costuma entregar de quatro a doze. Gravar é rápido depois que você tem um setup — briefing e ajustes é que tomam tempo."),
            ("Preciso de seguidores para ser UGC creator?",
             "Não. As marcas compram o vídeo para usar nos canais delas, então o número de seguidores geralmente não entra na negociação."),
            ("Devo cobrar mais quando o vídeo vira anúncio?",
             "Sim. Um vídeo que roda como anúncio pago vale mais que um post orgânico. Confirme o uso antes de passar o orçamento."),
        ],
    },
    "es": {
        "market": "Spain / Mexico", "cur": "€", "hl": "es",
        # Note the noun order: Spanish searches "creador ugc", not "ugc creator".
        # Confirmed by autocomplete in both es-ES and es-MX.
        "kw": "cuanto gana un creador ugc",
        "title": "Cuánto Gana un Creador UGC: Calculadora",
        "h1": "¿Cuánto gana un creador UGC?",
        "lede": "Calcula cuánto ganarías como creador UGC, a partir de tu propia tarifa por vídeo y de cuántos vídeos puedes entregar.",
        "answer": "Lo que gana un creador UGC es la tarifa por vídeo multiplicada por los vídeos entregados, menos el tiempo no pagado. Esta calculadora hace esa cuenta con tus números.",
        "rate": "Tu tarifa por vídeo", "videos": "Vídeos al mes",
        "hours": "Horas por vídeo", "target": "Objetivo de ingresos mensual",
        "monthly": "Al mes", "yearly": "Al año", "hourly": "Tarifa horaria efectiva",
        "needed": "Vídeos para tu objetivo",
        "cta": "Empieza como creador en 8x", "cta_path": "/es/for-creators",
        "note": "Esto no es una promesa. Es una cuenta con los datos que has introducido.",
        "faq": [
            ("¿Cuánto gana un creador UGC?",
             "Varía demasiado para dar una cifra honesta: depende de tu mercado, de los derechos de uso que compre la marca y de cuántos vídeos entregues. Por eso la calculadora pide tu tarifa en lugar de inventarse una."),
            ("¿Cuántos vídeos al mes son realistas?",
             "Quien empieza a tiempo parcial suele entregar entre cuatro y doce. Grabar es rápido cuando ya tienes un setup; el briefing y las revisiones son lo que consume tiempo."),
            ("¿Necesito seguidores para ser creador UGC?",
             "No. Las marcas compran el vídeo para usarlo en sus propios canales, así que tu número de seguidores no suele entrar en la negociación."),
            ("¿Debo cobrar más si el vídeo se usa como anuncio?",
             "Sí. Un vídeo que se emite como anuncio pagado vale más que una publicación orgánica. Confirma el uso antes de dar precio."),
        ],
    },
}


def keyword_is_real(keyword, hl, gl):
    """
    Check the target keyword against Google autocomplete before building a page
    for it.

    This exists because of a mistake made while writing this file: a Turkish
    earnings calculator was drafted around "ugc creator maaş", which turned out
    not to be a query Turkish users type. Turkey has real demand for "ugc creator
    nedir" and "nasıl olunur" — explainers, not calculators. Shipping the
    calculator would have produced a page aimed at nothing.

    So the generator now refuses unverified keywords. Returns (ok, evidence).
    """
    import json as _json
    import subprocess
    from urllib.parse import quote as _quote

    # Probe a prefix of the keyword and see whether autocomplete completes it.
    words = keyword.split()
    probe = " ".join(words[:-1]) + " " + words[-1][:3] if len(words) > 1 else keyword[:5]
    url = ("https://suggestqueries.google.com/complete/search?client=firefox"
           f"&hl={hl}&gl={gl}&ie=UTF-8&oe=UTF-8&q={_quote(probe)}")
    try:
        raw = subprocess.run(
            ["curl", "-sS", "--max-time", "15", "-A", "seo-growth-skill/1.0", url],
            capture_output=True, text=True, timeout=25,
        ).stdout
        suggestions = _json.loads(raw)[1]
    except Exception as e:
        return None, f"could not verify ({e})"

    target = keyword.lower()
    for sug in suggestions:
        if sug.lower() == target or target in sug.lower() or sug.lower() in target:
            return True, f'autocomplete ({hl}-{gl}) returns "{sug}"'
    return False, (f'autocomplete ({hl}-{gl}) for "{probe}" returned '
                   f'{suggestions[:3] or "nothing"} — not this keyword')


def slugify(s):
    import re, unicodedata
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s)).strip("-")


def build(loc_key):
    L = LOCALES[loc_key]
    slug = slugify(L["kw"])

    # Defaults are rendered server-side so the page has a real answer in the HTML
    # before JavaScript runs. This is the single most-skipped requirement on tool
    # pages, and the reason most of them never rank.
    d_rate, d_videos, d_hours, d_target = 150, 8, 3, 2000
    d_month = d_rate * d_videos
    d_year = d_month * 12
    d_hourly = round(d_month / (d_videos * d_hours), 2)
    d_needed = -(-d_target // d_rate)
    c = L["cur"]

    faq_html = "".join(
        f'\n    <details><summary>{q}</summary><p>{a}</p></details>'
        for q, a in L["faq"]
    )
    faq_schema = json.dumps({
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": a}}
            for q, a in L["faq"]
        ],
    }, ensure_ascii=False)

    app_schema = json.dumps({
        "@context": "https://schema.org",
        "@type": "WebApplication",
        "name": L["h1"],
        "applicationCategory": "FinanceApplication",
        "operatingSystem": "Any",
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
        "description": L["lede"],
    }, ensure_ascii=False)

    return slug, f"""<!doctype html>
<html lang="{L['hl']}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{L['title']}</title>
<meta name="description" content="{L['lede'][:155]}">
<link rel="canonical" href="/{L['hl']}/tools/{slug}">
<script type="application/ld+json">{app_schema}</script>
<script type="application/ld+json">{faq_schema}</script>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font: 16px/1.6 system-ui,-apple-system,sans-serif; max-width: 660px;
          margin: 0 auto; padding: 40px 20px; }}
  h1 {{ font-size: 30px; margin: 0 0 8px; }}
  .lede {{ font-size: 17px; opacity: .8; margin: 0 0 24px; }}
  .answer {{ border-left: 3px solid currentColor; padding: 10px 0 10px 16px;
             margin: 0 0 28px; font-weight: 500; }}
  .calc {{ border: 1px solid #8885; border-radius: 12px; padding: 20px; }}
  label {{ display: block; font-size: 13px; font-weight: 600; margin: 14px 0 4px; }}
  input {{ width: 100%; padding: 10px; font-size: 16px; border: 1px solid #8886;
           border-radius: 8px; background: transparent; color: inherit; }}
  .out {{ display: grid; grid-template-columns: repeat(auto-fit,minmax(140px,1fr));
          gap: 14px; margin-top: 22px; padding-top: 20px; border-top: 1px solid #8884; }}
  .out div span {{ display: block; font-size: 12px; opacity: .65; }}
  .out div strong {{ font-size: 24px; }}
  .note {{ font-size: 13px; opacity: .65; margin-top: 16px; }}
  .cta {{ display: inline-block; margin: 26px 0; padding: 12px 20px;
          border: 1px solid currentColor; border-radius: 8px;
          text-decoration: none; color: inherit; font-weight: 600; }}
  details {{ border-top: 1px solid #8884; padding: 12px 0; }}
  summary {{ font-weight: 600; cursor: pointer; }}
  details p {{ margin: 8px 0 0; opacity: .85; }}
</style>
</head>
<body>

<h1>{L['h1']}</h1>
<p class="lede">{L['lede']}</p>
<p class="answer">{L['answer']}</p>

<div class="calc">
  <label for="rate">{L['rate']} ({c})</label>
  <input id="rate" type="number" min="0" value="{d_rate}">

  <label for="videos">{L['videos']}</label>
  <input id="videos" type="number" min="0" value="{d_videos}">

  <label for="hours">{L['hours']}</label>
  <input id="hours" type="number" min="0" step="0.5" value="{d_hours}">

  <label for="target">{L['target']} ({c})</label>
  <input id="target" type="number" min="0" value="{d_target}">

  <!-- Rendered with real values already computed, so the page answers the
       question with JavaScript disabled and can be crawled and cited. -->
  <div class="out">
    <div><span>{L['monthly']}</span><strong id="m">{c}{d_month:,}</strong></div>
    <div><span>{L['yearly']}</span><strong id="y">{c}{d_year:,}</strong></div>
    <div><span>{L['hourly']}</span><strong id="h">{c}{d_hourly}</strong></div>
    <div><span>{L['needed']}</span><strong id="n">{d_needed}</strong></div>
  </div>
  <p class="note">{L['note']}</p>
</div>

<a class="cta" href="{L['cta_path']}">{L['cta']} &rarr;</a>

<h2>FAQ</h2>{faq_html}

<script>
  const $ = id => document.getElementById(id);
  const cur = {json.dumps(c)};
  function calc() {{
    const rate = +$("rate").value || 0, videos = +$("videos").value || 0;
    const hours = +$("hours").value || 0, target = +$("target").value || 0;
    const month = rate * videos;
    $("m").textContent = cur + month.toLocaleString();
    $("y").textContent = cur + (month * 12).toLocaleString();
    $("h").textContent = (videos && hours)
      ? cur + (month / (videos * hours)).toFixed(2) : "—";
    $("n").textContent = rate ? Math.ceil(target / rate) : "—";
  }}
  ["rate","videos","hours","target"].forEach(id =>
    $(id).addEventListener("input", calc));
</script>

</body>
</html>
"""


def main():
    argv = sys.argv[1:]
    if not argv:
        print(__doc__)
        print("Nothing written. Pass --locale <code> or --all-markets.\n")
        sys.exit(0)
    out_dir = argv[argv.index("--out") + 1] if "--out" in argv else "out/tools"
    if "--all-markets" in argv:
        locales = list(LOCALES)
    else:
        locales = [argv[argv.index("--locale") + 1]] if "--locale" in argv else ["en"]

    skip_verify = "--no-verify" in argv
    os.makedirs(out_dir, exist_ok=True)
    for lk in locales:
        if lk not in LOCALES:
            print(f"No copy for locale '{lk}'. Have: {', '.join(LOCALES)}")
            continue
        L0 = LOCALES[lk]

        if not skip_verify:
            ok, evidence = keyword_is_real(L0["kw"], L0["hl"], lk if lk != "en" else "us")
            if ok is False:
                print(f"  REFUSED  {lk}: \"{L0['kw']}\" is not a real query.")
                print(f"           {evidence}")
                print(f"           Find the query this market actually uses first.\n")
                continue
            print(f"  verified {lk}: {evidence}")

        slug, html = build(lk)
        path = os.path.join(out_dir, f"{lk}-{slug}.html")
        with open(path, "w") as f:
            f.write(html)
        L = LOCALES[lk]
        print(f"  {path}")
        print(f"      route  /{lk}/tools/{slug}")
        print(f"      target \"{L['kw']}\"  ({L['market']})")
    print(f"\nEach page answers before JavaScript runs, carries FAQPage +"
          f" WebApplication schema, and links to the creator signup.\n")


if __name__ == "__main__":
    main()
