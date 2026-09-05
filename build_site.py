#!/usr/bin/env python3
"""Regenerate Which Pack static site from coverage.json (Astra brief).

Usage: python3 build_site.py
Reads coverage.json in this directory, writes HTML/CSS/assets here,
then syncs key files to /workspace/affiliate-business/mvp/.
"""
from __future__ import annotations

import html
import json
import pathlib
import re
import shutil
from urllib.parse import parse_qs, urlparse

ROOT = pathlib.Path(__file__).resolve().parent
MVP = pathlib.Path("/workspace/affiliate-business/mvp")
BASE = "https://moonoce95.github.io/which-pack"
GSC = "frPZ5rPE7O19CZ2M46qLfvkckx6mxdPsTMzGyS9AQAI"

# Familiar verified categories first; niche / all-unknown last (Astra).
ROW_ORDER = [
    "circular_saw",
    "impact_wrench",
    "mitre_saw",
    "jobsite_table_saw",
    "track_saw___plunge_saw",
    "wet_dry_vac___dust_extractor",
    "angle_grinder",
    "reciprocating_saw",
    "jigsaw",
    "rotary_hammer_(sds)",
    "framing_nailer",
    "heat_gun",
    "oscillating_multi-tool",
    "chainsaw",
    "outdoor_string___line_trimmer",
    "18v-platform_lawn_mower",
    "metal_cut-off___chop_saw",
    "sds-max_rotary_hammer___breaker",
    "portable_band_saw",
    "drain_snake___drain_cleaner",
    "grease_gun",
    "caulk___adhesive_gun",
    "press_tool_(copper_pex)",
    "compact_banding_nailer",
]

PLATFORM_HEADERS = {
    "m18_au": ("Milwaukee", "M18 · 18V"),
    "dewalt_18v_au": ("DeWalt", "XR · 18V"),
    "dewalt_flexvolt_au": ("DeWalt", "FLEXVOLT · 54V"),
    "makita_lxt_au": ("Makita", "LXT · 18V"),
    "ryobi_one_au": ("Ryobi", "ONE+ · 18V"),
}

# Soft requirement hints: (tool_id, platform_id|None) -> text.
# Derived from existing notes in coverage.json — never invents coverage status.
REQUIREMENT_HINTS = {
    ("18v-platform_lawn_mower", None): "Often 18V×2 — check pack count",
    ("outdoor_string___line_trimmer", "m18_au"): "Needs two M18 packs (sampled)",
    ("outdoor_string___line_trimmer", None): "Some models need 18V×2",
    ("track_saw___plunge_saw", "makita_lxt_au"): "Sample is 18V×2 LXT",
    ("metal_cut-off___chop_saw", None): "Dedicated 230mm+ chop — not 76mm compact",
    ("sds-max_rotary_hammer___breaker", None): "SDS-MAX — not SDS-plus",
}


def esc(s: str) -> str:
    return html.escape(s, quote=True)



def display_tool_name(name: str) -> str:
    """Title-case tool labels for the matrix; preserve SDS / 18V / PEX."""
    specials = {
        "sds": "SDS",
        "sds-max": "SDS-MAX",
        "sds-plus": "SDS-plus",
        "pex": "PEX",
        "au": "AU",
        "18v-platform": "18V-platform",
        "18v": "18V",
    }
    out = []
    for raw in name.split():
        key = raw.lower()
        if key in specials:
            out.append(specials[key])
            continue
        if "/" in raw:
            bits = []
            for part in raw.split("/"):
                pk = part.lower()
                if pk in specials:
                    bits.append(specials[pk])
                elif part:
                    bits.append(part[:1].upper() + part[1:])
                else:
                    bits.append(part)
            out.append("/".join(bits))
            continue
        if raw.startswith("(") and raw.endswith(")"):
            inner = raw[1:-1]
            ik = inner.lower()
            if ik in specials:
                out.append(f"({specials[ik]})")
            else:
                out.append("(" + (inner[:1].upper() + inner[1:] if inner else inner) + ")")
            continue
        out.append(raw[:1].upper() + raw[1:] if raw else raw)
    return " ".join(out)


def amazon_label(url: str) -> str:
    path = urlparse(url).path or ""
    q = urlparse(url).query or ""
    if "/s?" in url or path.rstrip("/").endswith("/s") or q.startswith("k=") or "/s?" in (path + "?" + q):
        return "Search"
    # Product detail pages typically /dp/ or /gp/product/
    if "/dp/" in url or "/gp/product/" in url:
        return "View"
    return "Search"


def extract_model(cell: dict) -> str | None:
    """Best-effort model from evidence or amazon k= — never invent."""
    candidates: list[str] = []
    for e in cell.get("evidence") or []:
        path = urlparse(e).path
        m = re.search(r"/([A-Za-z][A-Za-z0-9\-]{3,})\.html?$", path)
        if m:
            candidates.append(m.group(1))
            continue
        m = re.search(r"/product/([a-z0-9\-]+)/", path, re.I)
        if m:
            candidates.append(m.group(1).upper())
    amz = cell.get("amazon")
    if amz:
        qs = parse_qs(urlparse(amz).query)
        k = (qs.get("k") or [""])[0]
        if re.match(r"^[A-Za-z0-9][A-Za-z0-9\-]{2,22}$", k) and " " not in k:
            candidates.append(k)
    # Prefer first evidence-derived, else amazon
    return candidates[0] if candidates else None


def source_host(url: str) -> str:
    host = urlparse(url).netloc.replace("www.", "")
    return host or "source"


def status_icon(status: str) -> str:
    if status == "has":
        return "✓"
    if status == "missing":
        return "–"
    return "?"


