"""21-Г, шаг 1: кандидаты в опись латиницы и служебных слов на экране.

Скрипт только читает app/*.py и печатает строковые литералы (с частями
f-строк), в которых есть находка по правилам задания 21-Г. Решение, выходит
ли литерал на экран, принимается вручную по коду; скрипт его не принимает.

Запуск из корня рабочей копии:
    python results/wave21_g/scripts/extract_candidates.py > candidates.tsv
    python results/wave21_g/scripts/extract_candidates.py --latin > latin_in_st.tsv
"""
from __future__ import annotations

import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
APP = ROOT / "app"

CYR = re.compile(r"[А-Яа-яЁё]")
LATIN_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9_\-./]*")

# Не находка по заданию 21-Г: фазы, элементы, величины, единицы, модели и
# авторы материаловеда, имена программ Kawin и pycalphad, подписи баз,
# форматы выгрузки. Имена фаз ловятся шаблоном ниже.
ALLOWED = {
    # элементы
    *"H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn "
    "Ga Ge As Se Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I Xe Cs Ba La "
    "Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi "
    "FE NI CR AL MO CO MN SI NB TI TA HF ZR CU VA".split(),
    # величины и единицы
    "E", "G", "T", "T0", "x", "X", "k_y", "d", "Pa", "MPa", "GPa", "kPa", "nm", "m", "s",
    "J", "mol", "kg", "g", "cm", "K", "h", "min", "P", "M", "N", "r", "u", "t",
    # модели, авторы, программы
    "CALPHAD", "Calphad", "TDB", "KWN", "Scheil", "Gulliver", "Scheil-Gulliver",
    "Hall", "Petch", "Hall-Petch", "Taylor", "Orowan", "Fleischer", "Labusch",
    "Voigt", "Reuss", "Hill", "VRH", "Kawin", "kawin", "pycalphad", "ThermoGar",
    # подписи баз
    "mc_ni", "mc_fe", "mc_al",
    # форматы выгрузки
    "Excel", "CSV", "PNG", "JSON", "NPZ",
}
# Имена фаз — из самих баз (только чтение): строки PHASE в databases/converted.
PHASE_NAMES = {
    match.group(1).strip("%#").upper()
    for tdb in (ROOT / "databases" / "converted").rglob("*.tdb")
    for match in re.finditer(r"(?im)^\s*PHASE\s+([A-Z0-9_#%]+)", tdb.read_text(encoding="utf-8", errors="replace"))
}
PHASE_NAMES |= {"LAVES", "FCC", "BCC", "HCP", "SIGMA", "GAMMA", "NIAL", "FE3C", "ALN", "L12"}

RU_PROGRAMMER = re.compile(
    r"релиз|контекст|привязк|профил|отпечат|парсер|конвертер|\bпатч|воркер|кэш|\bкеш|"
    r"бэкенд|бекенд|\bдвиж[оке]|сериализ|дескрипт|артефакт|манифест|брокер|дайджест|"
    r"квитанц|\bконверт|\bхеш|\bхэш|каноническ|детерминир|сигнатур|контрольн\w* сумм|"
    r"трассиров|\bстек|таймаут|тайм-аут|\bпорт\b|\bсервер|идентификатор|\bключ|"
    r"окружени|\bпакет\w*\b(?<!пакетный)(?<!пакетного)(?<!пакетном)|\bимпорт|\bмодул|\bскрипт|репозитор|"
    r"\bфлаг|\bсхем|валидац|верифиц|адаптер|бэкап|решател|\bвызов|\bочеред|\bпоток|"
    r"\bпроцесс|\bбайт|кодировк|\bаренд|fail|fallback|dispatch|\bзапасн|\bсыр[оы]|"
    r"\bисключени[еяю]\b|\bподмен",
    re.IGNORECASE,
)


def is_docstring(node: ast.AST, parents: dict) -> bool:
    parent = parents.get(node)
    if not isinstance(parent, ast.Expr):
        return False
    owner = parents.get(parent)
    body = getattr(owner, "body", None)
    return bool(body) and body[0] is parent


