"""21-Щ, ШАГ 6: таблицы результата для чисел глав (затвердевание, кинетика, диффузия).

Прогон ``tools/make_guide_screens.py --only zatverdevanie,kinetika`` с
перезапуском приложения; кадры — во временную папку (``docs/guide/img`` не
трогается). После сценария «Затвердевание» (вид «Выгрузка») и после сценария
«Кинетика» (диффузия на экране, затем вид «Экспорт и ограничения»
«Выделений») скачиваются кнопки «Скачать Excel» — те же расчёты и те же
входные данные, что у кадров ``zatverdevanie-04``, ``kinetika-05``,
``kinetika-08``.

Запуск из корня дерева:

    python -X utf8 results/wave21_shch/scripts/zamer_tablicy.py <папка> [порт]
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

import make_guide_screens as m  # noqa: E402

out = Path(sys.argv[1])
port = sys.argv[2] if len(sys.argv) > 2 else "8603"
out.mkdir(parents=True, exist_ok=True)
m.IMG_ROOT = out / "kadry"


def download_excel(page, target: str) -> None:
    root = m.main_area(page)
    button = root.get_by_role("button", name="Скачать Excel", exact=True).first
    button.wait_for(timeout=m.CALC_TIMEOUT_MS)
    with page.expect_download(timeout=m.UI_TIMEOUT_MS) as info:
        button.click()
    info.value.save_as(str(out / target))
    m.wait_idle(page)
    print(f"  {target}")


_zatverdevanie = m.SCENARIOS["zatverdevanie"]
_kinetika = m.SCENARIOS["kinetika"]


def zatverdevanie(page, log):
    _zatverdevanie(page, log)
    download_excel(page, "zatverdevanie.xlsx")


def kinetika(page, log):
    _kinetika(page, log)
    download_excel(page, "diffuziya.xlsx")
    m.open_tab(page, "Выделения")
    m.pick_view(page, "Кинетика выделений", "Экспорт и ограничения")
    download_excel(page, "kinetika.xlsx")


m.SCENARIOS["zatverdevanie"] = zatverdevanie
m.SCENARIOS["kinetika"] = kinetika
sys.argv = [sys.argv[0], "--only", "zatverdevanie,kinetika", "--no-html", "--port", port]
sys.exit(m.main())