def render_cell(platform_id: str, cell: dict, tool: dict, updated: str) -> str:
    status = cell.get("status") or "unknown"
    parts = [
        f'<span class="status {esc(status)}">'
        f'<span class="status-ico" aria-hidden="true">{status_icon(status)}</span> '
        f"{esc(status)}</span>"
    ]

    req = REQUIREMENT_HINTS.get((tool["id"], platform_id)) or REQUIREMENT_HINTS.get((tool["id"], None))
    if req:
        if tool["id"] in ("metal_cut-off___chop_saw", "sds-max_rotary_hammer___breaker"):
            if status != "unknown":
                parts.append(f'<div class="req">{esc(req)}</div>')
        elif status == "has":
            # Prefer platform-specific hint when present (already resolved above)
            parts.append(f'<div class="req">{esc(req)}</div>')

    if status == "has":
        model = extract_model(cell)
        evidence = cell.get("evidence") or []
        detail_bits = []
        if model:
            detail_bits.append(f"<span class=\"model\">{esc(model)}</span>")
        if evidence:
            src = evidence[0]
            detail_bits.append(
                f'<a class="src" href="{esc(src)}" rel="noopener noreferrer">{esc(source_host(src))}</a>'
            )
        detail_bits.append(f'<span class="date">{esc(tool.get("last_verified") or updated)}</span>')
        parts.append(f'<div class="details">{" · ".join(detail_bits)}</div>')

        amz = cell.get("amazon")
        if amz and platform_id != "ryobi_one_au":
            label = amazon_label(amz)
            parts.append(
                f'<a class="amz" rel="sponsored nofollow noopener" href="{esc(amz)}">'
                f"Amazon AU — {esc(label)}</a>"
            )
    return "<td>" + "".join(parts) + "</td>"


def order_tools(tool_types: list[dict]) -> list[dict]:
    by_id = {t["id"]: t for t in tool_types}
    ordered = []
    for tid in ROW_ORDER:
        if tid in by_id:
            ordered.append(by_id.pop(tid))
    # Any unexpected leftovers: known-heavy first, then unknown-heavy
    def score(t: dict) -> tuple:
        cells = t["cells"].values()
        unk = sum(1 for c in cells if c.get("status") == "unknown")
        return (unk, t["name"])

    ordered.extend(sorted(by_id.values(), key=score))
    return ordered


def is_trap_row(tool: dict) -> bool:
    note = (tool.get("note") or "").lower()
    keys = ("trap", "flexvolt", "54v", "dual-pack", "18vx2", "two m18", "voltage")
    return any(k in note for k in keys)


def known_flag(tool: dict) -> str:
    return "0" if all(c.get("status") == "unknown" for c in tool["cells"].values()) else "1"


def render_matrix_rows(tools: list[dict], platforms: list[dict], updated: str) -> str:
    rows = []
    for tool in tools:
        trap = "1" if is_trap_row(tool) else "0"
        known = known_flag(tool)
        cls = ' class="is-trap"' if trap == "1" else ""
        cells_html = "".join(
            render_cell(p["id"], tool["cells"].get(p["id"], {"status": "unknown", "evidence": []}), tool, updated)
            for p in platforms
        )
        note = tool.get("note") or ""
        note_html = ""
        if note:
            prefix = ""
            if trap == "1":
                prefix = '<span class="trap-tag">Watch — voltage / coverage</span>'
            note_html = f'<td class="note">{prefix}{esc(note)}</td>'
        else:
            note_html = '<td class="note"></td>'
        rows.append(
            f'<tr{cls} data-tool-id="{esc(tool["id"])}" data-known="{known}" data-trap="{trap}">'
            f'<th scope="row">{esc(display_tool_name(tool["name"]))}</th>'
            f"{cells_html}{note_html}</tr>"
        )
    return "\n".join(rows)


def platform_th(pid: str) -> str:
    brand, line = PLATFORM_HEADERS[pid]
    return (
        f'<th scope="col"><span class="plat-brand">{esc(brand)}</span>'
        f'<span class="plat-line">{esc(line)}</span></th>'
    )


def head(
    title: str,
    description: str,
    canonical_path: str,
    extra: str = "",
) -> str:
    canon = f"{BASE}/{canonical_path}" if canonical_path else f"{BASE}/"
    og_url = canon
    return f"""<!DOCTYPE html>
<html lang="en-AU">
<head>
<meta charset="utf-8">
<meta name="google-site-verification" content="{GSC}" />
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" href="favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="styles.css">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{esc(canon)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Which Pack">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{esc(og_url)}">
<meta property="og:image" content="{BASE}/og.png">
<meta property="og:locale" content="en_AU">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(description)}">
<meta name="twitter:image" content="{BASE}/og.png">
{extra}</head>"""


def site_header(current: str) -> str:
    def link(href: str, label: str, key: str) -> str:
        cur = ' aria-current="page"' if current == key else ""
        return f'<a href="{href}"{cur}>{label}</a>'

    return f"""<header class="site-header">
  <div class="header-inner">
    <a class="brand" href="index.html">
      <span class="brand-mark" aria-hidden="true">WP</span>
      <span>Which Pack<span class="brand-sub">AU cordless coverage</span></span>
    </a>
    <nav class="primary" aria-label="Primary">
      {link("index.html", "Matrix", "index")}
      {link("traps.html", "Traps", "traps")}
      {link("method.html", "Method", "method")}
      {link("disclosure.html", "Disclosure", "disclosure")}
    </nav>
  </div>
</header>"""


