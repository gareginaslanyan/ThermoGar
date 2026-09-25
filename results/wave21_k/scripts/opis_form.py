"""21-К, шаг 1: опись форм ThermoGar по AST, без импорта модулей app.

Что делает скрипт:
- разбирает файлы app/*.py модулем ast (код приложения не исполняется);
- для каждого экрана с основной кнопкой (type="primary") проходит участок
  кода от заголовка экрана до основной кнопки и выписывает элементы
  интерфейса по порядку; вспомогательные функции, которые рисуют поля
  (phase_selection_editor, _common_inputs, render_physical_overrides_toggle,
  _b4b_requested_phases), подставляются на место вызова;
- умолчания считает по каждой базе ni, al, fe: словари умолчаний берутся
  литералами из AST, список элементов базы — из строк ELEMENT файла TDB,
  простые присваивания участка вычисляются по порядку; что не вычисляется
  без базы (списки фаз), берётся из ручной разметки MANUAL_DEFAULTS или
  остаётся выражением кода;
- обязательность поля (пустое — расчёт отказывает) — ручная разметка
  REQUIRED с адресом проверки файл:строка, найденным чтением кода;
- предложение 9Б по каждому полю — ручная разметка PROPOSAL, из неё
  считается сводка.

Выход:
- results/wave21_k/formy.csv — опись (UTF-8 с BOM, разделитель «;»);
- results/wave21_k/predlozhenie_9b.csv — поля ввода с предложением 9Б;
- сводка на stdout.

Запуск (из корня дерева):
    D:\\Pets\\ThermoGar\\.venv-windows\\Scripts\\python.exe results\\wave21_k\\scripts\\opis_form.py
"""

from __future__ import annotations

import ast
import csv
import re
import sys
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
APP = ROOT / "app"
OUT = ROOT / "results" / "wave21_k"
BASES = ("ni", "al", "fe")

TDB = {
    "ni": ROOT / "databases/converted/mc_ni_v2036_with_mobility.garcalc.tdb",
    "al": ROOT / "databases/converted/al/mc_al_v2037_with_mobility.thermogar.tdb",
    "fe": ROOT / "databases/converted/fe/mc_fe_v2062_with_mobility.thermogar.tdb",
}

# ---------------------------------------------------------------------------
# Разбор модулей и констант
# ---------------------------------------------------------------------------

MODULES: dict[str, ast.Module] = {}
SOURCES: dict[str, list[str]] = {}
for path in sorted(APP.glob("*.py")):
    text = path.read_text(encoding="utf-8")
    MODULES[path.name] = ast.parse(text)
    SOURCES[path.name] = text.splitlines()


def _const_eval(node: ast.AST, env: dict[str, Any]) -> Any:
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "MappingProxyType":
        return dict(_const_eval(node.args[0], env))
    try:
        return ast.literal_eval(node)
    except Exception:
        pass
    code = compile(ast.Expression(node), "<const>", "eval")
    return eval(code, {"__builtins__": {}, **SAFE_BUILTINS, **env})


SAFE_BUILTINS: dict[str, Any] = {
    "float": float, "int": int, "len": len, "str": str, "list": list,
    "sorted": sorted, "max": max, "min": min, "set": set, "dict": dict,
    "tuple": tuple, "bool": bool, "any": any, "all": all, "abs": abs,
    "MappingProxyType": MappingProxyType, "round": round,
}

MODULE_CONSTS: dict[str, dict[str, Any]] = {}
GLOBAL_CONSTS: dict[str, Any] = {}
for _pass in range(3):
    for name, module in MODULES.items():
        consts = MODULE_CONSTS.setdefault(name, {})
        for stmt in module.body:
            targets: list[str] = []
            value = None
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                targets = [stmt.targets[0].id]
                value = stmt.value
            elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name) and stmt.value is not None:
                targets = [stmt.target.id]
                value = stmt.value
            if not targets or targets[0] in consts:
                continue
            try:
                result = _const_eval(value, {**GLOBAL_CONSTS, **consts})
            except Exception:
                continue
            consts[targets[0]] = result
            GLOBAL_CONSTS.setdefault(targets[0], result)


def tdb_elements(path: Path) -> list[str]:
    found: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.strip().split()
        if len(parts) >= 2 and parts[0].upper() == "ELEMENT":
            found.append(parts[1].upper())
    return sorted(element for element in found if element not in {"VA", "/-"})


ELEMENTS = {base: tdb_elements(TDB[base]) for base in BASES}


def element_symbol(element: object) -> str:
    text = str(element).strip()
    return text[:1].upper() + text[1:].lower()


def units_suffix(units: str) -> str:
    return "ат.%" if units == "at" else "мас.%"


APP_CONSTS = MODULE_CONSTS["ThermoGar_app.py"]
DIFF_CONSTS = MODULE_CONSTS["thermogar_diffusion.py"]
PREC_CONSTS = MODULE_CONSTS["thermogar_precipitation.py"]


def base_namespace(base: str, module: str) -> dict[str, Any]:
    definition = dict(APP_CONSTS["DATABASE_DEFINITIONS"][base])
    balance = definition["default_balance"]
    units = definition["default_units"]
    avail = ELEMENTS[base]
    ns: dict[str, Any] = {"__builtins__": {}}
    ns.update(SAFE_BUILTINS)
    ns.update(GLOBAL_CONSTS)
    ns.update(MODULE_CONSTS[module])
    ns.update(
        {
            "database_key": base,
            "definition": definition,
            "balance": balance,
            "units": units,
            "units_label": "атомные %" if units == "at" else "массовые %",
            "available_elements": avail,
            "element_symbol": element_symbol,
            "units_suffix": units_suffix,
            "diagram_defaults": APP_CONSTS["BINARY_DIAGRAM_DEFAULTS"][base],
            "isopleth_defaults": APP_CONSTS["ISOPLETH_DEFAULTS"][base],
            "ternary_defaults": APP_CONSTS["TERNARY_DIAGRAM_DEFAULTS"][base],
            "map_defaults": APP_CONSTS["TERNARY_PHASE_MAP_DEFAULTS"][base],
            "energy_defaults": APP_CONSTS["ENERGY_DEFAULTS"][base],
            "fe_profile_key": "thermogar_patch",
            "demo": False,
            "mode_key": "user",
            "widget_prefix": f"precipitation_{base}",
            "default_temperature_c": definition["default_temperature"],
            "default_min_c": definition["default_t_min"],
            "default_max_c": definition["default_t_max"],
            "default_step_c": definition["default_t_step"],
            "physical_overrides": True,
            "view_mode": "Проекты",
            "db": SimpleNamespace(elements=set(avail) | {"VA"}, phases={}),
        }
    )
    if module == "thermogar_diffusion.py":
        ns["defaults"] = DIFF_CONSTS["DEFAULTS"][base]
    elif module == "thermogar_precipitation.py":
        ns["default"] = PREC_CONSTS["DEFAULTS"][base]
    else:
        ns["defaults"] = APP_CONSTS["SOLIDIFICATION_DEFAULTS"][base]
    return ns


# ---------------------------------------------------------------------------
# Экраны
# ---------------------------------------------------------------------------

A = "ThermoGar_app.py"
D = "thermogar_diffusion.py"
P = "thermogar_precipitation.py"
W = "thermogar_workspace.py"
S = "thermogar_stage14.py"

