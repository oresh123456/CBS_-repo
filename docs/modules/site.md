# site

Source: `index.html`

Single-file static catalog browser (GitHub Pages, `.nojekyll`). Hebrew RTL.

## Inputs
- Embedded catalog JSON `#cbs-data` ([data-shapes](data-shapes.md#catalog)); reads `meta.total`, `meta.last_update`, `dicts`, `rows`.

## Behaviour
- Cascading filters over hierarchy (L1–L4, leaf) + dims (time, unit, calc, data, price), text search, active chips.
- Per-series XLS link: `apis.cbs.gov.il/series/data/list?id=<id>&format=xls&download=true&lang=he`; "download all" enabled when ≤30 matches.
