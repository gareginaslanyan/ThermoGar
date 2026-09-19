"""Солидус равновесного пути при несошедшемся ``equilibrium_solidification`` (18-В, BL-44).

16-А: на RS320 и AlSi10Mg0.3 ``scheil.equilibrium_solidification`` возвращает
``converged=False`` с долей твёрдого 0 в конце траектории, а приложение брало
температуру последней точки за солидус: у RS320 876,04 K против 838,14 K
половинным делением по доле жидкости на том же наборе фаз и pdens.

Теперь, если путь не сошёлся или доля твёрдого в его конце меньше 0,999,
солидус ищется половинным делением по «доля жидкости ≤ SOLID_PRESENCE_FLOOR»:
вилка — от ликвидуса вниз шагом 10 °C, не ниже нижней границы базы, точность
0,1 °C. Раскрытие вилки и зондирование равновесий — общий код с ликвидусом.
Не нашлось и так — прежнее «Расчёт завершён: нет», но без числа.

Быстрые тесты берут функции приложения из его исходника (без запуска
Streamlit) и подменяют равновесие модельной долей твёрдого. Медленные гоняют
вкладку целиком через AppTest: RS320 (полный набор, pdens 50) — 838,1 ± 0,3 K
с предупреждением; INCONEL 600 — путь сходится, 1698,31 K, без предупреждения.

Запуск:
    <root>/.venv-windows/Scripts/python.exe -m pytest tools/test_equilibrium_solidus_fallback.py -v
"""

from __future__ import annotations

import ast
import math
import sys
import warnings
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import matplotlib

matplotlib.use("Agg")

import numpy as np  # noqa: E402
import pytest  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
APP_PATH = ROOT / "app" / "ThermoGar_app.py"
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

OWNER_WARNING = (
    "Равновесное затвердевание не сошлось; солидус найден половинным "
    "делением по доле жидкости."
)
OWNER_SOLIDUS_STATUS = "Ищем солидус половинным делением…"

APP_NAMES = (
    "SOLID_PRESENCE_FLOOR",
    "LIQUIDUS_TOLERANCE_C",
    "LIQUIDUS_BRACKET_STEP_C",
    "LIQUIDUS_BRACKET_MARGIN_C",
    "EQUILIBRIUM_SOLIDUS_MIN_SOLID_FRACTION",
    "SOLIDUS_FALLBACK_WARNING",
    "SOLIDUS_SEARCH_STATUS_LABEL",
    "SOLIDIFICATION_METHOD_LABELS",
    "interpolate_temperature_at_solid_fraction",
    "equilibrium_solid_fraction_at",
    "_solid_fraction_probe",
    "_step_bracket_edge",
    "equilibrium_liquidus_c",
    "equilibrium_solidus_c",
    "database_lower_temperature_c",
    "_relations",
    "solidification_end_index",
    "equilibrium_solidus_needs_fallback",
    "equilibrium_solidus_override",
    "solidification_summary_row",
)


@pytest.fixture(scope="module")
def app() -> dict[str, Any]:
    """Импорты верхнего уровня приложения и нужные определения — его же текстом."""

    tree = ast.parse(APP_PATH.read_text("utf-8"))
    wanted = set(APP_NAMES)
    header: list[ast.stmt] = []
    definitions: list[ast.stmt] = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            header.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name in wanted:
            definitions.append(node)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(t, ast.Name) and t.id in wanted for t in targets):
                definitions.append(node)
    namespace: dict[str, Any] = {"__file__": str(APP_PATH), "__name__": "thermogar_app_extract"}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        exec(
            compile(ast.Module(body=header + definitions, type_ignores=[]), str(APP_PATH), "exec"),
            namespace,
        )
    missing = wanted - set(namespace)
    assert not missing, sorted(missing)
    return namespace


LIQUIDUS_C = 1000.0
SOLIDUS_C = 900.0


def model_solid(temperature_c: float) -> float:
    """Модельная доля твёрдого: 0 выше 1000 °C, 1 ниже 900 °C, линейно между."""

    t = float(temperature_c)
    if t >= LIQUIDUS_C:
        return 0.0
    if t <= SOLIDUS_C:
        return 1.0
    return (LIQUIDUS_C - t) / (LIQUIDUS_C - SOLIDUS_C)


@pytest.fixture
def modelled(app, monkeypatch) -> dict[str, Any]:
    calls: list[float] = []

    def fake(db, components, phases, conditions, temperature_c, pdens):
        calls.append(float(temperature_c))
        return model_solid(temperature_c)

    monkeypatch.setitem(app, "equilibrium_solid_fraction_at", fake)
    return {"app": app, "calls": calls}


