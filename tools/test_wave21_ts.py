#!/usr/bin/env python3
"""21-Ц: BL-73–BL-76 — мелкие недочёты экрана и выгрузок, найденные 21-Ф.

Лёгкий тест: приложение не запускается, AppTest не используется, равновесия
не считаются.

* BL-73: во встроенном кратком руководстве (``USER_GUIDE_MD``) нет
  «physical_data.pdb» и нет символов элементов заглавными (кроме имени
  патча «TG-FE-2062-C15-001»); примеры составов — символами, как на экране.
* BL-74: ``read_json`` на битом JSON — ``UserRuntimeError``, причина —
  ``json.JSONDecodeError``; «Техническая причина» в тексте — см. отчёт 21-Ц.
* BL-75: лист выгрузки покрытия физической базы — «Покрытие физической базы».
* BL-76: проект другой версии — одна утверждённая фраза на экран,
  расхождение — в цепочке исключения.

Запуск:
    <root>/.venv-windows/Scripts/python.exe -B -m pytest tools/test_wave21_ts.py -v
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

from thermogar_paths import ThermoGarPaths  # noqa: E402
from thermogar_release_policy import (  # noqa: E402
    APP_STAGE,
    APP_VERSION,
    PRODUCTION_USE,
    RELEASE_CLASS,
    SCIENTIFIC_MATERIAL_STATUS,
    SOFTWARE_RELEASE_STATUS,
)
from thermogar_user_errors import UserRuntimeError, UserValueError  # noqa: E402
import thermogar_workspace as workspace  # noqa: E402

APP = ROOT / "app"
APP_SOURCE = (APP / "ThermoGar_app.py").read_text(encoding="utf-8")
PATCH_NAME = "TG-FE-2062-C15-001"
PROJECT_OTHER_VERSION = "Проект сохранён другой версией ThermoGar и не открывается."

ELEMENTS = (
    "H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co "
    "Ni Cu Zn Ga Ge As Se Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb "
    "Te I Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re Os "
    "Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm "
    "Md No Lr"
).split()
# Односимвольные символы (C, N, …) заглавными и пишутся; ищутся двухбуквенные.
UPPER_SYMBOL = re.compile(
    r"\b(" + "|".join(item.upper() for item in ELEMENTS if len(item) == 2) + r")\b"
)


def _app_tree() -> ast.Module:
    return ast.parse(APP_SOURCE)


def _user_guide_md() -> str:
    for node in _app_tree().body:
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "USER_GUIDE_MD"
                for target in node.targets
            )
            and isinstance(node.value, ast.Constant)
        ):
            return node.value.value
    raise AssertionError("USER_GUIDE_MD не найден")


# ---------------------------------------------------------------------------
# BL-73: краткое руководство
# ---------------------------------------------------------------------------


def test_bl73_guide_has_no_physical_data_pdb() -> None:
    assert "physical_data.pdb" not in _user_guide_md()


def test_bl73_guide_has_no_upper_case_element_symbols() -> None:
    guide = _user_guide_md().replace(PATCH_NAME, "")
    found = [
        (guide[: match.start()].count("\n") + 1, match.group())
        for match in UPPER_SYMBOL.finditer(guide)
    ]
    assert found == []


def test_bl73_guide_examples_use_screen_symbols() -> None:
    guide = _user_guide_md()
    for fragment in (
        "`Al=15, Cr=10`",
        "`Cu=4, Mg=1`",
        "`C=0.20, Cr=11.5, Ni=0.7`",
    ):
        assert fragment in guide
    assert PATCH_NAME in guide


# ---------------------------------------------------------------------------
# BL-74: read_json на битом JSON
# ---------------------------------------------------------------------------


def _broken_json_error(tmp_path: Path) -> UserRuntimeError:
    paths = ThermoGarPaths(tmp_path / "state")
    workspace.workspace_directory(paths)
    source = paths.alloys_path
    source.write_bytes(b'{"alloys": [')
    with pytest.raises(UserRuntimeError) as caught:
        workspace.read_json(paths, source, {"alloys": []})
    return caught.value


def test_bl74_broken_json_keeps_cause(tmp_path: Path) -> None:
    error = _broken_json_error(tmp_path)
    assert isinstance(error.__cause__, json.JSONDecodeError)
    assert str(error).startswith("Файл alloys.json не читается.")


@pytest.mark.xfail(
    strict=True,
    reason=(
        "BL-74 не выполнен: ошибка read_json в «Марки и составы» не "
        "перехвачена, «Кода ошибки» и технического отчёта там нет "
        "(отчёт 21-Ц, ШАГ 2)"
    ),
)
def test_bl74_broken_json_message_has_no_technical_reason(tmp_path: Path) -> None:
    error = _broken_json_error(tmp_path)
    assert "Техническая причина" not in str(error)


# ---------------------------------------------------------------------------
# BL-75: лист выгрузки покрытия физической базы
# ---------------------------------------------------------------------------


def test_bl75_physical_coverage_sheet_name() -> None:
    calls = [
        node
        for node in ast.walk(_app_tree())
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_b4b_render_result_downloads"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "physical_coverage"
    ]
    assert len(calls) == 1
    sheets = calls[0].args[1]
    assert isinstance(sheets, ast.Dict)
    keys = [key.value for key in sheets.keys if isinstance(key, ast.Constant)]
    assert keys == ["Покрытие физической базы"]
    assert len(keys[0]) <= 31
    stems = [
        keyword.value.value
        for keyword in calls[0].keywords
        if keyword.arg == "file_stem"
    ]
    assert stems == ["ThermoGar_pdb_coverage"]


def test_bl75_no_pdb_sheet_name_in_app() -> None:
    for path in sorted(APP.glob("*.py")):
        assert "Покрытие PDB" not in path.read_text(encoding="utf-8"), path.name


# ---------------------------------------------------------------------------
# BL-76: проект другой версии
# ---------------------------------------------------------------------------


def _project(**changes: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": workspace.STORAGE_SCHEMA_VERSION,
        "kind": "thermogar_project_payload",
        "name": "Проект 21-Ц",
        "description": "",
        "created_at": "2026-09-26T00:00:00+00:00",
        "updated_at": "2026-09-26T00:00:00+00:00",
        "app_stage": APP_STAGE,
        "app_version": APP_VERSION,
        "release_class": RELEASE_CLASS,
        "software_release_status": SOFTWARE_RELEASE_STATUS,
        "scientific_material_status": SCIENTIFIC_MATERIAL_STATUS,
        "production_use": PRODUCTION_USE,
        "context": {
            "database_key": "ni",
            "balance": "NI",
            "units": "at",
            "composition": "AL=15",
            "pressure_pa": 101325.0,
            "steel_mode": "metastable",
        },
        "widget_state": {},
    }
    payload.update(changes)
    return payload


def test_bl76_current_version_project_passes() -> None:
    clean = workspace.validate_project_payload(_project())
    assert clean["app_version"] == APP_VERSION


def test_bl76_other_version_project_one_phrase_and_cause() -> None:
    other = "0.4.4" if APP_VERSION != "0.4.4" else "0.0.0"
    with pytest.raises(UserValueError) as caught:
        workspace.validate_project_payload(_project(app_version=other))
    assert str(caught.value) == PROJECT_OTHER_VERSION
    cause = caught.value.__cause__
    assert cause is not None
    assert "app_version" in str(cause)
    assert repr(other) in str(cause)
    assert repr(APP_VERSION) in str(cause)
