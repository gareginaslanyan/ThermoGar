"""21-Щ, ШАГ 4: символы элементов в сценариях tools/make_guide_screens.py, как на экране."""
from pathlib import Path

path = Path(__file__).resolve().parents[3] / "tools" / "make_guide_screens.py"
lines = path.read_bytes().decode("utf-8").split("\n")

# (строка, было, стало) — замена внутри строки, строка сверяется.
EDITS = [
    (506, '"NI=54.2, CR=17.9, NB=5.3, MO=2.99, TI=0.97, AL=0.5"',
          '"Ni=54.2, Cr=17.9, Nb=5.3, Mo=2.99, Ti=0.97, Al=0.5"'),
    (508, '"C=0.005, SI=5, MN=0.5, S=0.02, CR=23.5, MO=13, NB=0.06, AL=0.25, TI=0.1, FE=0.5"',
          '"C=0.005, Si=5, Mn=0.5, S=0.02, Cr=23.5, Mo=13, Nb=0.06, Al=0.25, Ti=0.1, Fe=0.5"'),
    (533, '"C=0.2, CR=11.5, NI=0.7"', '"C=0.2, Cr=11.5, Ni=0.7"'),
    (537, '"Поле «Добавки»: C=0.2, CR=11.5, NI=0.7"', '"Поле «Добавки»: C=0.2, Cr=11.5, Ni=0.7"'),
    (689, '"CU=4, MG=1"', '"Cu=4, Mg=1"'),
    (1014, '"Ni–12Al,ni,NI,ат.%,700,AL=12,,101325,\\n"', '"Ni–12Al,ni,Ni,ат.%,700,Al=12,,101325,\\n"'),
    (1015, '"Ni–15Al,ni,NI,ат.%,700,AL=15,,101325,\\n"', '"Ni–15Al,ni,Ni,ат.%,700,Al=15,,101325,\\n"'),
    (1016, '"Ni–18Al,ni,NI,ат.%,700,AL=18,,101325,\\n"', '"Ni–18Al,ni,Ni,ат.%,700,Al=18,,101325,\\n"'),
    (1139, '"C=0.2, CR=11.5, NI=0.7"', '"C=0.2, Cr=11.5, Ni=0.7"'),
    (1208, '"AL=9.8, CR=8.3"', '"Al=9.8, Cr=8.3"'),
]
for line_no, old, new in EDITS:
    line = lines[line_no - 1]
    assert line.count(old) == 1, (line_no, line)
    lines[line_no - 1] = line.replace(old, new)
path.write_bytes("\n".join(lines).encode("utf-8"))
print("ok", len(EDITS))