def trajectory(*, converged: bool, end_solid: float) -> SimpleNamespace:
    temperatures_c = np.array([1010.0, 1000.0, 990.0, 980.0])
    solid = np.array([0.0, 0.0, 0.5 * end_solid, end_solid])
    return SimpleNamespace(
        method="equilibrium",
        converged=converged,
        temperatures=temperatures_c + 273.15,
        fraction_solid=solid,
        fraction_liquid=1.0 - solid,
    )


# --------------------------------------------------------------------------- #
# Быстрые: функция солидуса, решение о запасном пути, строка сводки
# --------------------------------------------------------------------------- #


def test_solidus_bisection_finds_boundary_within_tolerance(modelled) -> None:
    app = modelled["app"]
    found = app["equilibrium_solidus_c"](None, [], [], {}, 1000.0, 25.0, 50)
    assert abs(found - SOLIDUS_C) <= app["LIQUIDUS_TOLERANCE_C"]
    # Вилка шла от ликвидуса вниз шагом 10 °C до первой точки без жидкости.
    walked = [t for t in modelled["calls"] if t < LIQUIDUS_C and t % 10.0 == 0.0]
    assert walked[:10] == [990.0 - 10.0 * i for i in range(10)]
    assert min(modelled["calls"]) == 900.0


def test_solidus_not_below_database_floor(modelled) -> None:
    app = modelled["app"]
    with pytest.raises(ValueError):
        app["equilibrium_solidus_c"](None, [], [], {}, 1000.0, 950.0, 50)
    assert min(modelled["calls"]) >= 950.0


def test_liquidus_and_solidus_share_probe_and_bracket(app) -> None:
    """Код раскрытия вилки и зондирования один, не копия."""

    for name in ("equilibrium_liquidus_c", "equilibrium_solidus_c"):
        names = app[name].__code__.co_names
        assert "_solid_fraction_probe" in names, name
        assert "_step_bracket_edge" in names, name
        assert "bisect_transition_temperature" in names, name


def test_liquidus_unchanged_on_model(modelled) -> None:
    app = modelled["app"]
    found = app["equilibrium_liquidus_c"](None, [], [], {}, 990.0, 1010.0, 50)
    assert abs(found - LIQUIDUS_C) <= app["LIQUIDUS_TOLERANCE_C"]


@pytest.mark.parametrize(
    ("converged", "end_solid", "needed"),
    [(True, 1.0, False), (False, 1.0, True), (True, 0.998, True), (True, 0.999, False)],
)
def test_fallback_condition(app, converged, end_solid, needed) -> None:
    result = trajectory(converged=converged, end_solid=end_solid)
    assert app["equilibrium_solidus_needs_fallback"](result) is needed


def test_override_converged_is_none(modelled) -> None:
    app = modelled["app"]
    result = trajectory(converged=True, end_solid=1.0)
    assert app["equilibrium_solidus_override"](result, None, [], [], {}, 1000.0, 50) is None
    assert modelled["calls"] == []


def test_override_not_converged_gives_bisection(modelled, monkeypatch) -> None:
    app = modelled["app"]
    monkeypatch.setitem(app, "database_lower_temperature_c", lambda db: 25.0)
    result = trajectory(converged=False, end_solid=0.0)
    found = app["equilibrium_solidus_override"](result, None, [], [], {}, 1000.0, 50)
    assert abs(found - SOLIDUS_C) <= app["LIQUIDUS_TOLERANCE_C"]


def test_override_failure_is_nan(modelled, monkeypatch) -> None:
    app = modelled["app"]
    monkeypatch.setitem(app, "database_lower_temperature_c", lambda db: 950.0)
    result = trajectory(converged=False, end_solid=0.0)
    assert math.isnan(app["equilibrium_solidus_override"](result, None, [], [], {}, 1000.0, 50))
    # Без ликвидуса вилку строить не от чего.
    assert math.isnan(app["equilibrium_solidus_override"](result, None, [], [], {}, None, 50))


def test_summary_row(app) -> None:
    row = app["solidification_summary_row"]
    result = trajectory(converged=False, end_solid=0.0)
    old = row(result, 1e-4, 1005.0)
    assert old["Температура окончания, °C"] == pytest.approx(980.0)
    assert old["Расчёт завершён"] == "нет"
    assert old == row(result, 1e-4, 1005.0, None)

    found = row(result, 1e-4, 1005.0, 900.0)
    assert found["Температура окончания, °C"] == 900.0
    assert found["Интервал кристаллизации, °C"] == 105.0
    assert math.isnan(found["Остаточный расплав в точке окончания, %"])
    assert found["Расчёт завершён"] == "нет"

    missing = row(result, 1e-4, 1005.0, float("nan"))
    assert math.isnan(missing["Температура окончания, °C"])
    assert math.isnan(missing["Интервал кристаллизации, °C"])
    assert missing["Остаточный расплав в точке окончания, %"] == old["Остаточный расплав в точке окончания, %"]
    assert missing["Расчёт завершён"] == "нет"


