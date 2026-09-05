#!/usr/bin/env python3
"""Regenerate Which Pack static site from coverage.json (Astra brief).

Usage: python3 build_site.py
Reads coverage.json in this directory, writes HTML/CSS/assets here,
writes blog-led homepage + matrix + posts, then syncs key files to /workspace/affiliate-business/mvp/.
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
                f"Amazon · {esc(label)}</a>"
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
      {link("blog.html", "Blog", "blog")}
      {link("matrix.html", "Matrix", "matrix")}
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
      <a href="blog.html">Blog</a>
      <a href="matrix.html">Matrix</a>
      <a href="traps.html">XR vs FlexVolt</a>
      <a href="makita-table-saw.html">Makita table saw</a>
      <a href="year-two-tools.html">Year-two tools</a>
      <a href="method.html">Method</a>
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

# Optional abstract SVG fallbacks (cards/featured now use /images/ stock photos). Written to /thumbs/ on build.
THUMB_FLEXVOLT_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 360" role="img" aria-label="Abstract illustration of two battery packs and a voltage gap">
  <defs>
    <linearGradient id="fvBg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#EEF0EC"/>
      <stop offset="100%" stop-color="#D8DED7"/>
    </linearGradient>
  </defs>
  <rect width="640" height="360" rx="16" fill="url(#fvBg)"/>
  <!-- small 18V pack -->
  <g transform="translate(88,96)">
    <rect x="0" y="24" width="120" height="168" rx="12" fill="#FFFFFF" stroke="#245C43" stroke-width="4"/>
    <rect x="28" y="0" width="64" height="28" rx="6" fill="#245C43"/>
    <rect x="24" y="56" width="72" height="16" rx="3" fill="#D8DED7"/>
    <rect x="24" y="84" width="72" height="16" rx="3" fill="#D8DED7"/>
    <rect x="24" y="112" width="72" height="28" rx="4" fill="#EDF7F0" stroke="#17603A" stroke-width="2"/>
    <text x="60" y="132" text-anchor="middle" font-family="system-ui,sans-serif" font-size="18" font-weight="700" fill="#17603A">18V</text>
  </g>
  <!-- gap / block -->
  <g transform="translate(268,150)">
    <circle cx="52" cy="40" r="40" fill="#FFF5DC" stroke="#E6D19A" stroke-width="3"/>
    <path d="M36 40 h32 M52 24 v32" stroke="#A67C1A" stroke-width="6" stroke-linecap="round" transform="rotate(45 52 40)"/>
    <text x="52" y="108" text-anchor="middle" font-family="system-ui,sans-serif" font-size="14" font-weight="700" fill="#765515">54V only</text>
  </g>
  <!-- taller FlexVolt-style pack (abstract, not branded) -->
  <g transform="translate(400,64)">
    <rect x="0" y="24" width="140" height="220" rx="14" fill="#FFFFFF" stroke="#202521" stroke-width="4"/>
    <rect x="34" y="0" width="72" height="28" rx="6" fill="#202521"/>
    <rect x="28" y="60" width="84" height="16" rx="3" fill="#D8DED7"/>
    <rect x="28" y="90" width="84" height="16" rx="3" fill="#D8DED7"/>
    <rect x="28" y="120" width="84" height="16" rx="3" fill="#D8DED7"/>
    <rect x="28" y="156" width="84" height="36" rx="4" fill="#FFF5DC" stroke="#A67C1A" stroke-width="2"/>
    <text x="70" y="180" text-anchor="middle" font-family="system-ui,sans-serif" font-size="20" font-weight="700" fill="#765515">54V</text>
  </g>
</svg>
"""

THUMB_TABLE_SAW_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 360" role="img" aria-label="Abstract illustration of a jobsite table saw silhouette">
  <defs>
    <linearGradient id="tsBg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#EDF7F0"/>
      <stop offset="100%" stop-color="#EEF0EC"/>
    </linearGradient>
  </defs>
  <rect width="640" height="360" rx="16" fill="url(#tsBg)"/>
  <!-- table top -->
  <rect x="80" y="150" width="480" height="28" rx="6" fill="#FFFFFF" stroke="#202521" stroke-width="3"/>
  <!-- fence -->
  <rect x="120" y="112" width="18" height="40" rx="3" fill="#245C43"/>
  <rect x="120" y="104" width="120" height="12" rx="3" fill="#245C43"/>
  <!-- blade -->
  <circle cx="320" cy="164" r="54" fill="#FFFFFF" stroke="#202521" stroke-width="4"/>
  <circle cx="320" cy="164" r="14" fill="#EEF0EC" stroke="#566159" stroke-width="3"/>
  <g stroke="#D8DED7" stroke-width="3" stroke-linecap="round">
    <path d="M320 114 L324 164 L320 214 L316 164 Z"/>
    <path d="M270 164 L320 168 L370 164 L320 160 Z"/>
    <path d="M285 129 L320 164 L355 199"/>
    <path d="M355 129 L320 164 L285 199"/>
  </g>
  <!-- stand -->
  <path d="M140 178 L180 300 L460 300 L500 178" fill="none" stroke="#566159" stroke-width="4" stroke-linejoin="round"/>
  <rect x="200" y="292" width="240" height="14" rx="4" fill="#245C43"/>
  <!-- missing badge -->
  <rect x="430" y="48" width="130" height="36" rx="8" fill="#EEF0EC" stroke="#454D46" stroke-width="2"/>
  <text x="495" y="72" text-anchor="middle" font-family="system-ui,sans-serif" font-size="16" font-weight="700" fill="#454D46">LXT gap</text>
</svg>
"""

THUMB_YEAR_TWO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 360" role="img" aria-label="Abstract illustration of a starter kit expanding into year-two tools">
  <defs>
    <linearGradient id="y2Bg" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#FFF5DC"/>
      <stop offset="100%" stop-color="#EEF0EC"/>
    </linearGradient>
  </defs>
  <rect width="640" height="360" rx="16" fill="url(#y2Bg)"/>
  <!-- year 1 kit box -->
  <g transform="translate(56,90)">
    <rect x="0" y="40" width="180" height="140" rx="12" fill="#FFFFFF" stroke="#245C43" stroke-width="4"/>
    <rect x="0" y="40" width="180" height="36" rx="12" fill="#245C43"/>
    <text x="90" y="64" text-anchor="middle" font-family="system-ui,sans-serif" font-size="16" font-weight="700" fill="#FFFFFF">Year 1 kit</text>
    <!-- mini drill -->
    <rect x="28" y="100" width="70" height="28" rx="6" fill="#EEF0EC" stroke="#202521" stroke-width="2"/>
    <rect x="90" y="106" width="28" height="16" rx="3" fill="#566159"/>
    <!-- mini impact -->
    <rect x="28" y="142" width="54" height="22" rx="5" fill="#EDF7F0" stroke="#17603A" stroke-width="2"/>
  </g>
  <!-- arrow -->
  <path d="M260 180 H340" stroke="#245C43" stroke-width="6" stroke-linecap="round"/>
  <path d="M328 164 L352 180 L328 196" fill="none" stroke="#245C43" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>
  <!-- year 2 tools -->
  <g transform="translate(380,70)">
    <text x="90" y="24" text-anchor="middle" font-family="system-ui,sans-serif" font-size="16" font-weight="700" fill="#765515">Year 2</text>
    <!-- table saw icon -->
    <rect x="0" y="48" width="80" height="56" rx="8" fill="#FFFFFF" stroke="#202521" stroke-width="3"/>
    <circle cx="40" cy="76" r="16" fill="#EEF0EC" stroke="#566159" stroke-width="2"/>
    <!-- track saw -->
    <rect x="100" y="48" width="80" height="56" rx="8" fill="#FFFFFF" stroke="#202521" stroke-width="3"/>
    <rect x="112" y="68" width="56" height="14" rx="3" fill="#245C43"/>
    <!-- SDS / hammer -->
    <rect x="0" y="124" width="80" height="56" rx="8" fill="#FFFFFF" stroke="#202521" stroke-width="3"/>
    <rect x="18" y="140" width="44" height="24" rx="4" fill="#FFF5DC" stroke="#A67C1A" stroke-width="2"/>
    <!-- dual pack outdoor -->
    <rect x="100" y="124" width="80" height="56" rx="8" fill="#FFFFFF" stroke="#202521" stroke-width="3"/>
    <rect x="112" y="140" width="22" height="28" rx="3" fill="#EDF7F0" stroke="#17603A" stroke-width="2"/>
    <rect x="146" y="140" width="22" height="28" rx="3" fill="#EDF7F0" stroke="#17603A" stroke-width="2"/>
  </g>
</svg>
"""

