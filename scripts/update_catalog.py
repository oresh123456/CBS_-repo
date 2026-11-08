"""Refresh CBS series catalog: fetch all series from apis.cbs.gov.il,
write catalog.json, re-embed into index.html (<script id="cbs-data">).

Finished groups are cached in .cache/catalog, so a rerun resumes. Output files
are written only if every group succeeded.

Usage:  python scripts/update_catalog.py [--workers 6] [--no-html] [--fresh]
"""
import argparse
import datetime as dt
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

API = "https://apis.cbs.gov.il/series"
ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache" / "catalog"
CACHE_MAX_AGE = 48 * 3600  # older cached groups are refetched
COLUMNS = ["id", "L1", "L2", "L3", "L4", "leaf", "time", "data", "unit", "calc", "price", "update"]


class NoData(Exception):
    """API says path has no series. Usually permanent, occasionally transient."""


class ShortResponse(ValueError):
    """Fewer series than total_items. Split to check; accepted if it can't be split."""

    def __init__(self, series, total):
        super().__init__(f"got {len(series)} of {total} series")
        self.series = series


def get(url, tries=5):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "cbs-catalog-updater"})
            with urllib.request.urlopen(req, timeout=600) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            body = e.read()
            if b"Series Path Data" in body or b"Result no found" in body:
                raise NoData(url) from e
            err = e
        except Exception as e:  # noqa: BLE001
            err = e
        if i == tries - 1:
            raise err
        wait = 10 * (i + 1)
        print(f"  retry {i+1} in {wait}s: {url} ({err})", file=sys.stderr)
        time.sleep(wait)


def listing(url, tries, depth=None):
    """Unique catalog paths from all pages, cut to depth if given."""
    seen, page = {}, 1
    while True:
        d = get(f"{url}&format=json&lang=he&pagesize=1000&page={page}", tries)["catalogs"]
        for c in d["catalog"]:
            p = list(c["path"])[:depth]
            while p and p[-1] is None:  # [47,2,1,None] = no L4 under [47,2,1]
                p.pop()
            seen[tuple(p)] = p
        if page >= d["paging"]["last_page"]:
            return list(seen.values())
        page += 1


def level(lvl, subj=None, tries=5):
    q = f"&subject={subj}" if subj else ""
    return listing(f"{API}/catalog/level?id={lvl}{q}", tries)


def below(path, depth, tries=2):
    """Prefixes from catalog/path, which lists leaf paths; works for subjects where
    catalog/level returns 500 (seen: 26, 31)."""
    return listing(f"{API}/catalog/path?id={','.join(map(str, path))}", tries, depth)


def groups(subj):
    """Fetch units for subject: L3 prefixes from catalog/path, which is complete;
    catalog/level omits groups (subject 18: 4 of 18 L3s). Else level, else whole subject."""
    try:
        paths = below([subj], 3)
        if paths:
            return paths
    except Exception:  # noqa: BLE001
        print(f"  catalog/path failed for {subj}", file=sys.stderr)
    for lvl in (3, 2):
        try:
            paths = level(lvl, subj, tries=1)
        except Exception:  # noqa: BLE001
            continue
        if paths:
            return paths
    print(f"  fetching whole subject {subj}", file=sys.stderr)
    return [[subj]]


def children(path):
    """Paths one level below path."""
    n = len(path)
    try:
        paths = below(path, n + 1)
    except Exception:  # noqa: BLE001
        paths = level(n + 1, path[0], tries=1)
    return [p for p in paths if p[:n] == path and len(p) > n]


def series_under(path, tries=5):
    # NB: data/path ignores paging -> returns every series under path in one response
    d = get(f"{API}/data/path?id={','.join(map(str, path))}&format=json&lang=he&last=1", tries)
    ds = d["DataSet"]
    series = ds.get("Series") or []
    if len(series) < ds["paging"]["total_items"]:  # total_items is off both ways (29 vs 30, 7 vs 6 seen)
        raise ShortResponse(series, ds["paging"]["total_items"])
    return series


def cache_file(path):
    return CACHE / ("_".join(map(str, path)) + ".json")


def cache_load(path):
    f = cache_file(path)
    if not f.exists() or time.time() - f.stat().st_mtime > CACHE_MAX_AGE:
        return None
    return json.loads(f.read_text(encoding="utf-8"))