def site_footer(updated: str) -> str:
    return f"""<footer class="site-footer">
  <div class="footer-inner">
    <p>Data last verified {esc(updated)} from manufacturer AU pages. No prices shown. As an Amazon Associate I earn from qualifying purchases. Amazon links appear only on <strong>has</strong> cells. Ryobi is editorial only.</p>
    <p>Method: <code>has</code> requires an official AU PDP or catalog listing; <code>missing</code> means we confirmed that voltage line does not carry the type; everything else is <code>unknown</code>.</p>
    <div class="footer-nav">
      <a href="method.html">Method</a>
      <a href="traps.html">Traps</a>
      <a href="disclosure.html">Disclosure</a>
    </div>
  </div>
</footer>"""


HERO_SVG = """<svg class="hero-art" viewBox="0 0 420 200" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Illustration of a generic cordless drill, battery pack and tools">
  <rect x="0" y="0" width="420" height="200" rx="8" fill="#EEF0EC"/>
  <!-- battery pack -->
  <rect x="38" y="58" width="72" height="92" rx="6" fill="#FFF" stroke="#245C43" stroke-width="2.5"/>
  <rect x="52" y="48" width="44" height="14" rx="3" fill="#245C43"/>
  <rect x="50" y="78" width="48" height="10" rx="2" fill="#D8DED7"/>
  <rect x="50" y="96" width="48" height="10" rx="2" fill="#D8DED7"/>
  <rect x="50" y="114" width="48" height="10" rx="2" fill="#EDF7F0" stroke="#17603A" stroke-width="1.5"/>
  <!-- drill body -->
  <g transform="translate(140,40)">
    <rect x="70" y="48" width="110" height="46" rx="10" fill="#FFF" stroke="#202521" stroke-width="2.5"/>
    <rect x="168" y="58" width="48" height="26" rx="6" fill="#566159"/>
    <circle cx="205" cy="71" r="18" fill="none" stroke="#202521" stroke-width="3"/>
    <circle cx="205" cy="71" r="8" fill="#D8DED7"/>
    <path d="M95 94 L95 140 L125 140 L125 110 L145 110 L145 94 Z" fill="#FFF" stroke="#202521" stroke-width="2.5" stroke-linejoin="round"/>
    <rect x="102" y="70" width="28" height="14" rx="3" fill="#245C43"/>
  </g>
  <!-- circular saw silhouette -->
  <g transform="translate(300,55)">
    <circle cx="48" cy="55" r="42" fill="#FFF" stroke="#202521" stroke-width="2.5"/>
    <circle cx="48" cy="55" r="12" fill="#EEF0EC" stroke="#566159" stroke-width="2"/>
    <path d="M48 13 L52 55 L48 97 L44 55 Z" fill="#D8DED7"/>
    <path d="M13 55 L48 59 L83 55 L48 51 Z" fill="#D8DED7"/>
    <rect x="8" y="8" width="36" height="18" rx="4" fill="#FFF" stroke="#245C43" stroke-width="2"/>
  </g>
</svg>"""


def json_ld_home() -> str:
    data = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "WebSite",
                "name": "Which Pack",
                "url": f"{BASE}/",
                "description": "Australian cordless platform coverage matrix for Milwaukee, DeWalt, Makita and Ryobi.",
                "inLanguage": "en-AU",
            },
            {
                "@type": "WebPage",
                "name": "Before you buy a kit, check what else its platform can run.",
                "url": f"{BASE}/",
                "isPartOf": {"@type": "WebSite", "url": f"{BASE}/"},
                "inLanguage": "en-AU",
            },
        ],
    }
    return (
        '<script type="application/ld+json">'
        + json.dumps(data, separators=(",", ":"))
        + "</script>\n"
    )