# Blog posts (trap landings kept as stable URLs; also listed on blog hub).
# Dates staggered within real publish window; sorted newest first in listings.
POSTS = [
    {
        "path": "year-two-tools.html",
        "title": "Before you buy a cordless kit in Australia, check year-two tools",
        "blurb": "Starter kits sell drills and impacts. Year two is table saws, track saws, SDS-MAX and dual-pack outdoor. Check coverage before you lock in.",
        "date": "2026-09-05",
        "nav": "blog",
        "thumb": "images/year-two.webp",
        "thumb_fallback": "images/year-two.jpg",
        "thumb_alt": "Construction worker with cordless circular saw, drill and clamps on a jobsite beam",
        "credit": "Stock photo via Unsplash (photo VLPUm5wP5Z0). Not an OEM product shot.",
        "theme": "year-two",
    },
    {
        "path": "traps.html",
        "title": "DeWalt XR vs FlexVolt in Australia: what an 18V kit can’t run",
        "blurb": "Table saw, track/plunge, SDS-MAX and 230mm+ chop on AU DeWalt sit on 54V FLEXVOLT. An XR pack won’t run those machines.",
        "date": "2026-09-04",
        "nav": "traps",
        "thumb": "images/flexvolt.webp",
        "thumb_fallback": "images/flexvolt.jpg",
        "thumb_alt": "Yellow and black DeWalt 20V MAX XR cordless drill on a workbench",
        "credit": "Stock photo via Unsplash (photo QvEXI1xquRY). Not an OEM product shot.",
        "theme": "flexvolt",
    },
    {
        "path": "makita-table-saw.html",
        "title": "Does Makita LXT have a cordless table saw in Australia?",
        "blurb": "Short answer: no on our matrix. Corded bench saws exist. Cordless LXT table saw does not. Milwaukee and Ryobi do have one.",
        "date": "2026-09-03",
        "nav": "traps",
        "thumb": "images/table-saw.webp",
        "thumb_fallback": "images/table-saw.jpg",
        "thumb_alt": "Person ripping plywood on a yellow portable jobsite table saw",
        "credit": "Stock photo via Pexels (photo 28518825). Not an OEM product shot.",
        "theme": "table-saw",
    },
]


def format_post_date(iso: str) -> str:
    """AU-friendly display date from YYYY-MM-DD."""
    months = (
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    )
    y, m, d = iso.split("-")
    return f"{int(d)} {months[int(m) - 1]} {y}"


def posts_newest_first() -> list[dict]:
    return sorted(POSTS, key=lambda p: (p["date"], p["path"]), reverse=True)


def post_by_path(path: str) -> dict | None:
    for p in POSTS:
        if p["path"] == path:
            return p
    return None


def featured_figure(post: dict) -> str:
    credit = post.get("credit") or "Stock photography. Not an OEM product shot."
    fallback = post.get("thumb_fallback")
    if fallback:
        img = (
            f'<picture>'
            f'<source srcset="{esc(post["thumb"])}" type="image/webp">'
            f'<img src="{esc(fallback)}" width="1280" height="720" '
            f'alt="{esc(post["thumb_alt"])}" loading="eager" decoding="async">'
            f'</picture>'
        )
    else:
        img = (
            f'<img src="{esc(post["thumb"])}" width="1280" height="720" '
            f'alt="{esc(post["thumb_alt"])}" loading="eager" decoding="async">'
        )
    return (
        f'<figure class="post-featured">'
        f'{img}'
        f'<figcaption>{esc(credit)}</figcaption>'
        f"</figure>"
    )


def post_list_html(posts: list[dict] | None = None, *, heading: str | None = None) -> str:
    posts = posts if posts is not None else posts_newest_first()
    items = []
    for p in posts:
        items.append(
            f"""<article class="post-card">
  <a class="post-card-media" href="{esc(p['path'])}" tabindex="-1" aria-hidden="true">
    <picture>
      <source srcset="{esc(p['thumb'])}" type="image/webp">
      <img src="{esc(p.get('thumb_fallback') or p['thumb'])}" width="1280" height="720" alt="" loading="lazy" decoding="async">
    </picture>
  </a>
  <div class="post-card-body">
    <p class="post-meta"><time datetime="{esc(p['date'])}">{esc(format_post_date(p['date']))}</time></p>
    <h2 class="post-title"><a href="{esc(p['path'])}">{esc(p['title'])}</a></h2>
    <p class="post-blurb">{esc(p['blurb'])}</p>
    <p class="post-more"><a href="{esc(p['path'])}">Read post →</a> · <a href="matrix.html">Check matrix →</a></p>
  </div>
</article>"""
        )
    head = f'<h2 class="section-label">{esc(heading)}</h2>\n' if heading else ""
    return head + '<div class="post-list">\n' + "\n".join(items) + "\n</div>"


