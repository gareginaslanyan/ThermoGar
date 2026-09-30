"""Проверка шага вкладки (BL-57, разрез головного сценария; 20-К, 20-Л и следующие).

Вкладка «with <переменная вкладки>:» головного сценария переносится в функцию
нового модуля: тело — без правок, имена головного сценария — прологом
«имя = sidebar.поле» / «имя = services.поле» (и «SIDEBAR = sidebar»,
«SERVICES = services»), в головном сценарии вместо тела — вызов функции.
Определения, нужные только вкладке, переносятся в модуль без правок, в прежнем
порядке, между импортами и функцией вкладки (20-Л). Скрипт сверяет:

1. Тело: операторы функции после строки документации и пролога — байт в байт
   текст тела «with <переменная вкладки>:» файла до правки и равны ему по
   ast.dump; вложенных областей в теле нет.
2. Пролог: присваивания «имя = sidebar.поле» или «имя = services.поле»; в файле
   до правки SIDEBAR = SidebarContext(…) или SERVICES = RunServices(…) передаёт
   «поле=имя» — тот же объект. «SIDEBAR = sidebar» и «SERVICES = services» —
   тот же объект: вызов в головном сценарии передаёт sidebar=SIDEBAR,
   services=SERVICES. После SIDEBAR и SERVICES имя на уровне модуля не
   переприсваивается и нигде не объявлено global; каждое имя пролога тело
   читает.
3. Перенесённые определения: все узлы верхнего уровня модуля, кроме строки
   документации, импортов и функции вкладки. Каждый — узел верхнего уровня
   файла до правки: текст с декораторами байт в байт и ast.dump равны, порядок
   прежний; ни одно их имя в головном сценарии после правки не связано. Имена,
   которые они читают как глобальные (в том числе в аннотациях), —
   перенесённые, импорты модуля с тем же источником, что в файле до правки,
   или встроенные; прочих 0.
4. Импорты модуля: каждый оператор — оператор импорта файла до правки (тот же
   модуль, те же псевдонимы, имена — подмножество в прежнем порядке);
   операторы — в порядке файла до правки; импортированных, но не читаемых
   модулем имён 0; имён, которые модуль читает и не связывает, а файл до
   правки импортирует, 0.
5. Имена, которые тело читает и само не связывает: имена пролога, перенесённые,
   импорты нового модуля (модуль и исходное имя — те же, что в импорте файла
   до правки), встроенные; прочих 0. Связывание телом — в том числе имя
   «except … as <имя>».
6. Имена, которые тело связывает, головной сценарий после правки не читает
   как глобальные: на уровне модуля — вне тел def, lambda и включений и вне
   своих «except … as <имя>»; в функциях, лямбдах и включениях — как
   глобальные по symtable.
7. symtable: неопределённые глобальные имена нового модуля и головного
   сценария после правки (аннотации — по AST, из-за
   «from __future__ import annotations» в symtable их нет); скрытые обращения
   в новом модуле (вызовы globals, vars, locals, eval, exec, __import__; слова
   __main__, sys.modules).
8. Головной сценарий по AST: узлы верхнего уровня и операторы импорта до и
   после; убранные и добавленные импортом имена, опустевшие операторы
   импорта; откат — из файла до правки убрать перенесённые узлы, в обоих
   файлах не считать убранных имён и опустевших операторов импорта, импорт из
   нового модуля убрать, тело вкладки вернуть — все узлы равны по ast.dump.
9. Импорт нового модуля из корня дерева.

Только стандартная библиотека (ast, builtins, subprocess, symtable).
Запуск из корня дерева:

    python -B -X utf8 results/wave20_l/scripts/proverka_vkladki.py \
        <блоб до правки> <головной сценарий> <модуль вкладки> <функция> <переменная вкладки>

Вывод — в stdout байтами UTF-8 с LF (для файла — перенаправление «>»).
Код выхода 0 — PASS, 1 — FAIL.
"""

from __future__ import annotations

import ast
import builtins
import subprocess
import sys
import symtable
from pathlib import Path

ROOT = Path.cwd()
MODULE_ATTRIBUTES = {
    "__name__", "__file__", "__doc__", "__spec__", "__loader__",
    "__package__", "__builtins__", "__annotations__", "__cached__",
}
BUILTINS = set(dir(builtins))
HIDDEN_CALLS = ("globals", "vars", "locals", "eval", "exec", "__import__")
HIDDEN_WORDS = ("__main__", "sys.modules")
# Параметр функции вкладки -> (имя объекта в головном сценарии, его класс).
CONTAINERS = {
    "sidebar": ("SIDEBAR", "SidebarContext"),
    "services": ("SERVICES", "RunServices"),
}
SCOPE_NODES = (
    ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda,
    ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp,
)
COMPREHENSIONS = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


