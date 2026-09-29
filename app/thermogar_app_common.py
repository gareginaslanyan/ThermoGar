"""Общие помощники головного сценария ThermoGar.

BL-57, разрез app/ThermoGar_app.py, шаг «общие помощники» (20-Ж). Здесь —
определения, нужные больше чем одной вкладке: разбор состава и подготовка
расчёта, списки фаз и примечания к ним, равновесие по точкам, графики и
выгрузка. Перенесены из головного сценария без изменений, в прежнем порядке.
Состояние прогона здесь не хранится: пути состояния, кэш баз и ленивая
загрузка scheil остаются в головном сценарии.
"""

from __future__ import annotations

from collections import defaultdict
from io import BytesIO
from pathlib import Path
import hashlib
import re
from typing import Any, Callable, Mapping
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from pycalphad import Database, variables as v
from pycalphad.core.utils import filter_phases, unpack_species
from thermogar_palette import (
    ThemedFigure,
    annotate_line_ends,
    chart_roles,
    element_case_text,
    normalize_theme,
    phase_styles,
    place_legend_below,
    resolve_figure,
)
import thermogar_parallel_ui as parallel_ui
import thermogar_restricted_fe_core as restricted_fe
import thermogar_verified_equilibrium as verified_equilibrium
import thermogar_verified_loaders as verified_loaders
import thermogar_verified_physical as verified_physical
import thermogar_verified_properties as verified_properties
from thermogar_release_policy import (
    DROPPED_PHASES_SHOWN,
    FE_EXCLUDED_PHASES,
    PHASE_MODE_ALL,
    PHASE_MODE_FAST,
    PHASE_MODE_HELP,
    PHASE_MODE_LABELS,
    RELEASE_DATABASE_LABELS,
    PhasePresetError,
    dropped_phases_expander_label,
    dropped_phases_full_list,
    dropped_phases_warning,
    effective_release_phases,
    load_phase_presets,
    phase_mode_note,
    preset_phases,
)
from thermogar_release_ui import (
    BLOCK_PHASES,
    FoldedFields,
    folded_block,
)
from thermogar_user_errors import (
    EMPTY_CELL_TEXT,
    UserRuntimeError,
    UserValueError,
    element_symbol,
    element_symbols,
)
from thermogar_app_texts import (
    PHASE_EXPLANATIONS,
)
from thermogar_app_context import SidebarContext


acquire_b3_execution = verified_loaders.acquire_execution


def find_project_root() -> Path:
    """Найти корень проекта независимо от текущей рабочей папки."""
    candidates = [
        Path(__file__).resolve().parent,
        Path(__file__).resolve().parent.parent,
        Path.cwd(),
        Path.cwd().parent,
    ]
    for candidate in candidates:
        if (candidate / "databases").exists():
            return candidate
    raise FileNotFoundError(
        "Файлы ThermoGar не найдены. Переустановите программу."
    )


PROJECT_ROOT = find_project_root()


# Case-sensitive on purpose. A TDB keyword is uppercase, while the indented
# bibliography inside REFERENCE_FILE contains lines such as
# "Phase diagram in the iron-rich corner ...". Matching those case-insensitively
# returned "diagram", "equilibria", "relations" and "stability" as phase names,
# which the verified loader then rejected as non-canonical, so binding any
# database failed and the application stopped before rendering any control.
_TDB_PHASE_DECLARATION = re.compile(
    r"(?m)^\s*PHASE\s+([A-Z][A-Z0-9_]*)\s"
)


def _verified_tdb_declared_phases(
    artifact: verified_loaders.VerifiedArtifact,
) -> tuple[str, ...]:
    """Read only canonical PHASE declarations from a verified TDB snapshot."""

    if type(artifact) is not verified_loaders.VerifiedArtifact:
        raise TypeError("Verified phase declaration provider requires TDB evidence.")
    phases = tuple(
        sorted(set(_TDB_PHASE_DECLARATION.findall(artifact.verified_text())))
    )
    if not phases:
        raise RuntimeError("Verified TDB contains no canonical PHASE declarations.")
    return phases


def clear_b4b_physical_session_results() -> None:
    for state_key in tuple(st.session_state):
        if str(state_key).startswith("_thermogar_vlb_b4b_result_"):
            st.session_state.pop(state_key, None)
    verified_properties.clear_property_witnesses()


def verified_b3_candidate_phases(
    context: verified_loaders.BoundDatabaseContext,
    candidates: tuple[str, ...],
) -> tuple[str, ...]:
    without_c15 = tuple(
        phase for phase in candidates if phase != restricted_fe.C15_PHASE
    )
    return context.phase_policy.effective((), candidates=without_c15)


