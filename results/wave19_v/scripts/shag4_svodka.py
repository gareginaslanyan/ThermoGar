# Шаг 4 задания 19-В: сверка разметки исполнителя и Jev.
import pandas as pd
from pathlib import Path

from shag3_jev import FRAZA

ROOT = Path(__file__).resolve().parents[3]
V = ROOT / "results" / "wave19_v"

isp = pd.read_csv(V / "razmetka_ispolnitel.csv", dtype=str, keep_default_na=False)
jev = pd.read_csv(V / "razmetka_jev.csv", dtype=str, keep_default_na=False)
sp = pd.read_csv(V / "spisok_99.csv", dtype=str, keep_default_na=False)
assert list(isp["faza"]) == list(jev["faza"]) and list(isp["opisanie_en"]) == list(jev["opisanie_en"])

out = pd.DataFrame({
    "faza": isp["faza"],
    "opisanie_en": isp["opisanie_en"],
    "klyuchi_ispolnitel": isp["klyuchi"],
    "klyuchi_jev": jev["klyuchi"],
})
out["sovpalo"] = ["да" if a == b else "нет" for a, b in zip(out["klyuchi_ispolnitel"], out["klyuchi_jev"])]
out["tekst_ispolnitel"] = [" ".join(FRAZA[k] for k in s.split()) for s in out["klyuchi_ispolnitel"]]
out["pusto_ispolnitel"] = ["да" if not s else "нет" for s in out["klyuchi_ispolnitel"]]
out.to_csv(V / "razmetka_svodka.csv", index=False, encoding="utf-8")

print("sovpalo", (out["sovpalo"] == "да").sum(), "iz", len(out))
pust = out[out["pusto_ispolnitel"] == "да"][["faza", "opisanie_en"]]
strok = sp.merge(pust, on=["faza", "opisanie_en"])
print("pustyh par", len(pust), "strok iz 99", len(strok), list(strok["baza"] + ":" + strok["faza"]))
pust_jev = (jev["klyuchi"] == "").sum()
print("pustyh par u jev", pust_jev)
for _, r in out[out["sovpalo"] == "нет"].iterrows():
    print(f"{r['faza']} | {r['opisanie_en']} | isp: {r['klyuchi_ispolnitel'] or '—'} | jev: {r['klyuchi_jev'] or '—'}")