def json_ld_home() -> str:
    data = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "WebSite",
                "name": "Which Pack",
                "url": f"{BASE}/",
                "description": "AU cordless coverage traps and platform matrix for Milwaukee, DeWalt, Makita and Ryobi.",
                "inLanguage": "en-AU",
            },
            {
                "@type": "WebPage",
                "name": "Which Pack: AU cordless coverage traps",
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


def build_home(updated: str) -> str:
    """Blog-led homepage. Matrix is linked as closer, not the hero."""
    title = "Which Pack: AU cordless coverage traps before you buy a kit"
    desc = (
        "Plain notes on AU cordless platform traps: FlexVolt vs XR, Makita table saw gaps, "
        "and year-two tools. Then check the coverage matrix."
    )
    posts_html = post_list_html(heading="Latest posts")
    return f"""{head(title, desc, "", json_ld_home())}
<body>
{site_header("blog")}
<main class="wrap">
  <section class="hero blog-hero" aria-labelledby="home-title">
    <div class="hero-copy">
      <p class="eyebrow">AU cordless coverage notes</p>
      <h1 id="home-title">AU cordless traps, before you buy the kit</h1>
      <p class="lede">I keep a living coverage matrix for Milwaukee, DeWalt, Makita and Ryobi in Australia. Start with the trap posts. When you know what you need in year two, <a href="matrix.html">check coverage</a>.</p>
      <p class="hero-actions"><a class="btn-primary" href="matrix.html">Check coverage</a> <a class="btn-ghost" href="blog.html">All posts</a></p>
    </div>
    <figure class="hero-figure">
      <picture>
        <source srcset="images/flexvolt.webp" type="image/webp">
        <img class="hero-photo" src="images/flexvolt.jpg" width="1280" height="720" alt="Yellow and black DeWalt 20V MAX XR cordless drill on a workbench" loading="eager" decoding="async">
      </picture>
      <figcaption>Stock photo via Unsplash. Not an OEM product shot.</figcaption>
    </figure>
  </section>

  <p class="disclosure-banner">As an Amazon Associate I earn from qualifying purchases. Affiliate relationships do not determine coverage results. <a href="disclosure.html">Full disclosure</a>.</p>

  {posts_html}

  <aside class="matrix-closer" aria-labelledby="matrix-closer-title">
    <h2 id="matrix-closer-title">Then check the matrix</h2>
    <p>Tool type × platform. Has, missing, or unknown from OEM AU pages. Amazon Search links only on verified <strong>has</strong> cells.</p>
    <p class="card-cta"><a class="cta-link" href="matrix.html">Open the AU coverage matrix →</a></p>
  </aside>
</main>
{site_footer(updated)}
</body>
</html>
"""


def build_blog(updated: str) -> str:
    title = "Blog: AU cordless coverage traps | Which Pack"
    desc = (
        "Posts on AU cordless platform traps: DeWalt XR vs FlexVolt, Makita LXT table saw, "
        "and year-two tools before you lock a kit."
    )
    posts_html = post_list_html(heading="All posts")
    return f"""{head(title, desc, "blog.html")}
<body>
{site_header("blog")}
<main class="wrap">
  <div class="page-hero blog-index-hero">
    <p class="eyebrow">Guides and coverage traps</p>
    <h1>Blog</h1>
    <p class="lede">Coverage traps and kit lock-in notes for Australia. Newest first. Not brand wars.</p>
  </div>
  {posts_html}
  <aside class="matrix-closer" aria-labelledby="blog-matrix-closer">
    <h2 id="blog-matrix-closer">Check the matrix</h2>
    <p>Has, missing, or unknown from OEM AU pages. Amazon Search links only on verified <strong>has</strong> cells.</p>
    <p class="card-cta"><a class="cta-link" href="matrix.html">Open the AU coverage matrix →</a></p>
  </aside>
</main>
{site_footer(updated)}
</body>
</html>
"""


def build_matrix(data: dict, tools: list[dict]) -> str:
    platforms = data["platforms"]
    updated = data.get("updated", "")
    thead = (
        "<tr><th scope=\"col\">Tool type</th>"
        + "".join(platform_th(p["id"]) for p in platforms)
        + "<th scope=\"col\">Notes</th></tr>"
    )
    tbody = render_matrix_rows(tools, platforms, updated)
    title = "AU cordless platform coverage matrix | Which Pack"
    desc = (
        "Compare Australian tool coverage across Milwaukee, DeWalt, Makita and Ryobi. "
        "See what's verified, what's missing and what still needs checking."
    )
    return f"""{head(title, desc, "matrix.html")}
<body>
{site_header("matrix")}
<main class="wrap">
  <section class="hero hero-compact" aria-labelledby="hero-title">
    <div class="hero-copy">
      <h1 id="hero-title">Before you buy a kit, check what else its platform can run.</h1>
      <p class="lede">Australian tool coverage across Milwaukee, DeWalt, Makita and Ryobi. Verified, missing, or still unknown.</p>
      <p class="hero-actions"><a class="btn-primary" href="#controls">Choose your tools</a> <a class="btn-ghost" href="blog.html">Read trap posts</a></p>
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
      <li>Some mowers and trimmers need two 18V packs. Check the notes before you buy.</li>
      <li>Ryobi ONE+ in AU is Bunnings-exclusive. Shown for catalog honesty (not sold via our Amazon links).</li>
    </ul>
    <p class="callout-more"><a href="traps.html">DeWalt XR vs FlexVolt traps →</a> · <a href="makita-table-saw.html">Makita LXT table saw?</a> · <a href="year-two-tools.html">Year-two tools</a></p>
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
    <button type="button" data-f="traps" aria-pressed="false" title="Rows with a trap note">Trap notes</button>
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


def tool_by_id(data: dict, tool_id: str) -> dict:
    for t in data["tool_types"]:
        if t["id"] == tool_id:
            return t
    raise KeyError(tool_id)


def oem_link(url: str, label: str | None = None) -> str:
    text = label or source_host(url)
    return (
        f'<a href="{esc(url)}" rel="noopener noreferrer">{esc(text)}</a>'
    )


def evidence_first(tool: dict, platform_id: str) -> str | None:
    cell = tool["cells"].get(platform_id) or {}
    ev = cell.get("evidence") or []
    return ev[0] if ev else None


def build_traps(data: dict) -> str:
    updated = data.get("updated", "")
    table = tool_by_id(data, "jobsite_table_saw")
    track = tool_by_id(data, "track_saw___plunge_saw")
    sdsmax = tool_by_id(data, "sds-max_rotary_hammer___breaker")
    chop = tool_by_id(data, "metal_cut-off___chop_saw")

    # Sampled FLEXVOLT models from coverage evidence (never invent).
    table_fv = evidence_first(table, "dewalt_flexvolt_au")
    track_fv = evidence_first(track, "dewalt_flexvolt_au")
    sds_fv = evidence_first(sdsmax, "dewalt_flexvolt_au")
    chop_fv = evidence_first(chop, "dewalt_flexvolt_au")

    title = "DeWalt XR vs FlexVolt in Australia: what an 18V kit can’t run | Which Pack"
    desc = (
        "AU coverage trap: DeWalt cordless table saw, track/plunge, SDS-MAX and 230mm+ "
        "chop sampled on FLEXVOLT 54V, not 18V XR. FLEXVOLT packs run XR tools; reverse fails on 54V-only machines."
    )
    return f"""{head(title, desc, "traps.html")}
<body>
{site_header("traps")}
<main class="wrap narrow article">
  <div class="page-hero article-hero">
    <p class="post-meta"><time datetime="2026-09-04">4 September 2026</time></p>
    <h1>DeWalt XR vs FlexVolt in Australia: what an 18V kit can’t run</h1>
    <p class="lede">On the AU catalog, several high-draw cordless types sit on <strong>54V FLEXVOLT</strong>, not 18V XR. FLEXVOLT packs can run XR tools; the reverse is not true for 54V-only machines. We list sampled OEM evidence only. No DIY electrical advice.</p>
  </div>
  {featured_figure(post_by_path("traps.html"))}

  <aside class="callout" aria-labelledby="fv-trap-summary">
    <h2 id="fv-trap-summary"><span class="badge">Coverage trap</span> 18V XR vs FLEXVOLT</h2>
    <ul>
      <li>Jobsite table saw, track/plunge saw, SDS-MAX, and dedicated 230mm+ chop/cut-off. Sampled DeWalt AU cordless models are <strong>FLEXVOLT</strong>, scored <code>missing</code> on 18V XR.</li>
      <li>FLEXVOLT packs can power 18V XR tools; an 18V XR pack cannot run a 54V-only machine.</li>
      <li>Verified {esc(updated)}. See the <a href="matrix.html">full coverage matrix</a>.</li>
    </ul>
  </aside>

  <div class="card">
    <h2>Jobsite table saw</h2>
    <p>DeWalt AU cordless table saw sampled is 54V FLEXVOLT (DCS7485N-XJ), not 18V XR. Scored <code>missing</code> on XR and <code>has</code> on FLEXVOLT.</p>
    <p>OEM evidence: {oem_link(table_fv) if table_fv else "see matrix"}.</p>
  </div>
  <div class="card">
    <h2>Track / plunge saw</h2>
    <p>Same class of trap: AU cordless track/plunge sampled is 54V FLEXVOLT (DCS520NT-XJ). 18V XR has circular saws, not a plunge/track saw in this matrix.</p>
    <p>OEM evidence: {oem_link(track_fv) if track_fv else "see matrix"}.</p>
  </div>
  <div class="card">
    <h2>SDS-MAX rotary hammer / breaker</h2>
    <p>DeWalt AU SDS-MAX hammers sampled are 54V FLEXVOLT (DCH614N-XJ). 18V XR rotary hammers on the AU catalog are SDS-plus. Scored <code>missing</code> for SDS-MAX on XR.</p>
    <p>OEM evidence: {oem_link(sds_fv) if sds_fv else "see matrix"}.</p>
  </div>
  <div class="card">
    <h2>Metal cut-off / 230mm+ chop saw</h2>
    <p>Dedicated 230mm+ abrasive chop/cut-off sampled is 54V FLEXVOLT (DCS691N-XJ). 18V XR has a 76mm compact cut-off tool, not counted as this type.</p>
    <p>OEM evidence: {oem_link(chop_fv) if chop_fv else "see matrix"}.</p>
  </div>

  <div class="card">
    <h2>What still works on 18V XR</h2>
    <p>Many common types are <code>has</code> on DeWalt 18V XR in the matrix (circular, recip, jigsaw, SDS-plus, framing nailer, and more). The trap is assuming every “cordless DeWalt” type runs on the XR pack you already own.</p>
    <p class="card-cta"><a class="cta-link" href="matrix.html">Open the AU coverage matrix →</a></p>
  </div>

  <div class="card">
    <h2>240V chargers &amp; naming</h2>
    <p>US chargers are typically 110–120V; Australia is 230–240V. A plug adapter is not a transformer. Grey Amazon AU listings can ship the US charger.</p>
    <p>US 20V MAX tools are often the same cell family as AU 18V XR. Local SKUs use -XJ / -XE. Chargers usually are not interchangeable.</p>
  </div>
  <div class="card">
    <h2>18V × 2 outdoor tools</h2>
    <p>Some mowers and line trimmers need two 18V packs (Milwaukee M18F2*, Makita 18Vx2, some Ryobi). Check the notes column before you buy a kit sized for a single pack. DeWalt AU lawn mowers exist on both 2×18V XR and 54V FLEXVOLT, not an XR-missing trap.</p>
  </div>
  <div class="card">
    <h2>Ryobi AU</h2>
    <p>ONE+ in Australia is Bunnings-exclusive. We still show the catalog so the comparison is honest (editorial, not an affiliate link).</p>
  </div>
  <div class="card">
    <h2>Related</h2>
    <p><a href="makita-table-saw.html">Does Makita LXT have a cordless table saw in Australia?</a> · <a href="year-two-tools.html">Year-two tools</a> · <a href="matrix.html">Coverage matrix</a> · <a href="blog.html">Blog</a></p>
  </div>
</main>
{site_footer(updated)}
</body>
</html>
"""


def build_makita_table_saw(data: dict) -> str:
    updated = data.get("updated", "")
    tool = tool_by_id(data, "jobsite_table_saw")
    cells = tool["cells"]

    def status_of(pid: str) -> str:
        return (cells.get(pid) or {}).get("status") or "unknown"

    def ev(pid: str) -> str | None:
        return evidence_first(tool, pid)

    # Facts only from coverage jobsite_table_saw
    assert status_of("makita_lxt_au") == "missing"
    assert status_of("m18_au") == "has"
    assert status_of("dewalt_18v_au") == "missing"
    assert status_of("dewalt_flexvolt_au") == "has"
    assert status_of("ryobi_one_au") == "has"

    makita_ev = ev("makita_lxt_au")
    m18_ev = ev("m18_au")
    dw18_ev = ev("dewalt_18v_au")
    dwfv_ev = ev("dewalt_flexvolt_au")
    ryobi_ev = ev("ryobi_one_au")

    title = "Does Makita LXT have a cordless table saw in Australia? | Which Pack"
    desc = (
        "Makita LXT AU has no cordless jobsite table saw in our matrix (corded bench saws only). "
        "Milwaukee M18 and Ryobi ONE+ have; DeWalt cordless sits on FLEXVOLT 54V, not 18V XR."
    )
    return f"""{head(title, desc, "makita-table-saw.html")}
<body>
{site_header("traps")}
<main class="wrap narrow article">
  <div class="page-hero article-hero">
    <p class="post-meta"><time datetime="2026-09-03">3 September 2026</time></p>
    <h1>Does Makita LXT have a cordless table saw in Australia?</h1>
    <p class="lede"><strong>No</strong>. In our AU matrix, Makita LXT is <code>missing</code> for jobsite table saw. Corded bench saws exist on Makita AU; cordless LXT table saws do not (catalog check last verified {esc(updated)}).</p>
  </div>
  {featured_figure(post_by_path("makita-table-saw.html"))}

  <div class="card">
    <h2>Short answer by platform</h2>
    <ul>
      <li><strong>Makita LXT 18V (AU)</strong>: <code>missing</code>{(" · " + oem_link(makita_ev, "LXT saws / corded table-saw evidence")) if makita_ev else ""}</li>
      <li><strong>Milwaukee M18 (AU)</strong>: <code>has</code>{(" · " + oem_link(m18_ev)) if m18_ev else ""}</li>
      <li><strong>DeWalt 18V XR (AU)</strong>: <code>missing</code> (cordless sampled is FLEXVOLT){(" · " + oem_link(dw18_ev)) if dw18_ev else ""}</li>
      <li><strong>DeWalt FLEXVOLT 54V (AU)</strong>: <code>has</code>{(" · " + oem_link(dwfv_ev)) if dwfv_ev else ""}</li>
      <li><strong>Ryobi ONE+ 18V (AU)</strong>: <code>has</code> (editorial; Bunnings-exclusive){(" · " + oem_link(ryobi_ev)) if ryobi_ev else ""}</li>
    </ul>
  </div>

  <div class="card">
    <h2>Why this matters before a kit buy</h2>
    <p>If a cordless table saw is on your must-have list, LXT alone will not cover it in Australia on current verified data. DeWalt buyers hit a related trap: the cordless AU table saw is FLEXVOLT, not 18V XR.</p>
    <p><a href="matrix.html">See every tool type on the coverage matrix →</a></p>
    <p class="card-cta"><a class="cta-link" href="traps.html">DeWalt XR vs FlexVolt: what 18V packs can’t run →</a></p>
  </div>

  <p class="disclosure-banner">As an Amazon Associate I earn from qualifying purchases. Affiliate relationships do not determine coverage results. <a href="disclosure.html">Full disclosure</a>.</p>
</main>
{site_footer(updated)}
</body>
</html>
"""



def build_year_two(data: dict) -> str:
    """Third post: year-two tools before kit lock-in. Facts from coverage only."""
    updated = data.get("updated", "")
    table = tool_by_id(data, "jobsite_table_saw")
    track = tool_by_id(data, "track_saw___plunge_saw")
    sdsmax = tool_by_id(data, "sds-max_rotary_hammer___breaker")
    trimmer = tool_by_id(data, "outdoor_string___line_trimmer")
    mower = tool_by_id(data, "18v-platform_lawn_mower")

    def st(tool: dict, pid: str) -> str:
        return (tool["cells"].get(pid) or {}).get("status") or "unknown"

    # Sanity: do not invent; assert known trap cells still hold
    assert st(table, "makita_lxt_au") == "missing"
    assert st(table, "dewalt_18v_au") == "missing"
    assert st(table, "dewalt_flexvolt_au") == "has"
    assert st(track, "dewalt_18v_au") == "missing"
    assert st(sdsmax, "dewalt_18v_au") == "missing"

    title = "Before you buy a cordless kit in Australia, check year-two tools | Which Pack"
    desc = (
        "Starter kits sell drills and impacts. Year-two tools (table saw, track saw, SDS-MAX, "
        "dual-pack outdoor) are where AU platforms diverge. Check coverage before you lock in."
    )
    return f"""{head(title, desc, "year-two-tools.html")}
<body>
{site_header("blog")}
<main class="wrap narrow article">
  <div class="page-hero article-hero">
    <p class="post-meta"><time datetime="2026-09-05">5 September 2026</time></p>
    <h1>Before you buy a cordless kit in Australia, check year-two tools</h1>
    <p class="lede">The kit box is drills, impacts, maybe a circular saw. Year two is when you want a table saw, track saw, SDS-MAX, or a mower. That is where platforms diverge in Australia.</p>
  </div>
  {featured_figure(post_by_path("year-two-tools.html"))}

  <div class="card">
    <h2>One finding</h2>
    <p>Buy for the tools you will need after the kit, not just what is in the foam. On our AU matrix, some common year-two types are <code>missing</code> on the 18V line you thought you were buying.</p>
  </div>

  <div class="card">
    <h2>Examples from the matrix</h2>
    <ul>
      <li><strong>Jobsite table saw</strong>. Makita LXT and DeWalt 18V XR are <code>missing</code>. DeWalt cordless sits on FLEXVOLT 54V. Milwaukee M18 and Ryobi ONE+ are <code>has</code>.</li>
      <li><strong>Track / plunge saw</strong>. DeWalt AU cordless sampled is FLEXVOLT, scored <code>missing</code> on 18V XR.</li>
      <li><strong>SDS-MAX</strong>. DeWalt AU sampled on FLEXVOLT. 18V XR hammers on the catalog are SDS-plus.</li>
      <li><strong>Outdoor</strong>. Some Milwaukee and Makita trimmers/mowers need two 18V packs. Check the notes before you size a kit for one battery.</li>
    </ul>
    <p>Verified {esc(updated)} from manufacturer AU pages. We do not invent cells.</p>
  </div>

  <div class="card">
    <h2>What to do</h2>
    <p>List the year-two tools you actually want. Open the matrix. If a must-have is <code>missing</code> or only on a higher-voltage line, factor that in before you commit packs.</p>
    <p class="card-cta"><a class="cta-link" href="matrix.html">Check coverage →</a></p>
    <p>Related: <a href="traps.html">DeWalt XR vs FlexVolt</a> · <a href="makita-table-saw.html">Makita LXT table saw?</a></p>
  </div>

  <p class="disclosure-banner">As an Amazon Associate I earn from qualifying purchases. Amazon Search links live on the matrix for verified <strong>has</strong> cells only. <a href="disclosure.html">Full disclosure</a>.</p>
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
    <p>Structured comparison first. Blog posts explain the traps. The matrix is where you check the full catalog.</p>
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
.matrix thead th:first-child {
  left: 0;
  z-index: 3;
  box-shadow: inset -1px 0 0 var(--border), inset 0 -1px 0 var(--border);
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
  display: inline-flex;
  align-items: center;
  margin-top: 6px;
  font-size: 0.75rem;
  font-weight: 550;
  color: var(--link);
  text-decoration: none;
  border-bottom: 1px solid transparent;
  white-space: nowrap;
  min-height: 32px;
  max-width: 100%;
}
a.amz:hover { border-bottom-color: var(--link); }

.cta-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-height: 44px;
  font-weight: 650;
  font-size: 0.95rem;
  color: var(--accent);
  text-decoration: none;
  border-bottom: 2px solid var(--accent);
  padding: 4px 0;
}
.cta-link:hover { color: var(--link); border-bottom-color: var(--link); }
.card-cta { margin-top: 12px !important; }

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
  .header-inner {
    padding: 10px 14px;
    gap: 8px;
  }
  .brand-sub { display: none; }
  nav.primary {
    width: 100%;
    gap: 2px;
  }
  nav.primary a {
    display: inline-flex;
    align-items: center;
    min-height: 40px;
    padding: 8px 10px;
    font-size: 13px;
  }
  .wrap { padding: 18px 14px 48px; }
  .hero {
    gap: 14px;
    margin: 0 0 22px;
  }
  .hero-copy h1, .page-hero h1 {
    font-size: 1.4rem;
    line-height: 1.25;
  }
  .lede {
    font-size: 0.98rem;
    margin-bottom: 14px;
  }
  .btn-primary {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-height: 44px;
    padding: 12px 18px;
    font-size: 1rem;
  }
  .hero-figure { margin-top: 2px; }
  .hero-art { max-height: 148px; width: auto; margin-inline: auto; }
  .callout { padding: 14px; }
  .callout-more a {
    display: inline-flex;
    align-items: center;
    min-height: 40px;
    font-weight: 600;
  }
  .disclosure-banner { padding: 12px 14px; font-size: 0.88rem; }
  .legend { gap: 8px 10px; }
  .toolbar.filters {
    gap: 8px;
    align-items: stretch;
  }
  .search-label, .toolbar .label {
    flex: 0 0 auto;
  }
  #tool-search {
    min-width: 0;
    width: 100%;
    flex: 1 1 100%;
    min-height: 44px;
    font-size: 16px; /* avoid iOS focus zoom */
    padding: 10px 12px;
  }
  .filters button {
    min-height: 44px;
    padding: 10px 12px;
    flex: 1 1 calc(50% - 8px);
  }
  .scroll-hint { margin-bottom: 10px; }
  /* Horizontal scroll only — grow with content, no fixed-height trap */
  .table-wrap {
    overflow-x: auto;
    overflow-y: visible;
    border-radius: var(--radius);
    /* subtle edge cue that more columns exist */
    background:
      linear-gradient(to right, var(--surface) 30%, transparent) left center / 24px 100% no-repeat local,
      linear-gradient(to left, var(--surface) 30%, transparent) right center / 24px 100% no-repeat local,
      linear-gradient(to right, rgba(32,37,33,0.08), transparent) left center / 12px 100% no-repeat scroll,
      linear-gradient(to left, rgba(32,37,33,0.08), transparent) right center / 12px 100% no-repeat scroll,
      var(--surface);
  }
  table.matrix {
    min-width: 900px;
    font-size: 0.8125rem;
  }
  .matrix th, .matrix td { padding: 10px; }
  .matrix tbody th[scope="row"] {
    min-width: 128px;
    max-width: 148px;
    font-size: 0.8rem;
    line-height: 1.3;
    /* sit under compact sticky header */
  }
  .matrix thead th {
    /* compact header ~52px after brand-sub hidden */
    top: 52px;
    font-size: 0.7rem;
    z-index: 4;
  }
  .matrix thead th:first-child {
    z-index: 5;
    left: 0;
  }
  .matrix tbody th[scope="row"] {
    z-index: 3;
    box-shadow: 4px 0 8px -4px rgba(32,37,33,0.12), inset -1px 0 0 var(--border);
  }
  .matrix tbody th .pick {
    width: 18px;
    height: 18px;
    margin-right: 8px;
    flex-shrink: 0;
  }
  a.amz {
    min-height: 40px;
    font-size: 0.78rem;
  }
  .note { max-width: 220px; font-size: 0.76rem; }
  .card { padding: 16px 14px; }
  .card h2 { font-size: 1.02rem; }
  .page-hero { margin-bottom: 8px; }
  .footer-inner { padding: 20px 14px 32px; }
}

