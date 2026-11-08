# site

Source: `index.html`

Single-file static catalog browser (GitHub Pages, `.nojekyll`). Hebrew RTL.

## Inputs
- Embedded catalog JSON `#cbs-data` ([data-shapes](data-shapes.md#catalog)); reads `meta.total`, `meta.last_update`, `dicts`, `rows`.

## Behaviour
- Cascading filters over hierarchy (L1–L4, leaf) + dims (time, unit, calc, data, price), text search, active chips.
- Excel export built in browser (SheetJS 0.18.5, cdnjs, lazy-loaded) from `apis.cbs.gov.il/series/data/list?id=<id>&format=json&lang=he&pagesize=1000` (CORS `*`). Per-row button = 1 series; "download all" = all matches in one file, enabled when ≤30.
- **One id per request** (5 parallel). Multi-id requests are unsafe: CBS pads some ids (e.g. 59015, 58976: "Result no found" alone) with 376 null obs that fill pages while `total_items` ignores them → real obs cut off.
- Pages read until a short page (not trusting `last_page` alone); null values dropped; conflicting duplicate period → error. 500 `Result no found`/`Series Path Data` = no data (column marked, single download → message).
- Short response (obs < `total_items`, seen once transiently): retry ×3, then warning in `הערה` column + alert. Never silent.
- Not CBS's `format=xls`: that is a raw dump (paging/id columns, metadata repeated per row) and stops at 100 obs.
- Workbook (RTL): `נתונים` = header rows (title = deepest topic level — name, topic path, unit, frequency, data type, id), then periods ascending × one column per series, source line; `פרטי הסדרות` = one row per series incl. last update, obs count, API link. Names come from the embedded catalog (API path can be null).