# ranges: (модуль, первая строка, последняя строка) — участки кода по порядку
# показа; первая строка — заголовок раздела или экрана, последняя — основная
# кнопка. button: (модуль, строка type="primary").
SCREENS: list[dict[str, Any]] = [
    dict(id="S01", tab="Расчёты", sub="Одна температура", view="", button="Рассчитать равновесие",
         bline=(A, 7499), ranges=[(A, 7397, 7409), (A, 7411, 7510)]),
    dict(id="S02", tab="Расчёты", sub="Температурный диапазон", view="", button="Построить график по температуре",
         bline=(A, 7849), ranges=[(A, 7397, 7409), (A, 7709, 7860)]),
    dict(id="S03", tab="Расчёты", sub="Изменение состава", view="", button="Построить график по составу",
         bline=(A, 8199), ranges=[(A, 7397, 7409), (A, 8025, 8210)]),
    dict(id="S04", tab="Диаграммы", sub="Бинарная T–X", view="", button="Построить диаграмму состояния",
         bline=(A, 8546), ranges=[(A, 8386, 8405), (A, 8406, 8548)]),
    dict(id="S05", tab="Диаграммы", sub="Многокомпонентное T–X", view="", button="Построить многокомпонентное сечение",
         bline=(A, 8956), ranges=[(A, 8386, 8405), (A, 8764, 8958)]),
    dict(id="S06", tab="Диаграммы", sub="Тройная при T = const", view="", button="Построить тройную диаграмму",
         bline=(A, 9407), ranges=[(A, 8386, 8405), (A, 9263, 9409)]),
    dict(id="S07", tab="Диаграммы", sub="Карта доли фазы", view="", button="Построить карту доли фазы",
         bline=(A, 9840), ranges=[(A, 8386, 8405), (A, 9636, 9842)]),
    dict(id="S08", tab="Затвердевание", sub="—", view="", button="Рассчитать затвердевание",
         bline=(A, 10402), ranges=[(A, 10200, 10407)]),
    dict(id="S09", tab="Энергии", sub="Энергии фаз", view="", button="Рассчитать энергии фаз",
         bline=(A, 11085), ranges=[(A, 10996, 11011), (A, 11013, 11087)]),
    dict(id="S10", tab="Энергии", sub="Движущая сила", view="", button="Рассчитать движущую силу",
         bline=(A, 11344), ranges=[(A, 10996, 11011), (A, 11259, 11346)]),
    dict(id="S11", tab="Энергии", sub="T₀", view="", button="Рассчитать T₀",
         bline=(A, 11627), ranges=[(A, 10996, 11011), (A, 11478, 11629)]),
    dict(id="S12", tab="Свойства", sub="Плотность", view="", button="Рассчитать плотность и объёмные доли",
         bline=(A, 1770), ranges=[(A, 11764, 11799), (A, 1710, 1772)]),
    dict(id="S13", tab="Свойства", sub="Плотность по T", view="", button="Построить плотность по температуре",
         bline=(A, 1941), ranges=[(A, 11764, 11799), (A, 1870, 1943)]),
    dict(id="S14", tab="Свойства", sub="Упругие свойства", view="шаг 1 — фазовые доли; шаг 2 — Voigt–Reuss–Hill",
         button="Получить фазовые доли (шаг 1); Рассчитать Voigt–Reuss–Hill (шаг 2)",
         bline=(A, 2232), ranges=[(A, 11764, 11799), (A, 2176, 2329)]),
    dict(id="S15", tab="Свойства", sub="Вклады упрочнения", view="", button="Рассчитать вклады",
         bline=(A, 2508), ranges=[(A, 11764, 11799), (A, 2393, 2510)]),
    dict(id="S16", tab="Кинетика", sub="Диффузия и гомогенизация", view="Однофазная пара",
         button="Рассчитать однофазную диффузию",
         bline=(D, 1559), ranges=[(A, 11882, 11885), (D, 1459, 1505), (D, 1507, 1561)]),
    dict(id="S17", tab="Кинетика", sub="Диффузия и гомогенизация", view="Многофазная гомогенизация",
         button="Рассчитать гомогенизацию",
         bline=(D, 1712), ranges=[(A, 11882, 11885), (D, 1459, 1505), (D, 1614, 1715)]),
    dict(id="S18", tab="Кинетика", sub="Диффузия и гомогенизация", view="Покрытие базы подвижностей",
         button="— (основной кнопки нет)",
         bline=None, ranges=[(A, 11882, 11885), (D, 1459, 1505), (D, 1775, 1805)]),
    dict(id="S19", tab="Кинетика", sub="Выделения", view="", button="Рассчитать кинетику выделений",
         bline=(P, 1616), ranges=[(A, 11882, 11885), (P, 1345, 1618)]),
    dict(id="S20", tab="Проекты и данные", sub="Марки и составы", view="",
         button="Сохранить текущий состав (кнопка формы); Загрузить состав в программу",
         bline=(W, 1138), ranges=[(W, 1096, 1216)]),
    dict(id="S21", tab="Проекты и данные", sub="Пакетный расчёт", view="",
         button="Рассчитать все составы (после загрузки файла)",
         bline=(W, 2788), ranges=[(W, 2667, 2790)]),
    dict(id="S22", tab="Проекты и данные", sub="Проекты и история", view="Что открыть: Проекты / История расчётов",
         button="Сохранить проект в папке ThermoGar (кнопка формы); Открыть проект; Восстановить материал из записи",
         bline=(W, 1740), ranges=[(W, 1703, 1871), (W, 2040, 2106)]),
    dict(id="S23", tab="Проекты и данные", sub="Проверка установки", view="",
         button="Проверить базы и запустить три контрольных расчёта",
         bline=(S, 1337), ranges=[(A, 12480, 12494), (S, 1275, 1339)]),
]

# Функции, которые рисуют поля, подставляются на место вызова.
INLINE = {
    "phase_selection_editor": A,
    "render_physical_overrides_toggle": A,
    "_b4b_requested_phases": A,
    "_common_inputs": D,
}
FUNCDEFS: dict[tuple[str, str], ast.FunctionDef] = {}
for mod_name, module in MODULES.items():
    for node in ast.walk(module):
        if isinstance(node, ast.FunctionDef):
            FUNCDEFS.setdefault((mod_name, node.name), node)

WIDGETS = {
    "number_input": "поле (число)",
    "text_input": "поле (текст)",
    "text_area": "поле (текст, многострочное)",
    "selectbox": "выбор",
    "multiselect": "мультивыбор",
    "checkbox": "галочка",
    "toggle": "галочка",
    "radio": "радио",
    "data_editor": "таблица-редактор",
    "slider": "ползунок",
    "select_slider": "ползунок",
    "file_uploader": "загрузка файла",
    "subheader": "заголовок",
    "header": "заголовок",
    "caption": "подпись",
    "markdown": "подпись",
    "write": "подпись",
    "code": "подпись (код)",
    "info": "плашка (info)",
    "warning": "плашка (warning)",
    "error": "плашка (error)",
    "success": "плашка (success)",
    "metric": "метрика",
    "dataframe": "таблица",
    "button": "кнопка",
    "form_submit_button": "кнопка формы",
}
INPUT_KINDS = {
    "поле (число)", "поле (текст)", "поле (текст, многострочное)", "выбор",
    "мультивыбор", "галочка", "радио", "таблица-редактор", "ползунок",
    "загрузка файла",
}
BUTTON_WRAPPERS = {
    "release_calculation_button": 0,
    "verified_equilibrium_button": 1,
    "verified_physical_button": 1,
    "verified_feature_button": 1,
    "verified_batch_execute_button": 1,
    "verified_batch_export_button": 1,
}
ERROR_RENDERERS = {"render_friendly_error", "render_error", "render_user_error", "show_rejection"}


def call_name(func: ast.AST) -> tuple[str, str]:
    """(база, имя): st.x → ("st", x); st.sidebar.x → ("sidebar", x); col.x → (col, x)."""
    if isinstance(func, ast.Name):
        return "", func.id
    if isinstance(func, ast.Attribute):
        value = func.value
        if isinstance(value, ast.Name):
            return value.id, func.attr
        if isinstance(value, ast.Attribute) and isinstance(value.value, ast.Name):
            return f"{value.value.id}.{value.attr}", func.attr
        if isinstance(value, ast.Subscript) and isinstance(value.value, ast.Name):
            return value.value.id, func.attr
    return "?", ""


def short(text: str, limit: int = 160) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


class Evaluated(dict):
    """Значения по базам; failed — базы, где выражение не вычислилось."""

    def __init__(self) -> None:
        super().__init__()
        self.failed: set[str] = set()