/* Blog-led homepage + visual post cards */
.btn-ghost {
  display: inline-block;
  margin-left: 10px;
  color: var(--accent) !important;
  text-decoration: none;
  font-weight: 600;
  font-size: 0.95rem;
  padding: 10px 14px;
  border-radius: var(--radius-ctrl);
  border: 1px solid var(--border);
  background: var(--surface);
}
.btn-ghost:hover { border-color: var(--accent); }
.eyebrow {
  margin: 0 0 8px;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--accent);
}
.blog-hero { margin-bottom: 22px; }
.blog-index-hero { margin-bottom: 8px; }
.section-label {
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--secondary);
  margin: 8px 0 12px;
  font-weight: 700;
}
.post-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 18px;
  margin: 0 0 28px;
}
.post-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  height: 100%;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}
.post-card:hover {
  border-color: #B7C4B8;
  box-shadow: 0 6px 18px rgba(32, 37, 33, 0.06);
}
.post-card-media {
  display: block;
  background: var(--miss-fill);
  aspect-ratio: 16 / 9;
  overflow: hidden;
}
.post-card-media picture,
.post-featured picture {
  display: block;
  width: 100%;
  height: 100%;
}
.post-card-media img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.hero-figure .hero-photo {
  width: 100%;
  height: auto;
  aspect-ratio: 16 / 9;
  object-fit: cover;
  border-radius: calc(var(--radius) - 2px);
  background: var(--miss-fill);
}
.post-card-body {
  padding: 16px 18px 18px;
  display: flex;
  flex-direction: column;
  flex: 1;
}
.post-meta {
  margin: 0 0 6px;
  font-size: 0.8rem;
  color: var(--secondary);
}
.post-title {
  margin: 0 0 8px;
  font-size: 1.12rem;
  letter-spacing: -0.02em;
  line-height: 1.3;
  font-weight: 700;
}
.post-title a {
  color: var(--text);
  text-decoration: none;
}
.post-title a:hover { color: var(--accent); }
.post-blurb {
  margin: 0;
  color: var(--secondary);
  font-size: 0.96rem;
  flex: 1;
}
.post-more {
  margin: 14px 0 0;
  font-size: 0.9rem;
  font-weight: 600;
}
.post-more a { text-decoration: none; }
.post-featured {
  margin: 0 0 22px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}