def build_index(data: dict, tools: list[dict]) -> str:
    platforms = data["platforms"]
    updated = data.get("updated", "")
    thead = (
        "<tr><th scope=\"col\">Tool type</th>"
        + "".join(platform_th(p["id"]) for p in platforms)
        + "<th scope=\"col\">Notes</th></tr>"
    )
    tbody = render_matrix_rows(tools, platforms, updated)
    title = "Before you buy a kit — AU cordless platform coverage | Which Pack"
    desc = (
        "Compare Australian tool coverage across Milwaukee, DeWalt, Makita and Ryobi. "
        "See what's verified, what's missing and what still needs checking."
    )
    return f"""{head(title, desc, "", json_ld_home())}
<body>
{site_header("index")}
<main class="wrap">
  <section class="hero" aria-labelledby="hero-title">
    <div class="hero-copy">
      <h1 id="hero-title">Before you buy a kit, check what else its platform can run.</h1>
      <p class="lede">Compare Australian tool coverage across Milwaukee, DeWalt, Makita and Ryobi. See what's verified, what's missing and what still needs checking.</p>
      <p class="hero-actions"><a class="btn-primary" href="#controls">Choose your tools</a></p>
    </div>
    <figure class="hero-figure">
      {HERO_SVG}
      <figcaption>Illustration. Battery requirements vary.</figcaption>
    </figure>
  </section>

  <aside class="callout" aria-labelledby="traps-heading">
    <h2 id="traps-heading"><span class="badge">Important</span> Voltage &amp; FLEXVOLT traps</h2>
    <ul>
      <li>US chargers are typically 110–120V. AU is 230–240V. A plug adapter is not a transformer.</li>
      <li>DeWalt AU 18V XR is the same cell family often sold as 20V MAX in the US. Local SKUs use -XJ / -XE.</li>
      <li>DeWalt’s AU cordless table saw, track/plunge saw, SDS-MAX, and 230mm+ chop saw in this matrix are <strong>54V FLEXVOLT</strong>, not 18V XR.</li>
      <li>Some mowers and trimmers need two 18V packs — check the notes before you buy.</li>
      <li>Ryobi ONE+ in AU is Bunnings-exclusive. Shown for catalog honesty (not sold via our Amazon links).</li>
    </ul>
    <p class="callout-more"><a href="traps.html">Read all traps →</a></p>
  </aside>

  <p class="disclosure-banner" id="disclosure">As an Amazon Associate I earn from qualifying purchases. Affiliate relationships do not determine coverage results. <a href="disclosure.html">Full disclosure</a>.</p>

  <div class="legend" aria-label="Status legend">
    <span class="legend-title">Legend</span>
    <span class="pill has"><span class="status-ico" aria-hidden="true">✓</span> has — AU catalog/PDP found</span>
    <span class="pill missing"><span class="status-ico" aria-hidden="true">–</span> missing — confirmed not on that line</span>
    <span class="pill unknown"><span class="status-ico" aria-hidden="true">?</span> unknown — not verified</span>
  </div>

  <div class="toolbar filters" id="controls" role="group" aria-label="Filter and search tools">
    <label class="search-label" for="tool-search">Search</label>
    <input type="search" id="tool-search" name="q" placeholder="Filter tool types…" autocomplete="off">
    <span class="label">Show</span>
    <button type="button" data-f="all" class="on" aria-pressed="true">All tools</button>
    <button type="button" data-f="known" aria-pressed="false">Hide all-unknown</button>
    <button type="button" data-f="traps" aria-pressed="false">Rows with a trap note</button>
    <button type="button" data-f="selected" aria-pressed="false" id="btn-selected" hidden>Selected only</button>
  </div>
  <p class="scroll-hint">Swipe sideways on the matrix on smaller screens. Tool column stays put.</p>

  <div class="table-wrap" id="table" role="region" aria-label="Platform coverage matrix" tabindex="0">
    <table class="matrix" id="matrix">
      <thead>{thead}</thead>
      <tbody>
{tbody}
      </tbody>
    </table>
  </div>

  <p class="meta-row">
    <span>Updated {esc(updated)}</span>
    <span>{len(tools)} tool types × {len(platforms)} platforms</span>
    <span>Works with JavaScript off</span>
  </p>
</main>
{site_footer(updated)}
<script>
(function () {{
  var buttons = document.querySelectorAll('[data-f]');
  var rows = Array.prototype.slice.call(document.querySelectorAll('#matrix tbody tr'));
  var search = document.getElementById('tool-search');
  var btnSelected = document.getElementById('btn-selected');
  var mode = 'all';
  var selected = {{}};

  rows.forEach(function (tr) {{
    var th = tr.querySelector('th[scope="row"]');
    if (!th) return;
    var cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.className = 'pick';
    cb.title = 'Select tool';
    cb.setAttribute('aria-label', 'Select ' + th.textContent);
    cb.addEventListener('change', function () {{
      var id = tr.getAttribute('data-tool-id');
      if (cb.checked) selected[id] = true; else delete selected[id];
      btnSelected.hidden = Object.keys(selected).length === 0;
      if (mode === 'selected') apply();
    }});
    th.insertBefore(cb, th.firstChild);
  }});

  function apply() {{
    var q = (search && search.value || '').trim().toLowerCase();
    rows.forEach(function (tr) {{
      var show = true;
      if (mode === 'known') show = tr.getAttribute('data-known') === '1';
      if (mode === 'traps') show = tr.getAttribute('data-trap') === '1';
      if (mode === 'selected') show = !!selected[tr.getAttribute('data-tool-id')];
      if (q) {{
        var name = (tr.querySelector('th[scope="row"]') || {{}}).textContent || '';
        if (name.toLowerCase().indexOf(q) === -1) show = false;
      }}
      if (show) tr.removeAttribute('hidden');
      else tr.setAttribute('hidden', '');
    }});
  }}

  buttons.forEach(function (b) {{
    b.addEventListener('click', function () {{
      buttons.forEach(function (x) {{
        x.classList.remove('on');
        x.setAttribute('aria-pressed', 'false');
      }});
      b.classList.add('on');
      b.setAttribute('aria-pressed', 'true');
      mode = b.getAttribute('data-f');
      apply();
    }});
  }});
  if (search) search.addEventListener('input', apply);
}})();
</script>
</body>
</html>
"""


def build_traps(updated: str) -> str:
    title = "Voltage and SKU traps | Which Pack"
    desc = (
        "AU voltage, DeWalt FLEXVOLT vs 18V XR, dual-pack outdoor tools, and Ryobi "
        "Bunnings exclusivity — why a US battery list is not an AU buying tool."
    )
    return f"""{head(title, desc, "traps.html")}
<body>
{site_header("traps")}
<main class="wrap narrow">
  <div class="page-hero">
    <h1>Voltage and SKU traps</h1>
    <p class="lede">These are why a US “same battery family” list is not an AU buying tool. We do not give electrical install advice.</p>
  </div>
  <div class="card">
    <h2>240V chargers</h2>
    <p>US chargers are typically 110–120V. Australia is 230–240V. A plug adapter is not a transformer. Grey Amazon AU listings can ship the US charger.</p>
  </div>
  <div class="card">
    <h2>DeWalt naming</h2>
    <p>US 20V MAX tools are often the same cell family as AU 18V XR. Local SKUs use -XJ / -XE. Chargers usually are not interchangeable.</p>
  </div>
  <div class="card">
    <h2>FLEXVOLT vs 18V XR</h2>
    <p>DeWalt AU cordless jobsite table saw sampled {esc(updated)} is 54V FLEXVOLT DCS7485N-XJ, not 18V XR. The same class of trap applies to track/plunge saw, SDS-MAX, and dedicated 230mm+ chop/cut-off saws on the AU catalog.</p>
    <p>FLEXVOLT packs can run 18V XR tools; the reverse is not true for 54V-only machines.</p>
  </div>
  <div class="card">
    <h2>18V × 2 outdoor tools</h2>
    <p>Some mowers and line trimmers need two 18V packs (Milwaukee M18F2*, Makita 18Vx2, some Ryobi). Check the notes column before you buy a kit sized for a single pack.</p>
  </div>
  <div class="card">
    <h2>Ryobi AU</h2>
    <p>ONE+ in Australia is Bunnings-exclusive. We still show the catalog so the comparison is honest (editorial, not an affiliate link).</p>
  </div>
</main>
{site_footer(updated)}
</body>
</html>
"""