class Visitor:
    def __init__(self, screen: dict[str, Any], module: str, lo: int, hi: int, rows: list[dict[str, Any]],
                 namespaces: dict[str, dict[str, Any]], via: str = "", site: int | None = None,
                 outer_ctx: list[tuple[str, str]] | None = None) -> None:
        self.screen = screen
        self.module = module
        self.lo, self.hi = lo, hi
        self.rows = rows
        self.ns = namespaces
        self.via = via
        self.site = site  # строка вызова вспомогательной функции
        self.ctx: list[tuple[str, str]] = list(outer_ctx or [])
        self.columns: dict[str, str] = {}

    # --- диапазон ---------------------------------------------------------
    def in_range(self, node: ast.AST) -> bool:
        if self.site is not None:
            return True
        line = getattr(node, "lineno", 0)
        return self.lo <= line <= self.hi

    def overlaps(self, node: ast.AST) -> bool:
        if self.site is not None:
            return True
        start = getattr(node, "lineno", 0)
        end = getattr(node, "end_lineno", start)
        return not (end < self.lo or start > self.hi)

    # --- вычисление по базам ------------------------------------------------
    def eval_all(self, node: ast.AST | None) -> dict[str, Any]:
        out = Evaluated()
        if node is None:
            return out
        code = compile(ast.fix_missing_locations(ast.Expression(node)), "<expr>", "eval")
        for base in BASES:
            try:
                out[base] = eval(code, self.ns[base])
            except Exception:
                out[base] = None
                out.failed.add(base)
        return out

    def active_bases(self) -> set[str]:
        """Базы, для которых ни одно условие контекста не ложно наверняка."""
        active = set(BASES)
        for item in self.ctx:
            if item[0] != "if" or item[2] is None:
                continue
            code = compile(ast.Expression(item[2]), "<cond>", "eval")
            for base in BASES:
                try:
                    value = bool(eval(code, self.ns[base]))
                except Exception:
                    continue
                if value == item[3]:
                    active.discard(base)
        return active

    def assign_all(self, targets: list[ast.AST], value: Any) -> None:
        # Присваивания в ветке исключения не выполняются: они описывают отказ,
        # а не показ по умолчанию. Невычисленное значение не записывается.
        if any(item[0] == "if" and item[1] == "при исключении" for item in self.ctx):
            return
        active = self.active_bases()
        failed = getattr(value, "failed", set())
        for base in BASES:
            if base not in active or base in failed:
                continue
            val = value.get(base) if isinstance(value, dict) else value
            for target in targets:
                if isinstance(target, ast.Name):
                    self.ns[base][target.id] = val
                elif (isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name)
                      and isinstance(target.slice, ast.Constant)
                      and isinstance(self.ns[base].get(target.value.id), dict)):
                    self.ns[base][target.value.id][target.slice.value] = val

    # --- обход ----------------------------------------------------------------
    def visit_body(self, body: list[ast.stmt]) -> None:
        pushed = 0
        for stmt in body:
            if not self.overlaps(stmt):
                continue
            self.visit_stmt(stmt)
            if isinstance(stmt, ast.If) and not stmt.orelse and stmt.body and isinstance(stmt.body[-1], ast.Return):
                self.ctx.append(("if", "не (" + short(ast.unparse(stmt.test), 90) + ")", stmt.test, True))
                pushed += 1
        for _ in range(pushed):
            self.ctx.pop()

    def visit_stmt(self, stmt: ast.stmt) -> None:
        if isinstance(stmt, (ast.FunctionDef, ast.ClassDef)):
            if self.site is not None:
                return
            self.visit_body(stmt.body)
            return
        if isinstance(stmt, ast.With):
            pushed = 0
            for item in stmt.items:
                expr = item.context_expr
                if isinstance(expr, ast.Call):
                    base, name = call_name(expr.func)
                    if name == "expander":
                        label = self.label_of(expr, 0)
                        exp = self.kw(expr, "expanded")
                        exp_text = "" if exp is None else f" (expanded={ast.unparse(exp)})"
                        if self.in_range(stmt):
                            self.add(stmt, "раскрывающийся блок", label + exp_text, expr)
                        self.ctx.append(("expander", label, None, False))
                        pushed += 1
                    elif name == "form":
                        self.ctx.append(("form", self.label_of(expr, 0), None, False))
                        pushed += 1
                    elif name in {"spinner", "status"}:
                        pass
                elif isinstance(expr, (ast.Name, ast.Subscript)):
                    key = expr.id if isinstance(expr, ast.Name) else (
                        expr.value.id if isinstance(expr.value, ast.Name) else "")
                    if key in self.columns:
                        self.ctx.append(("columns", self.columns[key], None, False))
                        pushed += 1
            self.visit_body(stmt.body)
            for _ in range(pushed):
                self.ctx.pop()
            return
        if isinstance(stmt, ast.If):
            cond = short(ast.unparse(stmt.test), 90)
            self.visit_expr(stmt.test, stmt)
            self.ctx.append(("if", cond, stmt.test, False))
            self.visit_body(stmt.body)
            self.ctx.pop()
            if stmt.orelse:
                self.ctx.append(("if", "не (" + cond + ")", stmt.test, True))
                self.visit_body(stmt.orelse)
                self.ctx.pop()
            return
        if isinstance(stmt, ast.Try):
            self.visit_body(stmt.body)
            for handler in stmt.handlers:
                self.ctx.append(("if", "при исключении", None, False))
                self.visit_body(handler.body)
                self.ctx.pop()
            self.visit_body(stmt.orelse)
            self.visit_body(stmt.finalbody)
            return
        if isinstance(stmt, (ast.For, ast.While)):
            self.ctx.append(("if", "в цикле " + short(ast.unparse(stmt.iter if isinstance(stmt, ast.For) else stmt.test), 60), None, False))
            self.visit_body(stmt.body)
            self.ctx.pop()
            return
        if isinstance(stmt, ast.Assign):
            value = stmt.value
            # st.columns → номер строки
            if isinstance(value, ast.Call) and call_name(value.func)[1] == "columns":
                ident = f"st.columns@{self.module}:{value.lineno}"
                for target in stmt.targets:
                    names = [target] if isinstance(target, ast.Name) else list(getattr(target, "elts", []))
                    for index, name in enumerate(names):
                        if isinstance(name, ast.Name):
                            self.columns[name.id] = ident if len(names) == 1 else f"{ident} (колонка {index + 1} из {len(names)})"
                return
            result = self.visit_expr(value, stmt)
            if result is None and self.in_range(stmt):
                if not self.contains_st_call(value):
                    self.assign_all(stmt.targets, self.eval_all(value))
            elif result is not None:
                self.assign_all(stmt.targets, result)
            return
        if isinstance(stmt, (ast.Expr, ast.Return, ast.AnnAssign, ast.AugAssign)):
            value = getattr(stmt, "value", None)
            if value is not None:
                result = self.visit_expr(value, stmt)
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    if result is None and not self.contains_st_call(value):
                        result = self.eval_all(value)
                    self.assign_all([stmt.target], result or {})
            return

    def contains_st_call(self, node: ast.AST) -> bool:
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                base, name = call_name(sub.func)
                if base in {"st", "sidebar", "st.sidebar"} or name in INLINE or name in BUTTON_WRAPPERS:
                    return True
        return False

    def visit_expr(self, node: ast.AST, stmt: ast.stmt) -> dict[str, Any] | None:
        """Найти вызовы виджетов в выражении; вернуть умолчание последнего виджета."""
        if isinstance(node, ast.IfExp):
            self.ctx.append(("if", short(ast.unparse(node.test), 90), node.test, False))
            result = self.visit_expr(node.body, stmt)
            self.ctx.pop()
            return result
        if isinstance(node, ast.Call):
            base, name = call_name(node.func)
            if name in INLINE and base == "":
                if self.in_range(node):
                    self.inline(node, name)
                return None
            if name in BUTTON_WRAPPERS and base == "":
                if self.in_range(node):
                    self.add(stmt, "кнопка", self.label_of(node, BUTTON_WRAPPERS[name]), node, wrapper=name)
                return None
            if name == "verified_state_uploader":
                if self.in_range(node):
                    self.add(stmt, "загрузка файла", self.label_of(node, 1), node)
                return None
            if name in ERROR_RENDERERS and base == "":
                if self.in_range(node):
                    title = self.kw(node, "title")
                    self.add(stmt, "плашка (error, текст исключения)",
                             self.text_of(title) if title is not None else "(текст исключения)", node)
                return None
            if base in {"st", "sidebar", "st.sidebar"} or (base and base in self.columns) or (
                    base not in {"", "?"} and name in {"metric"}):
                if name in WIDGETS and self.in_range(node):
                    return self.add(stmt, WIDGETS[name], self.label_of(node, 0), node, widget=name)
                return None
            for arg in list(node.args) + [kw.value for kw in node.keywords]:
                self.visit_expr(arg, stmt)
            return None
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.expr):
                self.visit_expr(child, stmt)
        return None

    def inline(self, call: ast.Call, name: str) -> None:
        module = INLINE[name]
        func = FUNCDEFS[(module, name)]
        # параметры вспомогательной функции → значения аргументов вызова
        params = [arg.arg for arg in func.args.args] + [arg.arg for arg in func.args.kwonlyargs]
        bound: dict[str, dict[str, Any]] = {base: {} for base in BASES}
        for param, arg in zip(func.args.args, call.args):
            values = self.eval_all(arg)
            for base in BASES:
                bound[base][param.arg] = values.get(base)
        for kw in call.keywords:
            if kw.arg in params:
                values = self.eval_all(kw.value)
                for base in BASES:
                    bound[base][kw.arg] = values.get(base)
        # значения по умолчанию параметров
        defaults = func.args.defaults
        for param, default in zip(func.args.args[len(func.args.args) - len(defaults):], defaults):
            for base in BASES:
                bound[base].setdefault(param.arg, None)
                if bound[base][param.arg] is None:
                    try:
                        bound[base][param.arg] = eval(compile(ast.Expression(default), "<d>", "eval"), self.ns[base])
                    except Exception:
                        pass
        namespaces = {base: {**base_namespace(base, module), **bound[base]} for base in BASES}
        sub = Visitor(self.screen, module, 0, 10**9, self.rows, namespaces,
                      via=f"{name} ({module}:{func.lineno}), вызов {self.module}:{call.lineno}",
                      site=call.lineno, outer_ctx=self.ctx)
        sub.columns = {}
        sub.visit_body(func.body)

    # --- запись -----------------------------------------------------------------
    def kw(self, node: ast.Call, name: str) -> ast.AST | None:
        for keyword in node.keywords:
            if keyword.arg == name:
                return keyword.value
        for keyword in node.keywords:
            if keyword.arg is None and isinstance(keyword.value, ast.Name):
                # st.number_input(**kwargs): значение из словаря, собранного выше.
                if any(isinstance(self.ns[b].get(keyword.value.id), dict)
                       and name in self.ns[b][keyword.value.id] for b in BASES):
                    return ast.Subscript(value=ast.Name(id=keyword.value.id, ctx=ast.Load()),
                                         slice=ast.Constant(value=name), ctx=ast.Load())
        return None

    def text_of(self, node: ast.AST | None) -> str:
        if node is None:
            return ""
        values = self.eval_all(node)
        texts = {base: value for base, value in values.items() if isinstance(value, str)}
        if len(texts) == 3 and len(set(texts.values())) == 1:
            return texts["ni"]
        if len(texts) == 3:
            return " | ".join(f"{base}: {texts[base]}" for base in BASES)
        return ast.unparse(node)

    def key_text(self, node: ast.AST) -> str:
        values = self.eval_all(node)
        texts = {b: v for b, v in values.items() if isinstance(v, str)}
        if len(texts) == 3:
            patterns = {re.sub(rf"(?<![a-z]){b}(?![a-z])", "{база}", texts[b]) for b in BASES}
            if len(patterns) == 1:
                return patterns.pop()
        return self.text_of(node)

    def label_of(self, node: ast.Call, index: int) -> str:
        label = self.kw(node, "label")
        if label is None and len(node.args) > index:
            label = node.args[index]
        if label is None and node.args and index == 0:
            label = node.args[0]
        return short(self.text_of(label), 400) if label is not None else ""

    def add(self, stmt: ast.stmt, kind: str, label: str, node: ast.Call, widget: str = "",
            wrapper: str = "") -> dict[str, Any] | None:
        key_node = self.kw(node, "key")
        key = self.key_text(key_node) if key_node is not None else ""
        default: dict[str, Any] = {}
        lo = self.kw(node, "min_value")
        hi = self.kw(node, "max_value")
        step = self.kw(node, "step")
        if widget in {"number_input"}:
            value = self.kw(node, "value")
            default = self.eval_all(value if value is not None else lo) if (value is not None or lo is not None) else {b: 0.0 for b in BASES}
        elif widget in {"text_area", "text_input"}:
            value = self.kw(node, "value")
            default = self.eval_all(value) if value is not None else {b: "" for b in BASES}
        elif widget in {"checkbox", "toggle"}:
            value = self.kw(node, "value")
            default = self.eval_all(value) if value is not None else {b: False for b in BASES}
        elif widget in {"selectbox", "radio"}:
            options = self.kw(node, "options") or (node.args[1] if len(node.args) > 1 else None)
            index = self.kw(node, "index")
            opts = self.eval_all(options)
            idx = self.eval_all(index) if index is not None else {b: 0 for b in BASES}
            for base in BASES:
                try:
                    default[base] = list(opts[base])[idx[base]]
                except Exception:
                    default[base] = None
            fmt = self.kw(node, "format_func")
            if fmt is not None and isinstance(fmt, ast.Name) and fmt.id == "element_symbol":
                default = {b: (element_symbol(v) if v is not None else None) for b, v in default.items()}
        elif widget == "multiselect":
            value = self.kw(node, "default")
            default = self.eval_all(value) if value is not None else {b: [] for b in BASES}
        elif widget in {"slider", "select_slider"}:
            value = self.kw(node, "value")
            if value is None and len(node.args) > 3:
                value = node.args[3]
            if lo is None and len(node.args) > 1:
                lo = node.args[1]
            if hi is None and len(node.args) > 2:
                hi = node.args[2]
            if step is None and len(node.args) > 4:
                step = node.args[4]
            if widget == "select_slider":
                opts = self.kw(node, "options")
                lo_hi = self.eval_all(opts)
                lo_text = str(lo_hi.get("ni"))
                default = self.eval_all(value)
                row = self._row(stmt, kind, label, key, default, lo_text, "", "", node, wrapper)
                return default
            default = self.eval_all(value)
        type_node = self.kw(node, "type")
        extra = ""
        if kind.startswith("кнопка") and type_node is not None:
            extra = f"type={ast.unparse(type_node)}"
        disabled = self.kw(node, "disabled")
        if disabled is not None:
            extra = (extra + "; " if extra else "") + "disabled=" + short(ast.unparse(disabled), 80)
        self._row(stmt, kind, label, key, default,
                  self.fmt_bound(lo), self.fmt_bound(hi), self.fmt_bound(step), node, wrapper, extra)
        return default if default else None

    def fmt_bound(self, node: ast.AST | None) -> str:
        if node is None:
            return ""
        values = self.eval_all(node)
        texts = {b: v for b, v in values.items() if b not in values.failed and v is not None}
        if len(texts) == 3 and len({repr(v) for v in texts.values()}) == 1:
            return fmt_value(texts["ni"])
        if texts:
            return " | ".join(f"{b}: {fmt_value(texts[b])}" for b in BASES if b in texts)
        return ast.unparse(node)

    def _row(self, stmt: ast.stmt, kind: str, label: str, key: str, default: dict[str, Any],
             lo: str, hi: str, step: str, node: ast.Call, wrapper: str, extra: str = "") -> None:
        help_node = self.kw(node, "help")
        conditions = [item[1] for item in self.ctx if item[0] == "if"]
        expanders = [item[1] for item in self.ctx if item[0] == "expander"]
        forms = [item[1] for item in self.ctx if item[0] == "form"]
        cols = [item[1] for item in self.ctx if item[0] == "columns"]
        active = self.active_bases()
        if default:
            default = {b: (default.get(b) if b in active else HIDDEN) for b in BASES}
        self.rows.append(
            {
                "screen": self.screen["id"],
                "line": f"{self.module}:{node.lineno}",
                "kind": kind,
                "label": label,
                "key": key,
                "default": default,
                "min": lo,
                "max": hi,
                "step": step,
                "condition": " И ".join(conditions),
                "expander": " › ".join(expanders),
                "form": " › ".join(forms),
                "columns": " › ".join(cols),
                "via": self.via,
                "help": short(self.text_of(help_node), 300) if help_node is not None else "",
                "extra": extra,
            }
        )


