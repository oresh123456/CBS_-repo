# Data shapes

## Catalog (`catalog.json` == `index.html` `<script type="application/json" id="cbs-data">`)

```json
{
  "meta": {"total": 0, "generated_at": "YYYY-MM-DD", "last_update": "YYYY-MM-DD",
           "columns": ["id","L1","L2","L3","L4","leaf","time","data","unit","calc","price","update"],
           "source": "CBS Israel API — apis.cbs.gov.il/series"},
  "dicts": {"L1": ["..."], "L2": [], "L3": [], "L4": [], "leaf": [],
            "time": [], "data": [], "unit": [], "calc": [], "price": []},
  "rows": [[3700, 0, 0, 2, 412, 2607, 3, 119, 20, -1, -1, "2026-03-15"]]
}
```

- row = `[id, <10 dict indices in columns order>, update]`; index `-1` = empty name.
- dicts: unique non-empty names, sorted; rows sorted by id.
- `last_update` = max row `update`; `total` = row count.

## API source (`/series/data/path?id=<L1>,<L2>,<L3>&format=json&lang=he&last=1`)
`DataSet.Series[]`: `id`, `time|data|unit|calc|price: {value,name}`,
`path.level1..level4|name_id: {value,name}`, `update`. Paging params ignored (all series returned).