def build_method(updated: str) -> str:
    title = "How we score coverage | Which Pack"
    desc = (
        "How Which Pack scores has, missing, and unknown for AU cordless platforms. "
        "No prices. Verified from manufacturer AU pages."
    )
    return f"""{head(title, desc, "method.html")}
<body>
{site_header("method")}
<main class="wrap narrow prose">
  <div class="page-hero">
    <h1>How a cell is scored</h1>
    <p class="lede">Transparent rules. We never invent coverage.</p>
  </div>
  <ul>
    <li><strong>has</strong> — official AU manufacturer PDP or catalog listing, with a source URL, last verified {esc(updated)}.</li>
    <li><strong>missing</strong> — we confirmed that voltage line does not carry the type (example: DeWalt AU 18V XR has no jobsite table saw; the cordless saw is 54V FLEXVOLT).</li>
    <li><strong>unknown</strong> — not verified. We do not guess. Compact banding nailer is unknown on every platform; we do not treat duplex nailers or band saws as the same type.</li>
  </ul>
  <div class="card">
    <h2>What we do not show</h2>
    <p>No prices on this site. Amazon Associates Australia forbids stale self-displayed prices. Last data pass: {esc(updated)}.</p>
    <p>This is a structured comparison tool. Pages exist to support the matrix, not as SEO filler articles.</p>
  </div>
</main>
{site_footer(updated)}
</body>
</html>
"""


def build_disclosure(updated: str) -> str:
    title = "Affiliate disclosure | Which Pack"
    desc = (
        "Amazon Associates disclosure for Which Pack Australia. "
        "Associate ID whichpackau-22. Commission does not change coverage cells."
    )
    return f"""{head(title, desc, "disclosure.html")}
<body>
{site_header("disclosure")}
<main class="wrap narrow">
  <div class="page-hero">
    <h1>Affiliate disclosure</h1>
    <p class="lede">Clear about how this site is funded.</p>
  </div>
  <div class="card">
    <h2>Amazon Associates</h2>
    <p>Which Pack is a participant in the Amazon Services LLC Associates Program, an affiliate advertising program. As an Amazon Associate I earn from qualifying purchases. Associate ID: <code>whichpackau-22</code>.</p>
    <p>I may earn a commission from qualifying Amazon AU purchases when you use links on this site.</p>
  </div>
  <div class="card">
    <h2>Editorial independence</h2>
    <p>Affiliate relationships do not determine coverage results. Commission does not change <strong>has</strong> / <strong>missing</strong> / <strong>unknown</strong> cells. Ryobi ONE+ AU is editorial (Bunnings exclusive; no affiliate link). We do not show street prices. We do not track prices.</p>
  </div>
</main>
{site_footer(updated)}
</body>
</html>
"""


