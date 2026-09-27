"""21-Щ, ШАГ 6, п. 17: двухбуквенные символы элементов заглавными в документах.

Ищет в docs/guide/*.md, docs/FEATURES.md, USER_GUIDE_THERMOGAR.md слово из двух
заглавных латинских букв, совпадающее с символом элемента, вне синтаксиса
базы и имён. Исключения — места целиком: `G(C15_LAVES,FE,NI:MN,SI;0)`,
`DP(LAVES_PHASE,FE:NB)`, `TG-FE-2062-C15-001`; имена фаз (слово с «_» или
цифрой, `NIAL` и т. п.) правило «слово целиком» и так не ловит.

Запуск из корня дерева:

    python -X utf8 results/wave21_shch/scripts/proverka_simvolov.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FILES = sorted((ROOT / "docs" / "guide").glob("*.md")) + [
    ROOT / "docs" / "FEATURES.md",
    ROOT / "USER_GUIDE_THERMOGAR.md",
]
ELEMENTS = (
    "He Li Be Ne Na Mg Al Si Cl Ar Ca Sc Ti Cr Mn Fe Co Ni Cu Zn Ga Ge As Se Br Kr "
    "Rb Sr Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd "
    "Tb Dy Ho Er Tm Yb Lu Hf Ta Re Os Ir Pt Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa "
    "Np Pu Am Cm Bk Cf Es Fm Md No Lr"
).split()
PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])(" + "|".join(e.upper() for e in ELEMENTS) + r")(?![A-Za-z0-9_])"
)
ALLOWED = (
    "G(C15_LAVES,FE,NI:MN,SI;0)",
    "DP(LAVES_PHASE,FE:NB)",
    "TG-FE-2062-C15-001",
)

found = 0
for path in FILES:
    for number, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
        masked = line
        for allowed in ALLOWED:
            masked = masked.replace(allowed, " " * len(allowed))
        for match in PATTERN.finditer(masked):
            found += 1
            start = max(0, match.start() - 40)
            print(
                f"{path.relative_to(ROOT).as_posix()}:{number}: {match.group(1)} | "
                f"{line[start:match.end() + 40]}"
            )
print(f"Найдено: {found}")
sys.exit(0)