def verified_b3_refresh_result(
    result_key: str,
    request_key: str,
    decision: verified_loaders.FeatureRequest | verified_loaders.RejectedFeatureReceipt | None,
) -> None:
    request_digest = (
        decision.request_digest
        if type(decision) is verified_loaders.FeatureRequest
        else None
    )
    if st.session_state.get(request_key) != request_digest:
        st.session_state.pop(result_key, None)
    if request_digest is None:
        st.session_state.pop(request_key, None)
    else:
        st.session_state[request_key] = request_digest


def verified_b3_store_result(
    state_key: str,
    display: dict[str, Any],
    execution: verified_equilibrium.VerifiedEquilibriumResult | None,
) -> None:
    st.session_state[state_key] = {
        "display": display,
        "receipt_digest": (
            execution.feature_receipt.receipt_digest
            if execution is not None
            else None
        ),
        "envelope_digest": (
            execution.result_envelope.envelope_digest
            if execution is not None
            else None
        ),
    }


def parse_composition(text: str) -> dict[str, float]:
    """Прочитать строку вида AL=15, CR=10."""
    text = text.strip()
    if not text:
        return {}

    pattern = re.compile(
        r"([A-Za-z]{1,2})\s*=\s*([+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+))"
    )
    matches = list(pattern.finditer(text))
    if not matches:
        raise UserValueError("Не удалось прочитать состав. Пример: Al=15, Cr=10")

    remainder = pattern.sub("", text)
    remainder = re.sub(r"[\s,;]+", "", remainder)
    if remainder:
        raise UserValueError(f"Непонятный фрагмент в составе: {remainder!r}")

    result: dict[str, float] = {}
    for match in matches:
        element = match.group(1).upper()
        value = float(match.group(2).replace(",", "."))
        if element in result:
            raise UserValueError(
                f"Элемент {element_symbol(element)} указан более одного раза."
            )
        result[element] = value
    return result


def units_suffix(units: str) -> str:
    """Единицы состава в подписи поля: «ат.%» или «мас.%» (21-Г, Д1–Д10)."""
    return "ат.%" if units == "at" else "мас.%"


def normalize(values: dict[str, float]) -> dict[str, float]:
    cleaned = {
        element: max(0.0, float(value))
        for element, value in values.items()
        if np.isfinite(value)
    }
    total = sum(cleaned.values())
    if total <= 0:
        return cleaned
    return {element: value / total for element, value in cleaned.items()}


def mole_to_mass(
    db: Database,
    mole_fractions: dict[str, float],
) -> dict[str, float]:
    masses = {
        element: float(db.refstates[element]["mass"])
        for element in mole_fractions
    }
    denominator = sum(
        mole_fractions[element] * masses[element]
        for element in mole_fractions
    )
    if denominator <= 0:
        raise UserValueError("Не удалось пересчитать состав в массовые доли.")
    return {
        element: mole_fractions[element] * masses[element] / denominator
        for element in mole_fractions
    }


def build_input(
    db: Database,
    available_elements: list[str],
    entered: dict[str, float],
    units: str,
    balance: str,
) -> tuple[
    list[str],
    dict[Any, float],
    dict[str, float],
    dict[str, float],
]:
    unknown = sorted(set(entered) - set(available_elements))
    if unknown:
        raise UserValueError("В базе отсутствуют элементы: " + element_symbols(unknown))
    if balance in entered:
        raise UserValueError(
            f"{element_symbol(balance)} выбран как основа; не указывайте его в "
            "строке добавок."
        )
    for element, value in entered.items():
        if value <= 0:
            raise UserValueError(
                f"Содержание {element_symbol(element)} должно быть больше нуля."
            )
    if sum(entered.values()) >= 100:
        raise UserValueError("Сумма добавок должна быть меньше 100 %.")

    components = sorted(set(entered) | {balance}) + ["VA"]

    if units == "at":
        independent = {
            v.X(element): value / 100.0 for element, value in entered.items()
        }
        overall_x = {
            element: value / 100.0 for element, value in entered.items()
        }
        overall_x[balance] = 1.0 - sum(overall_x.values())
    elif units == "wt":
        mass_conditions = {
            v.W(element): value / 100.0 for element, value in entered.items()
        }
        independent = dict(v.get_mole_fractions(mass_conditions, balance, db))
        overall_x = {
            str(variable.species): float(value)
            for variable, value in independent.items()
        }
        overall_x[balance] = 1.0 - sum(overall_x.values())
    else:
        raise UserValueError(f"Неизвестные единицы состава: {units}")

    overall_x = normalize(overall_x)
    overall_w = mole_to_mass(db, overall_x)
    return components, independent, overall_x, overall_w


def filter_for_mode(
    phases: list[str],
    database_key: str,
    steel_mode: str,
) -> list[str]:
    result = list(phases)
    if database_key == "fe" and steel_mode == "metastable":
        result = [
            phase
            for phase in result
            if phase not in {"GRAPHITE", "DIAMOND_A4"}
        ]
    return result