STYLES = """/* Which Pack — Astra tokens (2026-09-05) */
:root {
  --page: #F5F4EF;
  --surface: #FFFFFF;
  --text: #202521;
  --secondary: #566159;
  --border: #D8DED7;
  --accent: #245C43;
  --link: #215FA6;
  --focus: #245EEA;
  --has-text: #17603A;
  --has-fill: #EDF7F0;
  --miss-text: #454D46;
  --miss-fill: #EEF0EC;
  --unk-text: #765515;
  --unk-fill: #FFF5DC;
  --warn-bg: #FFF5DC;
  --warn-border: #E6D19A;
  --warn-fg: #765515;
  --warn-accent: #A67C1A;
  --radius: 8px;
  --radius-ctrl: 6px;
  --radius-label: 4px;
  --font: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
*, *::before, *::after { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  font: 16px/1.55 var(--font);
  background: var(--page);
  color: var(--text);
  -webkit-font-smoothing: antialiased;
}
a { color: var(--link); text-decoration-thickness: 1px; text-underline-offset: 2px; }
a:hover { color: var(--accent); }
a:focus-visible, button:focus-visible, input:focus-visible {
  outline: 2px solid var(--focus);
  outline-offset: 2px;
}
img, svg { display: block; max-width: 100%; }

.site-header {
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  z-index: 40;
}
.header-inner {
  max-width: 1180px;
  margin: 0 auto;
  padding: 14px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  color: inherit;
  text-decoration: none;
  font-weight: 650;
  letter-spacing: -0.02em;
}
.brand:hover { color: inherit; }
.brand-mark {
  width: 28px; height: 28px;
  border-radius: var(--radius-ctrl);
  background: var(--accent);
  color: #fff;
  display: grid;
  place-items: center;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}
.brand-sub {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: var(--secondary);
  letter-spacing: 0;
  margin-top: 1px;
}
nav.primary { display: flex; gap: 4px; flex-wrap: wrap; }
nav.primary a {
  color: var(--secondary);
  text-decoration: none;
  padding: 7px 11px;
  border-radius: var(--radius-ctrl);
  font-size: 14px;
  font-weight: 550;
}
nav.primary a:hover { background: var(--page); color: var(--text); }
nav.primary a[aria-current="page"] {
  background: var(--has-fill);
  color: var(--accent);
}

.wrap {
  max-width: 1180px;
  margin: 0 auto;
  padding: 28px 20px 56px;
}
.wrap.narrow { max-width: 760px; }

.hero {
  display: grid;
  grid-template-columns: 1.2fr 0.9fr;
  gap: 28px;
  align-items: center;
  margin: 0 0 28px;
}
.hero-copy h1 {
  font-size: clamp(1.45rem, 2.3vw, 1.95rem);
  line-height: 1.22;
  letter-spacing: -0.03em;
  margin: 0 0 12px;
  font-weight: 700;
}
.lede {
  color: var(--secondary);
  margin: 0 0 18px;
  max-width: 58ch;
  font-size: 1.05rem;
}
.hero-actions { margin: 0; }
.btn-primary {
  display: inline-block;
  background: var(--accent);
  color: #fff !important;
  text-decoration: none;
  font-weight: 600;
  font-size: 0.95rem;
  padding: 10px 16px;
  border-radius: var(--radius-ctrl);
}
.btn-primary:hover { filter: brightness(1.05); color: #fff !important; }
.hero-figure { margin: 0; }
.hero-figure figcaption {
  margin-top: 8px;
  font-size: 0.8rem;
  color: var(--secondary);
  text-align: center;
}
.hero-art { width: 100%; height: auto; border-radius: var(--radius); border: 1px solid var(--border); }

.page-hero h1 {
  font-size: clamp(1.45rem, 2.3vw, 1.9rem);
  line-height: 1.22;
  letter-spacing: -0.03em;
  margin: 0 0 10px;
  font-weight: 700;
}

.disclosure-banner {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 12px 16px;
  margin: 0 0 18px;
  font-size: 0.9rem;
  color: var(--secondary);
}
.disclosure-banner a { font-weight: 550; }

.callout {
  background: var(--warn-bg);
  border: 1px solid var(--warn-border);
  border-left: 4px solid var(--warn-accent);
  border-radius: var(--radius);
  padding: 16px 18px;
  margin: 0 0 20px;
}
.callout h2 {
  margin: 0 0 8px;
  font-size: 1rem;
  color: var(--warn-fg);
  display: flex;
  align-items: center;
  gap: 8px;
}
.callout h2 .badge {
  display: inline-block;
  background: var(--surface);
  border: 1px solid var(--warn-border);
  color: var(--warn-fg);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  padding: 2px 7px;
  border-radius: 999px;
}
.callout ul { margin: 0; padding-left: 1.15rem; }
.callout li { margin: 0.35rem 0; }
.callout-more { margin: 10px 0 0; font-size: 0.9rem; }

.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 14px;
  align-items: center;
  margin: 0 0 14px;
  font-size: 0.875rem;
}
.legend-title { color: var(--secondary); font-weight: 550; margin-right: 4px; }
.pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: var(--radius-label);
  border: 1px solid var(--border);
  background: var(--surface);
  font-weight: 550;
  font-size: 0.8rem;
}
.pill.has { background: var(--has-fill); color: var(--has-text); border-color: #C5DFCB; }
.pill.missing { background: var(--miss-fill); color: var(--miss-text); border-color: var(--border); }
.pill.unknown { background: var(--unk-fill); color: var(--unk-text); border-color: #E6D19A; }

.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin: 0 0 12px;
}
.toolbar .label, .search-label {
  font-size: 0.85rem;
  color: var(--secondary);
  font-weight: 550;
}
#tool-search {
  font: inherit;
  font-size: 0.875rem;
  padding: 7px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-ctrl);
  background: var(--surface);
  color: var(--text);
  min-width: 180px;
}
.filters button {
  appearance: none;
  background: var(--surface);
  color: var(--text);
  border: 1px solid var(--border);
  padding: 7px 12px;
  border-radius: var(--radius-ctrl);
  cursor: pointer;
  font: inherit;
  font-size: 0.875rem;
  font-weight: 550;
}
.filters button:hover { border-color: var(--accent); color: var(--accent); }
.filters button.on,
.filters button[aria-pressed="true"] {
  background: var(--has-fill);
  border-color: var(--accent);
  color: var(--accent);
}

.scroll-hint {
  display: none;
  font-size: 0.8rem;
  color: var(--secondary);
  margin: 0 0 8px;
}
@media (max-width: 900px) {
  .scroll-hint { display: block; }
  .hero { grid-template-columns: 1fr; }
}

/* Horizontal scroll only — NO fixed-height nested vertical trap */
.table-wrap {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow-x: auto;
  overflow-y: visible;
  -webkit-overflow-scrolling: touch;
  max-width: 100%;
}
table.matrix {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  font-size: 0.875rem;
  min-width: 980px;
}
.matrix th, .matrix td {
  border-bottom: 1px solid var(--border);
  border-right: 1px solid var(--border);
  padding: 10px 12px;
  text-align: left;
  vertical-align: top;
  background: var(--surface);
}
.matrix th:last-child, .matrix td:last-child { border-right: none; }
.matrix thead th {
  background: var(--page);
  position: sticky;
  top: 0;
  z-index: 2;
  font-size: 0.78rem;
  font-weight: 650;
  color: var(--text);
  box-shadow: inset 0 -1px 0 var(--border);
}
.plat-brand { display: block; font-weight: 700; }
.plat-line { display: block; font-weight: 500; color: var(--secondary); margin-top: 2px; font-size: 0.72rem; }
.matrix tbody th[scope="row"] {
  background: var(--page);
  font-weight: 600;
  color: var(--text);
  min-width: 150px;
  max-width: 190px;
  position: sticky;
  left: 0;
  z-index: 1;
  box-shadow: inset -1px 0 0 var(--border);
}
.matrix tbody th .pick {
  margin-right: 8px;
  vertical-align: middle;
}
.matrix tbody tr:last-child th,
.matrix tbody tr:last-child td { border-bottom: none; }
.matrix tbody tr:hover td,
.matrix tbody tr:hover th[scope="row"] { background: #F0F1EB; }
.matrix tbody tr.is-trap td.note {
  border-left: 3px solid var(--warn-accent);
}
.matrix tbody tr[hidden] { display: none; }

/* Status = small label only — no full-cell colouring */
.status {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-weight: 650;
  font-size: 0.72rem;
  letter-spacing: 0.02em;
  text-transform: uppercase;
  padding: 3px 8px;
  border-radius: var(--radius-label);
  border: 1px solid transparent;
}
.status-ico { font-size: 0.7rem; line-height: 1; }
.status.has { background: var(--has-fill); color: var(--has-text); border-color: #C5DFCB; }
.status.missing { background: var(--miss-fill); color: var(--miss-text); border-color: var(--border); }
.status.unknown { background: var(--unk-fill); color: var(--unk-text); border-color: #E6D19A; }

.req {
  margin-top: 6px;
  font-size: 0.72rem;
  color: var(--secondary);
  line-height: 1.35;
}
.details {
  margin-top: 6px;
  font-size: 0.72rem;
  color: var(--secondary);
  line-height: 1.4;
}
.details .model { font-family: var(--mono); color: var(--text); font-weight: 550; }
.details .src { color: var(--link); text-decoration: none; }
.details .src:hover { text-decoration: underline; }
.details .date { white-space: nowrap; }

a.amz {
  display: inline-block;
  margin-top: 6px;
  font-size: 0.75rem;
  font-weight: 550;
  color: var(--link);
  text-decoration: none;
  border-bottom: 1px solid transparent;
}
a.amz:hover { border-bottom-color: var(--link); }

.note {
  color: var(--secondary);
  font-size: 0.8rem;
  line-height: 1.45;
  max-width: 300px;
}
.note .trap-tag {
  display: inline-block;
  margin: 0 0 6px;
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--warn-fg);
  background: var(--surface);
  border: 1px solid var(--warn-border);
  padding: 2px 6px;
  border-radius: var(--radius-label);
}

.meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  margin: 16px 0 0;
  font-size: 0.85rem;
  color: var(--secondary);
}

.site-footer {
  border-top: 1px solid var(--border);
  background: var(--surface);
  margin-top: 8px;
}
.footer-inner {
  max-width: 1180px;
  margin: 0 auto;
  padding: 24px 20px 36px;
  color: var(--secondary);
  font-size: 0.875rem;
}
.footer-inner p { margin: 0 0 10px; max-width: 80ch; }
.footer-nav { display: flex; gap: 14px; flex-wrap: wrap; margin-top: 12px; }
.footer-nav a { color: var(--secondary); font-weight: 550; text-decoration: none; }
.footer-nav a:hover { color: var(--accent); }

.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px 18px;
  margin: 12px 0;
}
.card h2 {
  margin: 0 0 8px;
  font-size: 1.05rem;
  letter-spacing: -0.02em;
}
.card p { margin: 0; color: var(--secondary); }
.card p + p { margin-top: 8px; }

.prose ul { padding-left: 1.2rem; }
.prose li { margin: 0.45rem 0; }
.prose strong { color: var(--text); }

code {
  font-family: var(--mono);
  font-size: 0.85em;
  background: var(--miss-fill);
  padding: 1px 5px;
  border-radius: var(--radius-label);
}

@media (max-width: 600px) {
  .header-inner { padding: 12px 14px; }
  .wrap { padding: 20px 14px 40px; }
  .hero-copy h1, .page-hero h1 { font-size: 1.35rem; }
  #tool-search { min-width: 140px; width: 100%; }
}
"""

