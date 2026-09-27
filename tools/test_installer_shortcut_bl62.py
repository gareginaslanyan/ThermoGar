"""Ярлык ThermoGar на рабочем столе (BL-62, решение владельца 26.09.2026, «Б»; 21-Э).

Установщик ставит ярлык и в меню «Пуск», и на общий рабочий стол; при удалении
программы убираются оба. Проверка — разбором текста ``packaging/ThermoGar.nsi``,
без сборки установщика:

* ``DESKTOP_LNK`` определён на ``$DESKTOP``;
* в разделе установки ``CreateShortcut "${DESKTOP_LNK}"`` идёт с теми же
  аргументами (цель, аргумент, значок, режим окна, описание), что у
  ``"${SHORTCUT_LNK}"``;
* в разделе «Uninstall» есть ``Delete "${DESKTOP_LNK}"``;
* в обоих разделах ``SetShellVarContext all`` стоит раньше работы с ярлыками:
  тогда ``$DESKTOP`` и ``$SMPROGRAMS`` — общие для всех пользователей.

Запуск:

    python -m pytest tools/test_installer_shortcut_bl62.py
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
NSI = ROOT / "packaging" / "ThermoGar.nsi"


def statements(block: str) -> list[str]:
    """Строки NSIS без комментариев, с продолжениями ``\\`` склеенными в одну."""
    result: list[str] = []
    pending = ""
    for raw in block.splitlines():
        line = raw.strip()
        if not pending and (not line or line.startswith(";") or line.startswith("#")):
            continue
        if line.endswith("\\"):
            pending += line[:-1].strip() + " "
            continue
        result.append(pending + line)
        pending = ""
    if pending:
        result.append(pending.strip())
    return result


def section(name: str) -> list[str]:
    text = NSI.read_text(encoding="utf-8")
    match = re.search(rf'^Section "{re.escape(name)}".*?$(.*?)^SectionEnd', text, re.M | re.S)
    assert match is not None, f"в {NSI.name} нет раздела «{name}»"
    return statements(match.group(1))


def defines() -> dict[str, str]:
    text = NSI.read_text(encoding="utf-8")
    return dict(re.findall(r'^!define\s+(\w+)\s+"([^"]*)"', text, re.M))


def first_index(lines: list[str], prefix: str) -> int:
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            return index
    return -1


def shortcut_args(lines: list[str], macro: str) -> str | None:
    head = f'CreateShortcut "${{{macro}}}"'
    for line in lines:
        if line.startswith(head):
            return line[len(head):].strip()
    return None


def test_desktop_lnk_defined_on_desktop() -> None:
    found = defines()
    assert "DESKTOP_LNK" in found, "нет !define DESKTOP_LNK"
    assert found["DESKTOP_LNK"] == r"$DESKTOP\ThermoGar.lnk"


def test_desktop_shortcut_same_as_start_menu() -> None:
    lines = section("ThermoGar")
    start_menu = shortcut_args(lines, "SHORTCUT_LNK")
    desktop = shortcut_args(lines, "DESKTOP_LNK")
    assert start_menu, 'в разделе установки нет CreateShortcut "${SHORTCUT_LNK}"'
    assert desktop is not None, 'в разделе установки нет CreateShortcut "${DESKTOP_LNK}"'
    assert desktop == start_menu


def test_uninstall_deletes_desktop_shortcut() -> None:
    lines = section("Uninstall")
    assert 'Delete "${SHORTCUT_LNK}"' in lines
    assert 'Delete "${DESKTOP_LNK}"' in lines


@pytest.mark.parametrize("name", ["ThermoGar", "Uninstall"])
def test_shell_var_context_all_before_shortcuts(name: str) -> None:
    lines = section(name)
    context = first_index(lines, "SetShellVarContext all")
    assert context >= 0, f"в разделе «{name}» нет SetShellVarContext all"
    uses = [index for index, line in enumerate(lines) if "_LNK}" in line or "SHORTCUT_DIR}" in line]
    assert uses, f"в разделе «{name}» нет работы с ярлыками"
    assert context < min(uses)