def rejected_release_phases(
    database_key: str,
    phases: Any,
) -> list[str]:
    """Фазы набора, запрещённые для выбранной базы (для Fe — C15_LAVES)."""
    allowed = set(effective_release_phases(database_key, phases))
    return sorted(set(phases) - allowed)


def excluded_phase_message(rejected: list[str]) -> str:
    """Понятное сообщение об отклонённом ручном выборе фазы."""
    return (
        ", ".join(rejected)
        + " исключена для стальной базы и не может быть выбрана."
    )


def available_phase_presets() -> dict[str, tuple[str, ...]]:
    """Быстрые наборы фаз из ``configs/phase_presets.json``.

    Если файла нет или он не соответствует схеме, наборы недоступны и
    приложение работает как раньше — на всех совместимых фазах базы.
    """
    try:
        return dict(load_phase_presets(PROJECT_ROOT))
    except PhasePresetError:
        return {}


def compatible_phases_for_components(
    db: Database,
    database_key: str,
    components: list[str],
    steel_mode: str,
    phase_mode: str = PHASE_MODE_ALL,
) -> list[str]:
    """Вернуть совместимые с компонентами фазы с учётом режима стали.

    ``phase_mode`` выбирает между всеми совместимыми фазами базы
    (``PHASE_MODE_ALL``) и быстрым набором обычных для практики фаз
    (``PHASE_MODE_FAST``). Быстрый набор применяется до правила C15.
    """
    phases = filter_phases(
        db,
        unpack_species(db, components),
    )
    phases = filter_for_mode(
        phases,
        database_key,
        steel_mode,
    )
    if phase_mode == PHASE_MODE_FAST:
        phases = preset_phases(
            available_phase_presets(),
            database_key,
            phases,
        )
    # Единственная точка исключения C15_LAVES для Fe: через неё проходят все
    # автоматические списки фаз (равновесие, сканы, диаграммы, карта доли,
    # затвердевание, энергии, T₀). Правило действует в обоих режимах набора.
    phases = effective_release_phases(database_key, phases)
    # Здесь же снимаются пары «порядок/беспорядок», чью модель pycalphad на
    # этом наборе элементов построить не может: иначе ValueError из Model
    # уносит весь расчёт, а не одну фазу. Что и почему снято — в
    # unbuildable_phase_note ниже.
    phases, unbuildable = drop_unbuildable_order_disorder(db, components, phases)
    _remember_unbuildable_phases(unbuildable)
    return sorted(dict.fromkeys(phases))


UNBUILDABLE_PHASES_STATE_KEY = "_unbuildable_order_disorder_note"


def _remember_unbuildable_phases(removed: dict[str, Any]) -> None:
    """Запомнить снятые фазы, чтобы блок управления фазами о них сказал.

    Список фаз строится и вне отрисовки виджетов, поэтому запись в
    ``session_state`` защищена: без сессии Streamlit она просто не выполняется.
    """

    try:
        st.session_state[UNBUILDABLE_PHASES_STATE_KEY] = unbuildable_phase_note(removed)
    except Exception:
        pass


def unbuildable_order_disorder(
    db: Database,
    components: list[str],
) -> dict[str, Any]:
    """Фазы, снятые из-за несовместимой пары «порядок/беспорядок»."""

    try:
        from thermogar_database_repair import broken_order_disorder_phases
    except Exception:
        return {}
    try:
        return broken_order_disorder_phases(db, components)
    except Exception:
        return {}


def drop_unbuildable_order_disorder(
    db: Database,
    components: list[str],
    phases: list[str],
) -> tuple[list[str], dict[str, Any]]:
    """Убрать нестроящиеся упорядоченные фазы, вернув их с причиной."""

    broken = unbuildable_order_disorder(db, components)
    if not broken:
        return list(phases), {}
    kept = [name for name in phases if name not in broken]
    removed = {name: broken[name] for name in phases if name in broken}
    return kept, removed


def unbuildable_phase_note(removed: dict[str, Any]) -> str:
    """Сообщение пользователю о снятых парах «порядок/беспорядок».

    Текст живёт в ``thermogar_verified_physical``, потому что тот же самый
    нужен разделу плотности, который до основного расчёта не доходит. Две
    копии одной формулировки разъехались бы на первой же правке.
    """

    return verified_physical.excluded_phases_note(removed)


def phase_model_note(
    db: Database,
    phase_name: str,
) -> str:
    """Коротко пояснить связанную ordered/disordered-модель."""
    phase = db.phases.get(phase_name)
    if phase is None:
        return ""

    hints = phase.model_hints
    ordered = hints.get("ordered_phase")
    disordered = hints.get("disordered_phase")

    if ordered == phase_name and disordered:
        return (
            f"Связанная модель с {disordered}; это имя может представлять "
            "и упорядоченное, и разупорядоченное состояние."
        )
    if disordered == phase_name and ordered:
        return f"Разупорядоченная часть связанной модели {ordered}."
    return ""