.post-featured img {
  width: 100%;
  height: auto;
  aspect-ratio: 16 / 9;
  object-fit: cover;
  background: var(--miss-fill);
}
.post-featured figcaption {
  margin: 0;
  padding: 8px 12px 10px;
  font-size: 0.78rem;
  color: var(--secondary);
}
.article .article-hero h1 { margin-bottom: 10px; }
.article .card { margin-bottom: 14px; }
.matrix-closer {
  background: var(--has-fill);
  border: 1px solid #C5DFCB;
  border-radius: var(--radius);
  padding: 18px 20px;
  margin: 8px 0 12px;
}
.matrix-closer h2 {
  margin: 0 0 8px;
  font-size: 1.1rem;
  letter-spacing: -0.02em;
}
.matrix-closer p { margin: 0; color: var(--secondary); }
.matrix-closer .card-cta { margin-top: 10px; }
.hero-compact { margin-bottom: 20px; }
@media (max-width: 720px) {
  .post-list { grid-template-columns: 1fr; gap: 14px; }
}
@media (max-width: 600px) {
  .btn-ghost {
    display: inline-flex;
    margin: 10px 0 0;
    min-height: 44px;
    align-items: center;
  }
  .post-card-body { padding: 14px 14px 16px; }
  .post-title { font-size: 1.05rem; }
  .post-more a {
    display: inline-flex;
    align-items: center;
    min-height: 40px;
  }
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
    """Encode RGB PNG with stdlib only (filter-none rows)."""
    import struct
    import zlib

    rows = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            row += bytes(pixel_at(x, y))
        rows.append(bytes(row))
    return _png_rgb_bytes(width, height, b"".join(rows))


def _png_rgb_bytes(width: int, height: int, raw_rows: bytes) -> bytes:
    """Encode pre-built filter-0 row bytes (each row starts with 0)."""
    import struct
    import zlib

    compressed = zlib.compress(raw_rows, 9)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", compressed) + chunk(b"IEND", b"")


def _png_ihdr_size(png_path: pathlib.Path) -> tuple[int, int] | None:
    """Return (width, height) from PNG IHDR, or None if unreadable."""
    import struct

    try:
        data = png_path.read_bytes()
    except OSError:
        return None
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    # First chunk should be IHDR
    if data[12:16] != b"IHDR":
        return None
    w, h = struct.unpack(">II", data[16:24])
    return w, h


# Compact 5x7 glyphs for OG card text (no external fonts / Chrome).
_OG_GLYPHS: dict[str, list[int]] = {
    " ": [0, 0, 0, 0, 0, 0, 0],
    "A": [0b01110, 0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0b10001],
    "B": [0b11110, 0b10001, 0b10001, 0b11110, 0b10001, 0b10001, 0b11110],
    "C": [0b01110, 0b10001, 0b10000, 0b10000, 0b10000, 0b10001, 0b01110],
    "D": [0b11110, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b11110],
    "E": [0b11111, 0b10000, 0b10000, 0b11110, 0b10000, 0b10000, 0b11111],
    "F": [0b11111, 0b10000, 0b10000, 0b11110, 0b10000, 0b10000, 0b10000],
    "G": [0b01110, 0b10001, 0b10000, 0b10111, 0b10001, 0b10001, 0b01110],
    "H": [0b10001, 0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0b10001],
    "I": [0b01110, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110],
    "K": [0b10001, 0b10010, 0b10100, 0b11000, 0b10100, 0b10010, 0b10001],
    "L": [0b10000, 0b10000, 0b10000, 0b10000, 0b10000, 0b10000, 0b11111],
    "M": [0b10001, 0b11011, 0b10101, 0b10001, 0b10001, 0b10001, 0b10001],
    "N": [0b10001, 0b11001, 0b10101, 0b10011, 0b10001, 0b10001, 0b10001],
    "O": [0b01110, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110],
    "P": [0b11110, 0b10001, 0b10001, 0b11110, 0b10000, 0b10000, 0b10000],
    "R": [0b11110, 0b10001, 0b10001, 0b11110, 0b10100, 0b10010, 0b10001],
    "S": [0b01111, 0b10000, 0b10000, 0b01110, 0b00001, 0b00001, 0b11110],
    "T": [0b11111, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100],
    "U": [0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110],
    "V": [0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01010, 0b00100],
    "W": [0b10001, 0b10001, 0b10001, 0b10101, 0b10101, 0b10101, 0b01010],
    "X": [0b10001, 0b10001, 0b01010, 0b00100, 0b01010, 0b10001, 0b10001],
    "Y": [0b10001, 0b10001, 0b01010, 0b00100, 0b00100, 0b00100, 0b00100],
    "a": [0, 0b01110, 0b00001, 0b01111, 0b10001, 0b10001, 0b01111],
    "b": [0b10000, 0b10000, 0b11110, 0b10001, 0b10001, 0b10001, 0b11110],
    "c": [0, 0b01110, 0b10001, 0b10000, 0b10000, 0b10001, 0b01110],
    "d": [0b00001, 0b00001, 0b01111, 0b10001, 0b10001, 0b10001, 0b01111],
    "e": [0, 0b01110, 0b10001, 0b11111, 0b10000, 0b10001, 0b01110],
    "f": [0b00110, 0b01001, 0b01000, 0b11100, 0b01000, 0b01000, 0b01000],
    "g": [0, 0b01111, 0b10001, 0b10001, 0b01111, 0b00001, 0b01110],
    "h": [0b10000, 0b10000, 0b11110, 0b10001, 0b10001, 0b10001, 0b10001],
    "i": [0b00100, 0, 0b01100, 0b00100, 0b00100, 0b00100, 0b01110],
    "k": [0b10000, 0b10000, 0b10010, 0b10100, 0b11000, 0b10100, 0b10010],
    "l": [0b01100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110],
    "m": [0, 0b11010, 0b10101, 0b10101, 0b10101, 0b10101, 0b10101],
    "n": [0, 0b11110, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001],
    "o": [0, 0b01110, 0b10001, 0b10001, 0b10001, 0b10001, 0b01110],
    "p": [0, 0b11110, 0b10001, 0b10001, 0b11110, 0b10000, 0b10000],
    "r": [0, 0b10110, 0b11001, 0b10000, 0b10000, 0b10000, 0b10000],
    "s": [0, 0b01111, 0b10000, 0b01110, 0b00001, 0b00001, 0b11110],
    "t": [0b01000, 0b01000, 0b11100, 0b01000, 0b01000, 0b01001, 0b00110],
    "u": [0, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b01111],
    "v": [0, 0b10001, 0b10001, 0b10001, 0b10001, 0b01010, 0b00100],
    "w": [0, 0b10001, 0b10001, 0b10101, 0b10101, 0b10101, 0b01010],
    "x": [0, 0b10001, 0b01010, 0b00100, 0b00100, 0b01010, 0b10001],
    "y": [0, 0b10001, 0b10001, 0b10001, 0b01111, 0b00001, 0b01110],
    "z": [0, 0b11111, 0b00010, 0b00100, 0b01000, 0b10000, 0b11111],
    ",": [0, 0, 0, 0, 0, 0b00100, 0b01000],
    ".": [0, 0, 0, 0, 0, 0b00100, 0b00100],
    "·": [0, 0, 0b00100, 0, 0, 0, 0],
    "-": [0, 0, 0, 0b11111, 0, 0, 0],
    "+": [0, 0b00100, 0b00100, 0b11111, 0b00100, 0b00100, 0],
}


def _build_og_png_bytes() -> bytes:
    """1200x630 Astra-warm OG card with original copy (stdlib only)."""
    import random

    def hex_rgb(h: str) -> tuple[int, int, int]:
        h = h.lstrip("#")
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

    W, H = 1200, 630
    PAGE, WHITE, BORDER = hex_rgb("#F5F4EF"), hex_rgb("#FFFFFF"), hex_rgb("#D8DED7")
    ACCENT, TEXT, SEC = hex_rgb("#245C43"), hex_rgb("#202521"), hex_rgb("#566159")
    HASF, HAS_T = hex_rgb("#EDF7F0"), hex_rgb("#17603A")
    MISSF, MISS_T = hex_rgb("#EEF0EC"), hex_rgb("#454D46")
    UNKF, UNK_T = hex_rgb("#FFF5DC"), hex_rgb("#765515")

    buf = bytearray(W * H * 3)

    def fill_rect(x0: int, y0: int, x1: int, y1: int, c: tuple[int, int, int]) -> None:
        r, g, b = c
        for y in range(max(0, y0), min(H, y1)):
            o = y * W * 3
            for x in range(max(0, x0), min(W, x1)):
                i = o + x * 3
                buf[i] = r
                buf[i + 1] = g
                buf[i + 2] = b

    def blend_px(x: int, y: int, c: tuple[int, int, int], a: float) -> None:
        if not (0 <= x < W and 0 <= y < H):
            return
        i = (y * W + x) * 3
        inv = 1.0 - a
        buf[i] = int(buf[i] * inv + c[0] * a)
        buf[i + 1] = int(buf[i + 1] * inv + c[1] * a)
        buf[i + 2] = int(buf[i + 2] * inv + c[2] * a)

    def draw_text(
        x: int,
        y: int,
        text: str,
        color: tuple[int, int, int],
        scale: int = 3,
        tracking: int = 1,
    ) -> None:
        cx = x
        for ch in text:
            glyph = _OG_GLYPHS.get(ch)
            if glyph is None:
                glyph = [0b11111, 0b10001, 0b00110, 0b00100, 0b00100, 0, 0b00100]
            for gy, bits in enumerate(glyph):
                for gx in range(5):
                    if bits & (1 << (4 - gx)):
                        for sy in range(scale):
                            for sx in range(scale):
                                blend_px(cx + gx * scale + sx, y + gy * scale + sy, color, 1.0)
                                if sx == 0:
                                    blend_px(cx + gx * scale + sx - 1, y + gy * scale + sy, color, 0.25)
                                if sy == 0:
                                    blend_px(cx + gx * scale + sx, y + gy * scale + sy - 1, color, 0.25)
            cx += (5 + tracking) * scale

    fill_rect(0, 0, W, H, PAGE)
    # Light deterministic grain so the asset isn't a tiny flat stub.
    rng = random.Random(42)
    for y in range(H):
        for x in range(0, W, 3):
            n = rng.randint(-3, 3)
            i = (y * W + x) * 3
            for k in range(3):
                buf[i + k] = max(0, min(255, buf[i + k] + n))

    fill_rect(60, 60, 1140, 570, BORDER)
    fill_rect(62, 62, 1138, 568, WHITE)

    draw_text(100, 150, "Which Pack", ACCENT, scale=4, tracking=1)
    draw_text(100, 230, "Before you buy a kit,", TEXT, scale=5, tracking=1)
    draw_text(100, 290, "check what else its platform can run.", TEXT, scale=5, tracking=1)
    draw_text(100, 370, "AU coverage · Milwaukee · DeWalt · Makita · Ryobi", SEC, scale=3, tracking=1)

    def pill(x: int, y: int, w: int, h: int, bg, label: str, fg) -> None:
        fill_rect(x, y, x + w, y + h, bg)
        tw = len(label) * (5 + 1) * 2
        draw_text(x + (w - tw) // 2, y + (h - 7 * 2) // 2, label, fg, scale=2, tracking=1)

    pill(100, 440, 72, 28, HASF, "HAS", HAS_T)
    pill(188, 440, 96, 28, MISSF, "MISSING", MISS_T)
    pill(300, 440, 104, 28, UNKF, "UNKNOWN", UNK_T)

    rows = []
    stride = W * 3
    for y in range(H):
        rows.append(b"\x00" + bytes(buf[y * stride : (y + 1) * stride]))
    return _png_rgb_bytes(W, H, b"".join(rows))


def write_og_png(svg_path: pathlib.Path, png_path: pathlib.Path) -> None:
    """Write og.svg and a proper 1200x630 og.png via stdlib _png_rgb path.

    Always regenerates a branded card (Astra warm tokens + original copy).
    Does not use Chrome headless — that path previously overwrote the good
    asset with a tiny flat geometric stub when screenshot failed.
    """
    (ROOT / "og.svg").write_text(OG_SVG, encoding="utf-8")
    png_path.write_bytes(_build_og_png_bytes())
    dims = _png_ihdr_size(png_path)
    size = png_path.stat().st_size
    if dims != (1200, 630) or size < 20_000:
        raise RuntimeError(f"og.png invalid after build: dims={dims} size={size}")



def main() -> None:
    data = json.loads((ROOT / "coverage.json").read_text(encoding="utf-8"))
    tools = order_tools(data["tool_types"])
    assert len(tools) == 24, f"expected 24 tool types, got {len(tools)}"
    updated = data.get("updated", "")

    (ROOT / "styles.css").write_text(STYLES, encoding="utf-8")
    (ROOT / "favicon.svg").write_text(FAVICON, encoding="utf-8")
    (ROOT / "og.svg").write_text(OG_SVG, encoding="utf-8")
    write_og_png(ROOT / "og.svg", ROOT / "og.png")

    # Keep abstract SVG thumbs as optional fallbacks; cards use hosted stock photos.
    thumbs = ROOT / "thumbs"
    thumbs.mkdir(exist_ok=True)
    (thumbs / "flexvolt.svg").write_text(THUMB_FLEXVOLT_SVG, encoding="utf-8")
    (thumbs / "table-saw.svg").write_text(THUMB_TABLE_SAW_SVG, encoding="utf-8")
    (thumbs / "year-two.svg").write_text(THUMB_YEAR_TWO_SVG, encoding="utf-8")
    images = ROOT / "images"
    for stem in ("year-two", "flexvolt", "table-saw"):
        webp = images / f"{stem}.webp"
        jpg = images / f"{stem}.jpg"
        if not webp.is_file() or not jpg.is_file():
            raise FileNotFoundError(
                f"Missing stock photo pair for {stem}: expected {webp.name} and {jpg.name} under images/"
            )

    (ROOT / "index.html").write_text(build_home(updated), encoding="utf-8")
    (ROOT / "blog.html").write_text(build_blog(updated), encoding="utf-8")
    (ROOT / "matrix.html").write_text(build_matrix(data, tools), encoding="utf-8")
    (ROOT / "traps.html").write_text(build_traps(data), encoding="utf-8")
    (ROOT / "makita-table-saw.html").write_text(build_makita_table_saw(data), encoding="utf-8")
    (ROOT / "year-two-tools.html").write_text(build_year_two(data), encoding="utf-8")
    (ROOT / "method.html").write_text(build_method(updated), encoding="utf-8")
    (ROOT / "disclosure.html").write_text(build_disclosure(updated), encoding="utf-8")

    # sitemap
    sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>{BASE}/</loc><lastmod>{updated}</lastmod></url>
  <url><loc>{BASE}/blog.html</loc><lastmod>{updated}</lastmod></url>
  <url><loc>{BASE}/matrix.html</loc><lastmod>{updated}</lastmod></url>
  <url><loc>{BASE}/traps.html</loc><lastmod>{updated}</lastmod></url>
  <url><loc>{BASE}/makita-table-saw.html</loc><lastmod>{updated}</lastmod></url>
  <url><loc>{BASE}/year-two-tools.html</loc><lastmod>{updated}</lastmod></url>
  <url><loc>{BASE}/method.html</loc><lastmod>{updated}</lastmod></url>
  <url><loc>{BASE}/disclosure.html</loc><lastmod>{updated}</lastmod></url>
</urlset>
"""
    (ROOT / "sitemap.xml").write_text(sitemap, encoding="utf-8")

    # Validate SSR row count on matrix (not homepage)
    home = (ROOT / "index.html").read_text(encoding="utf-8")
    matrix = (ROOT / "matrix.html").read_text(encoding="utf-8")
    n_rows = len(re.findall(r"<tr[^>]*data-known=", matrix))
    assert n_rows == 24, f"matrix.html rows={n_rows}"
    assert "google-site-verification" in home
    assert 'rel="canonical"' in home
    assert "#F5F4EF" in (ROOT / "styles.css").read_text()
    assert "AU cordless traps, before you buy the kit" in home
    assert "matrix.html" in home
    assert "Check coverage" in home
    assert "blog.html" in home
    assert ("Amazon · Search" in matrix or "Amazon · View" in matrix or "Amazon AU — Search" in matrix or "Amazon AU — View" in matrix)
    # First data row should be circular saw (reorder check)
    first = re.search(r"<tbody>\s*<tr[^>]*>\s*<th scope=\"row\">([^<]+)", matrix)
    assert first and first.group(1).strip() == "Circular Saw", first.group(1) if first else None
    # Missing must not use alarm red tokens in CSS
    css = (ROOT / "styles.css").read_text()
    assert "--miss-text: #454D46" in css
    assert "#8a2f2f" not in css.lower()
    assert ".post-card" in css
    traps_html = (ROOT / "traps.html").read_text(encoding="utf-8")
    assert "DeWalt XR vs FlexVolt in Australia" in traps_html
    assert "makita-table-saw.html" in traps_html
    assert "matrix.html" in traps_html
    makita_html = (ROOT / "makita-table-saw.html").read_text(encoding="utf-8")
    assert "Does Makita LXT have a cordless table saw in Australia?" in makita_html
    assert "makita_lxt_au" not in makita_html  # no raw platform ids in copy
    assert ">missing<" in makita_html or "<code>missing</code>" in makita_html
    assert "matrix.html" in makita_html
    year_html = (ROOT / "year-two-tools.html").read_text(encoding="utf-8")
    assert "year-two tools" in year_html.lower() or "Year-two" in year_html or "year-two" in year_html
    assert "matrix.html" in year_html
    blog_html = (ROOT / "blog.html").read_text(encoding="utf-8")
    assert "traps.html" in blog_html and "year-two-tools.html" in blog_html
    assert "images/year-two.webp" in blog_html
    assert "images/flexvolt.webp" in blog_html
    assert "images/table-saw.webp" in blog_html
    assert "images/year-two.jpg" in blog_html
    assert "Stock photo via Unsplash" in blog_html or "images/year-two.webp" in blog_html
    # Newest post card first inside the card grid (nav/footer may link traps earlier)
    blog_cards = blog_html.split('class="post-list"', 1)[1]
    home_cards = home.split('class="post-list"', 1)[1]
    assert blog_cards.find("year-two-tools.html") < blog_cards.find("traps.html")
    assert blog_cards.find('datetime="2026-09-05"') < blog_cards.find('datetime="2026-09-04"')
    assert home_cards.find("year-two-tools.html") < home_cards.find("traps.html")
    assert "post-card-media" in home and "Latest posts" in home
    assert (ROOT / "images" / "flexvolt.webp").is_file()
    assert (ROOT / "images" / "flexvolt.jpg").is_file()
    traps_feat = (ROOT / "traps.html").read_text(encoding="utf-8")
    assert "images/flexvolt.webp" in traps_feat and "post-featured" in traps_feat
    assert "Stock photo via Unsplash" in traps_feat
    assert "4 September 2026" in traps_feat
    sm = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
    assert "makita-table-saw.html" in sm
    assert "matrix.html" in sm
    assert "blog.html" in sm
    assert "year-two-tools.html" in sm
    # Nav order: Blog primary
    assert 'href="blog.html"' in home
    assert "Blog" in (ROOT / "matrix.html").read_text(encoding="utf-8")

    sync_names = [
        "index.html",
        "blog.html",
        "matrix.html",
        "traps.html",
        "makita-table-saw.html",
        "year-two-tools.html",
        "method.html",
        "disclosure.html",
        "styles.css",
        "favicon.svg",
        "coverage.json",
        "og.svg",
        "sitemap.xml",
    ]
    if (ROOT / "og.png").exists():
        sync_names.append("og.png")
    if MVP.exists():
        for name in sync_names:
            src = ROOT / name
            if src.exists():
                shutil.copy2(src, MVP / name)
        mvp_thumbs = MVP / "thumbs"
        mvp_thumbs.mkdir(exist_ok=True)
        for thumb in (ROOT / "thumbs").glob("*.svg"):
            shutil.copy2(thumb, mvp_thumbs / thumb.name)
        mvp_images = MVP / "images"
        mvp_images.mkdir(exist_ok=True)
        for img in (ROOT / "images").glob("*"):
            if img.is_file() and img.suffix.lower() in {".webp", ".jpg", ".jpeg", ".png", ".md"}:
                shutil.copy2(img, mvp_images / img.name)
        print(f"Synced {len(sync_names)} files + thumbs + images to mvp")
    print(f"OK: blog-led home with stock photo cards, matrix {n_rows} rows, first={first.group(1)!r}, updated={updated}")


if __name__ == "__main__":
    main()