def git_blob(blob: str) -> bytes:
    completed = subprocess.run(
        ["git", "cat-file", "blob", blob], cwd=ROOT, capture_output=True, check=True
    )
    return completed.stdout


def source_lines(source: str, first: int, last: int) -> str:
    """Строки first..last (с 1, включительно) с переводами строк."""
    return "".join(source.splitlines(keepends=True)[first - 1:last])


def first_line(node: ast.stmt) -> int:
    """Первая строка узла вместе с декораторами."""
    decorators = getattr(node, "decorator_list", [])
    return min([node.lineno] + [d.lineno for d in decorators])


def node_text(source: str, node: ast.stmt) -> str:
    return source_lines(source, first_line(node), node.end_lineno)


def is_import(node: ast.stmt) -> bool:
    return isinstance(node, (ast.Import, ast.ImportFrom))


def is_future(node: ast.stmt) -> bool:
    return isinstance(node, ast.ImportFrom) and node.module == "__future__"


def is_docstring(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def tab_with(tree: ast.Module, tab_var: str) -> list[ast.With]:
    return [
        node for node in tree.body
        if isinstance(node, ast.With)
        and len(node.items) == 1
        and isinstance(node.items[0].context_expr, ast.Name)
        and node.items[0].context_expr.id == tab_var
        and node.items[0].optional_vars is None
    ]


def names(nodes: list[ast.stmt], context: type) -> set[str]:
    return {
        node.id
        for statement in nodes
        for node in ast.walk(statement)
        if isinstance(node, ast.Name) and isinstance(node.ctx, context)
    }


def handler_names(nodes: list[ast.stmt]) -> set[str]:
    """Имена «except … as <имя>»."""
    return {
        node.name
        for statement in nodes
        for node in ast.walk(statement)
        if isinstance(node, ast.ExceptHandler) and node.name
    }


def bound_by_node(node: ast.stmt) -> set[str]:
    """Имена, которые узел верхнего уровня связывает на уровне модуля."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return {node.name}
    targets: list[ast.expr] = []
    if isinstance(node, ast.Assign):
        targets = list(node.targets)
    elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
        targets = [node.target]
    return {
        sub.id
        for target in targets
        for sub in ast.walk(target)
        if isinstance(sub, ast.Name)
    }


def import_map(tree: ast.Module) -> dict[str, tuple[str, str]]:
    """Имя, связанное импортом верхнего уровня -> (модуль, исходное имя)."""
    found: dict[str, tuple[str, str]] = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            if node.module == "__future__":
                continue
            for alias in node.names:
                found[alias.asname or alias.name] = (node.module or "", alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                bound = alias.asname or alias.name.split(".")[0]
                found[bound] = (alias.name if alias.asname else bound, "")
    return found


def import_key(node: ast.stmt) -> tuple[str, str, int]:
    """Вид, модуль и уровень оператора импорта."""
    if isinstance(node, ast.ImportFrom):
        return ("from", node.module or "", node.level)
    return ("import", ",".join(alias.name for alias in node.names), 0)


def import_aliases(node: ast.stmt) -> list[tuple[str, str | None]]:
    return [(alias.name, alias.asname) for alias in node.names]


def is_subsequence(part: list, whole: list) -> bool:
    iterator = iter(whole)
    return all(item in iterator for item in part)


def module_level_stores(tree: ast.Module, after_line: int) -> dict[str, list[int]]:
    """Связывания имён на уровне модуля (без тел def/class/lambda) после строки."""
    found: dict[str, list[int]] = {}

    def visit(node: ast.AST) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if child.lineno > after_line:
                    found.setdefault(child.name, []).append(child.lineno)
                continue
            if isinstance(child, (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                continue
            if isinstance(child, (ast.Import, ast.ImportFrom)) and child.lineno > after_line:
                for alias in child.names:
                    found.setdefault(alias.asname or alias.name.split(".")[0], []).append(child.lineno)
            if (
                isinstance(child, ast.Name)
                and isinstance(child.ctx, (ast.Store, ast.Del))
                and child.lineno > after_line
            ):
                found.setdefault(child.id, []).append(child.lineno)
            if isinstance(child, ast.ExceptHandler) and child.name and child.lineno > after_line:
                found.setdefault(child.name, []).append(child.lineno)
            visit(child)

    visit(tree)
    return found


def module_level_reads(tree: ast.Module) -> dict[str, list[int]]:
    """Чтения имён на уровне модуля: вне тел def, lambda и включений и вне
    своих «except … as <имя>». Декораторы, значения по умолчанию, базы
    классов и первый итератор включения вычисляются на уровне модуля."""
    found: dict[str, list[int]] = {}

    def walk(node: ast.AST, shadowed: frozenset[str]) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for sub in node.decorator_list + node.args.defaults + [
                d for d in node.args.kw_defaults if d is not None
            ]:
                walk(sub, shadowed)
            return
        if isinstance(node, ast.ClassDef):
            for sub in node.decorator_list + node.bases + [k.value for k in node.keywords]:
                walk(sub, shadowed)
            for statement in node.body:
                walk(statement, shadowed)
            return
        if isinstance(node, ast.Lambda):
            for sub in node.args.defaults + [d for d in node.args.kw_defaults if d is not None]:
                walk(sub, shadowed)
            return
        if isinstance(node, COMPREHENSIONS):
            walk(node.generators[0].iter, shadowed)
            return
        if isinstance(node, ast.ExceptHandler):
            if node.type is not None:
                walk(node.type, shadowed)
            inner = shadowed | {node.name} if node.name else shadowed
            for statement in node.body:
                walk(statement, inner)
            return
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id not in shadowed:
            found.setdefault(node.id, []).append(node.lineno)
        for child in ast.iter_child_nodes(node):
            walk(child, shadowed)

    walk(tree, frozenset())
    return found


def nested_global_reads(table: symtable.SymbolTable, out: dict[str, int]) -> None:
    """Имена, которые вложенные области (функции, лямбды, включения, классы)
    читают как глобальные, с первой строкой области."""
    for child in table.get_children():
        for symbol in child.get_symbols():
            if symbol.is_referenced() and symbol.is_global():
                out.setdefault(symbol.get_name(), child.get_lineno())
        nested_global_reads(child, out)


def global_declarations(tree: ast.Module) -> dict[str, list[int]]:
    found: dict[str, list[int]] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            for name in node.names:
                found.setdefault(name, []).append(node.lineno)
    return found


def global_reads(table: symtable.SymbolTable, out: dict[str, int]) -> None:
    """Имена, которые область читает как глобальные, с первой строкой области."""
    top = table.get_type() == "module"
    for symbol in table.get_symbols():
        if not symbol.is_referenced():
            continue
        if top or symbol.is_global():
            out.setdefault(symbol.get_name(), table.get_lineno())
    for child in table.get_children():
        global_reads(child, out)


def module_bound(table: symtable.SymbolTable) -> set[str]:
    return {
        symbol.get_name()
        for symbol in table.get_symbols()
        if symbol.is_assigned() or symbol.is_imported() or symbol.is_namespace()
    }


def annotation_names(tree: ast.Module) -> dict[str, int]:
    """Имена из аннотаций (в том числе строковых), с номером строки."""
    found: dict[str, int] = {}

    def collect(annotation: ast.expr | None) -> None:
        if annotation is None:
            return
        for node in ast.walk(annotation):
            if isinstance(node, ast.Name):
                found.setdefault(node.id, node.lineno)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                try:
                    inner = ast.parse(node.value, mode="eval")
                except SyntaxError:
                    continue
                for sub in ast.walk(inner):
                    if isinstance(sub, ast.Name):
                        found.setdefault(sub.id, node.lineno)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            arguments = node.args
            for arg in (
                arguments.posonlyargs + arguments.args + arguments.kwonlyargs
                + [a for a in (arguments.vararg, arguments.kwarg) if a is not None]
            ):
                collect(arg.annotation)
            collect(node.returns)
        elif isinstance(node, ast.AnnAssign):
            collect(node.annotation)
    return found


def all_global_reads(source: str, filename: str) -> set[str]:
    """Имена, которые код читает как глобальные, и имена из аннотаций."""
    table = symtable.symtable(source, filename, "exec")
    reads: dict[str, int] = {}
    global_reads(table, reads)
    return set(reads) | set(annotation_names(ast.parse(source)))


def undefined_globals(source: str, filename: str) -> tuple[list[str], int, int]:
    tree = ast.parse(source)
    table = symtable.symtable(source, filename, "exec")
    known = module_bound(table) | BUILTINS | MODULE_ATTRIBUTES
    reads: dict[str, int] = {}
    global_reads(table, reads)
    annotations = annotation_names(tree)
    undefined = sorted(
        {name for name in reads if name not in known}
        | {name for name in annotations if name not in known}
    )
    return [
        f"{name} (строка {reads.get(name, annotations.get(name))})" for name in undefined
    ], len(reads), len(annotations)


def hidden_access(source: str) -> list[str]:
    hidden: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in HIDDEN_CALLS
        ):
            hidden.append(f"{node.lineno} | {node.func.id}()")
    for number, line in enumerate(source.split("\n"), start=1):
        for word in HIDDEN_WORDS:
            if word in line:
                hidden.append(f"{number} | слово {word}")
    return hidden


def strip_names(tree: ast.Module, removed: set[str]) -> None:
    """Убрать из импортов верхнего уровня имена removed и опустевшие операторы
    импорта (на месте)."""
    for node in tree.body:
        if is_import(node):
            node.names = [a for a in node.names if (a.asname or a.name) not in removed]
    tree.body = [node for node in tree.body if not (is_import(node) and not node.names)]


def main() -> int:
    if len(sys.argv) != 6:
        sys.stderr.write(__doc__)
        return 2
    blob, app_arg, module_arg, function_name, tab_var = sys.argv[1:]
    app_path = Path(app_arg)
    module_path = Path(module_arg)
    module_name = module_path.stem
    before_bytes = git_blob(blob)
    before = before_bytes.decode("utf-8")
    after = app_path.read_bytes().decode("utf-8")
    module = module_path.read_bytes().decode("utf-8")
    before_tree = ast.parse(before)
    after_tree = ast.parse(after)
    module_tree = ast.parse(module)
    after_table = symtable.symtable(after, app_path.as_posix(), "exec")

    out: list[str] = []
    fails: list[str] = []

    def check(ok: bool, label: str) -> None:
        if not ok:
            fails.append(label)

    out.append("Проверка шага вкладки")
    out.append(f"до правки: блоб {blob} (git cat-file blob), строк {before.count(chr(10))}")
    out.append(f"после правки: {app_path.as_posix()}, строк {after.count(chr(10))}")
    out.append(f"модуль вкладки: {module_path.as_posix()}, строк {module.count(chr(10))}")
    out.append(f"функция: {function_name}; переменная вкладки: {tab_var}")
    out.append("")

    # 1. Тело.
    out.append("== 1. тело")
    tabs_before = tab_with(before_tree, tab_var)
    tabs_after = tab_with(after_tree, tab_var)
    out.append(f"«with {tab_var}:» верхнего уровня: до {len(tabs_before)}, после {len(tabs_after)}")
    check(len(tabs_before) == 1 and len(tabs_after) == 1, "with вкладки не один")
    tab_before = tabs_before[0]
    tab_after = tabs_after[0]
    body_before = tab_before.body
    body_text_before = source_lines(before, body_before[0].lineno, body_before[-1].end_lineno)
    out.append(
        f"тело до правки: строки {body_before[0].lineno}–{body_before[-1].end_lineno}"
        f" ({body_text_before.count(chr(10))} строк), операторов {len(body_before)}"
    )
    functions = [
        node for node in module_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == function_name
    ]
    check(len(functions) == 1, "функция вкладки не одна")
    function = functions[0]
    check(function is module_tree.body[-1], "функция вкладки не последний узел модуля")
    statements = list(function.body)
    has_doc = bool(statements) and is_docstring(statements[0])
    if has_doc:
        statements = statements[1:]

    def prologue_kind(statement: ast.stmt) -> str | None:
        """«field» — имя = параметр.поле; «object» — ОБЪЕКТ = параметр."""
        if not (
            isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name)
        ):
            return None
        value = statement.value
        if (
            isinstance(value, ast.Attribute)
            and isinstance(value.value, ast.Name)
            and value.value.id in CONTAINERS
        ):
            return "field"
        if (
            isinstance(value, ast.Name)
            and value.id in CONTAINERS
            and statement.targets[0].id == CONTAINERS[value.id][0]
        ):
            return "object"
        return None

    prologue: list[ast.Assign] = []
    while statements and prologue_kind(statements[0]):
        prologue.append(statements.pop(0))
    body_after = statements
    body_text_after = (
        source_lines(module, body_after[0].lineno, body_after[-1].end_lineno) if body_after else ""
    )
    out.append(
        f"функция {function_name}: строки {function.lineno}–{function.end_lineno};"
        f" строка документации {'есть' if has_doc else 'нет'}; пролог {len(prologue)};"
        f" тело: строки {body_after[0].lineno}–{body_after[-1].end_lineno}"
        f" ({body_text_after.count(chr(10))} строк), операторов {len(body_after)}"
    )
    text_equal = body_text_after.encode("utf-8") == body_text_before.encode("utf-8")
    dump_equal = len(body_after) == len(body_before) and all(
        ast.dump(a) == ast.dump(b) for a, b in zip(body_after, body_before)
    )
    module_tail = module.split("\n")[body_after[-1].end_lineno:]
    nested = sum(isinstance(n, SCOPE_NODES) for s in body_before for n in ast.walk(s))
    out.append(f"текст тела байт в байт: {'равен' if text_equal else 'НЕ равен'}")
    out.append(f"ast.dump тела: {'равен' if dump_equal else 'НЕ равен'}")
    out.append(f"после тела в модуле: {'ничего' if module_tail == [''] else repr(module_tail)}")
    out.append(f"вложенных областей в теле (def, class, lambda, включения): {nested}")
    check(text_equal and dump_equal and module_tail == [""] and nested == 0, "тело")
    arguments = function.args
    signature_ok = (
        not arguments.posonlyargs and not arguments.args and arguments.vararg is None
        and arguments.kwarg is None
        and [a.arg for a in arguments.kwonlyargs] == list(CONTAINERS)
    )
    out.append(
        "параметры функции: только именованные "
        + ", ".join(a.arg for a in arguments.kwonlyargs)
        + ("" if signature_ok else " — НЕ как ждали")
    )
    check(signature_ok, "параметры функции")
    out.append("")

    # 2. Пролог.
    out.append("== 2. пролог")
    constructors: dict[str, dict[str, str]] = {}
    constructor_lines: dict[str, int] = {}
    for parameter, (object_name, class_name) in CONTAINERS.items():
        found = [
            node for node in before_tree.body
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == object_name
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == class_name
        ]
        check(len(found) == 1, f"{object_name} = {class_name}(…) не один")
        constructors[parameter] = {
            keyword.arg: (keyword.value.id if isinstance(keyword.value, ast.Name) else ast.unparse(keyword.value))
            for keyword in found[0].value.keywords
        }
        constructor_lines[parameter] = found[0].end_lineno
        out.append(f"до правки: {object_name} = {class_name}(…) — строка {found[0].lineno}")
    call_keywords: dict[str, str] = {}
    if (
        len(tab_after.body) == 1
        and isinstance(tab_after.body[0], ast.Expr)
        and isinstance(tab_after.body[0].value, ast.Call)
    ):
        call_keywords = {
            keyword.arg: ast.unparse(keyword.value) for keyword in tab_after.body[0].value.keywords
        }
    last_constructor = max(constructor_lines.values())
    stores = module_level_stores(before_tree, last_constructor)
    declared = global_declarations(before_tree)
    reads_body = names(body_before, ast.Load)
    prologue_names: list[str] = []
    prologue_bad = 0
    for assign in prologue:
        name = assign.targets[0].id
        if prologue_kind(assign) == "field":
            parameter = assign.value.value.id
            field = assign.value.attr
            object_name, class_name = CONTAINERS[parameter]
            passed = constructors[parameter].get(field)
            same = passed == name
            origin = f"{parameter}.{field}: {class_name}(… {field}={passed} …)"
        else:
            parameter = assign.value.id
            object_name, class_name = CONTAINERS[parameter]
            passed = call_keywords.get(parameter)
            same = passed == object_name
            origin = f"{parameter}: в головном сценарии {function_name}(… {parameter}={passed} …)"
        rebound = stores.get(name, [])
        is_global = declared.get(name, [])
        read = name in reads_body
        ok = same and not rebound and not is_global and read
        prologue_bad += not ok
        prologue_names.append(name)
        out.append(
            f"  {name} = {origin}"
            f" — {'тот же объект' if same else 'НЕ тот же'};"
            f" переприсваиваний после {object_name}: {len(rebound)}"
            + (f" {rebound}" if rebound else "")
            + f"; global: {len(is_global)}; тело читает: {'да' if read else 'НЕТ'}"
        )
    out.append(f"присваиваний пролога: {len(prologue)}; с отклонением: {prologue_bad}")
    check(prologue_bad == 0 and len(set(prologue_names)) == len(prologue_names), "пролог")
    out.append("")

    # 3. Перенесённые определения.
    out.append("== 3. перенесённые определения")
    imports_module = import_map(module_tree)
    imports_before = import_map(before_tree)
    after_bound = module_bound(after_table)
    moved = [
        node for index, node in enumerate(module_tree.body)
        if not (index == 0 and is_docstring(node))
        and not is_import(node)
        and node is not function
    ]
    before_by_text: dict[str, list[int]] = {}
    for index, node in enumerate(before_tree.body):
        before_by_text.setdefault(node_text(before, node), []).append(index)
    moved_indices: list[int] = []
    moved_bad = 0
    moved_lines = 0
    moved_names: set[str] = set()
    for node in moved:
        text = node_text(module, node)
        lines = text.count("\n")
        moved_lines += lines
        bound = bound_by_node(node)
        moved_names |= bound
        index = next(
            (
                i for i in before_by_text.get(text, [])
                if ast.dump(before_tree.body[i]) == ast.dump(node)
            ),
            None,
        )
        order_ok = index is not None and (not moved_indices or index > moved_indices[-1])
        if index is not None:
            moved_indices.append(index)
        bound_after = sorted(bound & after_bound)
        moved_bad += not (index is not None and order_ok and not bound_after)
        where = (
            f"до правки {first_line(before_tree.body[index])}–{before_tree.body[index].end_lineno}"
            if index is not None else "в файле до правки НЕТ узла с тем же текстом и ast.dump"
        )
        out.append(
            f"  {first_line(node)}–{node.end_lineno} ({lines}) {', '.join(sorted(bound)) or '—'}:"
            f" {where}; порядок {'прежний' if order_ok else 'НЕ прежний'};"
            f" связано в головном сценарии после правки: {len(bound_after)}"
            + (f" ({', '.join(bound_after)})" if bound_after else "")
        )
    moved_source = "from __future__ import annotations\n" + "".join(
        node_text(module, node) for node in moved
    )
    moved_reads = sorted(all_global_reads(moved_source, "<перенесённые>")) if moved else []
    reads_moved = [name for name in moved_reads if name in moved_names]
    reads_imports = [
        name for name in moved_reads if name not in moved_names and name in imports_module
    ]
    reads_import_bad = [
        name for name in reads_imports if imports_module[name] != imports_before.get(name)
    ]
    reads_builtins = [
        name for name in moved_reads
        if name not in moved_names and name not in imports_module and name in BUILTINS
    ]
    reads_other = [
        name for name in moved_reads
        if name not in moved_names and name not in imports_module and name not in BUILTINS
    ]
    out.append(
        f"узлов {len(moved)}, строк {moved_lines} (строки самих узлов, без пустых между ними);"
        f" с отклонением {moved_bad}"
    )
    out.append(
        f"имён, которые они читают как глобальные (в том числе в аннотациях), {len(moved_reads)}:"
        f" перенесённые {len(reads_moved)}, импорты модуля {len(reads_imports)}"
        f" (с другим источником {len(reads_import_bad)}), встроенные {len(reads_builtins)},"
        f" прочих {len(reads_other)}"
        + (f" — {', '.join(reads_other)}" if reads_other else "")
    )
    out.append(f"  встроенные: {', '.join(reads_builtins) or '—'}")
    if reads_import_bad:
        out.append(f"  с другим источником: {', '.join(reads_import_bad)}")
    check(moved_bad == 0 and not reads_other and not reads_import_bad, "перенесённые определения")
    out.append("")

    # 4. Импорты модуля.
    out.append("== 4. импорты модуля")
    before_imports = [(i, node) for i, node in enumerate(before_tree.body) if is_import(node)]
    module_imports = [node for node in module_tree.body if is_import(node)]
    futures = [node for node in module_imports if is_future(node)]
    future_ok = (
        len(futures) == 1
        and module_imports[0] is futures[0]
        and any(ast.dump(futures[0]) == ast.dump(node) for _i, node in before_imports)
    )
    out.append(
        f"from __future__: {len(futures)}"
        + (" — первый оператор импорта, как в файле до правки" if future_ok else " — НЕ как ждали")
    )
    import_bad = 0
    last_index = -1
    plain_imports = [node for node in module_imports if not is_future(node)]
    for node in plain_imports:
        match = next(
            (
                i for i, candidate in before_imports
                if i > last_index
                and import_key(candidate) == import_key(node)
                and is_subsequence(import_aliases(node), import_aliases(candidate))
            ),
            None,
        )
        if match is None:
            import_bad += 1
            out.append(f"  {node.lineno}: {ast.unparse(node)} — в файле до правки НЕТ или не по порядку")
            continue
        last_index = match
        out.append(
            f"  {node.lineno}: {import_key(node)[0]} {import_key(node)[1]} — до правки строка"
            f" {before_tree.body[match].lineno}, имён {len(node.names)} из"
            f" {len(before_tree.body[match].names)}"
        )
    module_reads = all_global_reads(module, module_path.as_posix())
    module_table_bound = module_bound(symtable.symtable(module, module_path.as_posix(), "exec"))
    unused = sorted(name for name in imports_module if name not in module_reads)
    missing = sorted(
        name for name in module_reads
        if name not in module_table_bound and name in imports_before
    )
    out.append(
        f"операторов {len(plain_imports)} и from __future__; не из файла до правки или не по"
        f" порядку: {import_bad}"
    )
    out.append(
        f"импортированных, но не читаемых модулем имён: {len(unused)}"
        + (f" ({', '.join(unused)})" if unused else "")
    )
    out.append(
        f"имён, которые модуль читает и не связывает, а файл до правки импортирует: {len(missing)}"
        + (f" ({', '.join(missing)})" if missing else "")
    )
    check(future_ok and import_bad == 0 and not unused and not missing, "импорты модуля")
    out.append("")

    # 5. Свободные имена тела.
    out.append("== 5. имена, которые тело читает и само не связывает")
    handlers = handler_names(body_before)
    bound_body = names(body_before, ast.Store) | names(body_before, ast.Del) | handlers
    free = sorted(reads_body - bound_body)
    from_prologue = [name for name in free if name in prologue_names]
    from_moved: list[str] = []
    from_imports: list[str] = []
    from_builtins: list[str] = []
    other: list[str] = []
    body_import_bad = 0
    for name in free:
        if name in prologue_names:
            continue
        if name in moved_names:
            from_moved.append(name)
        elif name in imports_module:
            from_imports.append(name)
            same = imports_module[name] == imports_before.get(name)
            body_import_bad += not same
            source_module, original = imports_module[name]
            out.append(
                f"  импорт {name}: {source_module}"
                + (f".{original}" if original and original != name else "")
                + f" — в файле до правки {'тот же' if same else 'ДРУГОЙ: ' + repr(imports_before.get(name))}"
            )
        elif name in BUILTINS:
            from_builtins.append(name)
        else:
            other.append(name)
    out.append(f"перенесённые: {', '.join(from_moved) or '—'}")
    out.append(f"встроенные: {', '.join(from_builtins) or '—'}")
    out.append(
        f"связывает тело: {len(bound_body)} — {', '.join(sorted(bound_body))}"
        + (f"; из них «except … as»: {', '.join(sorted(handlers))}" if handlers else "")
    )
    out.append(
        f"всего {len(free)}: из пролога {len(from_prologue)}, перенесённые {len(from_moved)},"
        f" импортом нового модуля {len(from_imports)} (с другим источником {body_import_bad}),"
        f" встроенные {len(from_builtins)}, прочих {len(other)}"
        + (f" — {', '.join(other)}" if other else "")
    )
    check(
        not other and body_import_bad == 0 and set(from_prologue) == set(prologue_names),
        "свободные имена тела",
    )
    out.append("")

    # 6. Имена, связанные телом, после правки.
    out.append("== 6. имена, которые тело связывает, в головном сценарии после правки")
    top_reads = module_level_reads(after_tree)
    nested_reads: dict[str, int] = {}
    nested_global_reads(after_table, nested_reads)
    stray_top = sorted(bound_body & set(top_reads))
    stray_nested = sorted(bound_body & set(nested_reads))
    out.append(f"имена: {', '.join(sorted(bound_body))}")
    out.append(
        "читаются на уровне модуля (вне тел def, lambda, включений и своих «except … as»):"
        f" {len(stray_top)}"
        + (f" ({', '.join(f'{n} {top_reads[n]}' for n in stray_top)})" if stray_top else "")
    )
    out.append(
        f"читаются как глобальные в функциях, лямбдах и включениях (symtable): {len(stray_nested)}"
        + (f" ({', '.join(f'{n} {nested_reads[n]}' for n in stray_nested)})" if stray_nested else "")
    )
    check(not stray_top and not stray_nested, "связанные телом имена читаются после правки")
    out.append("")

    # 7. symtable.
    out.append("== 7. symtable")
    module_undefined, module_reads_count, module_ann = undefined_globals(module, module_path.as_posix())
    app_undefined, app_reads, app_ann = undefined_globals(after, app_path.as_posix())
    module_hidden = hidden_access(module)
    app_hidden = hidden_access(after)
    out.append(
        f"{module_path.as_posix()}: глобальных чтений {module_reads_count}, имён в аннотациях"
        f" {module_ann}, неопределённых {len(module_undefined)}"
    )
    out.extend("  " + line for line in module_undefined)
    out.append(
        f"{app_path.as_posix()}: глобальных чтений {app_reads}, имён в аннотациях"
        f" {app_ann}, неопределённых {len(app_undefined)}"
    )
    out.extend("  " + line for line in app_undefined)
    out.append(
        f"скрытых обращений в {module_path.as_posix()} (вызовы " + ", ".join(HIDDEN_CALLS)
        + "; слова " + ", ".join(HIDDEN_WORDS) + f"): {len(module_hidden)}"
    )
    out.extend("  " + line for line in module_hidden)
    out.append(f"для сведения, скрытых обращений в {app_path.as_posix()}: {len(app_hidden)}")
    out.extend("  " + line for line in app_hidden)
    check(not module_undefined and not app_undefined and not module_hidden, "symtable")
    out.append("")

    # 8. Головной сценарий по AST.
    out.append("== 8. головной сценарий по AST")
    count_imports = lambda tree: sum(is_import(n) for n in tree.body)
    out.append(f"узлов верхнего уровня: {len(before_tree.body)} → {len(after_tree.body)}")
    out.append(f"операторов импорта: {count_imports(before_tree)} → {count_imports(after_tree)}")
    names_before = set(import_map(before_tree))
    names_after = set(import_map(after_tree))
    removed = names_before - names_after
    added = names_after - names_before
    emptied = [
        node for node in before_tree.body
        if is_import(node) and not is_future(node)
        and all((a.asname or a.name) in removed for a in node.names)
    ]
    out.append(f"убраны из импортов: {len(removed)} — {', '.join(sorted(removed)) or '—'}")
    out.append(
        f"из них целиком операторов импорта: {len(emptied)} — "
        + (", ".join(import_key(node)[1] for node in emptied) or "—")
    )
    out.append(f"добавлены импортом: {', '.join(sorted(added)) or '—'}")
    tab_imports = [
        node for node in after_tree.body
        if isinstance(node, ast.ImportFrom) and node.module == module_name
    ]
    call_expected = (
        f"{function_name}(" + ", ".join(f"{p}={o}" for p, (o, _c) in CONTAINERS.items()) + ")"
    )
    call_ok = (
        len(tab_after.body) == 1
        and isinstance(tab_after.body[0], ast.Expr)
        and ast.unparse(tab_after.body[0]) == call_expected
    )
    out.append(
        f"тело «with {tab_var}:» после правки: "
        + " | ".join(ast.unparse(s) for s in tab_after.body)
        + ("" if call_ok else " — НЕ как ждали")
    )
    rollback = ast.parse(after)
    rollback.body = [
        node for node in rollback.body
        if not (isinstance(node, ast.ImportFrom) and node.module == module_name)
    ]
    for node in tab_with(rollback, tab_var):
        node.body = ast.parse(before).body[before_tree.body.index(tab_before)].body
    original = ast.parse(before)
    moved_set = set(moved_indices)
    original.body = [node for index, node in enumerate(original.body) if index not in moved_set]
    strip_names(rollback, removed)
    strip_names(original, removed)
    equal = sum(
        ast.dump(a) == ast.dump(b) for a, b in zip(rollback.body, original.body)
    )
    rollback_ok = len(rollback.body) == len(original.body) == equal
    out.append(
        f"откат (из файла до правки убраны перенесённые узлы: {len(moved_indices)}; импорт из"
        f" {module_name} убран, тело вкладки из файла до правки; в обоих файлах без убранных"
        f" имён и опустевших операторов импорта): узлов {len(rollback.body)} и"
        f" {len(original.body)}, равны по ast.dump {equal}"
    )
    check(
        len(after_tree.body) == len(before_tree.body) - len(moved) - len(emptied) + 1
        and count_imports(after_tree) == count_imports(before_tree) - len(emptied) + 1
        and len(tab_imports) == 1
        and added == {function_name}
        and call_ok
        and rollback_ok,
        "головной сценарий по AST",
    )
    out.append("")

    # 9. Импорт.
    out.append("== 9. импорт из корня дерева")
    code = (
        "import sys; sys.path.insert(0, 'app'); "
        f"import {module_name} as k; print(k.{function_name}.__module__)"
    )
    completed = subprocess.run(
        [sys.executable, "-B", "-X", "utf8", "-c", code],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
    )
    printed = completed.stdout.strip()
    out.append(f'python -B -X utf8 -c "{code}"')
    out.append(f"код выхода: {completed.returncode}")
    out.append(f"вывод: {printed}")
    check(completed.returncode == 0 and printed == module_name, "импорт")
    out.append("")

    out.append(
        "ИТОГ: " + ("PASS" if not fails else "FAIL — " + "; ".join(fails))
        + f" — тело {len(body_after)} операторов, {body_text_after.count(chr(10))} строк;"
        + f" пролог {len(prologue)}; перенесённых узлов {len(moved)}, строк {moved_lines};"
        + f" импортов модуля {len(plain_imports)} и from __future__;"
        + f" свободных имён {len(free)} ({len(from_prologue)} + {len(from_moved)}"
        + f" + {len(from_imports)} + встроенные {len(from_builtins)}, прочих {len(other)});"
        + f" узлов {len(before_tree.body)} → {len(after_tree.body)},"
        + f" импортов {count_imports(before_tree)} → {count_imports(after_tree)};"
        + f" откат {equal} из {len(original.body)}"
    )
    sys.stdout.buffer.write(("\n".join(out) + "\n").encode("utf-8"))
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
