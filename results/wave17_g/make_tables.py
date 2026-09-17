"""Сборка таблиц отчёта 17-Г из results/wave17_g/summary.jsonl.

Пишет results/wave17_g/tables.md: таблица «файл | режим | итог | время | пик |
мин. свободно» по всем прогонам и сводные числа первой строки отчёта.
Ничего не пересчитывает — только раскладывает записи раннера и достаёт из логов
итоговую строку pytest дословно.

    python -B -X utf8 results/wave17_g/make_tables.py
"""
import json
import re
from pathlib import Path

OUT = Path(__file__).resolve().parent
recs = [json.loads(l) for l in (OUT / "summary.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]

_WORDS = ("passed", "failed", "error", "errors", "skipped", "deselected",
          "xfailed", "xpassed", "warning", "warnings")
SUMMARY_RE = re.compile(
    r"^(?:\d+ (?:" + "|".join(_WORDS) + r")|no tests ran|no tests collected)")


def pytest_summary(rec):
    """Итоговая строка pytest дословно — из лога, а не last_line раннера.

    У прогонов, где процесс умер уже после отчёта pytest (Tcl_AsyncDelete),
    last_line — строка аварии, а не итог файла.
    """
    log = OUT / "logs" / (rec["job"] + ".log.txt")
    if not log.exists():
        return rec.get("last_line", "")
    for line in reversed(log.read_text(encoding="utf-8", errors="replace").splitlines()):
        stripped = line.strip().strip("=").strip()
        if stripped and SUMMARY_RE.match(stripped):
            return stripped
    return rec.get("last_line", "")


def mode_of(job):
    if job.startswith("notslow__"):
        return job[len("notslow__"):], '-m "not slow"'
    if job.startswith("scenario__"):
        return job[len("scenario__"):], "сценарий"
    if job.startswith("slow__"):
        rest = job[len("slow__"):]
        if ".py__" in rest:
            name, group = rest.split(".py__", 1)
            return name + ".py", "-m slow, группа " + group
        return rest, "-m slow"
    return job, "?"


def gib(value):
    return "—" if not value else ("%.2f" % value).replace(".", ",")


def verdict(rec):
    if rec.get("outcome"):
        return "НЕ ЗАПУЩЕН"
    if rec.get("aborted_low_memory"):
        return "СНЯТ ПО ПАМЯТИ"
    if rec["job"].startswith("scenario__"):
        return "зелёный" if rec.get("exit") == 0 else "КРАСНЫЙ"
    if re.search(r"\d+ (failed|error)", pytest_summary(rec)):
        return "КРАСНЫЙ"
    # exit 5 — «нет кейсов под маркером», штатный исход, как в 14-Д.
    return "зелёный" if rec.get("exit") in (0, 5) else "КРАСНЫЙ"


rows = ["| файл | режим | exit | итоговая строка pytest | итог | время, с | пик, ГиБ | мин. свободно, ГиБ |",
        "|---|---|---:|---|---|---:|---:|---:|"]
for rec in recs:
    name, mode = mode_of(rec["job"])
    line = rec.get("outcome") or pytest_summary(rec)
    rows.append("| `%s` | %s | %s | `%s` | %s | %.1f | %s | %s |" % (
        name, mode, rec.get("exit", "—"), line, verdict(rec),
        rec.get("seconds", 0), gib(rec.get("peak_tree_gib")), gib(rec.get("min_free_gib"))))

total_s = sum(r.get("seconds", 0) for r in recs)
peak = max([r.get("peak_tree_gib", 0) for r in recs] or [0])
red = sorted({mode_of(r["job"])[0] for r in recs if verdict(r) != "зелёный"})
head = [
    "прогонов: %d" % len(recs),
    "суммарное время: %.0f с = %.2f ч" % (total_s, total_s / 3600),
    "максимальный пик дерева: %s ГиБ" % gib(peak),
    "красных файлов: %d%s" % (len(red), (" — " + ", ".join(red)) if red else ""),
]
(OUT / "tables.md").write_text("\n".join(head) + "\n\n" + "\n".join(rows) + "\n", encoding="utf-8")
print("\n".join(head))