HIDDEN = object()
PHASE_MODE_TEXT = {"fast": "быстрый набор", "all": "все фазы базы"}


def fmt_value(value: Any) -> str:
    if value is HIDDEN:
        return "— (не показывается)"
    if value is None:
        return ""
    if isinstance(value, str) and value in PHASE_MODE_TEXT:
        return PHASE_MODE_TEXT[value] + f" ({value})"
    if isinstance(value, float):
        text = f"{value:.10g}"
        return text
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(fmt_value(v) for v in value) + "]"
    return str(value)


# ---------------------------------------------------------------------------
# Ручная разметка
# ---------------------------------------------------------------------------

# Умолчания, которые без базы не вычисляются (списки фаз, выбор из них).
# Ключ: (экран, подстрока key или подписи). Значение: текст по базам.
# Основание — код в адресе строки и словари умолчаний, которые названы.
MANUAL_DEFAULTS: dict[tuple[str, str], dict[str, str]] = {
    ("S09", "energy_curve_phases"): {
        "ni": "FCC_A1, GAMMA_PRIME, LIQUID (ENERGY_DEFAULTS, если фазы есть среди кандидатов; иначе первые три)",
        "al": "GP_MAT, LIQUID (ENERGY_DEFAULTS; то же правило)",
        "fe": "BCC_B2, FCC_A1, LIQUID (ENERGY_DEFAULTS; то же правило)",
    },
    ("S10", "driving_target"): {
        "ni": "GAMMA_PRIME (ENERGY_DEFAULTS.driving_phase; нет в кандидатах — первая фаза)",
        "al": "LIQUID (то же правило)", "fe": "FCC_A1 (то же правило)",
    },
    ("S10", "driving_reference_phases"): {
        b: "все кандидаты, кроме выбранной фазы (галочка «Исключить…» стоит)" for b in BASES
    },
    ("S11", "tzero_phase_one"): {
        "ni": "FCC_A1 (ENERGY_DEFAULTS.tzero_phases)", "al": "GP_MAT", "fe": "BCC_B2",
    },
    ("S11", "tzero_phase_two"): {
        "ni": "GAMMA_PRIME (ENERGY_DEFAULTS.tzero_phases)", "al": "LIQUID", "fe": "FCC_A1",
    },
    ("S07", "ternary_map_target"): {
        "ni": "GAMMA_PRIME (TERNARY_PHASE_MAP_DEFAULTS.phase)", "al": "THETA_AL2CU", "fe": "CEMENTITE",
    },
    ("S16", "kin_single_phase"): {
        b: f"{DIFF_CONSTS['DEFAULTS'][b]['single_phase']} (DEFAULTS.single_phase, если есть в списке; иначе первая)" for b in BASES
    },
    ("S17", "kin_hom_phases"): {
        "ni": "FCC_A1, BCC_A2 из DEFAULTS — остаются только те, что есть в списке фаз с подвижностью; кадр 27 (ni): выбрана одна фаза",
        "al": "FCC_A1 (одна фаза с подвижностью; кнопка выключена, предупреждение до нажатия)",
        "fe": "FCC_A1, BCC_A2 (test_ui_g.py:691–711 проверяет именно это умолчание)",
    },
    ("S19", "_user_matrix"): {
        b: f"{PREC_CONSTS['DEFAULTS'][b][0]} (DEFAULTS[0], если есть среди матриц; иначе первая)" for b in BASES
    },
    ("S19", "_user_precipitate"): {
        b: f"{PREC_CONSTS['DEFAULTS'][b][1]} (DEFAULTS[1], если есть; иначе первая)" for b in BASES
    },
    ("S19", "_preset"): {
        "ni": "Параметры пользователя — значения нужно подтвердить (первый вариант; учебный набор — второй)",
        "al": "Параметры пользователя — значения нужно подтвердить (единственный вариант)",
        "fe": "Параметры пользователя — значения нужно подтвердить (единственный вариант)",
    },
    ("S01", "_phase_set_"): {b: "быстрый набор или все фазы — по default_phase_mode вызова" for b in BASES},
}

