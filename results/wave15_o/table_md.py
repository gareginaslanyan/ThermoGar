"""Markdown-таблица «тест | прирост | после теста | пик» по memlog.

    python table_md.py <stage>/<job>.memlog.jsonl ...
"""
import json
import sys


def name(nodeid: str) -> str:
    test = nodeid.split("::", 1)[1]
    try:
        test = test.encode("ascii").decode("unicode_escape")
    except UnicodeError:
        pass
    return test


def fmt(value: float) -> str:
    return f"{value:.2f}".replace(".", ",")


for path in sys.argv[1:]:
    print(f"\n`{path}`\n")
    print("| тест | с | прирост, ГиБ | после теста, ГиБ | пик, ГиБ |")
    print("|---|---|---|---|---|")
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
        print(f"| `{name(r['test'])}` | {r['seconds']:.0f} | {fmt(r['growth_gib'])} | "
              f"{fmt(r['rss_after_gib'])} | {fmt(r['peak_tree_gib'])} |")
