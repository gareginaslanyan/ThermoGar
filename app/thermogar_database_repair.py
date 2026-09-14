"""Починка разобранной базы: то, что нельзя чинить правкой байтов TDB.

Байты релизных TDB неприкосновенны — они привязаны к SHA-256 и к политике
релиза (``thermogar_release_policy``). Всё, что в них описано корректно по
правилам Thermo-Calc, но неверно понимается ``pycalphad``/``kawin``, чинится
здесь, над уже разобранным объектом ``Database``.

Правки идемпотентны: повторный вызов на том же объекте ничего не меняет и
возвращает отчёт с нулевыми счётчиками.

Правок две: умолчания подвижности (``repair_mobility_defaults``) и точечные
правки опечаток в отдельных записях (``repair_record_overrides``). Точечные
правки называются пользователю: ``applied_overrides`` и ``override_warnings``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

# Типы параметров кинетики: активационная энергия и предэкспонента подвижности
# (MQ/MF) и то же для прямой модели диффузии (DQ/DF). Именно их суммирует
# ``kawin.thermo.Mobility.MobilityModel``.
KINETIC_PARAMETER_TYPES: tuple[str, ...] = ("MQ", "MF", "DQ", "DF")

# Метка на объекте базы: правка уже применена.
_REPAIR_FLAG = "_thermogar_mobility_defaults_repaired"

WILDCARD = "*"


@dataclass(frozen=True)
class MobilityRepairReport:
    """Что именно убрано из таблицы параметров."""

    removed: int = 0
    materialised: int = 0
    kept_as_only_source: int = 0
    kept_as_different_expression: int = 0
    removed_keys: tuple[tuple[str, str, str, int], ...] = field(default=())
    kept_keys: tuple[tuple[str, str, str, int], ...] = field(default=())
    suspicious_keys: tuple[tuple[str, str, str, int], ...] = field(default=())
    database_label: str = ""
    already_repaired: bool = False

    @property
    def changed(self) -> bool:
        return self.removed > 0

    def log_line(self) -> str:
        """Строка для лога расчёта и для паспорта базы."""

        label = self.database_label or "база"
        line = (
            f"дедупликация подвижностей: {label} — "
            f"отброшено {self.removed} параметров-умолчаний, "
            f"развёрнуто в явные {self.materialised}"
        )
        if self.kept_as_different_expression:
            line += (
                f"; оставлено без изменений {self.kept_as_different_expression} "
                "мест, где выражения различаются"
            )
        if self.kept_as_only_source:
            line += (
                f"; {self.kept_as_only_source} умолчаний оставлены как "
                "единственный источник подвижности"
            )
        return line


def _expressions_are_identical(first: Any, second: Any) -> bool:
    """Символьное сравнение выражений параметров.

    Строковое сравнение не годится: пробелы и порядок слагаемых у разобранных
    выражений различаются. ``pycalphad`` держит выражения в ``symengine``,
    поэтому сравнение идёт им, а ``sympy`` используется как запасной вариант.
    Если символьная алгебра недоступна, возвращается ``False``: параметр
    считается не дублем и не отбрасывается. Ошибаться безопаснее в эту
    сторону — лишний параметр хуже, чем выброшенный нужный.
    """

    try:
        import symengine

        return bool(symengine.expand(first - second) == 0)
    except Exception:
        pass
    try:
        import sympy

        return bool(sympy.simplify(first - second) == 0)
    except Exception:
        return False


def _diffusing_species_name(record: Any) -> str:
    species = record.get("diffusing_species")
    return str(getattr(species, "name", "") or "").upper()


def _is_degenerate_default(constituent_array: Any, sublattice_count: int) -> bool:
    """Строка вида ``MQ(<фаза>&<элемент>,*)`` при фазе с несколькими подрешётками.

    В Thermo-Calc такая запись — значение по умолчанию «для любого
    составляющего», то есть замена отсутствующей явной строки. ``pycalphad``
    разбирает её как массив из одной подрешётки ``((*,),)``, а
    ``kawin.thermo.Mobility.MobilityModel._buildMobilityModels`` складывает все
    подходящие строки в один полином Редлиха — Кистера. В результате умолчание
    не заменяет явную строку, а прибавляется к ней, и подвижность выходит как
    ``exp(2·MQ/RT)`` вместо ``exp(MQ/RT)`` — то есть коэффициент диффузии
    возводится в квадрат.

    Признак вырожденности: ровно одна подрешётка, в ней ровно один
    составляющий ``*``, а сама фаза описана более чем одной подрешёткой.
    Настоящие однорешёточные фазы под это условие не попадают.
    """

    if sublattice_count <= 1:
        return False
    try:
        if len(constituent_array) != 1 or len(constituent_array[0]) != 1:
            return False
    except TypeError:
        return False
    return str(constituent_array[0][0]) == WILDCARD


def _sublattice_count(database: Any, phase_name: str) -> int:
    phase = database.phases.get(str(phase_name))
    if phase is None:
        return -1
    return len(phase.constituents)


def repair_mobility_defaults(
    database: Any,
    database_label: str = "",
) -> MobilityRepairReport:
    """Убрать умолчания подвижности, дублирующие явную строку того же элемента.

    Для каждого ключа «фаза + тип параметра + диффундирующий элемент + порядок»
    строка-умолчание ``(*)`` удаляется, только если выполнены оба условия:

    * для того же ключа есть обычная строка (например ``NI:*``);
    * выражения обеих строк символьно совпадают.

    Совпадение выражений — признак того, что умолчание и явная строка
    описывают одно и то же, и суммирование их даёт квадрат подвижности. Если
    выражения различаются, это уже не дубль: автор базы мог иметь в виду разные
    вклады. Тогда ничего не отбрасывается, ключ попадает в ``suspicious_keys``
    и в строку лога, а решение остаётся человеку.

    Если явной строки нет вовсе, умолчание — единственный источник подвижности
    этого элемента, и оно сохраняется: без него элемент остался бы вовсе без
    кинетики, что хуже исходного дефекта.

    Возвращает отчёт; сама база меняется на месте.
    """

    if getattr(database, _REPAIR_FLAG, False):
        return MobilityRepairReport(
            already_repaired=True, database_label=database_label
        )

    table = database._parameters.table(  # noqa: SLF001 — публичного доступа нет
        database._parameters.default_table_name  # noqa: SLF001
    )

    degenerate: dict[tuple[str, str, str, int], list[Any]] = {}
    explicit: dict[tuple[str, str, str, int], list[Any]] = {}

    for record in table.all():
        parameter_type = str(record.get("parameter_type", ""))
        if parameter_type not in KINETIC_PARAMETER_TYPES:
            continue
        phase_name = str(record.get("phase_name", ""))
        key = (
            phase_name,
            parameter_type,
            _diffusing_species_name(record),
            int(record.get("parameter_order", 0) or 0),
        )
        if _is_degenerate_default(
            record.get("constituent_array"), _sublattice_count(database, phase_name)
        ):
            degenerate.setdefault(key, []).append(record)
        else:
            explicit.setdefault(key, []).append(record)

    doomed: list[int] = []
    added: list[dict[str, Any]] = []
    removed_keys: list[tuple[str, str, str, int]] = []
    kept_keys: list[tuple[str, str, str, int]] = []
    suspicious_keys: list[tuple[str, str, str, int]] = []
    for key, records in sorted(degenerate.items()):
        phase_name, _parameter_type, _species, _order = key
        phase = database.phases.get(phase_name)
        if phase is None:
            kept_keys.append(key)
            continue
        counterparts = explicit.get(key, [])

        # Умолчание относится к тем составляющим первой подрешётки, у которых
        # своей строки нет. Материализуем его именно для них и убираем саму
        # вырожденную строку: тогда сумма Редлиха — Кистера снова считается по
        # полному набору составляющих с суммой весов, равной единице, и ни
        # двойного счёта, ни потери вклада не остаётся.
        covered = {
            _first_sublattice_name(record.get("constituent_array"))
            for record in counterparts
        }
        covered.discard("")
        targets = sorted(
            {str(species) for species in phase.constituents[0]} - covered - {WILDCARD}
        )
        if not targets and not counterparts:
            # Некого замещать и не с чем конфликтовать — оставляем как есть.
            kept_keys.append(key)
            continue

        template = counterparts[0] if counterparts else None
        for record in records:
            for target in targets:
                new_record = dict(record)
                new_record["constituent_array"] = _explicit_constituent_array(
                    record.get("constituent_array"),
                    template.get("constituent_array") if template else None,
                    target,
                    len(phase.constituents),
                )
                added.append(new_record)
            doomed.append(int(record.doc_id))

        if counterparts and any(
            _expressions_are_identical(
                record.get("parameter"), other.get("parameter")
            )
            for record in records
            for other in counterparts
        ):
            removed_keys.append(key)
        elif counterparts:
            # Выражения различаются — это не дубль. Строка всё равно
            # перераспределяется по «непокрытым» составляющим, потому что
            # именно так её понимает Thermo-Calc, но место отмечается как
            # подозрительное и уходит в лог.
            suspicious_keys.append(key)
        else:
            kept_keys.append(key)

    if doomed:
        table.remove(doc_ids=doomed)
    if added:
        table.insert_multiple(added)

    setattr(database, _REPAIR_FLAG, True)
    return MobilityRepairReport(
        removed=len(doomed),
        materialised=len(added),
        kept_as_only_source=len(kept_keys),
        kept_as_different_expression=len(suspicious_keys),
        removed_keys=tuple(removed_keys),
        kept_keys=tuple(kept_keys),
        suspicious_keys=tuple(suspicious_keys),
        database_label=database_label,
    )


def _first_sublattice_name(constituent_array: Any) -> str:
    """Имя единственного составляющего первой подрешётки или пустая строка."""

    try:
        first = constituent_array[0]
        if len(first) != 1:
            return ""
        return str(first[0])
    except Exception:
        return ""


def _explicit_constituent_array(
    degenerate_array: Any,
    template_array: Any,
    target: str,
    sublattice_count: int,
) -> Any:
    """Массив составляющих для материализованного умолчания.

    Форма берётся у существующей явной строки того же ключа, если она есть:
    так материализованная строка неотличима от написанной в базе руками. Если
    явных строк нет, массив собирается из целевого составляющего и звёздочек
    по числу подрешёток фазы.
    """

    species_type = type(degenerate_array[0][0])
    try:
        target_species = species_type(target)
    except Exception:
        target_species = target

    if template_array is not None:
        rebuilt = [tuple(sublattice) for sublattice in template_array]
        rebuilt[0] = (target_species,)
        return tuple(rebuilt)

    wildcard_species = degenerate_array[0][0]
    return tuple(
        [(target_species,)] + [(wildcard_species,)] * max(0, sublattice_count - 1)
    )


# --------------------------------------------------------------------------- #
# Пары «порядок/беспорядок», которые pycalphad не может построить
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class BrokenOrderDisorder:
    """Упорядоченная фаза, чью модель нельзя построить на этом наборе элементов."""

    ordered_phase: str
    disordered_phase: str
    interstitial_of_disordered: tuple[str, ...]
    interstitial_of_ordered: tuple[tuple[str, ...], ...]
    reason: str


def _active_names(constituents: Any, active: set[str]) -> set[str]:
    return {str(species) for species in constituents} & active


def broken_order_disorder_phases(
    database: Any,
    components: Iterable[str],
) -> dict[str, BrokenOrderDisorder]:
    """Пары «порядок/беспорядок», несовместимые с этим набором компонентов.

    ``pycalphad.model._extend_ordered_if_subset_of_disorder`` требует, чтобы у
    упорядоченной фазы была ровно одна подрешётка, набор активных составляющих
    которой совпадает с внедрённой подрешёткой разупорядоченной фазы. Если это
    не так, ``Model`` поднимает ``ValueError`` ещё до расчёта, и падает не одна
    фаза, а весь расчёт.

    Так происходит, например, с парой ``BCC_B2``/``BCC_A2`` в ``mc_ni``, когда
    в системе есть углерод: у ``BCC_A2`` внедрённая подрешётка содержит C, а у
    ``BCC_B2`` — только вакансии, потому что углерод в упорядоченной ОЦК-фазе
    этой базой не описан.

    Проверка повторяет условие pycalphad по структуре базы и ничего не строит,
    поэтому стоит доли миллисекунды на фазу. Расширять составляющие
    упорядоченной фазы нельзя: параметров для новых конечных членов в базе нет,
    и фаза получила бы выдуманную устойчивость. Правильный ответ — исключить её
    из расчёта и сказать об этом пользователю.
    """

    active = {str(name).upper() for name in components}
    broken: dict[str, BrokenOrderDisorder] = {}

    for phase_name, phase in database.phases.items():
        hints = getattr(phase, "model_hints", {}) or {}
        if hints.get("ordered_phase") != phase_name:
            continue
        disordered_name = hints.get("disordered_phase")
        disordered = database.phases.get(disordered_name)
        if disordered is None:
            continue
        if len(disordered.constituents) != 2:
            # Без внедрённой подрешётки условие не проверяется вовсе.
            continue

        interstitial = _active_names(disordered.constituents[1], active)
        matching = [
            _active_names(sublattice, active) for sublattice in phase.constituents
        ]
        equal = [names for names in matching if names == interstitial]
        if len(equal) == 1:
            continue

        broken[str(phase_name)] = BrokenOrderDisorder(
            ordered_phase=str(phase_name),
            disordered_phase=str(disordered_name),
            interstitial_of_disordered=tuple(sorted(interstitial)),
            interstitial_of_ordered=tuple(
                tuple(sorted(names)) for names in matching
            ),
            reason=(
                f"внедрённая подрешётка {disordered_name} на этом составе — "
                f"{{{', '.join(sorted(interstitial)) or '—'}}}, а у {phase_name} "
                f"совпадающих подрешёток {len(equal)}, нужна ровно одна"
            ),
        )
    return broken


# Точная фраза pycalphad, по которой узнаётся именно этот отказ модели.
# Ловим по типу исключения и по фразе, а не голым ``except Exception``: любая
# другая ошибка модели должна дойти до пользователя, а не быть проглоченной.
ORDER_DISORDER_ERROR_PHRASE = "must have no interstitial sublattice"

MODEL_BUILD_ERROR_NOTE = "модель фазы не строится на этом наборе элементов"


def is_order_disorder_model_error(error: BaseException) -> bool:
    """Это тот самый отказ пары «порядок/беспорядок»?"""

    return isinstance(error, ValueError) and ORDER_DISORDER_ERROR_PHRASE in str(error)


def verify_phase_builds(
    database: Any,
    components: Iterable[str],
    phase_name: str,
) -> tuple[bool, str]:
    """Построить ``Model`` фазы и вернуть «строится, причина отказа».

    Проверка настоящая, а не предсказание по структуре: именно так фаза ведёт
    себя в расчёте. Отказ пары «порядок/беспорядок» распознаётся по типу и
    фразе; всякая другая ошибка возвращается со своим текстом, но фаза тоже
    считается непригодной — расчёт с ней всё равно упадёт.
    """

    from pycalphad import Model

    try:
        Model(database, list(components), str(phase_name))
    except Exception as error:  # noqa: BLE001 — тип разбирается ниже
        if is_order_disorder_model_error(error):
            return False, f"{MODEL_BUILD_ERROR_NOTE}: {error}"
        return False, f"{type(error).__name__}: {error}"
    return True, ""


def unbuildable_phases(
    database: Any,
    components: Iterable[str],
    phases: Iterable[str],
    verify: bool = True,
) -> dict[str, str]:
    """Фазы из списка, чью модель нельзя построить, с причиной у каждой.

    Кандидатов сначала отбирает структурная проверка (доли миллисекунды на
    фазу), и только они проверяются построением ``Model``. Полный перебор
    построением стоил бы секунды на каждую из полусотни фаз.
    """

    ordered = [str(name) for name in phases]
    suspects = broken_order_disorder_phases(database, components)
    result: dict[str, str] = {}
    for name in ordered:
        item = suspects.get(name)
        if item is None:
            continue
        if not verify:
            result[name] = f"{MODEL_BUILD_ERROR_NOTE}: {item.reason}"
            continue
        builds, reason = verify_phase_builds(database, components, name)
        if not builds:
            result[name] = reason
    return result


def excluded_phases_note(removed: Mapping[str, Any]) -> str:
    """Одна строка для пользователя и для лога расчёта."""

    if not removed:
        return ""
    names = ", ".join(
        f"{name} (упорядоченная модель + межузельная подрешётка)"
        for name in sorted(removed)
    )
    return "Фазы, несовместимые с составом, исключены: " + names


def drop_broken_order_disorder(
    database: Any,
    components: Iterable[str],
    phases: Iterable[str],
    verify: bool = True,
) -> tuple[list[str], dict[str, BrokenOrderDisorder]]:
    """Убрать из списка фазы, чью модель на этом составе не строится.

    Возвращает пару «оставшиеся фазы, исключённые фазы с причиной». Порядок
    исходного списка сохраняется. При ``verify=True`` каждая фаза-кандидат
    дополнительно проверяется построением ``Model``.
    """

    structural = broken_order_disorder_phases(database, components)
    ordered = [str(name) for name in phases]
    if verify and structural:
        confirmed = unbuildable_phases(database, components, ordered, verify=True)
        structural = {
            name: item for name, item in structural.items() if name in confirmed
        }
    kept = [name for name in ordered if name not in structural]
    removed = {name: structural[name] for name in ordered if name in structural}
    if removed:
        _log(excluded_phases_note(removed))
    return kept, removed


# --------------------------------------------------------------------------- #
# Точечные правки записей: опечатки, которые разборщик понимает иначе
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class RecordOverride:
    """Одна наша правка отдельной записи разобранной базы.

    Поля повторяют ``thermogar_physical.DensityOverride``, чтобы обе базы
    сообщали о правках одинаково: что заменено, на что, почему и откуда число.
    """

    identifier: str
    phase_name: str
    parameter_type: str
    diffusing_species: str
    constituents: tuple[tuple[str, ...], ...]
    element: str
    original_expression: str
    expression: str
    broken_function: str
    broken_arguments: tuple[float, ...]
    replacement_argument: float
    reason: str
    source: str
    wave: str
    user_message: str


# BL-20. Строка подвижности ниобия в mc_ni записана с десятичной запятой:
#   PARAMETER MQ(FCC_A1&NB,NB:*) 273.00  -350000+R*T*LN(1,00E-4); 6000.00  N
# ``pycalphad`` отдаёт её ``symengine.sympify``, для которого запятая —
# разделитель аргументов, а ``00E-4`` — число 0.0. Получается неопределённая
# функция ``ln(1.0, 0.0)``: равновесию она не мешает (MQ в энергию Гиббса не
# входит), а ``kawin`` падает на компиляции ``MOB_NB`` с
# ``RuntimeError: ln(1.0, 0.0)`` на любом составе с ниобием. Разбор —
# ``tasks/WAVE13_G_REPORT.md``, раздел «BL-20».
NB_FCC_MOBILITY_DECIMAL_COMMA = RecordOverride(
    identifier="BL-20",
    phase_name="FCC_A1",
    parameter_type="MQ",
    diffusing_species="NB",
    constituents=(("NB",), ("*",)),
    element="NB",
    original_expression="-350000+R*T*LN(1,00E-4)",
    expression="-350000+R*T*LN(1.00E-4)",
    broken_function="ln",
    broken_arguments=(1.0, 0.0),
    replacement_argument=1.00e-4,
    reason=(
        "десятичная запятая в аргументе LN: разборщик читает LN(1,00E-4) как "
        "двухаргументную функцию ln(1, 0.0), которую kawin не может "
        "скомпилировать"
    ),
    source=(
        "Число взято из самой строки базы, заменён только разделитель: "
        "databases/converted/mc_ni_v2036_with_mobility.garcalc.tdb:10583, "
        "перенесено конвертером из databases/original/ni/mc_ni_v2012.ddb:476; "
        "ссылка строки REF:pov10 (E. Povoden-Karadeniz, unpublished, 2010) не "
        "опубликована, и сверить значение с первоисточником не с чем."
    ),
    wave="13-Д",
    user_message=(
        "Подвижность ниобия в FCC_A1: в базе записано LN(1,00E-4) с десятичной "
        "запятой, ThermoGar читает это как ln(1.00E-4). Правка сделана поверх "
        "разобранной базы, байты файла не менялись; число взято из той же "
        "строки, первоисточник строки (pov10) не опубликован и не сверен."
    ),
)

RECORD_OVERRIDES: tuple[RecordOverride, ...] = (NB_FCC_MOBILITY_DECIMAL_COMMA,)

# Правки, применённые к объекту базы. Хранится на самом объекте, а не в
# модуле: база уходит в кэш и в пул процессов через pickle, и признак правки
# должен доехать туда вместе с исправленной записью.
_OVERRIDES_ATTRIBUTE = "_thermogar_applied_overrides"


def _constituent_names(constituent_array: Any) -> tuple[tuple[str, ...], ...]:
    try:
        return tuple(
            tuple(str(getattr(item, "name", item)) for item in sublattice)
            for sublattice in constituent_array
        )
    except TypeError:
        return ()


def _broken_calls(expression: Any, override: RecordOverride) -> list[Any]:
    """Узлы выражения — неопределённые функции, описанные правкой."""

    try:
        import symengine

        atoms = expression.atoms(symengine.FunctionSymbol)
    except Exception:
        return []
    found = []
    for atom in atoms:
        if str(atom.get_name()) != override.broken_function:
            continue
        try:
            arguments = tuple(float(argument) for argument in atom.args)
        except (TypeError, ValueError):
            continue
        if arguments == override.broken_arguments:
            found.append(atom)
    return found


def repair_record_overrides(
    database: Any,
    database_label: str = "",
    overrides: Iterable[RecordOverride] = RECORD_OVERRIDES,
) -> tuple[RecordOverride, ...]:
    """Исправить записи, перечисленные в ``RECORD_OVERRIDES``.

    Запись меняется, только если совпало всё: фаза, тип параметра,
    диффундирующий элемент, составляющие и сама испорченная функция с теми же
    аргументами. На любой другой базе, в том числе на исправленной версии той
    же базы, правка ничего не делает. Повторный вызов тоже ничего не делает.

    Возвращает правки, применённые этим вызовом; все правки объекта —
    ``applied_overrides``.
    """

    import symengine

    table = database._parameters.table(  # noqa: SLF001 — публичного доступа нет
        database._parameters.default_table_name  # noqa: SLF001
    )
    applied: list[RecordOverride] = []
    for override in overrides:
        changed = False
        for record in table.all():
            if (
                str(record.get("phase_name", "")) != override.phase_name
                or str(record.get("parameter_type", "")) != override.parameter_type
                or _diffusing_species_name(record) != override.diffusing_species
                or _constituent_names(record.get("constituent_array"))
                != override.constituents
            ):
                continue
            expression = record.get("parameter")
            calls = _broken_calls(expression, override)
            if not calls:
                continue
            replacement = symengine.log(
                symengine.RealDouble(override.replacement_argument)
            )
            fixed = expression.xreplace({call: replacement for call in calls})
            table.update({"parameter": fixed}, doc_ids=[int(record.doc_id)])
            changed = True
        if changed:
            applied.append(override)
            _log(
                f"правка записи {override.identifier}: {database_label or 'база'} — "
                f"{override.parameter_type}({override.phase_name}&"
                f"{override.diffusing_species},"
                f"{':'.join(','.join(names) for names in override.constituents)}) "
                f"{override.original_expression} -> {override.expression}"
            )
    if applied:
        known = {item.identifier for item in applied_overrides(database)}
        setattr(
            database,
            _OVERRIDES_ATTRIBUTE,
            applied_overrides(database)
            + tuple(item for item in applied if item.identifier not in known),
        )
    return tuple(applied)


def applied_overrides(database: Any) -> tuple[RecordOverride, ...]:
    """Все точечные правки, применённые к этому объекту базы."""

    return tuple(getattr(database, _OVERRIDES_ATTRIBUTE, ()) or ())


def override_warnings(
    database: Any,
    elements: Iterable[str] | None = None,
) -> list[str]:
    """Тексты для пользователя о применённых правках.

    С ``elements`` остаются только правки, которые касаются элементов расчёта:
    исправленная подвижность ниобия не влияет на состав без ниобия.
    """

    wanted = None if elements is None else {str(name).upper() for name in elements}
    return [
        item.user_message
        for item in applied_overrides(database)
        if wanted is None or item.element in wanted
    ]


# Версия логики правок загрузки. Входит в ключ кэша разобранных баз: без этого
# пользователь со старым кэшем получил бы прежнее поведение. 4 — правка BL-20.
MOBILITY_DEDUP_VERSION = 4

_LAST_REPORTS: dict[str, MobilityRepairReport] = {}


def repair_database(database: Any, database_label: str = "") -> dict[str, Any]:
    """Все правки загрузки разом; вызывается из путей загрузки базы.

    Точечные правки идут первыми: дедупликация сравнивает выражения, и
    испорченная запись не должна в этом участвовать.
    """

    repair_record_overrides(database, database_label=database_label)
    mobility = repair_mobility_defaults(database, database_label=database_label)
    if not mobility.already_repaired:
        _LAST_REPORTS[database_label or "база"] = mobility
        _log(mobility.log_line())
        for key in mobility.suspicious_keys:
            _log(
                "  подозрительно: умолчание и явная строка различаются — "
                f"{key[0]} / {key[1]} / {key[2]} / порядок {key[3]}"
            )
    return {
        "mobility_defaults": mobility,
        "applied_overrides": applied_overrides(database),
        "warnings": override_warnings(database),
    }


def _log(message: str) -> None:
    """Строка в лог расчёта."""

    import logging

    logging.getLogger("thermogar.database_repair").info(message)


def last_mobility_report(database_label: str = "") -> "MobilityRepairReport | None":
    """Отчёт последней дедупликации — для паспорта базы в интерфейсе."""

    return _LAST_REPORTS.get(database_label or "база")


def mobility_report_of(
    database: Any,
    database_label: str = "",
) -> MobilityRepairReport:
    """Отчёт дедупликации, посчитанный на копии базы (для UI и тестов)."""

    import pickle

    copy = pickle.loads(pickle.dumps(database, protocol=pickle.HIGHEST_PROTOCOL))
    try:
        delattr(copy, _REPAIR_FLAG)
    except Exception:
        pass
    return repair_mobility_defaults(copy, database_label=database_label)


def mobility_repair_applied(database: Any) -> bool:
    """Была ли база пропущена через правку подвижностей."""

    return bool(getattr(database, _REPAIR_FLAG, False))


def degenerate_default_records(database: Any) -> list[Any]:
    """Оставшиеся строки-умолчания — для тестов и диагностики."""

    table = database._parameters.table(  # noqa: SLF001
        database._parameters.default_table_name  # noqa: SLF001
    )
    return [
        record
        for record in table.all()
        if str(record.get("parameter_type", "")) in KINETIC_PARAMETER_TYPES
        and _is_degenerate_default(
            record.get("constituent_array"),
            _sublattice_count(database, str(record.get("phase_name", ""))),
        )
    ]


def duplicated_default_keys(database: Any) -> list[tuple[str, str, str, int]]:
    """Ключи, где умолчание и явная строка сосуществуют (должно быть пусто)."""

    table = database._parameters.table(  # noqa: SLF001
        database._parameters.default_table_name  # noqa: SLF001
    )
    degenerate: set[tuple[str, str, str, int]] = set()
    explicit: set[tuple[str, str, str, int]] = set()
    for record in table.all():
        parameter_type = str(record.get("parameter_type", ""))
        if parameter_type not in KINETIC_PARAMETER_TYPES:
            continue
        phase_name = str(record.get("phase_name", ""))
        key = (
            phase_name,
            parameter_type,
            _diffusing_species_name(record),
            int(record.get("parameter_order", 0) or 0),
        )
        if _is_degenerate_default(
            record.get("constituent_array"), _sublattice_count(database, phase_name)
        ):
            degenerate.add(key)
        else:
            explicit.add(key)
    return sorted(degenerate & explicit)


def _iter_phase_names(database: Any) -> Iterable[str]:
    return sorted(str(name) for name in database.phases)
