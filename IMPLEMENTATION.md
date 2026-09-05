# Which Pack — Astra implementation notes (2026-09-05)

Implemented against `/workspace/affiliate-business/design/ASTRA_BRIEF.md`.  
Primary output: `/workspace/which-pack-site/`. Synced key files to `/workspace/affiliate-business/mvp/`.  
**No git push** (Chief reviews).

## One-command regenerate

```bash
cd /workspace/which-pack-site && python3 build_site.py
```

Reads `coverage.json`, rewrites `index.html` / `traps.html` / `method.html` / `disclosure.html` / `styles.css` / `favicon.svg` / `og.svg` / `og.png` / `sitemap.xml`, asserts 24 rows + Astra tokens, syncs to mvp.

## Done vs brief

| Requirement | Status |
|---|---|
| Warm page `#F5F4EF`, light theme, Astra status colours (missing not red-alarm) | Yes |
| H1 + support copy exact | Yes |
| SSR full matrix; JS off works | Yes (search/filter/select are progressive enhancement) |
| GSC meta + canonical kept | Yes |
| Row order: familiar verified first; banding + unknown-heavy last | Yes (circular → … → press → banding) |
| Platform headers brand + voltage lines | Yes (`Milwaukee / M18 · 18V`, etc.) |
| Hero SVG (generic drill/battery/saw) + caption | Yes — original, no OEM logos |
| Legend + Associate disclosure before matrix | Yes (“I earn… Affiliate relationships do not determine…”) |
| Amazon Search vs View; Ryobi no Amazon | Yes — all current URLs are `/s?` → **Search**; Ryobi never linked |
| Sticky tool column; horizontal scroll; no fixed-height nested trap | Yes (`overflow-x: auto`, no matrix `max-height`) |
| Pages: index, traps, method, disclosure | Same visual language |
| OG 1200×630 | `og.png` (+ `og.svg`); meta absolute under `/which-pack/` |
| Relative CSS/JS/asset paths | Yes (GitHub Pages project base) |
| JSON-LD WebSite/WebPage only | Yes |
| Cells from coverage.json only | Yes — never invents status |

## Deviations / notes

1. **Requirement line** — `coverage.json` has no `requirement` field. Soft hints are derived from existing notes (dual-pack / SDS-MAX / 230mm+ chop) and scoped per platform where possible. Not a new coverage claim.
2. **Model codes** — extracted best-effort from evidence URL slugs or Amazon `k=` when the key looks like a SKU. Category-only evidence → host + date only (no invented model).
3. **Amazon “destination checked”** — links emit only when `status=has` and `amazon` is present in JSON (and platform ≠ Ryobi). Label is honest Search/View from URL shape; today all are Search.
4. **`og.png`** — built via Chrome headless from `og.svg` when available; stdlib geometric PNG fallback otherwise.
5. **Selected-tools filter** — checkboxes injected by JS only (progressive enhancement); matrix remains complete with JS off.
6. **Trap callout** retained above the matrix (brief allows supporting pages; callout is calm, not a quiz/hero wall).

## Files

- `build_site.py` — sole generator
- `coverage.json` — data source (do not invent cells)
- `index.html`, `traps.html`, `method.html`, `disclosure.html`
- `styles.css`, `favicon.svg`, `og.svg`, `og.png`
- `sitemap.xml`, `robots.txt`, `.nojekyll` (unchanged verification files kept)