def literal_pieces(tree: ast.AST):
    parents: dict = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if isinstance(parents.get(node), ast.JoinedStr):
                continue
            if is_docstring(node, parents):
                continue
            yield node.lineno, node.end_lineno, node.value
        elif isinstance(node, ast.JoinedStr):
            text = "".join(
                v.value if isinstance(v, ast.Constant) else "{" + ast.unparse(v.value) + "}"
                for v in node.values
            )
            yield node.lineno, node.end_lineno, text


def findings(text: str) -> list[str]:
    found: list[str] = []
    plain = re.sub(r"\{[^{}]*\}", " ", text)
    for token in LATIN_TOKEN.findall(plain):
        token = token.strip("-./")
        if not token or token in ALLOWED or token.upper() in PHASE_NAMES:
            continue
        if re.fullmatch(r"[A-Z][a-z]?\d*", token):  # элемент с индексом
            continue
        found.append(token)
    found += [m.group(0) for m in RU_PROGRAMMER.finditer(plain)]
    return found


def main() -> int:
    out = sys.stdout
    out.write("file\tline\tend\tfindings\ttext\n")
    for path in sorted(APP.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for line, end, text in sorted(literal_pieces(tree)):
            if not CYR.search(text):
                continue
            hit = findings(text)
            if not hit:
                continue
            flat = text.replace("\t", " ").replace("\n", "\\n")
            out.write(f"{path.name}\t{line}\t{end}\t{', '.join(dict.fromkeys(hit))}\t{flat}\n")
    return 0



# --- вторая выборка: латиница без кириллицы прямо в вызовах Streamlit ---
ST_METHODS = {
    "error", "warning", "info", "success", "caption", "markdown", "write", "header",
    "subheader", "title", "button", "download_button", "checkbox", "radio", "selectbox",
    "multiselect", "number_input", "text_input", "text_area", "slider", "select_slider",
    "tabs", "expander", "metric", "file_uploader", "toggle", "code", "progress", "status",
    "toast", "form_submit_button", "TextColumn", "NumberColumn", "Column", "SelectboxColumn",
    "CheckboxColumn", "popover", "update", "data_editor", "dataframe",
}


SCREEN_KEYWORDS = {"label", "help", "placeholder", "options", "body", "value", "caption", "title"}


def screen_constants(node: ast.AST):
    """Строки, которые сами идут на экран: без ключей словарей и аргументов вызовов."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        yield node
    elif isinstance(node, (ast.List, ast.Tuple)):
        for elt in node.elts:
            yield from screen_constants(elt)
    elif isinstance(node, ast.JoinedStr):
        for value in node.values:
            yield from screen_constants(value)
    elif isinstance(node, ast.BinOp):
        yield from screen_constants(node.left)
        yield from screen_constants(node.right)
    elif isinstance(node, ast.IfExp):
        yield from screen_constants(node.body)
        yield from screen_constants(node.orelse)


def latin_in_st_calls(tree: ast.AST):
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in ST_METHODS:
            continue
        args = list(node.args[:2]) + [kw.value for kw in node.keywords if kw.arg in SCREEN_KEYWORDS]
        for arg in args:
            for sub in screen_constants(arg):
                text = sub.value
                if CYR.search(text) or not LATIN_TOKEN.search(text):
                    continue
                hit = findings(text)
                if hit:
                    yield sub.lineno, node.func.attr, ", ".join(dict.fromkeys(hit)), text


def main_latin() -> int:
    out = sys.stdout
    out.write("file\tline\tcall\tfindings\ttext\n")
    for path in sorted(APP.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for line, call, hit, text in sorted(set(latin_in_st_calls(tree))):
            flat = text.replace("\t", " ").replace("\n", "\n")
            out.write(f"{path.name}\t{line}\t{call}\t{hit}\t{flat}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main_latin() if "--latin" in sys.argv else main())
