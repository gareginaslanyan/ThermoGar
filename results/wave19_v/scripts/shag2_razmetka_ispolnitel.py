# Шаг 2 задания 19-В: разметка исполнителя (до Jev, без Jev).
# Разметка ручная; скрипт только записывает её в CSV и проверяет ограничения набора.
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
V = ROOT / "results" / "wave19_v"

ORDER = ["S_CUB", "S_TET", "S_ORT", "S_MON", "S_HEX", "S_RHO", "S_BCC", "S_FCC", "S_HCP",
         "C_INT", "C_SIL", "C_GAS", "C_OX", "C_BOR", "C_SUL", "C_CAR", "C_NIT", "C_LAV",
         "R_DISP", "R_DISPU", "R_UPR", "R_TPU", "R_OXR", "R_TVXR",
         "U_EQ", "U_MET", "T_HIGH", "T_LOW", "SL_EQ", "SL_TD"]
GROUPS = [[k for k in ORDER if k.startswith("S_")], [k for k in ORDER if k.startswith("C_")],
          ["R_DISP", "R_DISPU"], ["R_OXR", "R_TVXR"], ["U_EQ", "U_MET"], ["T_HIGH", "T_LOW"],
          ["SL_EQ", "SL_TD"]]

# Номер пары (порядок первого появления в spisok_99.csv), фаза, [(ключ, основание)].
# Пустой список — ничего не подходит (п. 12); пояснение — в NET.
R = {
 1: ("BETA_MN", [("S_CUB", "«Simple cubic» (п. 2)")]),
 2: ("BETA_RHOMBO_B", [("S_RHO", "«Rhombohedral» (п. 2)")]),
 3: ("B_CHALC", [("C_SUL", "формула «Cu2S» в тексте, есть S (п. 4)")]),
 4: ("CHI_A12", []),
 5: ("CORUND", [("C_OX", "формула «(Al,Cr,Fe)2O3» в тексте, есть O (п. 4)")]),
 6: ("CR2B", [("S_ORT", "«Orthorhombic» (п. 2)"), ("C_BOR", "имя CR2B = Cr2B, есть B (п. 4)")]),
 7: ("CR3MN5", [("C_INT", "имя CR3MN5 = Cr3Mn5, только металлы (п. 4)")]),
 8: ("CRB", [("C_BOR", "имя CRB = CrB, есть B (п. 4)")]),
 9: ("DIGENITE", [("SL_EQ", "«Use for equilibrium calculation only» (п. 11)")]),
 10: ("DISULF", [("C_SUL", "формула «FeS2» в тексте, есть S (п. 4)")]),
 11: ("D_NIMO", [("C_INT", "имя D_NIMO без приставки D_ = NiMo, только металлы (п. 4)")]),
 12: ("FC_MONO", [("S_MON", "«Monoclinic» (п. 2)"), ("T_HIGH", "«high T» (п. 10)")]),
 13: ("FC_ORTHO", [("S_ORT", "«Orthorhombic» (п. 2)"), ("T_LOW", "«low T» (п. 10)")]),
 14: ("HALITE", [("C_OX", "формула «(Cr,Fe,Ni)O» в тексте, есть O (п. 4)")]),
 15: ("HF1O2_C", [("S_CUB", "«cubic» (п. 2)"), ("C_OX", "имя HF1O2_C без суффикса _C = HfO2, есть O (п. 4)")]),
 16: ("HF1O2_M", [("S_MON", "«monoclinic» (п. 2)"), ("C_OX", "имя HF1O2_M без суффикса _M = HfO2, есть O (п. 4)"), ("R_DISPU", "«strengthening dispersoid» (п. 5)")]),
 17: ("HF1O2_T", [("S_TET", "«tetragonal» (п. 2)"), ("C_OX", "имя HF1O2_T без суффикса _T = HfO2, есть O (п. 4)")]),
 18: ("LA2O3_A", [("S_HEX", "«hexagonal» (п. 2)"), ("C_OX", "имя LA2O3_A без суффикса _A = La2O3, есть O (п. 4)"), ("R_DISPU", "«strengthening dispersoid» (п. 5)")]),
 19: ("LA2O3_C", [("S_CUB", "«cubic» (п. 2)"), ("C_OX", "имя LA2O3_C без суффикса _C = La2O3, есть O (п. 4)")]),
 20: ("M2B", [("S_TET", "«Tetragonal» (п. 2)"), ("C_BOR", "имя M2B, есть B (п. 4)")]),
 21: ("M6C_WY", [("C_CAR", "«M6C» в тексте и имя без суффикса _WY, есть C (п. 4)")]),
 22: ("MU_PHASE", [("R_TPU", "«can form as topologically close-packed structure» (п. 7)"), ("R_OXR", "«affecting brittleness» (п. 8)")]),
 23: ("O1_GAS", [("C_GAS", "GAS в имени O1_GAS (п. 4)"), ("SL_TD", "«for thermodynamic properties calculations only» (п. 11)")]),
 24: ("P_PHASE", [("R_TPU", "«Can form as topologically close-packed structure» (п. 7)"), ("R_OXR", "«affecting brittleness» (п. 8)")]),
 25: ("R_PHASE", [("R_TPU", "«Can form as topologically close-packed structure» (п. 7)"), ("R_OXR", "«affecting brittleness» (п. 8)")]),
 26: ("SIO2", [("C_OX", "имя SIO2 = SiO2, есть O (п. 4)")]),
 27: ("TIO2", [("C_OX", "имя TIO2 = TiO2, есть O (п. 4)")]),
 28: ("TRID", []),
 29: ("AL12MG2CR", [("C_INT", "имя AL12MG2CR = Al12Mg2Cr, только металлы (п. 4)"), ("R_DISP", "«dispersoid» без «strengthening» (п. 5)")]),
 30: ("AL18CR2MG3", [("C_INT", "имя AL18CR2MG3 = Al18Cr2Mg3, только металлы (п. 4)"), ("R_DISP", "«dispersoid» без «strengthening» (п. 5)")]),
 31: ("AL2CU3_D", [("C_INT", "имя AL2CU3_D без суффикса _D = Al2Cu3, только металлы (п. 4)")]),
 32: ("AL3TI_H", [("S_TET", "«Tetragonal» (п. 2)"), ("C_INT", "имя AL3TI_H без суффикса _H = Al3Ti, только металлы (п. 4)"), ("T_HIGH", "«high temperature» (п. 10)")]),
 33: ("AL3TI_L", [("S_TET", "«Tetragonal» (п. 2)"), ("C_INT", "имя AL3TI_L без суффикса _L = Al3Ti, только металлы (п. 4)"), ("T_LOW", "«low-temperature» (п. 10)")]),
 34: ("AL4MN", [("S_HEX", "«Hexagonal» (п. 2)"), ("C_INT", "имя AL4MN = Al4Mn, только металлы (п. 4)")]),
 35: ("AL8FEMNSI2", [("C_INT", "«Intermetallic» в тексте (п. 4)")]),
 36: ("AL9CU11_Z", [("C_INT", "имя AL9CU11_Z без суффикса _Z = Al9Cu11, только металлы (п. 4)")]),
 37: ("AL9CU11_ZP", [("C_INT", "имя AL9CU11_ZP без суффикса _ZP = Al9Cu11, только металлы (п. 4)")]),
 38: ("ALCUMN_T1", [("S_ORT", "«orthorhombic crystal structure» (п. 2)"), ("C_INT", "формулы «AL20CU2MN3», «Al20Cu3Mn4» в тексте, только металлы (п. 4)"), ("R_DISP", "«rodlike dispersoids» без «strengthening» (п. 5)")]),
 39: ("ALCU_EPL", [("C_INT", "имя ALCU_EPL без суффикса _EPL = AlCu, только металлы (п. 4)"), ("T_LOW", "«low T» (п. 10)")]),
 40: ("ALCU_EPS", [("C_INT", "«AlCu» в тексте, только металлы (п. 4)")]),
 41: ("ALCU_ETH", [("C_INT", "имя ALCU_ETH без суффикса _ETH = AlCu, только металлы (п. 4)"), ("T_HIGH", "«high T» (п. 10)")]),
 42: ("ALCU_ETL", [("C_INT", "имя ALCU_ETL без суффикса _ETL = AlCu, только металлы (п. 4)"), ("T_LOW", "«low T» (п. 10)")]),
 43: ("ALCU_G", [("C_INT", "имя ALCU_G без суффикса _G = AlCu, только металлы (п. 4)"), ("T_HIGH", "«stable as high T» (п. 10)")]),
 44: ("ALFENI_T1", [("S_MON", "«monoclinic structure» (п. 2)"), ("C_INT", "формула «Al9FeNi» в тексте, только металлы (п. 4)"), ("R_UPR", "«Contributes to hardening» (п. 6)")]),
 45: ("ALFESI_T5", [("S_HEX", "«hexagonal» (п. 2)"), ("C_INT", "«AlFeSi» в тексте, Si с несколькими металлами (п. 4)")]),
 46: ("ALFESI_T6", [("S_MON", "«Monoclinic» (п. 2)"), ("C_INT", "формула «Al5FeSi» в тексте, Si с несколькими металлами (п. 4)"), ("R_DISP", "«Important dispersoid» без «strengthening» (п. 5)")]),
 47: ("BCC_A2", [("S_BCC", "имя BCC_A2 (п. 3)")]),
 48: ("PI_ALFEMGSI", [("S_HEX", "«Hexagonal» (п. 2)"), ("C_INT", "имя PI_ALFEMGSI без приставки PI_ = AlFeMgSi, Si с несколькими металлами (п. 4)"), ("R_OXR", "«Influencing ductility» (п. 8)"), ("U_EQ", "«Hexagonal equilibrium pi-phase» (п. 9)")]),
 49: ("SI2TI", [("S_ORT", "символ Пирсона «oF24» (п. 2)"), ("C_SIL", "формула «TiSi2» в тексте, Si и один металл (п. 4)")]),
 50: ("SI3TI5", [("S_HEX", "символ Пирсона «hP16» (п. 2)"), ("C_SIL", "имя SI3TI5 = Ti5Si3, Si и один металл (п. 4)")]),
 51: ("SI4TI5", [("S_TET", "символ Пирсона «tP36» (п. 2)"), ("C_SIL", "имя SI4TI5 = Ti5Si4, Si и один металл (п. 4)")]),
 52: ("SITI", [("S_ORT", "символ Пирсона «oP8» (п. 2)"), ("C_SIL", "имя SITI = TiSi, Si и один металл (п. 4); «FeB» в тексте — прототип структурного типа после символа Пирсона и пространственной группы, не формула фазы")]),
 53: ("SITI3", [("S_TET", "символ Пирсона «tP30» (п. 2)"), ("C_SIL", "имя SITI3 = Ti3Si, Si и один металл (п. 4); «PTi3» в тексте — прототип структурного типа")]),
 54: ("TI17AL5SI14", [("S_ORT", "«orthorhombic» (п. 2)"), ("C_INT", "имя TI17AL5SI14, Si с несколькими металлами (п. 4)")]),
 55: ("TIALSI_TAU", [("S_ORT", "«orthorhombic» (п. 2)"), ("C_INT", "имя TIALSI_TAU без суффикса _TAU = TiAlSi, Si с несколькими металлами (п. 4)")]),
 56: ("BETA_MN", [("S_CUB", "«Simple cubic» (п. 2)")]),
 57: ("CR3MN5", [("C_INT", "имя CR3MN5 = Cr3Mn5, только металлы (п. 4)")]),
 58: ("CRB", [("S_ORT", "«Orthorhombic» (п. 2)"), ("C_BOR", "имя CRB = CrB, есть B (п. 4)")]),
 59: ("FEB", [("S_ORT", "«Orthorhombic» (п. 2)"), ("C_BOR", "имя FEB = FeB, есть B (п. 4)")]),
 60: ("M5B6", [("S_ORT", "«Orthorhombic» (п. 2)"), ("C_BOR", "имя M5B6, есть B (п. 4)")]),
 61: ("MN3B4", [("S_ORT", "«Orthorhombic» (п. 2)"), ("C_BOR", "имя MN3B4 = Mn3B4, есть B (п. 4)")]),
 62: ("MNB2", [("S_HEX", "«Hexagonal» (п. 2)"), ("C_BOR", "имя MNB2 = MnB2, есть B (п. 4)")]),
 63: ("MNNI", [("S_CUB", "«cubic» (п. 2)"), ("C_INT", "имя MNNI = MnNi, только металлы (п. 4)")]),
 64: ("MO2M1B2", [("S_TET", "«tetragonal» (п. 2)"), ("C_BOR", "имя MO2M1B2 = Mo2MB2, есть B (п. 4)")]),
 65: ("MU_PHASE", [("C_INT", "«intermetallic compound» (п. 4)"), ("R_UPR", "«Important hardening phase» (п. 6)"), ("R_TVXR", "«Hard, brittle» (п. 8)")]),
 66: ("MU_PHASE_I", [("C_INT", "«intermetallic compound» (п. 4)"), ("R_UPR", "«Important hardening phase» (п. 6)"), ("R_TVXR", "«Hard, brittle» (п. 8)")]),
 67: ("O_MN2B", [("S_ORT", "«Orthorhombic» (п. 2)"), ("C_BOR", "имя O_MN2B без приставки O_ = Mn2B, есть B (п. 4)")]),
 68: ("PD2MN", [("S_ORT", "«orthorhombic» (п. 2)"), ("C_INT", "имя PD2MN = Pd2Mn, только металлы (п. 4)")]),
 69: ("PD5MN3", [("S_ORT", "«orthorhombic» (п. 2)"), ("C_INT", "имя PD5MN3 = Pd5Mn3, только металлы (п. 4)")]),
 70: ("PD6FE5MN2", [("C_INT", "имя PD6FE5MN2 = Pd6Fe5Mn2, только металлы (п. 4)")]),
 71: ("R_PHASE", [("R_TPU", "«Topologically close-packed structure» — сама фаза названа ТПУ (п. 7)")]),
 72: ("SPINEL", []),
 73: ("TI3B4", [("S_ORT", "«Orthorhombic» (п. 2)"), ("C_BOR", "имя TI3B4 = Ti3B4, есть B (п. 4)")]),
 74: ("TIB", [("S_ORT", "«Orthorhombic» (п. 2)"), ("C_BOR", "имя TIB = TiB, есть B (п. 4)")]),
 75: ("TIB2", [("S_HEX", "«Hexagonal» (п. 2)"), ("C_BOR", "имя TIB2 = TiB2, есть B (п. 4)")]),
 76: ("WC", [("S_HEX", "«simple hexagonal» (п. 2)"), ("C_CAR", "имя WC, есть C (п. 4)")]),
 77: ("Y2TI2O7", [("C_OX", "имя Y2TI2O7 = Y2Ti2O7, есть O (п. 4)"), ("R_DISPU", "«strengthening dispersoid» (п. 5)")]),
 78: ("Y2TIO5", [("S_ORT", "«orthorhombic» (п. 2)"), ("C_OX", "имя Y2TIO5 = Y2TiO5, есть O (п. 4)"), ("R_DISPU", "«strengthening dispersoid» (п. 5)")]),
 79: ("Y4AL2O9", [("S_MON", "«monoclinic» (п. 2)"), ("C_OX", "имя Y4AL2O9 = Y4Al2O9, есть O (п. 4)"), ("R_DISPU", "«strengthening dispersoid» (п. 5)")]),
 80: ("YALO3", [("C_OX", "имя YALO3 = YAlO3, есть O (п. 4)"), ("R_DISPU", "«strengthening dispersoid» (п. 5)")]),
}