def phase_selection_editor(
    db: Database,
    database_key: str,
    candidate_phases: list[str],
    key_prefix: str,
    default_phase_mode: str = PHASE_MODE_ALL,
    folded: FoldedFields | None = None,
) -> tuple[list[str], str, str]:
    """Показать управление фазами и вернуть выбранные фазы.

    Возвращает ``(фазы, способ выбора, строка «Набор фаз: …»)``. Переключатель
    набора («быстрый набор» / «все фазы базы») сужает список кандидатов до
    ручного выбора, поэтому ручной выбор работает поверх любого набора.
    Выбор запоминается на сессию и на базу ключом виджета.
    """
    rejected_candidates = rejected_release_phases(
        database_key,
        candidate_phases,
    )
    if rejected_candidates:
        st.error(excluded_phase_message(rejected_candidates))
    unbuildable_note = st.session_state.get(UNBUILDABLE_PHASES_STATE_KEY, "")
    if unbuildable_note:
        st.info(unbuildable_note)
    candidate_phases = effective_release_phases(
        database_key,
        candidate_phases,
    )
    with folded_block(BLOCK_PHASES):
        all_phases = list(candidate_phases)
        fast_phases = effective_release_phases(
            database_key,
            preset_phases(
                available_phase_presets(),
                database_key,
                all_phases,
            ),
        )
        phase_mode = PHASE_MODE_ALL
        if len(fast_phases) < len(all_phases):
            phase_set_counts = {
                PHASE_MODE_FAST: len(fast_phases),
                PHASE_MODE_ALL: len(all_phases),
            }
            # Значения переключателя — "fast"/"all", а не подписи: подписи
            # содержат число фаз и меняются вместе с составом, а состояние
            # виджета должно пережить смену состава.
            phase_mode = st.radio(
                "Набор фаз",
                [PHASE_MODE_FAST, PHASE_MODE_ALL],
                index=0 if default_phase_mode == PHASE_MODE_FAST else 1,
                format_func=lambda value: (
                    f"{PHASE_MODE_LABELS[value]} "
                    f"({phase_set_counts[value]} фаз)"
                ),
                horizontal=True,
                key=f"{key_prefix}_phase_set_{database_key}",
            )
            if folded is not None:
                folded.note(
                    "Набор фаз",
                    phase_mode,
                    PHASE_MODE_FAST
                    if default_phase_mode == PHASE_MODE_FAST
                    else PHASE_MODE_ALL,
                )
            st.caption(PHASE_MODE_HELP)
            if phase_mode == PHASE_MODE_FAST:
                dropped = sorted(set(all_phases) - set(fast_phases))
                if dropped:
                    # Молчаливая потеря фазы недопустима: в волне 9 быстрый
                    # набор терял NI2CR с мольной долей 0,80 при 400 °C, и
                    # пользователь об этом никак не узнавал. Полный расчёт ради
                    # проверки здесь не делается — он стоит столько же, сколько
                    # сам быстрый режим, — но список выпавших фаз показывается
                    # всегда.
                    st.warning(dropped_phases_warning(dropped))
                    if len(dropped) > DROPPED_PHASES_SHOWN:
                        with st.expander(
                            dropped_phases_expander_label(len(dropped))
                        ):
                            st.markdown(dropped_phases_full_list(dropped))
        candidate_phases = (
            fast_phases if phase_mode == PHASE_MODE_FAST else all_phases
        )
        phase_set_note = phase_mode_note(
            phase_mode,
            len(fast_phases),
            len(all_phases),
        )

        mode = st.radio(
            "Какие фазы учитывать",
            [
                "Автоматически — все совместимые фазы",
                "Вручную — поставить или снять галочки",
            ],
            horizontal=True,
            key=f"{key_prefix}_phase_mode_{database_key}",
        )
        if folded is not None:
            folded.note(
                "Какие фазы учитывать",
                mode,
                "Автоматически — все совместимые фазы",
            )

        if mode.startswith("Автоматически"):
            st.caption(
                f"В расчёте будет учтено фаз: {len(candidate_phases)}. "
                "Это обычное равновесие для выбранной базы и состава."
            )
            return list(candidate_phases), "Автоматически", phase_set_note

        st.warning(
            "Если отключить устойчивую фазу, получится метастабильное "
            "равновесие только среди оставленных фаз."
        )

        rows = []
        for phase_name in candidate_phases:
            rows.append(
                {
                    "Использовать": True,
                    "Фаза": phase_name,
                    "Что это": PHASE_EXPLANATIONS.get(
                        database_key,
                        {},
                    ).get(phase_name, ""),
                    "Примечание модели": phase_model_note(
                        db,
                        phase_name,
                    ),
                }
            )

        phase_table = pd.DataFrame(rows)
        signature = hashlib.sha1(
            "|".join(candidate_phases).encode("utf-8")
        ).hexdigest()[:10]

        edited = st.data_editor(
            phase_table,
            hide_index=True,
            width="stretch",
            disabled=[
                "Фаза",
                "Что это",
                "Примечание модели",
            ],
            column_config={
                "Использовать": st.column_config.CheckboxColumn(
                    "Использовать",
                    help=(
                        "Снимите галку, чтобы исключить фазу "
                        "из равновесного расчёта."
                    ),
                ),
                "Фаза": st.column_config.TextColumn(
                    "Фаза",
                    width="medium",
                ),
                "Что это": st.column_config.TextColumn(
                    "Что это",
                    width="large",
                ),
                "Примечание модели": st.column_config.TextColumn(
                    "Примечание модели",
                    width="large",
                ),
            },
            key=(
                f"{key_prefix}_phase_editor_"
                f"{database_key}_{signature}"
            ),
            placeholder=EMPTY_CELL_TEXT,
        )

        selected = edited.loc[
            edited["Использовать"].astype(bool),
            "Фаза",
        ].tolist()

        rejected_selected = rejected_release_phases(database_key, selected)
        if rejected_selected:
            st.error(excluded_phase_message(rejected_selected))
            selected = effective_release_phases(database_key, selected)

        st.caption(
            f"Выбрано фаз: {len(selected)} из {len(candidate_phases)}."
        )

        if not selected:
            st.error("Нужно оставить хотя бы одну фазу.")

        return selected, "Вручную", phase_set_note


