"""21-Г, шаг 2: строки описи для tasks/NA_UTVERZHDENIE_21.md.

Делит строки описи (build_opis.ROWS) на три группы по столбцу «новое / уже
есть»: с новыми словами (часть 1, источник «в»), без новых слов (часть 2) и
«без изменений» (в список не идут). Одинаковое предложение в нескольких
строках описи — одна строка списка, адреса через запятую. Печатает markdown
двух таблиц и итоги; ключ --merge-into задаёт предложения, которые уже стоят
в части 1 из других источников (их адреса дописываются туда, а не отдельной
строкой).
"""
from __future__ import annotations

import re
import sys

import build_opis as opis
import screen_corpus as corpus

# Предложения описи, совпадающие дословно с фразами части 1 из других источников.
ALREADY_IN_PART1 = {
    "База не подключена. Выберите базу в боковой панели.": "В3 21-В",
    "{фаза}: энергия не рассчитана": "строка 34 CSV 21-В",
}


def _today(row) -> str:
    addrs, _, _, today, *_ = row
    return corpus.text_at(*addrs[0]) if today is None else today


def _short(text: str, finding: str, limit: int = 220) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    tokens = [t.strip(" «»") for t in re.split(r"[;,]", finding) if t.strip()]
    positions = [(text.find(t), t) for t in tokens if t and text.find(t) >= 0]
    if positions:
        start, token = min(positions)
        end = min(len(text), start + len(token))
        # до конца слова
        while end < len(text) and text[end] not in " .,;:":
            end += 1
        if end < limit * 2:
            return text[:end] + " …"
    return text[:limit] + " …"


def _new_words(status: str) -> str:
    match = re.search(r"[Нн]овое:\s*(.*)$", status)
    return match.group(1).strip() if match else status


def split_rows():
    part1, part2, unchanged = {}, {}, []
    for row in opis.ROWS:
        addrs, kind, where, today, finding, cls, proposal, status, why = row
        address = ", ".join(f"app/{n}:{l}" for n, l in addrs)
        if proposal.startswith("без изменений"):
            unchanged.append((address, _today(row), proposal))
            continue
        target = part1 if re.search(r"[Нн]овое:", status) else part2
        slot = target.setdefault(proposal, {"where": [], "today": [], "addr": [], "new": _new_words(status), "finding": finding})
        slot["where"].append(where)
        slot["today"].append(_short(_today(row), finding))
        slot["addr"].append(address)
    return part1, part2, unchanged


def cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def main() -> int:
    part1, part2, unchanged = split_rows()
    out = sys.stdout
    out.write("## part1\n")
    for proposal, slot in part1.items():
        merged = ALREADY_IN_PART1.get(proposal)
        out.write(
            "| {n} | " + cell("; ".join(dict.fromkeys(slot["where"]))) + " | "
            + cell(" / ".join(dict.fromkeys(slot["today"]))) + " | " + cell(proposal) + " | "
            + cell(slot["new"]) + " | " + cell(", ".join(slot["addr"])) + (f" | MERGE {merged}" if merged else "") + " |\n"
        )
    out.write("## part2\n")
    for proposal, slot in part2.items():
        out.write(
            "| {n} | " + cell("; ".join(dict.fromkeys(slot["where"]))) + " | "
            + cell(" / ".join(dict.fromkeys(slot["today"]))) + " | " + cell(proposal) + " | "
            + cell(", ".join(slot["addr"])) + " |\n"
        )
    out.write("## unchanged\n")
    for address, today, proposal in unchanged:
        out.write(f"- {address}: {cell(today[:100])} — {proposal}\n")
    out.write(f"## counts part1={len(part1)} part2={len(part2)} unchanged={len(unchanged)}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
