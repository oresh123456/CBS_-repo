# site

Source: `index.html`

Single-file static catalog browser (GitHub Pages, `.nojekyll`). Hebrew RTL.

## Inputs
- Embedded catalog JSON `#cbs-data` ([data-shapes](data-shapes.md#catalog)); reads `meta.total`, `meta.last_update`, `dicts`, `rows`.

## Behaviour
- Cascading filters over hierarchy (L1–L4, leaf) + dims (time, unit, calc, data, price), text search, active chips.
- Excel export built in browser (SheetJS 0.18.5, cdnjs, lazy-loaded) from `apis.cbs.gov.il/series/data/list?id=<ids>&format=json&lang=he&pagesize=1000` (CORS `*`; all pages followed, 10 ids/request). Per-row button = 1 series; "download all" = all matches in one file, enabled when ≤30.
- Not CBS's `format=xls`: that is a raw dump (paging/id columns, metadata repeated per row) and stops at 100 obs.
- Workbook (RTL): `נתונים` = header rows (title = deepest topic level — name, topic path, unit, frequency, data type, id), then periods ascending × one column per series, source line; `פרטי הסדרות` = one row per series incl. last update, obs count, API link. Names come from the embedded catalog (API path can be null).