def render_phase_set_note(settings: Any) -> None:
    """Показать строку «Набор фаз: …» рядом с уже посчитанным результатом.

    Строка читается из таблицы параметров результата, а не из текущего
    состояния переключателя: пользователь должен видеть набор, на котором
    результат действительно посчитан.
    """
    if not isinstance(settings, pd.DataFrame) or "Параметр" not in settings:
        return
    values = settings.loc[settings["Параметр"] == "Набор фаз", "Значение"]
    note = str(values.iloc[0]) if len(values) else ""
    if note:
        st.caption(note)


def release_exclusion_note(database_key: str) -> str:
    """Текст об исключении фаз релизной политикой для результата расчёта.

    Исключение делает не патч базы, а решение о составе поставки
    (``FE_EXCLUDED_PHASES`` в ``thermogar_release_policy``). Пользователю
    нужны три вещи: какая фаза снята, почему и для каких сплавов это может
    оказаться важно, — иначе результат по дуплексной стали выглядит полным,
    хотя фазы, введённой автором базы именно под такие марки, в нём нет.
    """
    if database_key != "fe" or not FE_EXCLUDED_PHASES:
        return ""
    names = ", ".join(sorted(FE_EXCLUDED_PHASES))
    head = (
        f"Из расчёта исключена фаза {names}"
        if len(FE_EXCLUDED_PHASES) == 1
        else f"Из расчёта исключены фазы {names}"
    )
    return (
        f"{head} (решение о составе поставки). "
        "Автор базы вводил фазы Лавеса под дуплексные нержавеющие и "
        "корпусные стали — для таких марок результат может быть неполным."
    )


def database_key_from_settings(settings: Any) -> str:
    """Ключ базы по строке «База» таблицы параметров результата.

    Ключ берётся из самого результата, а не из текущего состояния
    интерфейса: пользователь мог переключить базу после расчёта.
    """
    if not isinstance(settings, pd.DataFrame) or "Параметр" not in settings:
        return ""
    values = settings.loc[settings["Параметр"] == "База", "Значение"]
    if not len(values):
        return ""
    label = str(values.iloc[0]).strip()
    for key, known in RELEASE_DATABASE_LABELS.items():
        if label == known:
            return key
    return ""


def render_release_exclusion_note(settings: Any) -> None:
    """Показать исключение по релизной политике рядом с результатом.

    Волна 10 завела показ фаз, снятых по техническим причинам; здесь то же
    делается для фаз, снятых решением о поставке. Сообщение идёт в результат,
    а не только в подпись сайдбара, и не зависит от режима набора фаз.
    """
    note = release_exclusion_note(database_key_from_settings(settings))
    if note:
        st.warning(note)


def render_engine_note(settings: Any) -> None:
    """Показать строку «Параллельный расчёт: …» рядом с готовым результатом."""
    if not isinstance(settings, pd.DataFrame) or "Параметр" not in settings:
        return
    values = settings.loc[
        settings["Параметр"] == "Параллельный расчёт", "Значение"
    ]
    note = str(values.iloc[0]) if len(values) else ""
    if note:
        st.caption(note)