def cache_save(path, recs):
    f = cache_file(path)
    tmp = f.with_name(f"{f.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(recs, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, f)  # atomic: a killed run never leaves a half-written group


def fetch_group(path):
    """Return (recs, failures, no_data paths). A group that keeps failing is split one level down."""
    hit = cache_load(path)
    if hit is not None:
        return hit, [], []
    try:
        series = series_under(path, tries=3 if len(path) < 4 else 5)
    except NoData:
        return [], [], [path]
    except Exception as e:  # noqa: BLE001
        kids, err = [], str(e)
        if len(path) < 4:
            try:
                kids = children(path)
            except Exception as e2:  # noqa: BLE001
                err += f"; split failed: {e2}"
        if kids:
            print(f"  splitting {path} into {len(kids)} groups", file=sys.stderr)
            recs, failed, empty = [], [], []
            for k in kids:
                r, bad, em = fetch_group(k)
                recs += r
                failed += bad
                empty += em
            return recs, failed, empty
        if not isinstance(e, ShortResponse):
            return [], [(path, err)], []
        print(f"  accepted {path}: {err}", file=sys.stderr)
        series = e.series
    recs = [[s["id"], fields(s), (s.get("update") or "")[:10]] for s in series]
    cache_save(path, recs)
    return recs, [], []


def run_all(ex, fn, items):
    """Like ex.map, but with timed waits: an untimed one blocks Ctrl+C on Windows."""
    futs = [ex.submit(fn, x) for x in items]
    todo = set(futs)
    while todo:
        _, todo = wait(todo, timeout=1, return_when=FIRST_COMPLETED)
    return [f.result() for f in futs]


def fetch_all(workers):
    CACHE.mkdir(parents=True, exist_ok=True)
    subs = [p[0] for p in level(1)]
    recs, failed, empty = {}, [], []
    with ThreadPoolExecutor(workers) as ex:
        try:
            l2 = [p for ps in run_all(ex, groups, subs) for p in ps]
            print(f"{len(subs)} subjects, {len(l2)} groups", file=sys.stderr)
            pending = {ex.submit(fetch_group, p) for p in l2}
            total, i = len(pending), 0
            while pending:
                # timed wait: an untimed one blocks Ctrl+C on Windows
                done, pending = wait(pending, timeout=1, return_when=FIRST_COMPLETED)
                for f in done:
                    i += 1
                    got, bad, em = f.result()
                    for r in got:
                        recs[r[0]] = r
                    failed += bad
                    empty += em
                    if i % 20 == 0 or i == total:
                        print(f"  {i}/{total} groups, {len(recs)} series, {len(failed)} failed, "
                              f"{len(empty)} no data", file=sys.stderr)
            if empty:  # second look, minutes later: NoData is sometimes transient
                print(f"rechecking {len(empty)} no-data paths", file=sys.stderr)
                confirmed = []
                for got, bad, em in run_all(ex, fetch_group, empty):
                    for r in got:
                        recs[r[0]] = r
                    failed += bad
                    confirmed += em
                empty = confirmed
        except KeyboardInterrupt:
            # hard exit: leaving the with block would wait for every queued download
            print("stopped; finished groups are cached, rerun to resume", file=sys.stderr)
            sys.stderr.flush()
            os._exit(130)
    return list(recs.values()), failed, empty


def previous():
    """{id: fields} from the existing catalog.json; {} if none."""
    f = ROOT / "catalog.json"
    if not f.exists():
        return {}
    c = json.loads(f.read_text(encoding="utf-8"))
    keys = COLUMNS[1:-1]
    return {r[0]: {k: c["dicts"][k][r[i + 1]].strip() if r[i + 1] >= 0 else "" for i, k in enumerate(keys)}
            for r in c["rows"]}


def by_ids(ids):
    try:
        d = get(f"{API}/data/list?id={','.join(map(str, ids))}&format=json&lang=he&last=1")
    except NoData:
        return []
    return d["DataSet"].get("Series") or []


def recover(recs, prev, workers):
    """Previous-catalog series data/path didn't return but data/list still serves
    (path: null, or under a no-data path). Names come from prev when path is null.
    Series with no observations are dropped. Returns (recs, failures)."""
    have = {r[0] for r in recs}
    missing = sorted(set(prev) - have)
    print(f"checking {len(missing)} previous series by id", file=sys.stderr)
    out, failed = [], []
    with ThreadPoolExecutor(workers) as ex:
        try:
            pending = {ex.submit(by_ids, missing[i:i + 50]): missing[i:i + 50] for i in range(0, len(missing), 50)}
            todo = set(pending)
            while todo:
                done, todo = wait(todo, timeout=1, return_when=FIRST_COMPLETED)
                for f in done:
                    try:
                        series = f.result()
                    except Exception as e:  # noqa: BLE001
                        failed.append((pending[f][:1], f"data/list: {e}"))
                        continue
                    for s in series:
                        if s.get("obs"):
                            out.append([s["id"], with_names(fields(s), prev.get(s["id"])), (s.get("update") or "")[:10]])
        except KeyboardInterrupt:
            print("stopped; finished groups are cached, rerun to resume", file=sys.stderr)
            sys.stderr.flush()
            os._exit(130)
    print(f"  recovered {len(out)} series by id", file=sys.stderr)
    return out, failed


def with_names(f, old):
    """Fill hierarchy names from old fields when API gave none (path: null)."""
    if f["L1"] or not old:
        return f
    return {**f, **{k: old[k] for k in ("L1", "L2", "L3", "L4", "leaf")}}


def fields(s):
    p = s.get("path") or {}  # API can return path: null
    nm = lambda o: ((o or {}).get("name") or "").strip()  # noqa: E731
    return {
        "L1": nm(p.get("level1")), "L2": nm(p.get("level2")), "L3": nm(p.get("level3")),
        "L4": nm(p.get("level4")), "leaf": nm(p.get("name_id")),
        "time": nm(s.get("time")), "data": nm(s.get("data")), "unit": nm(s.get("unit")),
        "calc": nm(s.get("calc")), "price": nm(s.get("price")),
    }


def build(recs):
    keys = COLUMNS[1:-1]
    dicts = {k: sorted({f[k] for _, f, _ in recs if f[k]}) for k in keys}
    idx = {k: {v: i for i, v in enumerate(dicts[k])} for k in keys}
    rows = sorted(
        [[sid] + [idx[k].get(f[k], -1) for k in keys] + [upd] for sid, f, upd in recs],
        key=lambda r: r[0],
    )
    meta = {
        "total": len(rows),
        "generated_at": dt.date.today().isoformat(),
        "last_update": max((r[-1] for r in rows), default=""),
        "columns": COLUMNS,
        "source": "CBS Israel API — apis.cbs.gov.il/series",
    }
    return {"meta": meta, "dicts": dicts, "rows": rows}


def embed(cat):
    html_path = ROOT / "index.html"
    html = html_path.read_text(encoding="utf-8")
    blob = json.dumps(cat, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    pat = re.compile(r'(<script type="application/json" id="cbs-data">)(.*?)(</script>)', re.S)
    if not pat.search(html):
        sys.exit("cbs-data script tag not found in index.html")
    html_path.write_text(pat.sub(lambda m: m.group(1) + blob + m.group(3), html, count=1), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--no-html", action="store_true", help="only write catalog.json")
    ap.add_argument("--fresh", action="store_true", help="ignore cache, refetch everything")
    a = ap.parse_args()
    t0 = time.time()
    if a.fresh:
        shutil.rmtree(CACHE, ignore_errors=True)
    prev = previous()
    recs, failed, empty = fetch_all(a.workers)
    found, bad = recover(recs, prev, a.workers)
    recs += found
    failed += bad
    for r in recs:
        r[1] = with_names(r[1], prev.get(r[0]))
    if empty:
        print(f"  {len(empty)} paths have no series at CBS: {empty[:10]}{' ...' if len(empty) > 10 else ''}",
              file=sys.stderr)
    if failed:
        for path, err in failed:
            print(f"  FAILED {path}: {err}", file=sys.stderr)
        sys.exit(f"{len(failed)} groups failed; nothing written. Rerun to resume ({len(recs)} series cached).")
    no_path = [r[0] for r in recs if not r[1]["L1"]]
    if no_path:
        print(f"  {len(no_path)} series have no path at CBS: {sorted(no_path)[:10]}", file=sys.stderr)
    cat = build(recs)
    (ROOT / "catalog.json").write_text(
        json.dumps(cat, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    if not a.no_html:
        embed(cat)
    m = cat["meta"]
    print(f"done: {m['total']} series, last_update {m['last_update']}, {time.time()-t0:.0f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