# Обязательные поля: пустое или невыбранное — расчёт отказывает.
REQUIRED: dict[tuple[str, str], str] = {
    ("S01", "_phase_editor_"): "да, ≥1 фаза в ручном режиме — ThermoGar_app.py:3025–3026 (st.error до нажатия)",
    ("S02", "_phase_editor_"): "да, ≥1 фаза в ручном режиме — ThermoGar_app.py:3025–3026",
    ("S03", "_phase_editor_"): "да, ≥1 фаза в ручном режиме — ThermoGar_app.py:3025–3026",
    ("S04", "_phase_editor_"): "да, ≥1 фаза — ThermoGar_app.py:3025–3026, отказ :8575–8576",
    ("S05", "isopleth_fixed_"): "да, ≥1 постоянная добавка — ThermoGar_app.py:8894–8899 (до нажатия), :8974–8979 (после нажатия)",
    ("S05", "_phase_editor_"): "да, ≥1 фаза — ThermoGar_app.py:3025–3026, отказ :9066–9068",
    ("S06", "_phase_editor_"): "да, ≥1 фаза — ThermoGar_app.py:3025–3026, отказ :9435–9437",
    ("S07", "_phase_editor_"): "да, ≥1 фаза — ThermoGar_app.py:3025–3026, отказ :9871–9872",
    ("S07", "ternary_map_target"): "да — ThermoGar_app.py:9826–9828 (st.error до нажатия), :9844–9845",
    ("S08", "_phase_editor_"): "да, должна остаться LIQUID — ThermoGar_app.py:10395–10398 (st.error), кнопка выключена :10404–10407",
    ("S09", "energy_curve_phases"): "да, 1–8 фаз — ThermoGar_app.py:4009–4012",
    ("S10", "driving_target"): "да — ThermoGar_app.py:11348–11349",
    ("S10", "driving_reference_phases"): "да, ≥1 фаза — ThermoGar_app.py:4164–4165",
    ("S11", "tzero_phase_one"): "да — ThermoGar_app.py:11631–11632",
    ("S11", "tzero_phase_two"): "да — ThermoGar_app.py:11631–11632",
    ("S14", "b4b2_elastic_editor"): "да (шаг 2): E, ν, происхождение, источник, T отсчёта каждой фазы — thermogar_verified_properties.py:953–955",
    ("S15", "b4b2_strengthening_provenance"): "да — thermogar_verified_properties.py:1074–1081 (USER_INPUT_REQUIRED)",
    ("S15", "b4b2_strengthening_confirmation"): "да — thermogar_verified_properties.py:1085–1086 (USER_INPUT_REQUIRED)",
    ("S16", "_left_"): "да: стороны различаются хотя бы одной добавкой — thermogar_diffusion.py:421–424, :452–453",
    ("S16", "_right_"): "да: то же — thermogar_diffusion.py:421–424, :452–453",
    ("S17", "_left_"): "да: то же — thermogar_diffusion.py:421–424, :452–453",
    ("S17", "_right_"): "да: то же — thermogar_diffusion.py:421–424, :452–453",
    ("S17", "kin_hom_phases"): "да, ≥2 фазы — thermogar_diffusion.py:1717–1718",
    ("S20", "Название марки или состава"): "да — thermogar_workspace.py:936–937",
    ("S21", "Файл составов"): "да — кнопка расчёта появляется только после загрузки: thermogar_workspace.py:2765–2792",
    ("S22", "Название проекта"): "да — thermogar_workspace.py:685–686",
}
NOT_REQUIRED_NOTE: dict[tuple[str, str], str] = {
    ("S16", "_input_provenance_"): "нет: пустое заменяется строкой по умолчанию — thermogar_diffusion.py:1452–1454",
    ("S17", "_input_provenance_"): "нет: пустое заменяется строкой по умолчанию — thermogar_diffusion.py:1452–1454",
    ("S19", "_input_provenance"): "нет: пустое заменяется строкой по умолчанию — thermogar_precipitation.py:1606",
    ("S03", "fixed_composition_"): "нет: пустое — бинарная система основа + изменяемый элемент",
    ("S11", "tzero_fixed_"): "нет: пустое — бинарная система",
}


def lookup(table: dict[tuple[str, str], Any], screen: str, key: str, label: str) -> Any:
    """Разметка по подстроке key или подписи; при нескольких совпадениях — самая длинная."""
    best = None
    for (scr, needle), value in table.items():
        if scr == screen and (needle in key or needle in label):
            if best is None or len(needle) > len(best[0]):
                best = (needle, value)
    return best[1] if best else None


# ---------------------------------------------------------------------------
# Предложение 9Б: поле → (решение, блок, ранг, причина)
# решение: «открыто» / «свернуть» / «уже в блоке» / «уже в блоке, блок переименовать»
# ранг: 1 — меняют реже всего (сворачивать первым).
# ---------------------------------------------------------------------------

B_TOCHNOST = "Точность и критерии"
B_MODEL = "Параметры модели"
B_KWN = "Параметры модели KWN"
B_SETKA = "Численная сетка размеров"
B_PHASES = "Управление фазами / метастабильный расчёт"