def requested_phase_tuple(
    selection_mode: str,
    phase_mode_line: str,
    selected_phases: list[str] | None,
) -> tuple[str, ...]:
    """Фазы, которые попадают в квитанцию запроса.

    Пустой кортеж означает «все совместимые фазы базы». Быстрый набор и
    ручной выбор — это подмножество, и оно должно быть видно в квитанции,
    иначе квитанция описывает не тот расчёт, который был выполнен.
    """
    fast_used = phase_mode_line.startswith("Набор фаз: быстрый")
    if selection_mode == "Вручную" or fast_used:
        return tuple(sorted(selected_phases or ()))
    return ()


def phase_candidates_for_standard_composition(
    db: Database,
    database_key: str,
    composition_text: str,
    units: str,
    balance: str,
    steel_mode: str,
) -> list[str]:
    """Предварительно определить список фаз для обычного состава."""
    available = sorted(
        element for element in db.elements if element != "VA"
    )
    entered = parse_composition(composition_text)
    components, _conditions, _overall_x, _overall_w = build_input(
        db,
        available,
        entered,
        units,
        balance,
    )
    return compatible_phases_for_components(
        db,
        database_key,
        components,
        steel_mode,
    )


def prepare_calculation(
    db: Database,
    database_key: str,
    entered: dict[str, float],
    units: str,
    balance: str,
    steel_mode: str,
    selected_phases: list[str] | None = None,
) -> tuple[
    list[str],
    dict[Any, float],
    dict[str, float],
    dict[str, float],
    list[str],
]:
    available = sorted(element for element in db.elements if element != "VA")
    components, conditions, overall_x, overall_w = build_input(
        db,
        available,
        entered,
        units,
        balance,
    )
    phases = compatible_phases_for_components(
        db,
        database_key,
        components,
        steel_mode,
    )

    if selected_phases is not None:
        rejected = rejected_release_phases(database_key, selected_phases)
        if rejected:
            raise UserRuntimeError(excluded_phase_message(rejected))
        selected_set = set(selected_phases)
        phases = [
            phase
            for phase in phases
            if phase in selected_set
        ]

    if not phases:
        raise UserRuntimeError(
            "Для выбранного состава и набора галочек "
            "не осталось допустимых фаз."
        )
    return components, conditions, overall_x, overall_w, phases


def summarize_equilibrium(
    db: Database,
    eq: Any,
    elements: list[str],
    database_key: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    phase_names = np.asarray(eq.Phase.values, dtype=str).ravel()
    phase_fractions = np.asarray(eq.NP.values, dtype=float).ravel()
    phase_x = {
        element: np.asarray(
            eq.X.sel(component=element).values,
            dtype=float,
        ).ravel()
        for element in elements
    }

    aggregated: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"fraction": 0.0, "weighted_x": defaultdict(float)}
    )

    for index, (phase_name, fraction) in enumerate(
        zip(phase_names, phase_fractions)
    ):
        if (
            phase_name == ""
            or not np.isfinite(fraction)
            or fraction <= 1e-9
        ):
            continue

        phase_name = str(phase_name)
        fraction = float(fraction)
        aggregated[phase_name]["fraction"] += fraction

        for element in elements:
            value = phase_x[element][index]
            if np.isfinite(value):
                aggregated[phase_name]["weighted_x"][element] += (
                    fraction * float(value)
                )

    summary_rows: list[dict[str, Any]] = []
    at_rows: list[dict[str, Any]] = []
    wt_rows: list[dict[str, Any]] = []

    for phase_name, values in aggregated.items():
        fraction = float(values["fraction"])
        composition_x = normalize(
            {
                element: values["weighted_x"][element] / fraction
                for element in elements
            }
        )
        composition_w = mole_to_mass(db, composition_x)
        explanation = PHASE_EXPLANATIONS.get(database_key, {}).get(
            phase_name,
            "",
        )

        summary_rows.append(
            {
                "Фаза": phase_name,
                "Что это": explanation,
                "Мольная доля фазы, %": 100.0 * fraction,
            }
        )

        at_row: dict[str, Any] = {
            "Фаза": phase_name,
            "Что это": explanation,
        }
        wt_row: dict[str, Any] = {
            "Фаза": phase_name,
            "Что это": explanation,
        }

        for element in elements:
            at_row[f"{element}, ат.%"] = (
                100.0 * composition_x.get(element, 0.0)
            )
            wt_row[f"{element}, мас.%"] = (
                100.0 * composition_w.get(element, 0.0)
            )

        at_rows.append(at_row)
        wt_rows.append(wt_row)

    summary = pd.DataFrame(summary_rows)
    phase_at = pd.DataFrame(at_rows)
    phase_wt = pd.DataFrame(wt_rows)

    if not summary.empty:
        summary = summary.sort_values(
            "Мольная доля фазы, %",
            ascending=False,
        ).reset_index(drop=True)
        order = summary["Фаза"].tolist()
        phase_at = phase_at.set_index("Фаза").loc[order].reset_index()
        phase_wt = phase_wt.set_index("Фаза").loc[order].reset_index()

    return summary, phase_at, phase_wt