# Пояснения к решениям «ключа нет» там, где текст мог бы навести на ключ.
NET = {
 1: "интервал «between 1000 K and 1370 K» ключа не даёт (п. 10); модификация одного элемента Mn — класса нет (п. 4)",
 2: "модификация одного элемента B — класса нет (п. 4)",
 4: "пусто: «Alpha-Mn structure» — структурный тип (п. 2); «closely related to topologically close-packed» — не R_TPU (п. 7); CHI_A12 — имя без формулы, «carbon» — слово, не формула (п. 4)",
 5: "«corund-structured» — структурный тип (п. 2)",
 10: "«Pyrite» — минерал (п. 2)",
 12: "сера — модификация одного элемента, класса нет (п. 4)",
 13: "сера — модификация одного элемента, класса нет (п. 4)",
 14: "«halite-structured» — структурный тип (п. 2)",
 16: "«strengthening dispersoid» — не R_UPR (п. 6)",
 18: "«strengthening dispersoid» — не R_UPR (п. 6)",
 21: "«Wyckoff positions» кристаллическую систему не называет (п. 2)",
 22: "MU_PHASE — имя без формулы, класса нет (п. 4)",
 24: "P_PHASE — имя без формулы, класса нет (п. 4)",
 25: "R_PHASE — имя без формулы, класса нет (п. 4)",
 26: "«Low Quartz»: quartz — минерал (п. 2); «Low» — не «low T» / «low-temperature», T_LOW не ставлю (п. 10, п. 12)",
 28: "пусто: «Tridymite» — минерал (п. 2), TRID — имя без формулы (п. 4)",
 35: "«cubic» в тексте относится к другой фазе («cubic alpha-phase ALCRFEMNSI_A»), S_CUB не ставлю (п. 2, п. 12); «high-Si» — не температура",
 44: "«Al9Co2-type» — структурный тип; «up to 600C» — число, ключа не даёт (п. 10)",
 47: "BCC_A2 класса не даёт (п. 3)",
 56: "интервал «between around 1000 K and 1370 K» ключа не даёт (п. 10); модификация одного элемента Mn — класса нет (п. 4)",
 65: "«W6Fe7-type» — структурный тип (п. 2)",
 66: "«W6Fe7-type» — структурный тип (п. 2)",
 70: "«high-Pd» — не температура (п. 10)",
 71: "R_PHASE — имя без формулы, класса нет (п. 4)",
 72: "пусто: SPINEL — минерал без формулы; «Fe-Cr» — обозначение системы, не формула фазы (п. 4, п. 12)",
 77: "«pyrochlore structure» — структурный тип (п. 2)",
 80: "«perovskite structure» — структурный тип (п. 2)",
}

sp = pd.read_csv(V / "spisok_99.csv", dtype=str, keep_default_na=False)
pary = sp.drop_duplicates(["faza", "opisanie_en"]).reset_index(drop=True)
assert len(pary) == 80 == len(R)
out = []
for i, r in pary.iterrows():
    faza, kl = R[i + 1]
    assert faza == r["faza"], (i + 1, faza, r["faza"])
    keys = [k for k, _ in kl]
    assert all(k in ORDER for k in keys), keys
    assert keys == sorted(keys, key=ORDER.index), (faza, keys)
    for g in GROUPS:
        assert sum(k in g for k in keys) <= 1, (faza, keys)
    osn = "; ".join(f"{k}: {o}" for k, o in kl)
    if i + 1 in NET:
        osn = (osn + "; " if osn else "") + "прочее: " + NET[i + 1]
    out.append({"faza": faza, "opisanie_en": r["opisanie_en"], "klyuchi": " ".join(keys), "osnovanie": osn})
pd.DataFrame(out).to_csv(V / "razmetka_ispolnitel.csv", index=False, encoding="utf-8")
print("pary", len(out), "pustyh", sum(not o["klyuchi"] for o in out))
