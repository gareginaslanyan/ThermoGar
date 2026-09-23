"""Версия в файлах поставки и в документах пользователя равна ``APP_VERSION`` (18-Г2).

Повтор 15-Р/15-С и 18-Г: при подъёме версии перечень файлов, где она записана,
вёлся по памяти, и часть заголовков оставалась прежней. Здесь перечень
собирается из дерева:

* файлы нагрузки установщика — те же источники, что в
  ``packaging/stage_payload.ps1`` (75 файлов, их сверял 18-Г с установленной
  копией);
* документы пользователя вне нагрузки: ``docs/FEATURES.md``, ``docs/guide/*.md``
  и HTML руководства текущей версии;
* ``packaging/product-version.json`` и подпись боковой панели приложения.

В каждом файле берётся **первое** упоминание вида «ThermoGar 0.4.x»
(``ThermoGar-0.4.x-…``, ``ThermoGar_Guide_0.4.x``), в JSON — ``display_version``
и ``vi_product_version``. Оно должно равняться ``APP_VERSION``. Файлы без
упоминания проходят; у документов из ``MUST_MENTION`` упоминание обязательно.
Исторические упоминания ниже первого («С версии 0.4.2 …») не проверяются.
HTML руководства прежних версий (``ThermoGar_Guide_0.4.1.html``…) — история
и в перечень не входят.

Запуск:

    python -m pytest tools/test_version_consistency.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "app") not in sys.path:
    sys.path.insert(0, str(ROOT / "app"))

from thermogar_release_policy import APP_VERSION  # noqa: E402

# Источники нагрузки — packaging/stage_payload.ps1.
PAYLOAD_TREES = ("app", "configs", "databases/converted", "databases/physical", "licenses", ".streamlit")
PAYLOAD_FILES = (
    "packaging/launcher.pyw",
    "packaging/stop.pyw",
    "packaging/healthcheck.py",
    "packaging/assets/ThermoGar.ico",
    "README.md",
    "USER_GUIDE_THERMOGAR.md",
    "QUICK_START_THERMOGAR.md",
    "THIRD_PARTY_NOTICES.txt",
    "SOURCES.txt",
    "PHYSICAL_DATA_README.md",
    "USER_DATA_README.txt",
)
GUIDE_HTML = f"docs/guide/ThermoGar_Guide_{APP_VERSION}.html"
MUST_MENTION = (
    "README.md",
    "USER_GUIDE_THERMOGAR.md",
    "QUICK_START_THERMOGAR.md",
    "docs/FEATURES.md",
    "docs/guide/README.md",
    GUIDE_HTML,
    "packaging/product-version.json",
    "app/ThermoGar_app.py",
)
MENTION = re.compile(r"ThermoGar[ _-](?:Guide_)?(\d+\.\d+\.\d+)")
SIDEBAR = re.compile(r'st\.sidebar\.caption\(\s*"ThermoGar (\d+\.\d+\.\d+) ')


def tracked(*paths: str) -> list[str]:
    output = subprocess.run(
        ["git", "ls-files", "--", *paths], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    return [line for line in output.splitlines() if line]


def checked_files() -> list[str]:
    files = tracked(*PAYLOAD_TREES) + list(PAYLOAD_FILES)
    files += ["docs/FEATURES.md", GUIDE_HTML, "packaging/product-version.json"]
    files += tracked("docs/guide/*.md")
    return sorted(set(files))


def first_mention(relative: str) -> str | None:
    text = (ROOT / relative).read_bytes().decode("utf-8", errors="ignore")
    match = MENTION.search(text)
    return match.group(1) if match else None


def test_payload_list_is_complete() -> None:
    payload = tracked(*PAYLOAD_TREES) + list(PAYLOAD_FILES)
    assert len(payload) == 76, len(payload)
    missing = [name for name in checked_files() if not (ROOT / name).is_file()]
    assert not missing, missing


@pytest.mark.parametrize("relative", checked_files())
def test_first_version_mention_is_app_version(relative: str) -> None:
    found = first_mention(relative) if (ROOT / relative).is_file() else None
    if relative in MUST_MENTION and relative != "packaging/product-version.json":
        assert found is not None, f"{relative}: нет упоминания «ThermoGar {APP_VERSION}»"
    if found is not None:
        assert found == APP_VERSION, f"{relative}: первое упоминание {found}, APP_VERSION {APP_VERSION}"


def test_product_version_json() -> None:
    product = json.loads((ROOT / "packaging/product-version.json").read_text("utf-8"))
    assert product["display_version"] == APP_VERSION
    assert product["vi_product_version"] == f"{APP_VERSION}.0"


def test_sidebar_caption() -> None:
    source = (ROOT / "app/ThermoGar_app.py").read_text("utf-8")
    match = SIDEBAR.search(source)
    assert match is not None, "подпись боковой панели с версией не найдена"
    assert match.group(1) == APP_VERSION


def test_guide_builder_names_current_version() -> None:
    source = (ROOT / "tools/make_guide_screens.py").read_text("utf-8")
    assert f'HTML_NAME = "ThermoGar_Guide_{APP_VERSION}.html"' in source
    assert f'HTML_TITLE = "ThermoGar {APP_VERSION} — ' in source