def aggregate_phase_fractions(eq: Any) -> dict[str, float]:
    names = np.asarray(eq.Phase.values, dtype=str).ravel()
    fractions = np.asarray(eq.NP.values, dtype=float).ravel()
    result: dict[str, float] = defaultdict(float)

    for name, fraction in zip(names, fractions):
        if (
            name != ""
            and np.isfinite(fraction)
            and fraction > 1e-10
        ):
            result[str(name)] += float(fraction)

    return dict(result)


def mole_fraction_map(conditions: Mapping[Any, float]) -> dict[str, float]:
    """Условия состава pycalphad в простой словарь ``{элемент: мольная доля}``.

    Описание точки уходит в воркер через ``pickle``, поэтому переменные
    pycalphad в него не кладутся — движок соберёт их заново
    (``thermogar_parallel.default_conditions_builder``). Порядок ключей
    сохраняется: он задаёт порядок условий в ``equilibrium``, а от него
    зависят последние биты результата.
    """
    mapping: dict[str, float] = {}
    for variable, value in conditions.items():
        label = str(variable)
        if not label.startswith("X_"):
            # Массовые доли сюда попасть не должны: их переводит build_input
            # и scan_axis_conditions. Молча принять W_* значило бы посчитать
            # массовую долю как мольную.
            raise UserValueError(
                f"Условие состава {label!r} не является мольной долей."
            )
        species = getattr(variable, "species", None)
        mapping[str(species) if species is not None else label[2:]] = float(value)
    return mapping


def run_equilibrium_points(
    components: list[str],
    phases: list[str],
    points: list[dict[str, Any]],
    *,
    sidebar: SidebarContext,
    pdens: int = 500,
    reuse_models: bool = False,
    capture: tuple[str, ...] = ("X",),
    models: Any | None = None,
    progress_text: str = "Рассчитано",
    progress: Any | None = None,
    database: Any | None = None,
    database_file: Any | None = None,
    sha256: str | None = None,
    database_id: str | None = None,
) -> parallel_ui.PointRun:
    """Посчитать независимые точки равновесия движком волны 5B.

    Пул поднимается только когда окупается (порог — в
    ``thermogar_parallel_ui``); ниже порога и при выключенном переключателе
    точки считаются в текущем процессе тем же кодом, поэтому числа режимов
    совпадают побайтово. Прогресс показывается как «точка i из N».
    """
    own_bar = None
    if progress is None:
        own_bar = st.progress(0.0, text=f"{progress_text}: 0 из {len(points)}")

        def report(completed: int, total: int) -> None:
            own_bar.progress(
                completed / total,
                text=f"{progress_text}: точка {completed} из {total}",
            )

        progress = report
    try:
        return parallel_ui.run_points(
            database=sidebar.db if database is None else database,
            database_path=sidebar.database_path if database_file is None else database_file,
            sha256=(
                str(sidebar.current_context["database_sha256"])
                if sha256 is None
                else str(sha256)
            ),
            database_key=sidebar.database_key if database_id is None else database_id,
            points=points,
            components=components,
            phases=phases,
            pdens=pdens,
            reuse_models=reuse_models,
            capture=capture,
            models=models,
            progress=progress,
        )
    finally:
        if own_bar is not None:
            own_bar.empty()


def require_successful_points(run: parallel_ui.PointRun) -> list[Any]:
    """Переходники всех точек; первая упавшая точка поднимает свою ошибку."""
    return [parallel_ui.snapshot_of(result) for result in run.results]