def test_owner_warning_text(app) -> None:
    assert app["SOLIDUS_FALLBACK_WARNING"] == OWNER_WARNING
    assert app["EQUILIBRIUM_SOLIDUS_MIN_SOLID_FRACTION"] == 0.999


def test_solidus_search_status_label(app) -> None:
    """18-Г: подпись окна состояния на время поиска солидуса — текст владельца.

    Ставится тем же ``status.update``, что подпись ликвидуса, перед вызовом
    ``equilibrium_solidus_override`` и только при запасном пути.
    """

    assert app["SOLIDUS_SEARCH_STATUS_LABEL"] == OWNER_SOLIDUS_STATUS
    source = APP_PATH.read_text("utf-8")
    liquidus = source.index('label="Ищем ликвидус половинным делением…"')
    solidus = source.index("label=SOLIDUS_SEARCH_STATUS_LABEL")
    override = source.index("equilibrium_solidus_override(\n", solidus)
    assert liquidus < solidus < override
    assert "equilibrium_solidus_needs_fallback(" in source[liquidus:solidus]
    assert "status.update(" in source[solidus - 120 : solidus]


@pytest.mark.parametrize(
    ("relative", "lower_k"),
    [
        ("databases/converted/mc_ni_v2036.garcalc.tdb", 298.15),
        ("databases/converted/al/mc_al_v2037.thermogar.tdb", 298.15),
        ("databases/converted/fe/mc_fe_v2062.thermogar.tdb", 273.0),
    ],
)
def test_database_lower_temperature(app, relative, lower_k) -> None:
    from pycalphad import Database

    path = ROOT / relative
    if not path.is_file():
        pytest.skip(f"Нет базы {path}")
    assert app["database_lower_temperature_c"](Database(str(path))) == pytest.approx(
        lower_k - 273.15, abs=1e-9
    )


# --------------------------------------------------------------------------- #
# Медленные: вкладка целиком
# --------------------------------------------------------------------------- #

# tasks/lilith_16A/marki_16A.csv, столбцы w_*; основа — AL и NI.
RS320 = (
    "FE=0.2503755633450175, MG=0.500751126690035, "
    "MN=0.1502253380070105, SI=8.01201802704056"
)
INCONEL_600 = "CR=15.0, FE=8.0"


def run_tab(database_key: str, composition: str, balance: str, tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("THERMOGAR_STATE_ROOT", str(tmp_path / "state"))
    at = AppTest.from_file(str(APP_PATH), default_timeout=3600)
    for name, value in {
        "thermogar_database_key": database_key,
        f"thermogar_composition_{database_key}": composition,
        f"thermogar_units_{database_key}": "массовые %",
        f"thermogar_balance_{database_key}": balance,
        f"solidification_pdens_{database_key}": 50,
        f"solidification_phase_set_{database_key}": "all",
        f"solidification_method_{database_key}": "Только равновесное затвердевание",
    }.items():
        at.session_state[name] = value
    at.run()
    at.button(key="solidification_calculate").click().run()
    assert not at.exception, [str(e.value) for e in at.exception]
    state = at.session_state["solidification_result"]
    settings = dict(state["settings"].itertuples(index=False))
    row = state["summary"].iloc[0]
    return at, state, settings, row


@pytest.mark.slow
def test_rs320_full_set_bisection_solidus(tmp_path, monkeypatch) -> None:
    at, state, settings, row = run_tab("al", RS320, "AL", tmp_path, monkeypatch)
    assert state["results"]["equilibrium"].converged is False
    assert len(settings["Выбранные фазы"].split(", ")) == 95  # полный набор 16-А
    solidus_k = float(row["Температура окончания, °C"]) + 273.15
    assert abs(solidus_k - 838.1) <= 0.3, solidus_k
    assert row["Расчёт завершён"] == "нет"
    assert settings["Критерий солидуса"] == "бисекция"
    assert OWNER_WARNING in [w.value for w in at.warning]


@pytest.mark.slow
def test_inconel600_scheil_solidus_unchanged(tmp_path, monkeypatch) -> None:
    at, state, settings, row = run_tab("ni", INCONEL_600, "NI", tmp_path, monkeypatch)
    assert state["results"]["equilibrium"].converged is True
    solidus_k = float(row["Температура окончания, °C"]) + 273.15
    assert round(solidus_k, 2) == 1698.31, solidus_k
    assert row["Расчёт завершён"] == "да"
    assert settings["Критерий солидуса"] == "scheil"
    assert OWNER_WARNING not in [w.value for w in at.warning]
