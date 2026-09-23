# Шаг 1 задания 19-В: список фаз-заглушек BL-58.
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "results" / "wave19_a" / "posle"
OUT = ROOT / "results" / "wave19_v" / "spisok_99.csv"

rows = []
for baza in ("ni", "al", "fe"):
    df = pd.read_csv(SRC / f"1v_phase_reference_{baza}.csv", dtype=str, keep_default_na=False)
    if baza == "ni":
        print("columns:", list(df.columns))
    m = df["Описание по-русски"].str.contains("Русская расшифровка", regex=False) & (df["Оригинал из базы (англ.)"].str.strip() != "")
    sel = df[m]
    faza_col = df.columns[0]
    print(baza, "rows", len(df), "selected", len(sel), "faza col", faza_col,
          "prostymi nonempty", (sel["Простыми словами"].str.strip() != "").sum())
    for _, r in sel.iterrows():
        rows.append({"baza": baza, "faza": r[faza_col], "opisanie_en": r["Оригинал из базы (англ.)"]})

out = pd.DataFrame(rows)
print("total", len(out))
print("unique pairs", len(out.drop_duplicates(["faza", "opisanie_en"])))
print("unique descriptions", out["opisanie_en"].nunique())
out.to_csv(OUT, index=False, encoding="utf-8")
