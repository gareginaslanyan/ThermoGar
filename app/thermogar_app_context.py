"""Контекст боковой панели ThermoGar.

BL-57, разрез app/ThermoGar_app.py, шаг «контекст боковой панели» (20-Е). То, что
выбрано в боковой панели, собирается в один неизменяемый объект; вкладки и
помощники получают его параметром, а не читают глобальные имена головного
сценария. Значения — те же объекты, что в боковой панели, без копий.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


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
