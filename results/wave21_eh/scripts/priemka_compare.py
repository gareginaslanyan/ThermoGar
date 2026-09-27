"""Приёмка 0.5.0, (б) и (в): побайтовая сверка выходов приёмки с байтами из git (сценарий 21-Э
для задачи выпуска 21-Ю). Копия ``results/wave19_d/priemka_compare.py``; отличия: эталон (в) —
``results/wave21_eh/spravochnik_faz/phase_reference_{ni,al,fe}.csv`` (снят в 21-Э: 21-Ж сменил
«order/disorder-модель» на «модель порядок/беспорядок», со старыми CSV 19-В2 побайтово не
сходится); ревизия по умолчанию — ``wave21-eh``; выходы приёмки — ``RELEASE_OUT/priemka`` (одна
переменная в начале скрипта, results/wave21_yu/). (б) — как в 19-Д.

    python -B -X utf8 results/wave21_eh/scripts/priemka_compare.py [ревизия]

Прежняя шапка 19-Д:
19-Д, шаг 9 (б), (в): побайтовая сверка выходов приёмки с байтами из git.

(б) ``b_batch_Fe-{пусто,метастабильный,стабильный}.csv`` — с блобами
``results/wave19_a/posle/1g_batch_Fe-*.csv``; (в) ``v_phase_reference_{ni,al,fe}.csv`` — с блобами
``results/wave19_v2/posle/phase_reference_*.csv``. Блобы берутся ``git cat-file`` из ревизии
(первый аргумент, по умолчанию ``v0.4.4``), рабочая копия не читается.
"""
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RELEASE_OUT = ROOT / "results" / "wave21_yu"  # каталог вывода задачи выпуска 21-Ю
REV = sys.argv[1] if len(sys.argv) > 1 else "wave21-eh"
GOT = RELEASE_OUT / "priemka"
PAIRS = [(f"b_batch_Fe-{label}.csv", f"results/wave19_a/posle/1g_batch_Fe-{label}.csv")
         for label in ("пусто", "метастабильный", "стабильный")]
PAIRS += [(f"v_phase_reference_{key}.csv", f"results/wave21_eh/spravochnik_faz/phase_reference_{key}.csv")
          for key in ("ni", "al", "fe")]

lines = [f"ревизия: {REV}"]
equal = 0
for got, ref in PAIRS:
    blob = subprocess.run(["git", "cat-file", "blob", f"{REV}:{ref}"], cwd=ROOT, capture_output=True,
                          check=True).stdout
    data = (GOT / got).read_bytes()
    same = data == blob
    equal += same
    lines.append(f"{'РАВНЫ' if same else 'РАЗНЫЕ'} | {got} {hashlib.sha256(data).hexdigest()} | "
                 f"{ref} {hashlib.sha256(blob).hexdigest()}")
lines.append(f"равных: {equal} из {len(PAIRS)}")
(GOT / "compare.txt").write_text("\n".join(lines) + "\n", "utf-8")
print("\n".join(lines))
