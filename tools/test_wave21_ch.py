#!/usr/bin/env python3
"""21-Ч: BL-74 — ошибка чтения марок в «Марки и составы» перехвачена.

Лёгкий тест: приложение не запускается, AppTest не используется, равновесия
не считаются. ``st.error`` и ``render_error_details`` подменяются.

* Битый ``alloys.json``: список своих марок пустой, ``st.error`` вызван один
  раз со своим сообщением («Файл alloys.json не читается.», без «Техническая
  причина»), ``render_error_details`` получил исключение с причиной
  ``json.JSONDecodeError`` — «Код ошибки» и технический отчёт.
* Повторная загрузка за тот же прогон ошибку не показывает второй раз.
* Исправный файл: прежний список, ``st.error`` не вызывается.
* В ``render_alloy_library`` обе загрузки марок идут через помощник.

Запуск:
    <root>/.venv-windows/Scripts/python.exe -B -m pytest tools/test_wave21_ch.py -v
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

from thermogar_paths import ThermoGarPaths  # noqa: E402
from thermogar_user_errors import UserRuntimeError  # noqa: E402
import thermogar_workspace as workspace  # noqa: E402

WORKSPACE_SOURCE = (ROOT / "app" / "thermogar_workspace.py").read_text(
    encoding="utf-8"
)
HELPER = "load_user_alloys_for_screen"


class _Calls:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.details: list[tuple[Exception, dict[str, Any]]] = []


@pytest.fixture()
def calls(monkeypatch: pytest.MonkeyPatch) -> _Calls:
    recorded = _Calls()
    monkeypatch.setattr(
        workspace.st, "error", lambda text, *args, **kwargs: recorded.errors.append(text)
    )

    def fake_details(error: Exception, **kwargs: Any) -> str:
        recorded.details.append((error, kwargs))
        return "TG-TEST"

    monkeypatch.setattr(workspace, "render_error_details", fake_details, raising=False)
    return recorded


def _paths(tmp_path: Path) -> ThermoGarPaths:
    paths = ThermoGarPaths(tmp_path / "state")
    workspace.workspace_directory(paths)
    return paths


def _helper():
    return getattr(workspace, HELPER)


def test_broken_alloys_json_shows_error_once_with_details(
    tmp_path: Path, calls: _Calls
) -> None:
    paths = _paths(tmp_path)
    paths.alloys_path.write_bytes(b'{"alloys": [')

    alloys, failed = _helper()(paths)

    assert alloys == []
    assert failed is True
    assert len(calls.errors) == 1
    assert calls.errors[0].startswith("Файл alloys.json не читается.")
    assert "Техническая причина" not in calls.errors[0]
    assert len(calls.details) == 1
    error, kwargs = calls.details[0]
    assert isinstance(error, UserRuntimeError)
    assert isinstance(error.__cause__, json.JSONDecodeError)
    assert kwargs["context"] == "Марки и составы"
    assert kwargs["paths"] is paths


def test_second_load_in_same_run_does_not_repeat_error(
    tmp_path: Path, calls: _Calls
) -> None:
    paths = _paths(tmp_path)
    paths.alloys_path.write_bytes(b'{"alloys": [')

    _alloys, failed = _helper()(paths)
    alloys, failed_again = _helper()(paths, show_error=not failed)

    assert alloys == []
    assert failed_again is True
    assert len(calls.errors) == 1
    assert len(calls.details) == 1


def test_valid_alloys_json_returns_list_without_error(
    tmp_path: Path, calls: _Calls
) -> None:
    paths = _paths(tmp_path)
    stored = [{"id": "user-1", "name": "Опытный"}, {"id": "user-2", "name": "Второй"}]
    paths.alloys_path.write_text(
        json.dumps({"schema_version": 1, "alloys": stored + ["не запись"]}),
        encoding="utf-8",
    )

    alloys, failed = _helper()(paths)

    assert alloys == workspace.load_user_alloys(paths) == stored
    assert failed is False
    assert calls.errors == []
    assert calls.details == []


def test_missing_alloys_json_is_empty_without_error(
    tmp_path: Path, calls: _Calls
) -> None:
    alloys, failed = _helper()(_paths(tmp_path))

    assert alloys == []
    assert failed is False
    assert calls.errors == []
    assert calls.details == []


def test_render_alloy_library_loads_alloys_only_through_helper() -> None:
    tree = ast.parse(WORKSPACE_SOURCE)
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "render_alloy_library"
    )
    called = [
        node.func.id
        for node in ast.walk(function)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    assert "load_user_alloys" not in called
    assert called.count(HELPER) == 2