def direct_equilibrium_scan(
    db: Database,
    components: list[str],
    phases: list[str],
    pressure_pa: float,
    axis_label: str,
    points: list[tuple[float, dict[Any, float], float]],
    *,
    sidebar: SidebarContext,
    progress_text: str = "Рассчитано",
) -> tuple[pd.DataFrame, parallel_ui.PointRun]:
    """Скан равновесия по сетке точек из полей интерфейса.

    Численный бэкенд тот же, что и в остальных маршрутах приложения —
    ``pycalphad.equilibrium`` с ``pdens=500``, но точки независимы и идут
    через движок волны 5B. Свёртка долей остаётся за
    ``aggregate_phase_fractions``: движок отдаёт сырые массивы равновесия,
    переходник подставляет их вместо объекта ``eq``, поэтому таблица
    совпадает с последовательным счётом побайтово. Список фаз приходит из
    ``prepare_calculation``, то есть для Fe уже без C15_LAVES.
    """
    axis_values = [float(axis_value) for axis_value, _conditions, _t in points]
    engine_points = [
        {
            "N": 1.0,
            "P": float(pressure_pa),
            "T": float(temperature_k),
            "X": mole_fraction_map(composition_conditions),
        }
        for _axis_value, composition_conditions, temperature_k in points
    ]
    run = run_equilibrium_points(
        components,
        phases,
        engine_points,
        pdens=500,
        progress_text=progress_text,
        database=db,
        sidebar=sidebar,
    )
    rows: list[dict[str, float]] = []
    for axis_value, snapshot in zip(axis_values, require_successful_points(run)):
        row: dict[str, float] = {axis_label: axis_value}
        row.update(
            {
                phase: 100.0 * fraction
                for phase, fraction in aggregate_phase_fractions(snapshot).items()
            }
        )
        rows.append(row)
    return pd.DataFrame(rows).fillna(0.0), run


def current_theme_type() -> str:
    """Вернуть тип активной темы Streamlit без падения на старой сборке."""
    try:
        return normalize_theme(st.context.theme.type)
    except Exception:
        return "light"


def chart_figure(item: Any) -> plt.Figure:
    """Фигура для показа и PNG в теме текущего прогона (решение 7Б)."""
    return resolve_figure(item, current_theme_type())


def build_themed_figure(
    builder: Callable[..., Any],
    *args: Any,
    **kwargs: Any,
) -> ThemedFigure:
    """Сохранить построитель графика с данными и сразу построить фигуру.

    Первая фигура строится в теме расчёта, чтобы ошибка построения попала в
    обработку ошибок расчёта; фигуры других тем строятся из тех же данных
    при смене темы, без повторного расчёта.
    """
    themed = ThemedFigure(builder, *args, **kwargs)
    themed.figure(current_theme_type())
    return themed


def style_chart_axes(
    figure: plt.Figure,
    axes: plt.Axes,
    title: str,
    x_label: str,
    y_label: str,
    theme_type: str | None = None,
) -> None:
    """Применить единый визуальный стандарт ThermoGar к matplotlib."""
    roles = chart_roles(theme_type or current_theme_type())
    figure.set_facecolor(roles["background"])
    axes.set_facecolor(roles["background"])
    axes.set_title(element_case_text(title), fontsize=13, color=roles["text"])
    axes.set_xlabel(element_case_text(x_label), fontsize=13, color=roles["axis"])
    axes.set_ylabel(element_case_text(y_label), fontsize=13, color=roles["axis"])
    # Сетка — роль grid, прозрачность 0.25 (решение владельца 24.09.2026).
    axes.grid(True, color=roles["grid"], alpha=0.25)
    axes.tick_params(
        axis="both",
        which="both",
        labelsize=11,
        colors=roles["axis"],
    )
    for spine in axes.spines.values():
        spine.set_color(roles["axis"])


def plot_phase_fraction_scan(
    dataframe: pd.DataFrame,
    x_column: str,
    phases: list[str],
    title: str,
    database_key: str,
    theme_type: str | None = None,
) -> plt.Figure:
    """Построить фазовые доли с закреплённой палитрой и формами линий."""
    theme_type = normalize_theme(theme_type or current_theme_type())
    roles = chart_roles(theme_type)
    styles = phase_styles(phases, theme_type)

    figure, axes = plt.subplots(figsize=(11.5, 6.5), dpi=100)
    end_points: dict[str, tuple[float, float]] = {}

    for phase in phases:
        style = styles[phase]
        explanation = PHASE_EXPLANATIONS.get(database_key, {}).get(
            phase,
            "",
        )
        label = f"{phase} — {explanation}" if explanation else phase
        axes.plot(
            dataframe[x_column],
            dataframe[phase],
            color=style["color"],
            linestyle=style["linestyle"],
            marker=style["marker"],
            linewidth=1.8,
            markersize=4.0,
            label=label,
        )

        valid = dataframe[[x_column, phase]].dropna()
        if not valid.empty:
            last = valid.iloc[-1]
            end_points[phase] = (float(last[x_column]), float(last[phase]))

    style_chart_axes(
        figure,
        axes,
        title,
        x_column,
        "Мольная доля фазы, %",
        theme_type,
    )
    figure.tight_layout()
    annotate_line_ends(
        axes,
        end_points,
        {phase: styles[phase]["color"] for phase in end_points},
    )
    if phases:
        place_legend_below(figure, axes, roles)
    return figure


def figure_to_png(figure: plt.Figure | ThemedFigure) -> bytes:
    figure = chart_figure(figure)
    buffer = BytesIO()
    figure.savefig(buffer, format="png", dpi=200, bbox_inches="tight")
    return buffer.getvalue()
