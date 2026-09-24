"""Воркер пула не пишет журнал ошибок (21-З, ШАГ 3).

Воркер пула (spawn) заново исполняет скрипт приложения как ``__mp_main__``
без сеанса (BL-54). После 21-Ж раздел «Выделения» показывает ошибку состава
через ``render_error`` с записью в ``logs/stage14/errors.jsonl``: воркеры
дописывали в журнал ошибку пустого состава и падали на блокировке журнала.
"""

from __future__ import annotations

import json
import subprocess
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

import thermogar_stage14 as stage14  # noqa: E402
from thermogar_paths import ThermoGarPaths  # noqa: E402
from thermogar_user_errors import UserValueError  # noqa: E402


def make_paths(tmp_path: Path) -> ThermoGarPaths:
    paths = ThermoGarPaths(tmp_path / "profile")
    paths.stage14_errors_path.parent.mkdir(parents=True)
    return paths


def rerun_as_mp_main(monkeypatch) -> None:
    """Скрипт исполняется в воркере: parent_process() ещё None."""
    monkeypatch.setitem(sys.modules, "__mp_main__", types.ModuleType("__mp_main__"))


def after_bootstrap(monkeypatch) -> None:
    """Задание воркера: parent_process() уже задан."""
    monkeypatch.setattr(stage14.multiprocessing, "parent_process", lambda: object())


@pytest.mark.parametrize("worker_state", (rerun_as_mp_main, after_bootstrap))
def test_worker_process_does_not_write_error_log(tmp_path, monkeypatch, worker_state):
    paths = make_paths(tmp_path)
    worker_state(monkeypatch)
    error_id, payload = stage14.log_user_error(
        UserValueError("Укажите хотя бы одну добавку."),
        context="кинетика выделений",
        paths=paths,
    )
    assert error_id and payload["error_id"] == error_id
    assert payload["message"] == "Укажите хотя бы одну добавку."
    assert not paths.stage14_errors_path.exists()
    assert list(paths.stage14_errors_path.parent.iterdir()) == []


def test_main_process_writes_error_log(tmp_path, monkeypatch):
    paths = make_paths(tmp_path)
    # В родителе multiprocessing держит «__mp_main__» псевдонимом «__main__».
    main_alias = types.ModuleType("__main__")
    monkeypatch.setitem(sys.modules, "__mp_main__", main_alias)
    monkeypatch.setattr(stage14.multiprocessing, "parent_process", lambda: None)
    error_id, _payload = stage14.log_user_error(
        UserValueError("Укажите хотя бы одну добавку."),
        context="кинетика выделений",
        paths=paths,
    )
    lines = paths.stage14_errors_path.read_text("utf-8").splitlines()
    assert [json.loads(line)["error_id"] for line in lines] == [error_id]


SPAWN_SCRIPT = '''
import multiprocessing
import sys
from pathlib import Path

sys.path.insert(0, {app!r})
import thermogar_stage14 as stage14
from thermogar_paths import ThermoGarPaths
from thermogar_user_errors import UserValueError

# Как скрипт приложения: код верхнего уровня исполняется и в воркере.
stage14.log_user_error(
    UserValueError("Укажите хотя бы одну добавку."),
    context="кинетика выделений",
    paths=ThermoGarPaths(Path({profile!r})),
)


def task(value):
    return value + 1


if __name__ == "__main__":
    with multiprocessing.get_context("spawn").Pool(2) as pool:
        assert pool.map(task, [1, 2]) == [2, 3]
'''


def test_spawn_worker_rerunning_the_script_leaves_the_log_alone(tmp_path):
    paths = make_paths(tmp_path)
    script = tmp_path / "app_like.py"
    script.write_text(
        SPAWN_SCRIPT.format(app=str(ROOT / "app"), profile=str(tmp_path / "profile")),
        encoding="utf-8",
    )
    completed = subprocess.run(
        [sys.executable, "-B", str(script)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "Traceback" not in completed.stderr, completed.stderr
    lines = paths.stage14_errors_path.read_text("utf-8").splitlines()
    assert len(lines) == 1
