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
    ("18v-platform_lawn_mower", None): "Often 18V×2. Check pack count",
    ("outdoor_string___line_trimmer", "m18_au"): "Needs two M18 packs (sampled)",
    ("outdoor_string___line_trimmer", None): "Some models need 18V×2",
    ("track_saw___plunge_saw", "makita_lxt_au"): "Sample is 18V×2 LXT",
    ("metal_cut-off___chop_saw", None): "Dedicated 230mm+ chop, not 76mm compact",
    ("sds-max_rotary_hammer___breaker", None): "SDS-MAX, not SDS-plus",
}

# Buyer-facing notes for the matrix. Facts (models/voltages) stay; lab/crawl voice goes.
# Coverage statuses still come only from coverage.json cells. Never invent has/missing/unknown.
PLAIN_NOTES = {
    "jobsite_table_saw": (
        "DeWalt’s cordless table saw in AU is 54V FlexVolt (DCS7485N-XJ), not the 18V XR pack you’d buy in a starter kit. "
        "Milwaukee M18FTS210-0 and Ryobi RTBS18X are 18V. Makita LXT has no cordless table saw here. "
        "Corded Makita bench saws exist (2704N, MLT100N)."
    ),
    "track_saw___plunge_saw": (
        "Same voltage trap as the table saw. DeWalt’s cordless track/plunge saw in AU is 54V FlexVolt (DCS520NT-XJ). "
        "XR has circular saws (DCS565, DCS570, DCS571), not a plunge/track saw. "
        "Makita DSP600ZJ needs two 18V LXT packs. Milwaukee M18FPS55-0P and Ryobi RPLS18X are single 18V."
    ),
    "sds-max_rotary_hammer___breaker": (
        "DeWalt AU SDS-MAX hammers we sampled are 54V FlexVolt (DCH614N-XJ and similar). "
        "XR rotary hammers on that catalog are SDS-plus. Milwaukee M18FHACO7450C is M18 SDS-MAX. "
        "Makita DHR400ZKN is 18Vx2 LXT. Ryobi ONE+ lists SDS+ only, no SDS-MAX."
    ),
    "metal_cut-off___chop_saw": (
        "This row is dedicated 230mm+ abrasive chop/cut-off saws, not the little 76mm cut-off tools. "
        "Milwaukee M18CHS355-0 is 355mm. Makita DLW140Z is 18Vx2 355mm. "
        "DeWalt’s cordless dedicated cut-off sampled is 54V FlexVolt DCS691N-XJ. XR DCS438N-XJ is only 76mm. "
        "Ryobi ONE+ has the compact 76mm and a corded 355mm, not a ONE+ dedicated chop."
    ),
    "outdoor_string___line_trimmer": (
        "Milwaukee M18F2LT needs two M18 packs. Makita DUR192LZ is single 18V LXT "
        "(DUR368/DUR369 kits are 18Vx2). Check pack count before you size a kit."
    ),
    "18v-platform_lawn_mower": (
        "Not a FlexVolt-only trap. DeWalt AU lists both a 2×18V XR mower (DCMWSP156W2-XE) and a 54V FlexVolt mower (DCMWP500N-XJ). "
        "Milwaukee M18F2LM180 and Makita DLM432Z/DLM382Z need two packs. Some Ryobi mowers are 2×18V. "
        "Dual-pack vs single-pack still matters when you buy."
    ),
    "mitre_saw": (
        "Not a FlexVolt-only trap. DeWalt AU has 18V XR (DCS365N-XE) and 54V FlexVolt mitres "
        "(DCS781N-XE 305mm, DCS777N-XJ 216mm). Milwaukee M18FMS184-0 is 18V. "
        "Makita DLS600Z is single 18V (bigger ones are 18Vx2). Ryobi RMS 184mm is ONE+."
    ),
    "circular_saw": (
        "Makita LXT circulars show up on the AU catalog (DHS680Z and similar). Ryobi ONE+ has a Circular Saws category. "
        "DeWalt FlexVolt DCS577N-XJ 190mm high-torque is confirmed (DCS578N-XE 184mm also listed)."
    ),
    "impact_wrench": (
        "Makita LXT has an impact-wrenches category on the AU site. Ryobi ONE+ nav lists Impact Wrenches."
    ),
    "reciprocating_saw": (
        "Sawzall, recipro, and reciprocating count as one type here. A FlexVolt recip was not sampled this pass."
    ),
    "jigsaw": (
        "A FlexVolt jigsaw was not sampled this pass."
    ),
    "angle_grinder": (
        "FlexVolt DCG418N-XJ 54V 125mm side-handle is confirmed on the AU site. "
        "Also sampled: Milwaukee M18FSAG125XPDB20, DeWalt XR DCG405FN-XJ, Makita DGA504Z, Ryobi 125mm ONE+."
    ),
    "rotary_hammer_(sds)": (
        "Ryobi ONE+ includes Rotary Hammer Drills in nav (category presence, not one model sampled). "
        "DeWalt FlexVolt DCH333NT-XJ is 54V SDS-plus, separate from the SDS-MAX row."
    ),
    "wet_dry_vac___dust_extractor": (
        "Stick vac, wet/dry vac, and dust extractor count as one type. "
        "DeWalt has an 18V XR L-class stick vac (DCV501LN-XJ) and a 54V FlexVolt M-class extractor (DCV586MN-XJ). "
        "Also sampled: Milwaukee M18WDV-0 7.5L, Makita DVC750LZX1, Ryobi 18L ONE+ wet/dry."
    ),
    "chainsaw": (
        "Pole saws are excluded. Milwaukee M18FCHS-0 is single-pack 16in (dual-pack M18F2CHS200 also listed). "
        "DeWalt DCM565N-XE is 18V XR 30cm. FlexVolt chainsaw DCMCS574 only showed on accessory pages, so left unknown. "
        "Makita DUC254Z is single 18V (DUC306Z/DUC400Z are 18Vx2). Ryobi 12in ONE+ HP."
    ),
    "heat_gun": (
        "Makita DHG181ZK 18V and DeWalt DCE530N-XJ 18V XR heat guns are confirmed on official AU pages. "
        "No FlexVolt heat gun on a sitting OEM page, so left unknown."
    ),
    "framing_nailer": (
        "Framing only, not finish, brad, duplex, or banding. Milwaukee M18FFN-0C 30–34°. "
        "DeWalt DCN930N-XJ 18V XR 33° 90mm. No FlexVolt framing nailer on the AU framing catalog (left unknown). "
        "Makita DBN900ZK 18V LXT (BN001GZ is 40V XGT, not this column). Ryobi RFN1830X ONE+ HP."
    ),
    "portable_band_saw": (
        "Handheld/portable band saw, not a compact banding nailer. Milwaukee M18FBS85-0, DeWalt DCS378N-XJ 18V XR, Makita DPB183Z. "
        "FlexVolt band saw not sampled (unknown). Ryobi RBDS18 shows on support only, not a clean product page, so left unknown."
    ),
    "oscillating_multi-tool": (
        "Oscillating tool and multi-tool count as one type. Makita DTM52ZX3 18V brushless multi-tool confirmed on the official AU page."
    ),
    "drain_snake___drain_cleaner": (
        "Milwaukee AU also lists drum machines and chain snakes. DeWalt DCD200N-XJ is 18V XR. "
        "Ryobi RDA1825 18V ONE+ 7.6m drain auger is confirmed. Makita LXT drain search had no product cards, so left unknown (not missing). "
        "No FlexVolt drain snake found (unknown)."
    ),
    "grease_gun": (
        "DeWalt DCGG581N-XE shows in search as an 18V XR 450g grease gun, but the official product page did not load cleanly. "
        "Left unknown, not has."
    ),
    "caulk___adhesive_gun": (
        "DeWalt DCE580D1-XE shows in search as an 18V XR 600ml caulk gun, but the official product page 404’d. "
        "Left unknown, not has."
    ),
    "press_tool_(copper_pex)": (
        "Copper/PEX jaw press, not a caulk gun or electrical crimper. Milwaukee M18ONEBLHPT-0 FORCE LOGIC confirmed. "
        "DeWalt and Makita press tools not confirmed on AU pages (unknown, not missing). Ryobi press page not found (unknown)."
    ),
    "compact_banding_nailer": (
        "No OEM page titled compact banding nailer found. Do not mix this up with Milwaukee’s duplex nailer "
        "(US 2844-21, AU M18FDN0C), a compact band saw, or framing/finish nailers."
    ),
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
        return "Search Amazon AU"
    # Product detail pages typically /dp/ or /gp/product/
    if "/dp/" in url or "/gp/product/" in url:
        return "Shop Amazon AU"
    return "Search Amazon AU"


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
        # Shop CTA is the loud action on has cells (never invent links; never for Ryobi).
        amz = cell.get("amazon")
        if amz and platform_id != "ryobi_one_au":
            label = amazon_label(amz)
            parts.append(
                f'<a class="amz" rel="sponsored nofollow noopener" href="{esc(amz)}">'
                f"{esc(label)}</a>"
            )

        model = extract_model(cell)
        evidence = cell.get("evidence") or []
        meta_bits = []
        if model:
            meta_bits.append(f'<span class="model">{esc(model)}</span>')
        if evidence:
            src = evidence[0]
            meta_bits.append(
                f'<a class="src" href="{esc(src)}" rel="noopener noreferrer">{esc(source_host(src))}</a>'
            )
        verified = tool.get("last_verified") or updated
        if verified:
            meta_bits.append(f'<span class="date">Verified {esc(verified)}</span>')
        if meta_bits:
            parts.append(
                '<details class="cell-meta">'
                "<summary>Source and date</summary>"
                f'<div class="meta-body">{" · ".join(meta_bits)}</div>'
                "</details>"
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
    # Detect from source coverage note (not display copy), so rebuilds stay honest.
    note = (tool.get("note") or "").lower()
    keys = ("trap", "flexvolt", "54v", "dual-pack", "18vx2", "two m18", "voltage")
    return any(k in note for k in keys)


def trap_tag_label(tool: dict) -> str:
    tid = tool.get("id") or ""
    note = (tool.get("note") or "").lower()
    if tid == "outdoor_string___line_trimmer":
        return "Dual-pack trap"
    if tid in ("18v-platform_lawn_mower", "mitre_saw"):
        return "Pack-count note"
    if "not a table-saw-style voltage trap" in note:
        return "Pack-count note"
    if any(k in note for k in ("dual-pack", "two m18", "needs two")) and "flexvolt" not in note and "54v" not in note:
        return "Dual-pack trap"
    if any(k in note for k in ("flexvolt", "54v", "voltage")):
        return "Voltage trap"
    if "trap" in note:
        return "Coverage trap"
    return "Voltage trap"


def plain_note_text(tool: dict) -> str:
    tid = tool.get("id") or ""
    if tid in PLAIN_NOTES:
        return PLAIN_NOTES[tid]
    # Fallback: soft-clean source note if a new tool appears before mapping is updated.
    raw = (tool.get("note") or "").strip()
    if not raw:
        return ""
    cleaned = raw
    for junk in (
        " (WebFetch was Cloudflare)",
        " via curl of official PDP",
        " (one /product/ fetch is a JS homepage shell)",
        " /product/ fetch was homepage chrome — not used.",
        " /product/ historically JS-shelled",
        "Cloudflare on hub fetch",
    ):
        cleaned = cleaned.replace(junk, "")
    return cleaned


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
        note = plain_note_text(tool)
        if note:
            prefix = ""
            if trap == "1":
                prefix = f'<span class="trap-tag">{esc(trap_tag_label(tool))}</span>'
            note_html = f'<td class="note">{prefix}{esc(note)}</td>'
        else:
            note_html = '<td class="note"></td>'
        rows.append(
            f'<tr{cls} data-tool-id="{esc(tool["id"])}" data-known="{known}" data-trap="{trap}">'
            f'<th scope="row">{esc(display_tool_name(tool["name"]))}</th>'
            f"{cells_html}{note_html}</tr>"
        )
    return "\n".join(rows)


def render_card_plat(platform_id: str, cell: dict, tool: dict, updated: str) -> str:
    """One platform row inside a mobile stacked card. Same facts as table cells."""
    status = cell.get("status") or "unknown"
    brand, line = PLATFORM_HEADERS[platform_id]
    bits = [
        f'<div class="mcard-plat" data-plat="{esc(platform_id)}">'
        f'<div class="mcard-plat-name"><span class="plat-brand">{esc(brand)}</span>'
        f'<span class="plat-line">{esc(line)}</span></div>'
        f'<span class="status {esc(status)}">'
        f'<span class="status-ico" aria-hidden="true">{status_icon(status)}</span> '
        f"{esc(status)}</span>"
    ]
    req = REQUIREMENT_HINTS.get((tool["id"], platform_id)) or REQUIREMENT_HINTS.get((tool["id"], None))
    if req:
        if tool["id"] in ("metal_cut-off___chop_saw", "sds-max_rotary_hammer___breaker"):
            if status != "unknown":
                bits.append(f'<div class="req">{esc(req)}</div>')
        elif status == "has":
            bits.append(f'<div class="req">{esc(req)}</div>')
    if status == "has":
        amz = cell.get("amazon")
        if amz and platform_id != "ryobi_one_au":
            label = amazon_label(amz)
            bits.append(
                f'<a class="amz" rel="sponsored nofollow noopener" href="{esc(amz)}">'
                f"{esc(label)}</a>"
            )
        model = extract_model(cell)
        evidence = cell.get("evidence") or []
        meta_bits = []
        if model:
            meta_bits.append(f'<span class="model">{esc(model)}</span>')
        if evidence:
            src = evidence[0]
            meta_bits.append(
                f'<a class="src" href="{esc(src)}" rel="noopener noreferrer">{esc(source_host(src))}</a>'
            )
        verified = tool.get("last_verified") or updated
        if verified:
            meta_bits.append(f'<span class="date">Verified {esc(verified)}</span>')
        if meta_bits:
            bits.append(
                '<details class="cell-meta">'
                "<summary>Source and date</summary>"
                f'<div class="meta-body">{" · ".join(meta_bits)}</div>'
                "</details>"
            )
    bits.append("</div>")
    return "".join(bits)


def render_matrix_cards(tools: list[dict], platforms: list[dict], updated: str) -> str:
    """Stacked cards for mobile. Same coverage facts as the table. No invented cells."""
    cards = []
    for tool in tools:
        trap = "1" if is_trap_row(tool) else "0"
        known = known_flag(tool)
        cls = " mcard-trap" if trap == "1" else ""
        plats = "".join(
            render_card_plat(
                p["id"],
                tool["cells"].get(p["id"], {"status": "unknown", "evidence": []}),
                tool,
                updated,
            )
            for p in platforms
        )
        note = plain_note_text(tool)
        note_html = ""
        if note:
            prefix = ""
            if trap == "1":
                prefix = f'<span class="trap-tag">{esc(trap_tag_label(tool))}</span>'
            note_html = f'<p class="mcard-note">{prefix}{esc(note)}</p>'
        cards.append(
            f'<article class="mcard{cls}" data-tool-id="{esc(tool["id"])}" '
            f'data-known="{known}" data-trap="{trap}">'
            f'<h3 class="mcard-title">{esc(display_tool_name(tool["name"]))}</h3>'
            f"{note_html}"
            f'<div class="mcard-plats">{plats}</div>'
            f"</article>"
        )
    return (
        '<div class="matrix-cards" id="matrix-cards" aria-label="Coverage by tool">'
        + "\n".join(cards)
        + "</div>"
    )


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
      <a href="sds-max-vs-sds-plus.html">SDS-MAX vs SDS-plus</a>
      <a href="dual-pack-outdoor.html">Dual-pack outdoor</a>
      <a href="amazon-au-110v-chargers.html">110V chargers</a>
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
# Same-date posts keep this list order (stable sort by date only).
POSTS = [
    {
        "path": "sds-max-vs-sds-plus.html",
        "title": "SDS-MAX vs SDS-plus in Australia: the DeWalt FlexVolt trap",
        "blurb": "SDS-plus and SDS-MAX are different chucks. DeWalt AU SDS-MAX hammers we sampled sit on 54V FlexVolt. An XR SDS-plus kit does not cover that row.",
        "date": "2026-09-05",
        "nav": "traps",
        "thumb": "images/sds-max.webp",
        "thumb_fallback": "images/sds-max.jpg",
        "thumb_alt": "Gloved hand using a dusty SDS rotary hammer on a construction site",
        "credit": "Stock photo via Pexels (photo 16280548). Not an OEM product shot.",
        "theme": "sds-max",
    },
    {
        "path": "dual-pack-outdoor.html",
        "title": "Dual-pack outdoor tools: when a mower or trimmer needs two batteries",
        "blurb": "Some AU mowers and line trimmers need two 18V packs. A single-pack kit looks fine until you buy outdoor gear. Check the notes before you size batteries.",
        "date": "2026-09-05",
        "nav": "traps",
        "thumb": "images/dual-pack.webp",
        "thumb_fallback": "images/dual-pack.jpg",
        "thumb_alt": "Person using a string trimmer on a green residential lawn",
        "credit": "Stock photo via Unsplash (photo CWYxsqROgwo). Not an OEM product shot.",
        "theme": "dual-pack",
    },
    {
        "path": "amazon-au-110v-chargers.html",
        "title": "Grey 110V chargers on Amazon AU: plug adapters do not fix voltage",
        "blurb": "US chargers are typically 110–120V. Australia is 230–240V. Amazon AU can list US-spec kits. Local DeWalt SKUs use -XJ / -XE. Adapters are not transformers.",
        "date": "2026-09-05",
        "nav": "traps",
        "thumb": "images/grey-charger.webp",
        "thumb_fallback": "images/grey-charger.jpg",
        "thumb_alt": "Stack of black international power plug adapters including US and AU pins",
        "credit": "Stock photo via Pexels (photo 3639030). Not an OEM product shot.",
        "theme": "grey-charger",
    },
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
    # Stable: same-date posts keep POSTS list order (newest first in POSTS).
    return sorted(POSTS, key=lambda p: p["date"], reverse=True)


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
    """First-visit conversion homepage. Benefit H1, one primary CTA, methodology trust."""
    title = "Which Pack: AU cordless coverage traps before you buy a kit"
    desc = (
        "Check what Milwaukee, DeWalt, Makita or Ryobi kits can run in Australia. "
        "Spot coverage gaps, then shop matching tools on Amazon AU."
    )
    posts_html = post_list_html(heading="Latest posts")
    return f"""{head(title, desc, "", json_ld_home())}
<body>
{site_header("home")}
<main class="wrap">
  <section class="hero blog-hero" aria-labelledby="home-title">
    <div class="hero-copy">
      <p class="eyebrow">AU cordless coverage checker</p>
      <h1 id="home-title">See what your cordless kit can actually run</h1>
      <p class="lede">For Australians choosing Milwaukee, DeWalt, Makita or Ryobi. Spot the gaps before you lock a kit. Verified <strong>has</strong> cells open Amazon AU search so you can shop matching tools.</p>
      <p class="hero-actions"><a class="btn-primary" href="matrix.html">Check what your kit can run</a></p>
      <ul class="trust-strip" aria-label="How we verify coverage">
        <li>Checked against AU OEM catalogs</li>
        <li><strong>has</strong> needs an official AU listing</li>
        <li><strong>missing</strong> means we confirmed it is not on that line</li>
        <li><a href="method.html">How we verify</a></li>
      </ul>
      <p class="disclosure-quiet">As an Amazon Associate I earn from qualifying purchases. <a href="disclosure.html">Details</a>.</p>
    </div>
    <figure class="hero-figure">
      <picture>
        <source srcset="images/flexvolt.webp" type="image/webp">
        <img class="hero-photo" src="images/flexvolt.jpg" width="1280" height="720" alt="Cordless drill on a workbench. Starter kits look fine until year-two tools." loading="eager" decoding="async">
      </picture>
      <figcaption>Starter kits look fine. Year-two tools are where packs fail. Stock photo via Unsplash. Not an OEM product shot.</figcaption>
    </figure>
  </section>

  <p class="below-fold-secondary">Prefer a story first? <a href="blog.html">Read trap posts</a>.</p>

  {posts_html}

  <aside class="matrix-closer" aria-labelledby="matrix-closer-title">
    <h2 id="matrix-closer-title">Then check the matrix</h2>
    <p>Tool type × platform. Has, missing, or unknown from OEM AU pages. Shop matching tools on Amazon AU from verified <strong>has</strong> cells only.</p>
    <p class="card-cta"><a class="btn-primary" href="matrix.html">Open the AU coverage matrix</a></p>
    <p class="disclosure-quiet">Amazon Associate links. Coverage results are editorial. <a href="disclosure.html">Full disclosure</a>.</p>
  </aside>
</main>
{site_footer(updated)}
</body>
</html>
"""


def build_blog(updated: str) -> str:
    title = "Blog: AU cordless coverage traps | Which Pack"
    desc = (
        "Posts on AU cordless platform traps: SDS-MAX vs SDS-plus, dual-pack outdoor, grey 110V chargers, "
        "DeWalt XR vs FlexVolt, Makita LXT table saw, and year-two tools."
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
    cards = render_matrix_cards(tools, platforms, updated)
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
      <p class="lede">Australian tool coverage across Milwaukee, DeWalt, Makita and Ryobi. Verified, missing, or still unknown. Checked against AU OEM catalogs.</p>
      <p class="hero-actions"><a class="btn-primary" href="#controls">Choose your tools</a></p>
      <p class="below-fold-secondary">Prefer a story first? <a href="blog.html">Read trap posts</a>.</p>
    </div>
    <figure class="hero-figure">
      {HERO_SVG}
      <figcaption>Illustration. Battery requirements vary.</figcaption>
    </figure>
  </section>

  <section class="how-to-read" aria-labelledby="how-to-read-title">
    <h2 id="how-to-read-title">How to read this</h2>
    <p>Pick your platform column (the kit you own or are about to buy). <strong>Has</strong> means that tool exists on that AU line. <strong>Missing</strong> means it does not. <strong>Unknown</strong> means we have not checked it yet.</p>
    <p>Yellow tags flag kit traps: wrong voltage, or a tool that needs two packs. The Notes column says what that means before you spend.</p>
    <p class="how-to-shop"><a class="btn-primary" href="#controls">Jump to the matrix</a></p>
    <p class="below-fold-secondary">Looking for the overview? <a href="index.html">Back to home</a>.</p>
  </section>

  <aside class="callout" aria-labelledby="traps-heading">
    <h2 id="traps-heading"><span class="badge">Important</span> Voltage and FlexVolt traps</h2>
    <ul>
      <li>US chargers are usually 110–120V. AU is 230–240V. A plug adapter is not a transformer.</li>
      <li>DeWalt AU 18V XR is the same cell family often sold as 20V MAX in the US. Local packs use -XJ / -XE SKUs.</li>
      <li>DeWalt’s AU cordless table saw, track/plunge saw, SDS-MAX, and 230mm+ chop saw in this matrix are <strong>54V FlexVolt</strong>, not 18V XR.</li>
      <li>Some mowers and trimmers need two 18V packs. Check the notes before you buy.</li>
      <li>Ryobi ONE+ in AU is Bunnings-only. Shown for catalog honesty (not sold via our Amazon links).</li>
    </ul>
    <p class="callout-more"><a href="traps.html">DeWalt XR vs FlexVolt traps →</a> · <a href="sds-max-vs-sds-plus.html">SDS-MAX vs SDS-plus</a> · <a href="dual-pack-outdoor.html">Dual-pack outdoor</a> · <a href="amazon-au-110v-chargers.html">110V chargers</a></p>
  </aside>

  <p class="disclosure-banner" id="disclosure">As an Amazon Associate I earn from qualifying purchases. Affiliate relationships do not determine coverage results. <a href="disclosure.html">Full disclosure</a>.</p>

  <div class="legend" aria-label="Status legend">
    <span class="legend-title">Legend</span>
    <span class="pill has"><span class="status-ico" aria-hidden="true">✓</span> has · found on that AU line</span>
    <span class="pill missing"><span class="status-ico" aria-hidden="true">–</span> missing · not on that line</span>
    <span class="pill unknown"><span class="status-ico" aria-hidden="true">?</span> unknown · not verified yet</span>
  </div>

  <div class="toolbar filters" id="controls" role="group" aria-label="Filter and search tools">
    <label class="search-label" for="tool-search">Search</label>
    <input type="search" id="tool-search" name="q" placeholder="Search tools (saw, nailer…)" autocomplete="off">
    <span class="label">Show</span>
    <button type="button" data-f="all" class="on" aria-pressed="true">All tools</button>
    <button type="button" data-f="known" aria-pressed="false">Hide unknowns</button>
    <button type="button" data-f="traps" aria-pressed="false" title="Rows with a voltage or pack trap note">Voltage traps</button>
    <button type="button" data-f="selected" aria-pressed="false" id="btn-selected" hidden>Selected only</button>
  </div>
  <p class="scroll-hint desktop-only">On wider screens, swipe sideways if needed. The tool column stays put.</p>

  <div class="table-wrap desktop-only" id="table" role="region" aria-label="Platform coverage matrix" tabindex="0">
    <table class="matrix" id="matrix">
      <thead>{thead}</thead>
      <tbody>
{tbody}
      </tbody>
    </table>
  </div>

  <p class="cards-hint mobile-only">On phones, each tool is a stacked card. Pick a platform below to highlight it.</p>
  <div class="platform-picker mobile-only" id="platform-picker" role="group" aria-label="Highlight a platform">
    <button type="button" data-plat="all" class="on" aria-pressed="true">All platforms</button>
    <button type="button" data-plat="m18_au" aria-pressed="false">Milwaukee</button>
    <button type="button" data-plat="dewalt_18v_au" aria-pressed="false">DeWalt XR</button>
    <button type="button" data-plat="dewalt_flexvolt_au" aria-pressed="false">FlexVolt</button>
    <button type="button" data-plat="makita_lxt_au" aria-pressed="false">Makita</button>
    <button type="button" data-plat="ryobi_one_au" aria-pressed="false">Ryobi</button>
  </div>
  {cards}

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
  var cards = Array.prototype.slice.call(document.querySelectorAll('#matrix-cards .mcard'));
  var search = document.getElementById('tool-search');
  var btnSelected = document.getElementById('btn-selected');
  var platButtons = document.querySelectorAll('#platform-picker [data-plat]');
  var mode = 'all';
  var selected = {{}};
  var platFocus = 'all';

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

  function matchItem(el, q) {{
    var show = true;
    if (mode === 'known') show = el.getAttribute('data-known') === '1';
    if (mode === 'traps') show = el.getAttribute('data-trap') === '1';
    if (mode === 'selected') show = !!selected[el.getAttribute('data-tool-id')];
    if (q) {{
      var name = '';
      var title = el.querySelector('th[scope="row"], .mcard-title');
      if (title) name = title.textContent || '';
      if (name.toLowerCase().indexOf(q) === -1) show = false;
    }}
    return show;
  }}

  function applyPlatFocus() {{
    cards.forEach(function (card) {{
      var plats = card.querySelectorAll('.mcard-plat');
      plats.forEach(function (p) {{
        if (platFocus === 'all') {{
          p.classList.remove('is-dim');
          p.classList.remove('is-focus');
        }} else if (p.getAttribute('data-plat') === platFocus) {{
          p.classList.add('is-focus');
          p.classList.remove('is-dim');
        }} else {{
          p.classList.add('is-dim');
          p.classList.remove('is-focus');
        }}
      }});
    }});
  }}

  function apply() {{
    var q = (search && search.value || '').trim().toLowerCase();
    rows.forEach(function (tr) {{
      if (matchItem(tr, q)) tr.removeAttribute('hidden');
      else tr.setAttribute('hidden', '');
    }});
    cards.forEach(function (card) {{
      if (matchItem(card, q)) card.removeAttribute('hidden');
      else card.setAttribute('hidden', '');
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
  platButtons.forEach(function (b) {{
    b.addEventListener('click', function () {{
      platButtons.forEach(function (x) {{
        x.classList.remove('on');
        x.setAttribute('aria-pressed', 'false');
      }});
      b.classList.add('on');
      b.setAttribute('aria-pressed', 'true');
      platFocus = b.getAttribute('data-plat') || 'all';
      applyPlatFocus();
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
    <p><a href="sds-max-vs-sds-plus.html">SDS-MAX vs SDS-plus</a> · <a href="dual-pack-outdoor.html">Dual-pack outdoor</a> · <a href="amazon-au-110v-chargers.html">Grey 110V chargers</a> · <a href="makita-table-saw.html">Makita LXT table saw?</a> · <a href="year-two-tools.html">Year-two tools</a> · <a href="matrix.html">Coverage matrix</a></p>
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
    <p>Related: <a href="sds-max-vs-sds-plus.html">SDS-MAX vs SDS-plus</a> · <a href="dual-pack-outdoor.html">Dual-pack outdoor</a> · <a href="traps.html">DeWalt XR vs FlexVolt</a> · <a href="makita-table-saw.html">Makita LXT table saw?</a></p>
  </div>

  <p class="disclosure-banner">As an Amazon Associate I earn from qualifying purchases. Amazon Search links live on the matrix for verified <strong>has</strong> cells only. <a href="disclosure.html">Full disclosure</a>.</p>
</main>
{site_footer(updated)}
</body>
</html>
"""



def build_sds_max_vs_plus(data: dict) -> str:
    """SDS-MAX vs SDS-plus AU trap. Facts from coverage only."""
    updated = data.get("updated", "")
    sdsmax = tool_by_id(data, "sds-max_rotary_hammer___breaker")
    sdsplus = tool_by_id(data, "rotary_hammer_(sds)")

    def st(tool: dict, pid: str) -> str:
        return (tool["cells"].get(pid) or {}).get("status") or "unknown"

    assert st(sdsmax, "dewalt_18v_au") == "missing"
    assert st(sdsmax, "dewalt_flexvolt_au") == "has"
    assert st(sdsmax, "m18_au") == "has"
    assert st(sdsmax, "makita_lxt_au") == "has"
    assert st(sdsmax, "ryobi_one_au") == "missing"
    assert st(sdsplus, "dewalt_18v_au") == "has"

    dw18 = evidence_first(sdsmax, "dewalt_18v_au")
    dwfv = evidence_first(sdsmax, "dewalt_flexvolt_au")
    m18 = evidence_first(sdsmax, "m18_au")
    mak = evidence_first(sdsmax, "makita_lxt_au")
    ryobi = evidence_first(sdsmax, "ryobi_one_au")
    dw_plus = evidence_first(sdsplus, "dewalt_18v_au")
    dw_fv_plus = evidence_first(sdsplus, "dewalt_flexvolt_au")

    title = "SDS-MAX vs SDS-plus in Australia: the DeWalt FlexVolt trap | Which Pack"
    desc = (
        "SDS-plus and SDS-MAX are different chucks. DeWalt AU SDS-MAX hammers sampled are "
        "54V FlexVolt (DCH614). XR rotary hammers on the AU catalog are SDS-plus."
    )
    post = post_by_path("sds-max-vs-sds-plus.html")
    return f"""{head(title, desc, "sds-max-vs-sds-plus.html")}
<body>
{site_header("traps")}
<main class="wrap narrow article">
  <div class="page-hero article-hero">
    <p class="post-meta"><time datetime="2026-09-05">5 September 2026</time></p>
    <h1>SDS-MAX vs SDS-plus in Australia: the DeWalt FlexVolt trap</h1>
    <p class="lede">SDS-plus and SDS-MAX are not the same chuck. On DeWalt AU, the SDS-MAX hammers we sampled sit on <strong>54V FlexVolt</strong>. The 18V XR rotary hammers on that catalog are SDS-plus. Buying an XR kit does not cover the SDS-MAX row.</p>
  </div>
  {featured_figure(post)}

  <aside class="callout" aria-labelledby="sds-trap-summary">
    <h2 id="sds-trap-summary"><span class="badge">Coverage trap</span> Different chuck, different voltage on DeWalt AU</h2>
    <ul>
      <li>DeWalt AU SDS-MAX sampled: 54V FlexVolt (DCH614N-XJ). Scored <code>missing</code> on 18V XR and <code>has</code> on FlexVolt.</li>
      <li>DeWalt AU SDS-plus on XR: sampled DCH133N-XJ. Separate FlexVolt SDS-plus exists (DCH333NT-XJ). That is still SDS-plus, not SDS-MAX.</li>
      <li>Verified {esc(updated)}. See the <a href="matrix.html">coverage matrix</a>.</li>
    </ul>
  </aside>

  <div class="card">
    <h2>What the matrix shows</h2>
    <ul>
      <li><strong>DeWalt 18V XR</strong>: SDS-MAX <code>missing</code>{(" · " + oem_link(dw18)) if dw18 else ""}. SDS-plus <code>has</code>{(" · " + oem_link(dw_plus)) if dw_plus else ""}.</li>
      <li><strong>DeWalt FlexVolt 54V</strong>: SDS-MAX <code>has</code>{(" · " + oem_link(dwfv)) if dwfv else ""}. SDS-plus also <code>has</code>{(" · " + oem_link(dw_fv_plus)) if dw_fv_plus else ""}.</li>
      <li><strong>Milwaukee M18</strong>: SDS-MAX <code>has</code> (M18FHACO7450C, not MX FUEL){(" · " + oem_link(m18)) if m18 else ""}.</li>
      <li><strong>Makita LXT</strong>: SDS-MAX <code>has</code> (DHR400ZKN is 18Vx2){(" · " + oem_link(mak)) if mak else ""}.</li>
      <li><strong>Ryobi ONE+</strong>: SDS-MAX <code>missing</code> (SDS+ hammers and a corded SDS listed; SDS-MAX string count 0){(" · " + oem_link(ryobi)) if ryobi else ""}.</li>
    </ul>
    <p>We do not invent cells. Evidence is manufacturer AU pages only.</p>
  </div>

  <div class="card">
    <h2>Why this bites kit buyers</h2>
    <p>Starter kits sell SDS-plus hammers for brick and light concrete. Year two on slab or demo often wants SDS-MAX. On DeWalt AU that jump is also a voltage jump. FlexVolt packs can run XR tools. An XR pack cannot run a 54V-only SDS-MAX machine.</p>
  </div>

  <aside class="matrix-closer" aria-labelledby="sds-matrix-closer">
    <h2 id="sds-matrix-closer">Check SDS-MAX on your platform</h2>
    <p>Open the matrix, filter the SDS-MAX row, and confirm has vs missing before you lock packs.</p>
    <p class="card-cta"><a class="btn-primary" href="matrix.html">Open the AU coverage matrix</a></p>
    <p class="disclosure-quiet">Related: <a href="traps.html">XR vs FlexVolt</a> · <a href="year-two-tools.html">Year-two tools</a> · <a href="blog.html">Blog</a></p>
  </aside>

  <p class="disclosure-banner">As an Amazon Associate I earn from qualifying purchases. Affiliate relationships do not determine coverage results. <a href="disclosure.html">Full disclosure</a>.</p>
</main>
{site_footer(updated)}
</body>
</html>
"""


def build_dual_pack_outdoor(data: dict) -> str:
    """Dual-pack outdoor mower/trimmer trap. Facts from coverage only."""
    updated = data.get("updated", "")
    mower = tool_by_id(data, "18v-platform_lawn_mower")
    trimmer = tool_by_id(data, "outdoor_string___line_trimmer")

    def st(tool: dict, pid: str) -> str:
        return (tool["cells"].get(pid) or {}).get("status") or "unknown"

    # Platforms have the types; trap is pack count in notes, not missing cells.
    assert st(mower, "m18_au") == "has"
    assert st(mower, "dewalt_18v_au") == "has"
    assert st(mower, "makita_lxt_au") == "has"
    assert st(trimmer, "m18_au") == "has"
    assert st(trimmer, "makita_lxt_au") == "has"

    m18_m = evidence_first(mower, "m18_au")
    dw18_m = evidence_first(mower, "dewalt_18v_au")
    dwfv_m = evidence_first(mower, "dewalt_flexvolt_au")
    mak_m = evidence_first(mower, "makita_lxt_au")
    ryobi_m = evidence_first(mower, "ryobi_one_au")
    m18_t = evidence_first(trimmer, "m18_au")
    mak_t = evidence_first(trimmer, "makita_lxt_au")
    dw18_t = evidence_first(trimmer, "dewalt_18v_au")

    title = "Dual-pack outdoor tools: when a mower or trimmer needs two batteries | Which Pack"
    desc = (
        "AU outdoor trap: some Milwaukee and Makita mowers need two 18V packs. "
        "Milwaukee M18F2 line trimmers need two M18 packs. Size the kit for that, not one battery."
    )
    post = post_by_path("dual-pack-outdoor.html")
    return f"""{head(title, desc, "dual-pack-outdoor.html")}
<body>
{site_header("traps")}
<main class="wrap narrow article">
  <div class="page-hero article-hero">
    <p class="post-meta"><time datetime="2026-09-05">5 September 2026</time></p>
    <h1>Dual-pack outdoor tools: when a mower or trimmer needs two batteries</h1>
    <p class="lede">A kit with one spare pack looks fine until you buy outdoor gear. On our AU matrix, several mowers and line trimmers need <strong>two 18V packs</strong> at once. That is a coverage trap, even when the cell is scored <code>has</code>.</p>
  </div>
  {featured_figure(post)}

  <aside class="callout" aria-labelledby="dual-trap-summary">
    <h2 id="dual-trap-summary"><span class="badge">Coverage trap</span> Has the tool. Needs two packs.</h2>
    <ul>
      <li>Milwaukee AU M18F2 line trimmer requires two M18 packs.</li>
      <li>Milwaukee M18F2LM180 and Makita DLM432Z / DLM382Z mowers are dual-pack (18Vx2). Some Ryobi mowers are 2×18V.</li>
      <li>DeWalt AU lists both a 2×18V XR mower and a 54V FlexVolt mower. Not an XR-missing trap. Still check pack count.</li>
      <li>Verified {esc(updated)}.</li>
    </ul>
  </aside>

  <div class="card">
    <h2>Lawn mowers</h2>
    <p>Every platform in the matrix scores <code>has</code> for 18V-platform lawn mower. The trap is how many packs the machine eats.</p>
    <ul>
      <li><strong>Milwaukee / Makita</strong>: dual-pack examples above{(" · " + oem_link(mak_m, "Makita DLM432Z")) if mak_m else ""}{(" · " + oem_link(m18_m)) if m18_m else ""}.</li>
      <li><strong>DeWalt</strong>: 2×18V XR (DCMWSP156W2-XE) and 54V FlexVolt (DCMWP500N-XJ){(" · " + oem_link(dw18_m)) if dw18_m else ""}{(" · " + oem_link(dwfv_m)) if dwfv_m else ""}.</li>
      <li><strong>Ryobi</strong>: some ONE+ mowers are 2×18V{(" · " + oem_link(ryobi_m)) if ryobi_m else ""}.</li>
    </ul>
  </div>

  <div class="card">
    <h2>Line trimmers</h2>
    <p>Milwaukee AU M18F2LT needs two M18 packs{(" · " + oem_link(m18_t)) if m18_t else ""}. Makita AU DUR192LZ is single 18V LXT. Dual-pack Makita DUR368 / DUR369 kits also exist{(" · " + oem_link(mak_t)) if mak_t else ""}. DeWalt AU sample DCMST561N-XE is 18V XR{(" · " + oem_link(dw18_t)) if dw18_t else ""}.</p>
    <p>Amazon Lawn &amp; Garden commission is 5%, not the 10% Tools rate. Editorial note only. It does not change coverage.</p>
  </div>

  <div class="card">
    <h2>What to do before you buy packs</h2>
    <p>List the outdoor tools you actually want. Open the matrix notes. If a must-have needs two packs, budget two high-capacity batteries, not one plus a tiny spare.</p>
  </div>

  <aside class="matrix-closer" aria-labelledby="dual-matrix-closer">
    <h2 id="dual-matrix-closer">Check outdoor rows on the matrix</h2>
    <p>Filter mower and trimmer. Read the notes column for dual-pack language before you size a kit.</p>
    <p class="card-cta"><a class="btn-primary" href="matrix.html">Open the AU coverage matrix</a></p>
    <p class="disclosure-quiet">Related: <a href="year-two-tools.html">Year-two tools</a> · <a href="sds-max-vs-sds-plus.html">SDS-MAX vs SDS-plus</a> · <a href="blog.html">Blog</a></p>
  </aside>

  <p class="disclosure-banner">As an Amazon Associate I earn from qualifying purchases. Amazon Search links live on the matrix for verified <strong>has</strong> cells only. <a href="disclosure.html">Full disclosure</a>.</p>
</main>
{site_footer(updated)}
</body>
</html>
"""


def build_amazon_au_110v(data: dict) -> str:
    """Grey 110V chargers on Amazon AU. Facts from coverage.traps only."""
    updated = data.get("updated", "")
    traps = data.get("traps") or []
    # Sanity: expected trap strings present
    joined = " ".join(traps)
    assert "110" in joined and "230" in joined
    assert "-XJ" in joined or "-XE" in joined

    title = "Grey 110V chargers on Amazon AU: plug adapters do not fix voltage | Which Pack"
    desc = (
        "US chargers are typically 110–120V. Australia is 230–240V. Amazon AU can list US-spec tools "
        "with the wrong charger. Local DeWalt SKUs use -XJ / -XE. Adapters are not transformers."
    )
    post = post_by_path("amazon-au-110v-chargers.html")
    return f"""{head(title, desc, "amazon-au-110v-chargers.html")}
<body>
{site_header("traps")}
<main class="wrap narrow article">
  <div class="page-hero article-hero">
    <p class="post-meta"><time datetime="2026-09-05">5 September 2026</time></p>
    <h1>Grey 110V chargers on Amazon AU: plug adapters do not fix voltage</h1>
    <p class="lede">Voltage and plugs are easy to miss in a product photo. US chargers are typically <strong>110–120V</strong>. Australia is <strong>230–240V</strong>. A plug adapter does not convert voltage. Grey Amazon AU listings can ship the US charger with a local-looking kit.</p>
  </div>
  {featured_figure(post)}

  <aside class="callout" aria-labelledby="charger-trap-summary">
    <h2 id="charger-trap-summary"><span class="badge">Coverage trap</span> Same cells. Wrong charger.</h2>
    <ul>
      <li>US chargers typically 110–120V. AU mains are 230–240V. Plug adapters do not convert voltage.</li>
      <li>DeWalt US labels 20V MAX / 60V FlexVolt. AU labels 18V XR / 54V FlexVolt. Cells and tools are often shared. Chargers often are not.</li>
      <li>Amazon AU can list US-spec kits with 110V chargers. Local DeWalt SKUs use -XJ / -XE suffixes.</li>
      <li>Verified notes {esc(updated)}. No DIY electrical advice.</li>
    </ul>
  </aside>

  <div class="card">
    <h2>What we are warning about</h2>
    <p>This site scores tool coverage, not every grey charger listing. The trap still matters before you buy a kit online. If the charger is US-spec, the packs may sit uncharged, or worse if someone forces the wrong supply. We are not electricians. Treat voltage mismatch as a hard stop.</p>
  </div>

  <div class="card">
    <h2>How to spot local DeWalt SKUs</h2>
    <p>On DeWalt AU, local cordless SKUs commonly end in <strong>-XJ</strong> or <strong>-XE</strong>. That is a catalog signal, not a guarantee for every third-party Amazon listing. Prefer OEM AU pages and the matrix evidence links when you care about platform coverage.</p>
  </div>

  <div class="card">
    <h2>What this site still checks</h2>
    <p>Which Pack maps which tool types each platform carries in Australia. Charger voltage is a purchase trap sitting beside that. Use both: confirm the tool type exists on your platform, then confirm the listing ships an AU-voltage charger.</p>
  </div>

  <aside class="matrix-closer" aria-labelledby="charger-matrix-closer">
    <h2 id="charger-matrix-closer">Then check tool coverage</h2>
    <p>Open the matrix for has / missing / unknown by platform. Shop Amazon AU from verified <strong>has</strong> cells only, and still read the charger spec on the listing.</p>
    <p class="card-cta"><a class="btn-primary" href="matrix.html">Open the AU coverage matrix</a></p>
    <p class="disclosure-quiet">Related: <a href="traps.html">XR vs FlexVolt</a> · <a href="sds-max-vs-sds-plus.html">SDS-MAX vs SDS-plus</a> · <a href="blog.html">Blog</a></p>
  </aside>

  <p class="disclosure-banner">As an Amazon Associate I earn from qualifying purchases. Affiliate relationships do not determine coverage results. <a href="disclosure.html">Full disclosure</a>.</p>
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
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--accent);
  color: #fff !important;
  text-decoration: none;
  font-weight: 600;
  font-size: 1rem;
  min-height: 48px;
  padding: 14px 22px;
  border-radius: var(--radius-ctrl);
  box-sizing: border-box;
}
.btn-primary:hover { filter: brightness(1.05); color: #fff !important; }
.disclosure-quiet {
  margin: 14px 0 0;
  font-size: 0.8rem;
  color: var(--secondary);
  line-height: 1.45;
  max-width: 52ch;
}
.disclosure-quiet a {
  color: var(--secondary);
  font-weight: 500;
  text-decoration: underline;
  text-underline-offset: 2px;
}
.matrix-closer .disclosure-quiet { margin-top: 12px; }
.matrix-closer .card-cta .btn-primary { margin-top: 2px; }
.hero-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}
.hero-actions .btn-ghost { margin-left: 0; }
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
  background: transparent;
  border: 0;
  border-radius: 0;
  padding: 0;
  margin: 0 0 16px;
  font-size: 0.82rem;
  color: var(--secondary);
  line-height: 1.45;
}
.disclosure-banner a { font-weight: 500; }

.callout {
  background: var(--warn-bg);
  border: 1px solid var(--warn-border);
  border-left: 4px solid var(--warn-accent);
  border-radius: var(--radius);
  padding: 16px 18px;
  margin: 0 0 20px;
}
.callout h2 {
  margin: 0 0 10px;
  font-size: 1.08rem;
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
.callout li { margin: 0.35rem 0; font-size: 1rem; line-height: 1.5; }
.callout-more { margin: 10px 0 0; font-size: 0.9rem; }

.how-to-read {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 18px 20px;
  margin: 0 0 20px;
}
.how-to-read h2 {
  margin: 0 0 10px;
  font-size: 1.15rem;
  letter-spacing: -0.02em;
  font-weight: 700;
}
.how-to-read p {
  margin: 0 0 10px;
  color: var(--text);
  font-size: 1.05rem;
  line-height: 1.55;
  max-width: 68ch;
}
.how-to-read p:last-of-type { margin-bottom: 0; }
.how-to-read strong { color: var(--text); }
.how-to-shop {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin: 16px 0 0;
}

.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 14px;
  align-items: center;
  margin: 0 0 16px;
  font-size: 1.05rem;
}
.legend-title { color: var(--secondary); font-weight: 600; margin-right: 4px; font-size: 1.05rem; }
.pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 12px;
  border-radius: var(--radius-label);
  border: 1px solid var(--border);
  background: var(--surface);
  font-weight: 600;
  font-size: 1rem;
}
.pill.has { background: var(--has-fill); color: var(--has-text); border-color: #C5DFCB; }
.pill.missing { background: var(--miss-fill); color: var(--miss-text); border-color: var(--border); }
.pill.unknown { background: var(--unk-fill); color: var(--unk-text); border-color: #E6D19A; }

.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin: 0 0 14px;
}
.toolbar .label, .search-label {
  font-size: 0.95rem;
  color: var(--secondary);
  font-weight: 600;
}
#tool-search {
  font: inherit;
  font-size: 1rem;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-ctrl);
  background: var(--surface);
  color: var(--text);
  min-width: 220px;
  min-height: 44px;
}
.filters button {
  appearance: none;
  background: var(--surface);
  color: var(--text);
  border: 1px solid var(--border);
  padding: 10px 14px;
  border-radius: var(--radius-ctrl);
  cursor: pointer;
  font: inherit;
  font-size: 0.95rem;
  font-weight: 600;
  min-height: 44px;
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
  font-size: 1.2rem;
  min-width: 1240px;
}
.matrix th, .matrix td {
  border-bottom: 1px solid var(--border);
  border-right: 1px solid var(--border);
  padding: 18px 16px;
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
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--text);
  box-shadow: inset 0 -1px 0 var(--border);
  padding: 16px;
}
.matrix thead th:first-child {
  left: 0;
  z-index: 3;
  box-shadow: inset -1px 0 0 var(--border), inset 0 -1px 0 var(--border);
}
.plat-brand { display: block; font-weight: 700; font-size: 1.15rem; }
.plat-line { display: block; font-weight: 550; color: var(--secondary); margin-top: 4px; font-size: 1.05rem; }
.matrix tbody th[scope="row"] {
  background: var(--page);
  font-weight: 700;
  color: var(--text);
  font-size: 1.3rem;
  line-height: 1.35;
  min-width: 196px;
  max-width: 240px;
  position: sticky;
  left: 0;
  z-index: 1;
  box-shadow: inset -1px 0 0 var(--border);
}
.matrix tbody th .pick {
  margin-right: 10px;
  vertical-align: middle;
  width: 20px;
  height: 20px;
}
.matrix tbody tr:nth-child(even) td,
.matrix tbody tr:nth-child(even) th[scope="row"] { background: #FAFAF6; }
.matrix tbody tr:last-child th,
.matrix tbody tr:last-child td { border-bottom: none; }
.matrix tbody tr:hover td,
.matrix tbody tr:hover th[scope="row"] { background: #F0F1EB; }
.matrix tbody tr.is-trap td.note {
  border-left: 3px solid var(--warn-accent);
}
.matrix tbody tr[hidden] { display: none; }

/* Status = label only — no full-cell colouring */
.status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-weight: 700;
  font-size: 1rem;
  letter-spacing: 0.02em;
  text-transform: uppercase;
  padding: 7px 12px;
  border-radius: var(--radius-label);
  border: 1px solid transparent;
}
.status-ico { font-size: 1rem; line-height: 1; }
.status.has { background: var(--has-fill); color: var(--has-text); border-color: #C5DFCB; }
.status.missing { background: var(--miss-fill); color: var(--miss-text); border-color: var(--border); }
.status.unknown { background: var(--unk-fill); color: var(--unk-text); border-color: #E6D19A; }

.req {
  margin-top: 10px;
  font-size: 1.05rem;
  color: var(--secondary);
  line-height: 1.45;
}
/* Amazon shop CTA: loudest action on has cells */
a.amz {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-top: 12px;
  font-size: 1.12rem;
  font-weight: 700;
  letter-spacing: 0.01em;
  color: #fff !important;
  text-decoration: none;
  border: 1px solid var(--accent);
  background: var(--accent);
  border-radius: var(--radius-ctrl);
  padding: 12px 16px;
  white-space: nowrap;
  min-height: 48px;
  max-width: 100%;
  box-sizing: border-box;
  box-shadow: 0 1px 2px rgba(32, 37, 33, 0.14);
}
a.amz:hover {
  filter: brightness(1.06);
  color: #fff !important;
  background: var(--accent);
  border-color: var(--accent);
}

/* Quiet OEM source / verified date behind details */
.cell-meta {
  margin-top: 10px;
  font-size: 0.88rem;
  color: var(--secondary);
  line-height: 1.45;
  max-width: 16rem;
}
.cell-meta summary {
  cursor: pointer;
  list-style: none;
  color: var(--secondary);
  font-size: 0.88rem;
  font-weight: 550;
  user-select: none;
}
.cell-meta summary::-webkit-details-marker { display: none; }
.cell-meta summary::before {
  content: "▸ ";
  font-size: 0.8em;
  opacity: 0.8;
}
.cell-meta[open] summary::before { content: "▾ "; }
.cell-meta .meta-body {
  margin-top: 6px;
  padding: 6px 0 0;
  border-top: 1px solid var(--border);
  font-size: 0.85rem;
  color: var(--secondary);
  line-height: 1.45;
  word-break: break-word;
}
.cell-meta .model {
  font-family: var(--mono);
  color: var(--text);
  font-weight: 600;
  font-size: 0.85rem;
}
.cell-meta .src {
  color: var(--secondary);
  text-decoration: underline;
  text-underline-offset: 2px;
}
.cell-meta .src:hover { color: var(--link); }
.cell-meta .date { white-space: nowrap; }

/* Legacy details class kept for any residual markup */
.details {
  margin-top: 10px;
  font-size: 0.9rem;
  color: var(--secondary);
  line-height: 1.5;
}
.details .model { font-family: var(--mono); color: var(--text); font-weight: 600; font-size: 0.9rem; }
.details .src { color: var(--secondary); text-decoration: underline; text-underline-offset: 2px; }
.details .src:hover { color: var(--link); }
.details .date { white-space: nowrap; }

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
  color: var(--text);
  font-size: 1.12rem;
  line-height: 1.55;
  max-width: 420px;
  min-width: 280px;
}
.note .trap-tag {
  display: block;
  width: fit-content;
  margin: 0 0 10px;
  font-size: 0.95rem;
  font-weight: 700;
  letter-spacing: 0.02em;
  text-transform: none;
  color: var(--warn-fg);
  background: var(--warn-bg);
  border: 1px solid var(--warn-border);
  padding: 5px 10px;
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
    width: 100%;
    min-height: 52px;
    padding: 14px 18px;
    font-size: 1.05rem;
  }
  .hero-actions {
    flex-direction: column;
    align-items: stretch;
  }
  .hero-actions .btn-ghost {
    width: 100%;
    justify-content: center;
    margin: 0;
  }
  .disclosure-quiet { font-size: 0.78rem; }
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
  .how-to-read { padding: 16px 14px; }
  .how-to-read h2 { font-size: 1.08rem; }
  .how-to-read p { font-size: 1rem; }
  .how-to-shop { flex-direction: column; align-items: stretch; }
  .how-to-shop .btn-ghost { width: 100%; justify-content: center; }
  .legend { font-size: 1.05rem; }
  .pill { font-size: 1rem; padding: 7px 11px; }
  table.matrix {
    min-width: 1180px;
    font-size: 1.125rem;
  }
  .matrix th, .matrix td { padding: 16px 14px; }
  .matrix tbody th[scope="row"] {
    min-width: 168px;
    max-width: 210px;
    font-size: 1.2rem;
    font-weight: 700;
    line-height: 1.35;
  }
  .matrix thead th {
    top: 52px;
    font-size: 1.05rem;
    z-index: 4;
  }
  .matrix thead th:first-child {
    z-index: 5;
    left: 0;
  }
  .plat-brand { font-size: 1.1rem; }
  .plat-line { font-size: 1.05rem; }
  .matrix tbody th[scope="row"] {
    z-index: 3;
    box-shadow: 4px 0 8px -4px rgba(32,37,33,0.12), inset -1px 0 0 var(--border);
  }
  .matrix tbody th .pick {
    width: 20px;
    height: 20px;
    margin-right: 8px;
    flex-shrink: 0;
  }
  .status { font-size: 1rem; padding: 7px 11px; }
  .req { font-size: 1.05rem; }
  .cell-meta, .cell-meta summary { font-size: 0.88rem; }
  .cell-meta .meta-body, .cell-meta .model { font-size: 0.85rem; }
  a.amz {
    display: inline-flex;
    width: 100%;
    justify-content: center;
    min-height: 48px;
    font-size: 1.1rem;
    padding: 12px 14px;
  }
  .note { max-width: 300px; min-width: 240px; font-size: 1.1rem; }
  .note .trap-tag { font-size: 0.95rem; }
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

/* First-visit trust + one-CTA helpers */
.trust-strip {
  list-style: none;
  margin: 14px 0 0;
  padding: 12px 14px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  background: var(--has-fill);
  border: 1px solid #C5DFCB;
  border-radius: var(--radius);
  font-size: 0.88rem;
  color: var(--secondary);
  line-height: 1.4;
  max-width: 58ch;
}
.trust-strip li {
  margin: 0;
  padding: 0;
}
.trust-strip li::before {
  content: "✓ ";
  color: var(--has-text);
  font-weight: 700;
}
.trust-strip a {
  color: var(--accent);
  font-weight: 600;
  text-decoration: none;
}
.trust-strip a:hover { text-decoration: underline; }
.below-fold-secondary {
  margin: 0 0 18px;
  font-size: 0.92rem;
  color: var(--secondary);
}
.below-fold-secondary a {
  color: var(--accent);
  font-weight: 600;
  text-decoration: none;
}
.below-fold-secondary a:hover { text-decoration: underline; }
.hero-actions .btn-primary { margin-right: 0; }

/* Desktop table / mobile stacked cards */
.mobile-only { display: none; }
.matrix-cards { display: none; }
.cards-hint {
  margin: 0 0 10px;
  font-size: 0.92rem;
  color: var(--secondary);
}
.platform-picker {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 0 0 14px;
}
.platform-picker button {
  min-height: 44px;
  padding: 8px 12px;
  border-radius: var(--radius-ctrl);
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  font: inherit;
  font-weight: 600;
  font-size: 0.9rem;
  cursor: pointer;
}
.platform-picker button.on {
  background: var(--has-fill);
  border-color: #C5DFCB;
  color: var(--accent);
}
.mcard {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 14px 14px 12px;
  margin: 0 0 12px;
}
.mcard-trap {
  border-left: 4px solid var(--warn-accent);
}
.mcard-title {
  margin: 0 0 8px;
  font-size: 1.15rem;
  letter-spacing: -0.02em;
  line-height: 1.3;
}
.mcard-note {
  margin: 0 0 12px;
  font-size: 0.95rem;
  color: var(--secondary);
  line-height: 1.45;
}
.mcard-plats {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.mcard-plat {
  border: 1px solid var(--border);
  border-radius: var(--radius-ctrl);
  padding: 10px 12px;
  background: #FAFAF7;
  transition: opacity 0.15s ease, border-color 0.15s ease;
}
.mcard-plat.is-dim { opacity: 0.38; }
.mcard-plat.is-focus {
  opacity: 1;
  border-color: var(--accent);
  background: var(--has-fill);
}
.mcard-plat-name {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 10px;
  align-items: baseline;
  margin-bottom: 6px;
}
.mcard-plat .status { margin-bottom: 6px; }
.mcard-plat .amz {
  margin-top: 8px;
  display: inline-flex;
  width: 100%;
  justify-content: center;
  min-height: 48px;
  font-size: 1.05rem;
  padding: 12px 14px;
}
.mcard-plat .cell-meta { margin-top: 6px; }

@media (max-width: 720px) {
  .desktop-only { display: none !important; }
  .mobile-only { display: block; }
  .platform-picker.mobile-only { display: flex; }
  .matrix-cards {
    display: block;
    margin: 0 0 16px;
  }
  .trust-strip {
    flex-direction: column;
    gap: 6px;
    font-size: 0.9rem;
  }
  .hero-copy .lede { max-width: none; }
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
    for stem in (
        "year-two",
        "flexvolt",
        "table-saw",
        "sds-max",
        "dual-pack",
        "grey-charger",
    ):
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
    (ROOT / "sds-max-vs-sds-plus.html").write_text(build_sds_max_vs_plus(data), encoding="utf-8")
    (ROOT / "dual-pack-outdoor.html").write_text(build_dual_pack_outdoor(data), encoding="utf-8")
    (ROOT / "amazon-au-110v-chargers.html").write_text(build_amazon_au_110v(data), encoding="utf-8")
    (ROOT / "method.html").write_text(build_method(updated), encoding="utf-8")
    (ROOT / "disclosure.html").write_text(build_disclosure(updated), encoding="utf-8")

    # sitemap
    sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>{BASE}/</loc><lastmod>{updated}</lastmod></url>
  <url><loc>{BASE}/blog.html</loc><lastmod>{updated}</lastmod></url>
  <url><loc>{BASE}/matrix.html</loc><lastmod>{updated}</lastmod></url>
  <url><loc>{BASE}/traps.html</loc><lastmod>{updated}</lastmod></url>
  <url><loc>{BASE}/sds-max-vs-sds-plus.html</loc><lastmod>{updated}</lastmod></url>
  <url><loc>{BASE}/dual-pack-outdoor.html</loc><lastmod>{updated}</lastmod></url>
  <url><loc>{BASE}/amazon-au-110v-chargers.html</loc><lastmod>{updated}</lastmod></url>
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
    assert "See what your cordless kit can actually run" in home
    assert "matrix.html" in home
    assert "Check what your kit can run" in home
    assert "disclosure-banner" not in home
    assert "disclosure-quiet" in home
    assert "Shop matching tools on Amazon AU" in home
    assert "blog.html" in home
    assert "trust-strip" in home
    assert "AU OEM" in home or "OEM catalogs" in home
    assert "How we verify" in home
    # One primary CTA in hero: no competing btn-ghost beside the matrix CTA
    hero_chunk = home.split("Latest posts")[0]
    assert "btn-primary" in hero_chunk and "Check what your kit can run" in hero_chunk
    assert "btn-ghost" not in hero_chunk
    assert "matrix-cards" in matrix
    assert "platform-picker" in matrix
    assert "mcard" in matrix
    assert "Checked against AU OEM catalogs" in matrix
    assert (
        "Search Amazon AU" in matrix
        or "Shop Amazon AU" in matrix
        or "Amazon · Search" in matrix
        or "Amazon · View" in matrix
    )
    assert 'class="amz"' in matrix
    assert 'class="cell-meta"' in matrix
    assert "Source and date" in matrix
    assert "Amazon · Search" not in matrix  # new human CTA labels
    # Ryobi is last platform column (index 4): editorial only, never Amazon
    import re as _re
    rows = _re.findall(r"<tr[^>]*data-known=.*?</tr>", matrix, _re.S)
    ryobi_amz = 0
    for row in rows:
        tds = _re.findall(r"<td>(?:(?!</td>).)*</td>", row, _re.S)
        # platform cells only (plain <td>), notes use class="note"
        plat_tds = [td for td in tds if not td.startswith('<td class=')]
        if len(plat_tds) >= 5 and 'class="amz"' in plat_tds[4]:
            ryobi_amz += 1
    assert ryobi_amz == 0, f"Ryobi Amazon CTAs found: {ryobi_amz}"
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
    assert "sds-max-vs-sds-plus.html" in blog_html
    assert "dual-pack-outdoor.html" in blog_html
    assert "amazon-au-110v-chargers.html" in blog_html
    assert "images/year-two.webp" in blog_html
    assert "images/flexvolt.webp" in blog_html
    assert "images/table-saw.webp" in blog_html
    assert "images/sds-max.webp" in blog_html
    assert "images/dual-pack.webp" in blog_html
    assert "images/grey-charger.webp" in blog_html
    assert "images/year-two.jpg" in blog_html
    assert "Stock photo via Unsplash" in blog_html or "images/year-two.webp" in blog_html
    # Newest post cards first inside the card grid (nav/footer may link traps earlier)
    blog_cards = blog_html.split('class="post-list"', 1)[1]
    home_cards = home.split('class="post-list"', 1)[1]
    assert blog_cards.find("sds-max-vs-sds-plus.html") < blog_cards.find("year-two-tools.html")
    assert blog_cards.find("sds-max-vs-sds-plus.html") < blog_cards.find("dual-pack-outdoor.html")
    assert blog_cards.find("dual-pack-outdoor.html") < blog_cards.find("amazon-au-110v-chargers.html")
    assert blog_cards.find("amazon-au-110v-chargers.html") < blog_cards.find("year-two-tools.html")
    assert blog_cards.find("year-two-tools.html") < blog_cards.find("traps.html")
    assert blog_cards.find('datetime="2026-09-05"') < blog_cards.find('datetime="2026-09-04"')
    assert home_cards.find("sds-max-vs-sds-plus.html") < home_cards.find("traps.html")
    assert "post-card-media" in home and "Latest posts" in home
    assert (ROOT / "images" / "flexvolt.webp").is_file()
    assert (ROOT / "images" / "flexvolt.jpg").is_file()
    assert (ROOT / "images" / "sds-max.webp").is_file()
    assert (ROOT / "images" / "dual-pack.jpg").is_file()
    assert (ROOT / "images" / "grey-charger.webp").is_file()
    traps_feat = (ROOT / "traps.html").read_text(encoding="utf-8")
    assert "images/flexvolt.webp" in traps_feat and "post-featured" in traps_feat
    assert "Stock photo via Unsplash" in traps_feat
    assert "4 September 2026" in traps_feat
    sds_html = (ROOT / "sds-max-vs-sds-plus.html").read_text(encoding="utf-8")
    assert "SDS-MAX vs SDS-plus" in sds_html and "matrix.html" in sds_html
    assert "images/sds-max.webp" in sds_html and "matrix-closer" in sds_html
    dual_html = (ROOT / "dual-pack-outdoor.html").read_text(encoding="utf-8")
    assert "Dual-pack outdoor" in dual_html and "two" in dual_html.lower()
    assert "images/dual-pack.webp" in dual_html and "matrix-closer" in dual_html
    charger_html = (ROOT / "amazon-au-110v-chargers.html").read_text(encoding="utf-8")
    assert "110" in charger_html and "230" in charger_html
    assert "images/grey-charger.webp" in charger_html and "matrix-closer" in charger_html
    sm = (ROOT / "sitemap.xml").read_text(encoding="utf-8")
    assert "makita-table-saw.html" in sm
    assert "matrix.html" in sm
    assert "blog.html" in sm
    assert "year-two-tools.html" in sm
    assert "sds-max-vs-sds-plus.html" in sm
    assert "dual-pack-outdoor.html" in sm
    assert "amazon-au-110v-chargers.html" in sm
    # Nav order: Blog primary
    assert 'href="blog.html"' in home
    assert "Blog" in (ROOT / "matrix.html").read_text(encoding="utf-8")

    sync_names = [
        "index.html",
        "blog.html",
        "matrix.html",
        "traps.html",
        "sds-max-vs-sds-plus.html",
        "dual-pack-outdoor.html",
        "amazon-au-110v-chargers.html",
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