PROPOSAL: dict[tuple[str, str], tuple[str, str, int | str, str]] = {
    # --- S01
    ("S01", "single_temperature_"): ("открыто", "", "", "вопрос расчёта: температура точки"),
    ("S01", "_phase_set_"): ("уже в блоке", B_PHASES, "", "набор фаз — уже свёрнут"),
    ("S01", "_phase_mode_"): ("уже в блоке", B_PHASES, "", "уже свёрнут"),
    ("S01", "_phase_editor_"): ("уже в блоке", B_PHASES, "", "уже свёрнут; обязательна ≥1 фаза только в ручном режиме"),
    # --- S02
    ("S02", "t_min_"): ("открыто", "", "", "вопрос расчёта: диапазон"),
    ("S02", "t_max_"): ("открыто", "", "", "вопрос расчёта: диапазон"),
    ("S02", "t_step_"): ("открыто", "", "", "численный шаг, но стоит в одной строке с «От/До»: свёртка одного шага высоты не даёт — строка остаётся"),
    ("S02", "Показывать на графике фазы"): ("свернуть", B_TOCHNOST, 1, "порог показа на графике; на расчёт не влияет, только отбор линий (подпись поля)"),
    ("S02", "_phase_set_"): ("уже в блоке", B_PHASES, "", "уже свёрнут"),
    ("S02", "_phase_mode_"): ("уже в блоке", B_PHASES, "", "уже свёрнут"),
    ("S02", "_phase_editor_"): ("уже в блоке", B_PHASES, "", "уже свёрнут"),
    # --- S03
    ("S03", "Изменяемый элемент"): ("открыто", "", "", "вопрос расчёта: ось состава"),
    ("S03", "fixed_composition_"): ("открыто", "", "", "вопрос расчёта: состав сплава"),
    ("S03", ": от,"): ("открыто", "", "", "вопрос расчёта: диапазон состава"),
    ("S03", ": до,"): ("открыто", "", "", "вопрос расчёта: диапазон состава"),
    ("S03", ": шаг,"): ("открыто", "", "", "численный шаг, но в одной строке с «от/до»: свёртка одного шага высоты не даёт"),
    ("S03", "concentration_temperature_"): ("открыто", "", "", "вопрос расчёта: температура"),
    ("S03", "concentration_threshold"): ("свернуть", B_TOCHNOST, 1, "порог показа на графике; на расчёт не влияет"),
    ("S03", "_phase_set_"): ("уже в блоке", B_PHASES, "", "уже свёрнут"),
    ("S03", "_phase_mode_"): ("уже в блоке", B_PHASES, "", "уже свёрнут"),
    ("S03", "_phase_editor_"): ("уже в блоке", B_PHASES, "", "уже свёрнут"),
    # --- S04
    ("S04", "binary_left_"): ("открыто", "", "", "вопрос расчёта: система"),
    ("S04", "binary_right_"): ("открыто", "", "", "вопрос расчёта: система"),
    ("S04", "binary_units_"): ("открыто", "", "", "единицы оси задают смысл чисел «от/до»; держать рядом с ними"),
    ("S04", "binary_c_min_"): ("открыто", "", "", "вопрос расчёта: окно состава"),
    ("S04", "binary_c_max_"): ("открыто", "", "", "вопрос расчёта: окно состава"),
    ("S04", "binary_c_step_"): ("свернуть", B_TOCHNOST, 3, "шаг сетки по составу — численная настройка (подпись «Шаг по составу»); отдельная строка, свёртка даёт высоту"),
    ("S04", "binary_t_min_"): ("открыто", "", "", "вопрос расчёта: окно температуры"),
    ("S04", "binary_t_max_"): ("открыто", "", "", "вопрос расчёта: окно температуры"),
    ("S04", "binary_t_step_"): ("свернуть", B_TOCHNOST, 3, "шаг сетки по температуре — численная настройка; отдельная строка"),
    ("S04", "binary_tielines_"): ("свернуть", B_TOCHNOST, 1, "вид графика: линии связи; на расчёт не влияет"),
    ("S04", "binary_nodes_"): ("свернуть", B_TOCHNOST, 1, "вид графика: узловые точки; на расчёт не влияет"),
    ("S04", "_phase_set_"): ("уже в блоке", B_PHASES, "", "уже свёрнут"),
    ("S04", "_phase_mode_"): ("уже в блоке", B_PHASES, "", "уже свёрнут"),
    ("S04", "_phase_editor_"): ("уже в блоке", B_PHASES, "", "уже свёрнут"),
    # --- S05
    ("S05", "isopleth_variable_"): ("открыто", "", "", "вопрос расчёта: ось сечения"),
    ("S05", "isopleth_fixed_"): ("открыто", "", "", "обязательное поле (≥1 добавка)"),
    ("S05", "isopleth_c_min_"): ("открыто", "", "", "вопрос расчёта: окно состава"),
    ("S05", "isopleth_c_max_"): ("открыто", "", "", "вопрос расчёта: окно состава"),
    ("S05", "isopleth_c_step_"): ("свернуть", B_TOCHNOST, 3, "шаг сетки по составу; ISOPLETH_DEFAULTS подобраны под время расчёта (комментарий ThermoGar_app.py:540–542)"),
    ("S05", "isopleth_t_min_"): ("открыто", "", "", "вопрос расчёта: окно температуры"),
    ("S05", "isopleth_t_max_"): ("открыто", "", "", "вопрос расчёта: окно температуры"),
    ("S05", "isopleth_t_step_"): ("свернуть", B_TOCHNOST, 3, "шаг сетки по температуре; то же"),
    ("S05", "isopleth_nodes_"): ("свернуть", B_TOCHNOST, 1, "вид графика: узловые точки"),
    ("S05", "_phase_set_"): ("уже в блоке", B_PHASES, "", "уже свёрнут"),
    ("S05", "_phase_mode_"): ("уже в блоке", B_PHASES, "", "уже свёрнут"),
    ("S05", "_phase_editor_"): ("уже в блоке", B_PHASES, "", "уже свёрнут"),
    # --- S06
    ("S06", "ternary_x_"): ("открыто", "", "", "вопрос расчёта: система"),
    ("S06", "ternary_y_"): ("открыто", "", "", "вопрос расчёта: система"),
    ("S06", "ternary_dependent_"): ("открыто", "", "", "вопрос расчёта: система"),
    ("S06", "ternary_temperature_"): ("открыто", "", "", "вопрос расчёта: температура"),
    ("S06", "ternary_step_"): ("свернуть", B_TOCHNOST, 2, "подсказка поля: «Меньший шаг точнее, но расчёт длится дольше» — точность"),
    ("S06", "ternary_tielines_"): ("свернуть", B_TOCHNOST, 1, "вид графика: линии связи"),
    ("S06", "ternary_tieline_every_"): ("свернуть", B_TOCHNOST, 1, "вид графика: прореживание линий связи"),
    ("S06", "ternary_nodes_"): ("свернуть", B_TOCHNOST, 1, "вид графика: точки трёхфазного равновесия"),
    ("S06", "_phase_set_"): ("уже в блоке", B_PHASES, "", "уже свёрнут"),
    ("S06", "_phase_mode_"): ("уже в блоке", B_PHASES, "", "уже свёрнут"),
    ("S06", "_phase_editor_"): ("уже в блоке", B_PHASES, "", "уже свёрнут"),
    # --- S07
    ("S07", "ternary_map_x_"): ("открыто", "", "", "вопрос расчёта: система"),
    ("S07", "ternary_map_y_"): ("открыто", "", "", "вопрос расчёта: система"),
    ("S07", "ternary_map_dependent_"): ("открыто", "", "", "вопрос расчёта: система"),
    ("S07", "ternary_map_units_"): ("свернуть", B_TOCHNOST, 2, "единицы треугольника; на вопрос расчёта не влияют, только на оси"),
    ("S07", "ternary_map_temperature_"): ("открыто", "", "", "вопрос расчёта: температура"),
    ("S07", "ternary_map_step_"): ("свернуть", B_TOCHNOST, 2, "подсказка: число узлов и время; «Начните с шага по умолчанию»"),
    ("S07", "ternary_map_threshold_"): ("свернуть", B_TOCHNOST, 1, "линия появления фазы на карте — вид графика"),
    ("S07", "ternary_map_color_scale_"): ("свернуть", B_TOCHNOST, 1, "шкала цвета — вид графика"),
    ("S07", "_phase_set_"): ("уже в блоке", B_PHASES, "", "уже свёрнут"),
    ("S07", "_phase_mode_"): ("уже в блоке", B_PHASES, "", "уже свёрнут"),
    ("S07", "_phase_editor_"): ("уже в блоке", B_PHASES, "", "уже свёрнут"),
    ("S07", "ternary_map_target_"): ("открыто", "", "", "вопрос расчёта: фаза карты; обязательное"),
    # --- S08
    ("S08", "solidification_method_"): ("открыто", "", "", "вопрос расчёта: метод"),
    ("S08", "solidification_start_"): ("свернуть", B_TOCHNOST, 3, "подсказка: «ThermoGar может автоматически поднять её» — численная настройка поиска расплава"),
    ("S08", "solidification_step_"): ("свернуть", B_TOCHNOST, 3, "шаг охлаждения — численный шаг"),
    ("S08", "solidification_auto_start_"): ("уже в блоке", B_TOCHNOST, "", "уже в «Точность и критерии»"),
    ("S08", "solidification_start_increment_"): ("уже в блоке", B_TOCHNOST, "", "уже в блоке"),
    ("S08", "solidification_max_start_"): ("уже в блоке", B_TOCHNOST, "", "уже в блоке"),
    ("S08", "solidification_stop_"): ("уже в блоке", B_TOCHNOST, "", "уже в блоке"),
    ("S08", "solidification_appearance_"): ("уже в блоке", B_TOCHNOST, "", "уже в блоке"),
    ("S08", "solidification_display_"): ("уже в блоке", B_TOCHNOST, "", "уже в блоке"),
    ("S08", "solidification_pdens_"): ("уже в блоке", B_TOCHNOST, "", "уже в блоке"),
    ("S08", "solidification_binary_tol_"): ("уже в блоке", B_TOCHNOST, "", "уже в блоке"),
    ("S08", "solidification_adaptive_"): ("уже в блоке", B_TOCHNOST, "", "уже в блоке"),
    ("S08", "_phase_set_"): ("уже в блоке", B_PHASES, "", "уже свёрнут"),
    ("S08", "_phase_mode_"): ("уже в блоке", B_PHASES, "", "уже свёрнут"),
    ("S08", "_phase_editor_"): ("уже в блоке", B_PHASES, "", "уже свёрнут"),
    # --- S09
    ("S09", "energy_curve_phases_"): ("открыто", "", "", "вопрос расчёта: фазы; обязательное"),
    ("S09", "energy_t_min_"): ("открыто", "", "", "вопрос расчёта: диапазон"),
    ("S09", "energy_t_max_"): ("открыто", "", "", "вопрос расчёта: диапазон"),
    ("S09", "energy_t_step_"): ("свернуть", B_TOCHNOST, 2, "шаг температуры — численный шаг; отдельная строка"),
    ("S09", "energy_view_"): ("свернуть", B_TOCHNOST, 1, "подпись «Что показать на графике» — вид графика"),
    # --- S10
    ("S10", "driving_target_"): ("открыто", "", "", "вопрос расчёта: фаза; обязательное"),
    ("S10", "driving_exclude_target_"): ("свернуть", B_PHASES, 2, "подсказка: так рассчитывается стимул появления фазы — выбор фаз исходного равновесия с умолчанием; по смыслу — «Управление фазами»"),
    ("S10", "driving_reference_phases_"): ("свернуть", B_PHASES, 2, "фазы исходного равновесия; умолчание — все кандидаты, кроме выбранной; обязательное ≥1 умолчание выполняет"),
    ("S10", "driving_t_min_"): ("открыто", "", "", "вопрос расчёта: диапазон"),
    ("S10", "driving_t_max_"): ("открыто", "", "", "вопрос расчёта: диапазон"),
    ("S10", "driving_t_step_"): ("свернуть", B_TOCHNOST, 1, "шаг температуры — численный шаг"),
    # --- S11
    ("S11", "tzero_variable_"): ("открыто", "", "", "вопрос расчёта: ось состава"),
    ("S11", "tzero_units_"): ("открыто", "", "", "единицы задают смысл чисел «от/до»"),
    ("S11", "tzero_fixed_"): ("открыто", "", "", "вопрос расчёта: состав"),
    ("S11", "tzero_c_min_"): ("открыто", "", "", "вопрос расчёта: окно состава"),
    ("S11", "tzero_c_max_"): ("открыто", "", "", "вопрос расчёта: окно состава"),
    ("S11", "tzero_c_step_"): ("свернуть", B_TOCHNOST, 1, "шаг по составу — численный шаг; отдельная строка"),
    ("S11", "tzero_phase_one_"): ("открыто", "", "", "вопрос расчёта: пара фаз; обязательное"),
    ("S11", "tzero_phase_two_"): ("открыто", "", "", "вопрос расчёта: пара фаз; обязательное"),
    ("S11", "tzero_t_min_"): ("свернуть", B_TOCHNOST, 2, "окно поиска корня — численная настройка (подпись «Границы задают окно, в котором ищется…»); сворачивать вместе с подписью"),
    ("S11", "tzero_t_max_"): ("свернуть", B_TOCHNOST, 2, "то же"),
    # --- S12–S15 (общая галочка над подвкладками)
    ("S12", "physical_overrides_enabled"): ("открыто", "", "", "общая галочка над подвкладками «Свойств»; решение 9Б её не касается"),
    ("S13", "physical_overrides_enabled"): ("открыто", "", "", "то же"),
    ("S14", "physical_overrides_enabled"): ("открыто", "", "", "то же"),
    ("S15", "physical_overrides_enabled"): ("открыто", "", "", "то же"),
    ("S12", "physical_temperature_"): ("открыто", "", "", "вопрос расчёта: температура"),
    ("S12", "physical_single_manual"): ("свернуть", B_PHASES, 2, "ручной выбор фаз — как «Управление фазами» на других экранах"),
    ("S12", "physical_single_tokens"): ("свернуть", B_PHASES, 2, "то же"),
    ("S13", "physical_t_min_"): ("открыто", "", "", "вопрос расчёта: диапазон"),
    ("S13", "physical_t_max_"): ("открыто", "", "", "вопрос расчёта: диапазон"),
    ("S13", "physical_t_step_"): ("открыто", "", "", "шаг в одной строке с «от/до»: свёртка одного шага высоты не даёт"),
    ("S13", "physical_scan_manual"): ("свернуть", B_PHASES, 2, "ручной выбор фаз"),
    ("S13", "physical_scan_tokens"): ("свернуть", B_PHASES, 2, "то же"),
    ("S14", "b4b2_elastic_temperature_"): ("открыто", "", "", "вопрос расчёта: температура"),
    ("S14", "b4b2_elastic_prepare_manual"): ("свернуть", B_PHASES, 2, "ручной выбор фаз"),
    ("S14", "b4b2_elastic_prepare_tokens"): ("свернуть", B_PHASES, 2, "то же"),
    ("S14", "b4b2_elastic_editor_"): ("открыто", "", "", "шаг 2: обязательная таблица E, ν и источника"),
    ("S14", "b4b2_elastic_update_"): ("открыто", "", "", "шаг 2, одна галочка под таблицей; блок ради неё не заводить"),
    ("S15", "b4b2_strengthening_provenance_"): ("открыто", "", "", "обязательное"),
    ("S15", "b4b2_strengthening_confirmation_"): ("открыто", "", "", "обязательное"),
    ("S15", "b4b2_strengthening_sigma_"): ("открыто", "", "", "вклад в итог; без него сумма не задана"),
    ("S15", "b4b2_strengthening_rule_"): ("открыто", "", "", "метод объединения — вопрос расчёта"),
    ("S15", "b4b2_hall_use_"): ("открыто", "", "", "выбор механизма — вопрос расчёта; сейчас внутри «Hall–Petch», предлагается вынести галочку наружу"),
    ("S15", "b4b2_hall_k_"): ("свернуть", B_MODEL, 2, "параметр модели с умолчанием без источника"),
    ("S15", "b4b2_hall_grain_"): ("свернуть", B_MODEL, 2, "параметр микроструктуры с умолчанием"),
    ("S15", "b4b2_strengthening_hill_"): ("открыто", "", "", "источник G и ν — выбор, который меняет смысл параметров"),
    ("S15", "b4b2_taylor_use_"): ("открыто", "", "", "выбор механизма; вынести из «Taylor»"),
    ("S15", "b4b2_taylor_m_"): ("свернуть", B_MODEL, 1, "параметр модели с умолчанием без источника"),
    ("S15", "b4b2_taylor_alpha_"): ("свернуть", B_MODEL, 1, "то же"),
    ("S15", "b4b2_taylor_g_"): ("свернуть", B_MODEL, 1, "то же"),
    ("S15", "b4b2_taylor_b_"): ("свернуть", B_MODEL, 1, "то же"),
    ("S15", "b4b2_taylor_rho_"): ("свернуть", B_MODEL, 2, "параметр микроструктуры"),
    ("S15", "b4b2_solid_use_"): ("открыто", "", "", "выбор механизма"),
    ("S15", "b4b2_solid_"): ("открыто", "", "", "значение вклада рядом со своей галочкой"),
    ("S15", "b4b2_orowan_use_"): ("открыто", "", "", "выбор механизма; вынести из «Orowan»"),
    ("S15", "b4b2_orowan_m_"): ("свернуть", B_MODEL, 1, "параметр модели"),
    ("S15", "b4b2_orowan_g_"): ("свернуть", B_MODEL, 1, "параметр модели"),
    ("S15", "b4b2_orowan_b_"): ("свернуть", B_MODEL, 1, "параметр модели"),
    ("S15", "b4b2_orowan_nu_"): ("свернуть", B_MODEL, 1, "параметр модели"),
    ("S15", "b4b2_orowan_radius_"): ("свернуть", B_MODEL, 2, "параметр микроструктуры"),
    ("S15", "b4b2_orowan_spacing_"): ("свернуть", B_MODEL, 2, "параметр микроструктуры"),
    ("S15", "b4b2_other_use_"): ("открыто", "", "", "выбор вклада"),
    ("S15", "b4b2_other_"): ("открыто", "", "", "значение вклада рядом со своей галочкой"),
    # --- S16/S17 (_common_inputs)
    ("S16", "kin_single_balance_"): ("открыто", "", "", "вопрос расчёта: материал пары"),
    ("S16", "kin_single_units_"): ("открыто", "", "", "единицы задают смысл составов"),
    ("S16", "kin_single_left_"): ("открыто", "", "", "обязательное: состав стороны"),
    ("S16", "kin_single_right_"): ("открыто", "", "", "обязательное: состав стороны"),
    ("S16", "kin_single_temperature_"): ("открыто", "", "", "вопрос расчёта: температура выдержки"),
    ("S16", "kin_single_length_"): ("свернуть", B_TOCHNOST, 2, "геометрия области — численная настройка; строка из 4 полей: высоту даёт только свёртка всей строки вместе со «Временем»"),
    ("S16", "kin_single_interface_"): ("свернуть", B_TOCHNOST, 1, "положение границы пары; умолчание 50 %; та же строка"),
    ("S16", "kin_single_time_"): ("открыто", "", "", "вопрос расчёта: время; та же строка — предлагается вынести из строки на отдельную"),
    ("S16", "kin_single_nodes_"): ("свернуть", B_TOCHNOST, 1, "число ячеек — сетка; та же строка"),
    ("S16", "kin_single_input_provenance_"): ("свернуть", B_MODEL, 1, "подсказка: строка идёт в Excel, историю и JSON; пустое заменяется умолчанием (thermogar_diffusion.py:1452–1454)"),
    ("S16", "kin_single_phase_"): ("открыто", "", "", "вопрос расчёта: фаза"),
    ("S17", "kin_hom_balance_"): ("открыто", "", "", "вопрос расчёта: материал пары"),
    ("S17", "kin_hom_units_"): ("открыто", "", "", "единицы составов"),
    ("S17", "kin_hom_left_"): ("открыто", "", "", "обязательное"),
    ("S17", "kin_hom_right_"): ("открыто", "", "", "обязательное"),
    ("S17", "kin_hom_temperature_"): ("открыто", "", "", "вопрос расчёта: температура"),
    ("S17", "kin_hom_length_"): ("свернуть", B_TOCHNOST, 2, "геометрия; строка из 4 полей — см. S16"),
    ("S17", "kin_hom_interface_"): ("свернуть", B_TOCHNOST, 1, "та же строка"),
    ("S17", "kin_hom_time_"): ("открыто", "", "", "вопрос расчёта: время; вынести из строки"),
    ("S17", "kin_hom_nodes_"): ("свернуть", B_TOCHNOST, 1, "сетка"),
    ("S17", "kin_hom_input_provenance_"): ("свернуть", B_MODEL, 1, "то же, что в «Однофазной паре»: одно поле — один блок на обоих видах"),
    ("S17", "kin_hom_phases_"): ("открыто", "", "", "вопрос расчёта: фазы; обязательное ≥2"),
    ("S17", "kin_hom_function_"): ("свернуть", B_MODEL, 2, "параметр модели с умолчанием; плашка под полем советует первый вариант"),
    ("S17", "kin_hom_eps_"): ("свернуть", B_MODEL, 1, "сглаживающий коэффициент — численный параметр; строка из 2 полей: сворачивать обе"),
    ("S17", "kin_hom_lab_"): ("свернуть", B_MODEL, 1, "та же строка; активно только для лабиринтной модели"),
    # --- S19
    ("S19", "_preset"): ("открыто", "", "", "выбор набора (материала) на экране"),
    ("S19", "_user_matrix"): ("открыто", "", "", "вопрос расчёта: пара фаз"),
    ("S19", "_user_precipitate"): ("открыто", "", "", "вопрос расчёта: пара фаз"),
    ("S19", "_user_temperature_mode"): ("открыто", "", "", "вопрос расчёта: режим"),
    ("S19", "_user_temperature_c"): ("открыто", "", "", "вопрос расчёта"),
    ("S19", "_user_duration_h"): ("открыто", "", "", "вопрос расчёта"),
    ("S19", "_user_temperature_profile"): ("открыто", "", "", "вопрос расчёта (режим цикла)"),
    ("S19", "_user_gamma"): ("уже в блоке", B_KWN, 3, "блок открыт по умолчанию (expanded=True): предложение — закрыть; γ база не задаёт (плашка раздела)"),
    ("S19", "_user_matrix_vm"): ("уже в блоке", B_KWN, 3, "то же"),
    ("S19", "_user_precip_vm"): ("уже в блоке", B_KWN, 3, "то же"),
    ("S19", "_user_nucleation_type"): ("уже в блоке", B_KWN, 2, "то же"),
    ("S19", "_user_bulk_n0"): ("уже в блоке", B_KWN, 2, "то же"),
    ("S19", "_user_grain_size_um"): ("уже в блоке", B_KWN, 1, "то же"),
    ("S19", "_user_dislocation_density"): ("уже в блоке", B_KWN, 1, "то же"),
    ("S19", "_user_gb_energy"): ("уже в блоке", B_KWN, 1, "то же"),
    ("S19", "_user_cmin_nm"): ("уже в блоке", B_SETKA, 1, "сетка размеров — численная настройка; блок уже свёрнут"),
    ("S19", "_user_cmax_nm"): ("уже в блоке", B_SETKA, 1, "то же"),
    ("S19", "_user_bins"): ("уже в блоке", B_SETKA, 1, "то же"),
    ("S19", "_user_input_provenance"): ("свернуть", B_KWN, 2, "подсказка: источник γ, Vm и параметров зарождения — входов этого блока; пустое заменяется умолчанием (thermogar_precipitation.py:1606)"),
    # --- S20–S23
    ("S20", "Название марки или состава"): ("открыто", "", "", "обязательное"),
    ("S20", "Заметка (не обязательно)"): ("открыто", "", "", "форма из трёх полей; сворачивать нечего"),
    ("S20", "Разрешить обновить"): ("открыто", "", "", "форма из трёх полей"),
    ("S20", "alloy_selected_id"): ("открыто", "", "", "выбор записи для второй кнопки"),
    ("S21", "Файл составов"): ("открыто", "", "", "обязательное"),
    ("S22", "projects_history_mode"): ("открыто", "", "", "переключатель вида"),
    ("S22", "Название проекта"): ("открыто", "", "", "обязательное"),
    ("S22", "Описание (не обязательно)"): ("открыто", "", "", "форма из трёх полей"),
    ("S22", "Разрешить заменить"): ("открыто", "", "", "форма из трёх полей"),
    ("S22", "project_selected_path"): ("открыто", "", "", "выбор проекта"),
    ("S22", "Показывать события"): ("открыто", "", "", "фильтр истории"),
    ("S22", "history_restore_entry"): ("открыто", "", "", "выбор записи"),
}


