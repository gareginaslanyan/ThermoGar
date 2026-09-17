"""Таблица по memlog: python table.py <stage>/<job>.memlog.jsonl ..."""
import json, sys
for path in sys.argv[1:]:
    print(f"# {path}")
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
        extra = "".join(f" {k}={r[k]}" for k in ("pool_workers", "apptest_alive", "rss_after_gc_gib") if k in r)
        print(f"{r['test'].split('::')[1]:52} {r['seconds']:7} {r['growth_gib']:7} {r['rss_after_gib']:6} {r['peak_tree_gib']:6} figs={r['open_figures']}{extra}")