FAVICON = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" role="img" aria-label="Which Pack">
  <rect width="32" height="32" rx="7" fill="#245C43"/>
  <rect x="8" y="10" width="16" height="14" rx="2.5" fill="#F5F4EF"/>
  <rect x="11" y="7" width="10" height="4" rx="1.5" fill="#EDF7F0"/>
  <rect x="11" y="14" width="10" height="2.5" rx="1" fill="#245C43"/>
  <rect x="11" y="18.5" width="10" height="2.5" rx="1" fill="#D8DED7"/>
</svg>
"""

OG_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <rect width="1200" height="630" fill="#F5F4EF"/>
  <rect x="60" y="60" width="1080" height="510" rx="16" fill="#FFFFFF" stroke="#D8DED7" stroke-width="2"/>
  <text x="100" y="180" font-family="system-ui,Segoe UI,sans-serif" font-size="28" font-weight="600" fill="#245C43">Which Pack</text>
  <text x="100" y="260" font-family="system-ui,Segoe UI,sans-serif" font-size="48" font-weight="700" fill="#202521">Before you buy a kit,</text>
  <text x="100" y="320" font-family="system-ui,Segoe UI,sans-serif" font-size="48" font-weight="700" fill="#202521">check what else its platform can run.</text>
  <text x="100" y="390" font-family="system-ui,Segoe UI,sans-serif" font-size="24" fill="#566159">AU coverage · Milwaukee · DeWalt · Makita · Ryobi</text>
  <rect x="100" y="440" width="72" height="28" rx="4" fill="#EDF7F0"/>
  <text x="112" y="460" font-family="system-ui,Segoe UI,sans-serif" font-size="14" font-weight="700" fill="#17603A">HAS</text>
  <rect x="188" y="440" width="96" height="28" rx="4" fill="#EEF0EC"/>
  <text x="200" y="460" font-family="system-ui,Segoe UI,sans-serif" font-size="14" font-weight="700" fill="#454D46">MISSING</text>
  <rect x="300" y="440" width="104" height="28" rx="4" fill="#FFF5DC"/>
  <text x="312" y="460" font-family="system-ui,Segoe UI,sans-serif" font-size="14" font-weight="700" fill="#765515">UNKNOWN</text>
</svg>
"""


