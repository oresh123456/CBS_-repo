# Modules

| Module | Role | Governance |
|---|---|---|
| [update-catalog](update-catalog.md) | fetch CBS API → `catalog.json` + embed in `index.html` | none |
| [site](site.md) | static GH Pages catalog browser (`index.html`) | none |

```
apis.cbs.gov.il/series ──> update-catalog ──> catalog.json
                                         └──> index.html <script id="cbs-data"> ──> site (browser)
```

## Rules for Subagents
- Read only target module doc + direct interfaces + [data-shapes](data-shapes.md).
- Shapes live only in data-shapes.md.