# ---------------------------------------------------------------------------
# Сборка
# ---------------------------------------------------------------------------

def main() -> int:
    all_rows: list[dict[str, Any]] = []
    for screen in SCREENS:
        rows: list[dict[str, Any]] = []
        for module, lo, hi in screen["ranges"]:
            namespaces = {base: base_namespace(base, module) for base in BASES}
            visitor = Visitor(screen, module, lo, hi, rows, namespaces)
            visitor.visit_body(MODULES[module].body)
        # уникальность: один элемент — одна строка (обход функций мог дать повтор)
        seen: set[tuple[str, str, str]] = set()
        for row in rows:
            ident = (row["line"], row["via"], row["kind"])
            if ident in seen:
                continue
            seen.add(ident)
            all_rows.append(row)

    header = [
        "экран", "вкладка", "подвкладка", "вид (переключатель)", "основная кнопка", "кнопка файл:строка",
        "№", "вид элемента", "подпись", "key", "умолчание ni", "умолчание al", "умолчание fe",
        "мин", "макс", "шаг", "условие показа", "в раскрывающемся блоке", "форма", "в одной строке (st.columns)",
        "обязательное", "через функцию", "подсказка (help)", "прочее", "файл:строка",
    ]
    screen_by_id = {screen["id"]: screen for screen in SCREENS}
    counters: dict[str, int] = {}
    out_rows: list[list[str]] = []
    proposal_rows: list[list[str]] = []
    summary: dict[str, dict[str, int]] = {}
    for row in all_rows:
        screen = screen_by_id[row["screen"]]
        counters[row["screen"]] = counters.get(row["screen"], 0) + 1
        manual = lookup(MANUAL_DEFAULTS, row["screen"], row["key"], row["label"])
        defaults = {}
        for base in BASES:
            value = row["default"].get(base) if row["default"] else None
            if manual and value is not HIDDEN and (value is None or value == [] or row["kind"] in {"мультивыбор"}):
                defaults[base] = manual.get(base, "")
            else:
                defaults[base] = fmt_value(value)
        required = ""
        if row["kind"] in INPUT_KINDS:
            required = lookup(REQUIRED, row["screen"], row["key"], row["label"]) or \
                lookup(NOT_REQUIRED_NOTE, row["screen"], row["key"], row["label"]) or "нет"
        bline = screen["bline"]
        out_rows.append([
            row["screen"], screen["tab"], screen["sub"], screen["view"], screen["button"],
            f"app/{bline[0]}:{bline[1]}" if bline else "—",
            str(counters[row["screen"]]), row["kind"], row["label"], row["key"],
            defaults["ni"], defaults["al"], defaults["fe"],
            row["min"], row["max"], row["step"], row["condition"], row["expander"], row["form"],
            row["columns"], required, row["via"], row["help"], row["extra"], "app/" + row["line"],
        ])
        if row["kind"] in INPUT_KINDS:
            stat = summary.setdefault(row["screen"], {"полей": 0, "открыто": 0, "свернуть": 0, "уже в блоке": 0, "без решения": 0})
            stat["полей"] += 1
            decision = lookup(PROPOSAL, row["screen"], row["key"], row["label"])
            if decision is None:
                stat["без решения"] += 1
                decision = ("", "", "", "")
            else:
                if decision[0] == "открыто":
                    stat["открыто"] += 1
                elif decision[0] == "свернуть":
                    stat["свернуть"] += 1
                else:
                    stat["уже в блоке"] += 1
            proposal_rows.append([
                row["screen"], screen["tab"], screen["sub"] + (" / " + screen["view"] if screen["view"] else ""),
                row["kind"], row["label"], row["key"], row["expander"], row["columns"], required,
                decision[0], decision[1], str(decision[2]), decision[3], "app/" + row["line"],
            ])

    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "formy.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(header)
        writer.writerows(out_rows)
    with (OUT / "predlozhenie_9b.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow([
            "экран", "вкладка", "подвкладка / вид", "вид элемента", "подпись", "key",
            "сейчас в блоке", "в одной строке (st.columns)", "обязательное", "решение 9Б",
            "блок", "ранг (1 — сворачивать первым)", "причина по коду", "файл:строка",
        ])
        writer.writerows(proposal_rows)

    total = {"полей": 0, "открыто": 0, "свернуть": 0, "уже в блоке": 0, "без решения": 0}
    print("экран;полей;открыто;свернуть;уже в блоке;без решения")
    for screen in SCREENS:
        stat = summary.get(screen["id"], {"полей": 0, "открыто": 0, "свернуть": 0, "уже в блоке": 0, "без решения": 0})
        for name in total:
            total[name] += stat[name]
        print(f"{screen['id']};{stat['полей']};{stat['открыто']};{stat['свернуть']};{stat['уже в блоке']};{stat['без решения']}")
    print("итого;" + ";".join(str(total[name]) for name in total))
    print(f"строк описи: {len(out_rows)}; экранов: {len(SCREENS)}")
    print("элементы баз:", {base: len(ELEMENTS[base]) for base in BASES})
    return 0


if __name__ == "__main__":
    sys.exit(main())