def _png_rgb(width: int, height: int, pixel_at) -> bytes:
    """Encode RGB PNG with stdlib only."""
    import struct
    import zlib

    rows = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            row += bytes(pixel_at(x, y))
        rows.append(bytes(row))
    raw = b"".join(rows)
    compressed = zlib.compress(raw, 9)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", compressed) + chunk(b"IEND", b"")


def write_og_png(svg_path: pathlib.Path, png_path: pathlib.Path) -> None:
    """Write og.svg plus a 1200x630 og.png."""
    (ROOT / "og.svg").write_text(OG_SVG, encoding="utf-8")
    # Prefer Chrome headless for crisp text from SVG
    import shutil
    import subprocess

    chrome = shutil.which("google-chrome") or shutil.which("google-chrome-stable") or shutil.which("chromium")
    if chrome:
        try:
            r = subprocess.run(
                [
                    chrome,
                    "--headless",
                    "--disable-gpu",
                    "--no-sandbox",
                    f"--window-size=1200,630",
                    f"--screenshot={png_path}",
                    svg_path.as_uri(),
                ],
                capture_output=True,
                timeout=60,
            )
            if r.returncode == 0 and png_path.exists() and png_path.stat().st_size > 1000:
                return
        except Exception:
            pass

    def hex_rgb(h: str):
        h = h.lstrip("#")
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

    PAGE, WHITE, BORDER = hex_rgb("#F5F4EF"), hex_rgb("#FFFFFF"), hex_rgb("#D8DED7")
    ACCENT, TEXT, SEC = hex_rgb("#245C43"), hex_rgb("#202521"), hex_rgb("#566159")
    HASF, MISSF, UNKF = hex_rgb("#EDF7F0"), hex_rgb("#EEF0EC"), hex_rgb("#FFF5DC")

    def pixel_at(x, y):
        c = PAGE
        if 60 <= x < 1140 and 60 <= y < 570:
            c = WHITE
            if x in (60, 1139) or y in (60, 569):
                c = BORDER
        if 100 <= x < 108 and 140 <= y < 168:
            c = ACCENT
        if 120 <= x < 300 and 148 <= y < 160:
            c = ACCENT
        if 100 <= x < 720 and 218 <= y < 234:
            c = TEXT
        if 100 <= x < 860 and 278 <= y < 294:
            c = TEXT
        if 100 <= x < 680 and 358 <= y < 370:
            c = SEC
        if 100 <= x < 172 and 430 <= y < 462:
            c = HASF
        if 188 <= x < 292 and 430 <= y < 462:
            c = MISSF
        if 308 <= x < 420 and 430 <= y < 462:
            c = UNKF
        return c

    png_path.write_bytes(_png_rgb(1200, 630, pixel_at))



def main() -> None:
    data = json.loads((ROOT / "coverage.json").read_text(encoding="utf-8"))
    tools = order_tools(data["tool_types"])
    assert len(tools) == 24, f"expected 24 tool types, got {len(tools)}"
    updated = data.get("updated", "")

    (ROOT / "styles.css").write_text(STYLES, encoding="utf-8")
    (ROOT / "favicon.svg").write_text(FAVICON, encoding="utf-8")
    (ROOT / "og.svg").write_text(OG_SVG, encoding="utf-8")
    write_og_png(ROOT / "og.svg", ROOT / "og.png")

    (ROOT / "index.html").write_text(build_index(data, tools), encoding="utf-8")
    (ROOT / "traps.html").write_text(build_traps(updated), encoding="utf-8")
    (ROOT / "method.html").write_text(build_method(updated), encoding="utf-8")
    (ROOT / "disclosure.html").write_text(build_disclosure(updated), encoding="utf-8")

    # sitemap
    sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>{BASE}/</loc><lastmod>{updated}</lastmod></url>
  <url><loc>{BASE}/traps.html</loc><lastmod>{updated}</lastmod></url>
  <url><loc>{BASE}/method.html</loc><lastmod>{updated}</lastmod></url>
  <url><loc>{BASE}/disclosure.html</loc><lastmod>{updated}</lastmod></url>
</urlset>
"""
    (ROOT / "sitemap.xml").write_text(sitemap, encoding="utf-8")

    # Validate SSR row count
    idx = (ROOT / "index.html").read_text(encoding="utf-8")
    n_rows = len(re.findall(r"<tr[^>]*data-known=", idx))
    assert n_rows == 24, f"index.html rows={n_rows}"
    assert "google-site-verification" in idx
    assert 'rel="canonical"' in idx
    assert "#F5F4EF" in (ROOT / "styles.css").read_text()
    assert "Before you buy a kit, check what else its platform can run." in idx
    assert "Amazon AU — Search" in idx or "Amazon AU — View" in idx
    # First data row should be circular saw (reorder check)
    first = re.search(r"<tbody>\s*<tr[^>]*>\s*<th scope=\"row\">([^<]+)", idx)
    assert first and first.group(1).strip() == "Circular Saw", first.group(1) if first else None
    # Missing must not use alarm red tokens in CSS
    css = (ROOT / "styles.css").read_text()
    assert "--miss-text: #454D46" in css
    assert "#8a2f2f" not in css.lower()

    sync_names = [
        "index.html",
        "traps.html",
        "method.html",
        "disclosure.html",
        "styles.css",
        "favicon.svg",
        "coverage.json",
        "og.svg",
    ]
    if (ROOT / "og.png").exists():
        sync_names.append("og.png")
    if MVP.exists():
        for name in sync_names:
            src = ROOT / name
            if src.exists():
                shutil.copy2(src, MVP / name)
        print(f"Synced {len(sync_names)} files to mvp")
    print(f"OK: {n_rows} rows, first={first.group(1)!r}, updated={updated}")


if __name__ == "__main__":
    main()
