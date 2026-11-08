# update-catalog

Source: `scripts/update_catalog.py`

Refreshes the series catalog from the public CBS API.

## Run
`python scripts/update_catalog.py [--workers 6] [--no-html] [--fresh]` (stdlib only, Python 3.9+). Slow: ~85ms/series server-side, expect 1h+.

## Inputs
- `catalog/level?id=1` → subjects; `catalog/path?id=S` → all leaf paths, cut to L3.
- Existing `catalog.json` → previous ids + names for recovery.
- `data/path?id=S,L2,L3&last=1` per L3 (paging ignored by API; split keeps responses small).

## Outputs
- `catalog.json` + replaces contents of `<script id="cbs-data">` in `index.html` (unless `--no-html`). Shape: [data-shapes](data-shapes.md#catalog).

## Notes
- All subjects incl. SDDS PLUS (distinct ids). Dedup by series id.
- Resume: each finished group cached in `.cache/catalog/<path>.json` (gitignored, 48h max age; `--fresh` clears). Rerun skips cached groups.
- Fetch unit = L3 (L2s reach ~20k series and drop connections). Groups come from `catalog/path?id=S` prefixes: `catalog/level` silently omits groups (subject 18: 4 of 18 L3s) and 500s on some subjects. Fallback: level, then whole subject (54, 71: all catalog calls 500, `data/path` no data). Group failing 3 tries splits one level down; L4 gets 5 tries.
- Recovery: ids in the existing `catalog.json` not returned by `data/path` are looked up via `data/list` in batches of 50. Needed because some live series have `path: null` or sit under no-data paths. Null-path series keep names from previous catalog; no-observation ones are dropped. **So keep `catalog.json`: it is an input too.**
- `paging.total_items` is unreliable both ways. Fewer series than it says: group is split to check; if it can't split, accepted with an `accepted` warning (repeat calls return the same set).
- 500 `Error: Series Path Data` = path listed in catalog but no series (usually permanent, e.g. most of subject 26; sometimes transient). No retry/split; rechecked once at end of run, then skipped and counted.
- Old catalog (2026-04-29) had 173,492 rows but 94,873 unique ids: paging duplicates. Many ids are also gone from CBS ("Result no found"), so new totals are lower by design.
- Trailing `None` in catalog paths = level doesn't exist; stripped.
- Any group still failed: lists them, exits 1, writes nothing.
