"""Контекст прогона головного сценария ThermoGar.

BL-57, разрез app/ThermoGar_app.py. Объекты, которые головной сценарий собирает
на каждом прогоне страницы; вкладки и помощники получают их параметром, а не
читают глобальные имена головного сценария:

* SidebarContext (20-Е) — то, что выбрано в боковой панели;
* RunServices (20-З) — службы этого прогона: пути состояния, показ и запись
  ошибок, выгрузка Excel, загрузка баз, ленивая загрузка scheil, привязка базы;
* VerifiedBinding (20-И) — проверенная привязка базы этого прогона; пакетный
  расчёт и проекты перепривязывают её на месте, поэтому объект изменяемый.

Значения — те же объекты, что в головном сценарии, без копий.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from thermogar_paths import ThermoGarPaths


@dataclass(frozen=True)
class SidebarContext:
    database_key: str
    definition: dict[str, Any]
    fe_profile_key: str
    db: Any
    database_path: Path
    available_elements: list[str]
    balance: str
    units: str
    units_label: str
    composition_text: str
    pressure_pa: float
    steel_mode: str
    current_context: dict[str, Any]


@dataclass
class VerifiedBinding:
    bound: Any


@dataclass(frozen=True)
class RunServices:
    paths: ThermoGarPaths
    render_friendly_error: Callable[..., None]
    log_error: Callable[..., tuple[str, dict[str, Any]]]
    dataframe_to_excel: Callable[[dict[str, Any]], bytes]
    load_database: Callable[[str, str], tuple[Any, Path]]
    load_scheil: Callable[[], dict[str, Any]]
    scheil_available: Callable[[], bool]
    scheil_state: dict[str, Any]
    fe_profile_sha256: dict[str, str]
    binding: VerifiedBinding
