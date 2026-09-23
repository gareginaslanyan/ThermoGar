# Шаг 3 задания 19-В: разметка Jev (TypeSafe System One).
# Вендору уходит только состояние {"faza", "opisanie_en"} и вопросы. Ключ берётся из
# окружения TYPESAFE_API_KEY и нигде не печатается и не пишется.
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
V = ROOT / "results" / "wave19_v"
URL = "https://api.typesafe.ai/v1/systemone"
MODELS = ["jev-1.13.0", "jev-latest"]

ORDER = ["S_CUB", "S_TET", "S_ORT", "S_MON", "S_HEX", "S_RHO", "S_BCC", "S_FCC", "S_HCP",
         "C_INT", "C_SIL", "C_GAS", "C_OX", "C_BOR", "C_SUL", "C_CAR", "C_NIT", "C_LAV",
         "R_DISP", "R_DISPU", "R_UPR", "R_TPU", "R_OXR", "R_TVXR",
         "U_EQ", "U_MET", "T_HIGH", "T_LOW", "SL_EQ", "SL_TD"]

# Фразы ключей и правила 2–12 — дословно из задания (tasks/WAVE19_V_OPUS.md).
FRAZA = {
    "S_CUB": "Кубическая структура.",
    "S_TET": "Тетрагональная структура.",
    "S_ORT": "Ромбическая структура.",
    "S_MON": "Моноклинная структура.",
    "S_HEX": "Гексагональная структура.",
    "S_RHO": "Ромбоэдрическая структура.",
    "S_BCC": "Объёмно-центрированная кубическая (ОЦК) структура.",
    "S_FCC": "Гранецентрированная кубическая (ГЦК) структура.",
    "S_HCP": "Гексагональная плотноупакованная (ГПУ) структура.",
    "C_INT": "Интерметаллидная фаза.",
    "C_SIL": "Силицидная фаза.",
    "C_GAS": "Газовая фаза.",
    "C_OX": "Оксидная фаза.",
    "C_BOR": "Боридная фаза.",
    "C_SUL": "Сульфидная фаза.",
    "C_CAR": "Карбидная фаза.",
    "C_NIT": "Нитридная фаза.",
    "C_LAV": "Фаза Лавеса.",
    "R_DISP": "Дисперсоид.",
    "R_DISPU": "Упрочняющий дисперсоид.",
    "R_UPR": "Упрочняющая фаза.",
    "R_TPU": "Топологически плотноупакованная (ТПУ) фаза.",
    "R_OXR": "Может охрупчивать сплав.",
    "R_TVXR": "Твёрдая и хрупкая фаза.",
    "U_EQ": "Равновесная фаза.",
    "U_MET": "Метастабильная фаза.",
    "T_HIGH": "Высокотемпературная модификация.",
    "T_LOW": "Низкотемпературная модификация.",
    "SL_EQ": "Служебная фаза базы: только для расчёта равновесия.",
    "SL_TD": "Служебная фаза базы: только для расчёта термодинамических свойств.",
}
P = {
    2: "2. Структура — только если текст называет кристаллическую систему (cubic, simple cubic, tetragonal, orthorhombic, monoclinic, hexagonal, rhombohedral, bcc, fcc, hcp) или даёт символ Пирсона (первая буква: c -> S_CUB, t -> S_TET, o -> S_ORT, m -> S_MON, hP -> S_HEX, hR -> S_RHO). Структурный тип или минерал (halite, corundum, pyrite, perovskite, pyrochlore, spinel, quartz, tridymite, alpha-Mn, W6Fe7-type, Al9Co2-type) структуры не даёт.",
    3: "3. Структура по имени — только если имя BCC_A2, FCC_A1 или HCP_A3; такие имена класса не дают.",
    4: "4. Класс, по порядку проверок: GAS в имени или gas в тексте -> C_GAS; слово intermetallic в тексте -> C_INT; Laves -> C_LAV; иначе по химической формуле в тексте или в имени (имя — формула без приставок и суффиксов вида D_, _H, _L, _Z, _WY, _T1; M = металл): есть O -> C_OX; есть S -> C_SUL; есть B -> C_BOR; есть C -> C_CAR; есть N -> C_NIT; Si и ровно один металл -> C_SIL; только металлы или Si с несколькими металлами -> C_INT. Модификация одного элемента (Mn, B, S) — класса нет. Минерал или имя без формулы (SPINEL, TRID, DIGENITE, MU_PHASE, CHI_A12) — класса нет, если формулы нет и в тексте.",
    5: "5. R_DISPU — «strengthening dispersoid»; R_DISP — «dispersoid» без «strengthening».",
    6: "6. R_UPR — текст прямо говорит, что фаза упрочняет (hardening, strengthening), кроме «strengthening dispersoid».",
    7: "7. R_TPU — текст называет саму фазу топологически плотноупакованной или говорит, что она образуется как ТПУ-структура; одно «closely related to … TCP» — нет.",
    8: "8. R_OXR — «affecting brittleness», «embrittle», «influencing ductility». R_TVXR — «hard, brittle».",
    9: "9. U_EQ — текст называет фазу равновесной («equilibrium … phase»); «Use for equilibrium calculation only» — это SL_EQ, не U_EQ. U_MET — «metastable».",
    10: "10. T_HIGH — «high T», «high temperature», «stable as high T»; T_LOW — «low T», «low-temperature». Интервал температур числами ключа не даёт.",
    11: "11. SL_EQ — «Use for equilibrium calculation only»; SL_TD — «for thermodynamic properties calculations only».",
    12: "12. Ничего не подходит — пустой набор (заглушка останется). Не додумывать по знанию о фазе.",
}
INSTR = "Судить только по полям состояния."


def variant(key, *rules):
    return {"ключ": key, "фраза": FRAZA[key], "правила": [P[n] for n in rules]}


NOT_STATED = {"правила": [P[12]]}


def choice(keys, *rules):
    crit = {k: variant(k, *rules) for k in keys}
    crit["not_stated"] = NOT_STATED
    return {"type": "choice", "instructions": INSTR, "criteria": crit}


def noul(key, rule):
    return {"type": "noul", "instructions": INSTR,
            "criteria": {"true": variant(key, rule), "false": NOT_STATED}}


QUESTIONS = {
    "struktura": choice(["S_CUB", "S_TET", "S_ORT", "S_MON", "S_HEX", "S_RHO", "S_BCC", "S_FCC", "S_HCP"], 2, 3),
    "klass": choice(["C_GAS", "C_INT", "C_LAV", "C_OX", "C_SUL", "C_BOR", "C_CAR", "C_NIT", "C_SIL"], 4),
    "dispersoid": choice(["R_DISPU", "R_DISP"], 5),
    "uprochnenie": noul("R_UPR", 6),
    "tpu": noul("R_TPU", 7),
    "khrupkost": choice(["R_OXR", "R_TVXR"], 8),
    "ustojchivost": choice(["U_EQ", "U_MET"], 9),
    "temperatura": choice(["T_HIGH", "T_LOW"], 10),
    "sluzhebnaya": choice(["SL_EQ", "SL_TD"], 11),
}
CHOICE_Q = [q for q, d in QUESTIONS.items() if d["type"] == "choice"]
NOUL_Q = {"uprochnenie": "R_UPR", "tpu": "R_TPU"}


def post(key, model, state):
    body = json.dumps({"model": model, "state": state, "questions": QUESTIONS}).encode("utf-8")
    req = urllib.request.Request(URL, data=body, method="POST", headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def ask(key, model, state):
    for attempt in range(6):
        try:
            return post(key, model, state)
        except urllib.error.HTTPError as e:
            if e.code in (429, 529, 500, 502, 503, 504) and attempt < 5:
                time.sleep(2 ** attempt)
                continue
            raise


def main():
    key = os.environ.get("TYPESAFE_API_KEY")
    if not key:
        sys.exit("СТОП: TYPESAFE_API_KEY нет в окружении")
    pary = pd.read_csv(V / "razmetka_ispolnitel.csv", dtype=str, keep_default_na=False)[["faza", "opisanie_en"]]

    # Выбор модели: сначала jev-1.13.0; при отказе (HTTP 4xx) — jev-latest.
    first = {"faza": pary.iloc[0]["faza"], "opisanie_en": pary.iloc[0]["opisanie_en"]}
    model, otkaz, resp0 = None, [], None
    t0 = time.perf_counter()
    for m in MODELS:
        try:
            resp0 = ask(key, m, first)
            model = m
            break
        except urllib.error.HTTPError as e:
            otkaz.append(f"{m}: HTTP {e.code} {e.read().decode('utf-8', 'replace')[:300]}")
            if not (400 <= e.code < 500):
                raise
    print("zaproshena model:", model, "| otkaz:", otkaz)
    if model is None:
        sys.exit("СТОП: обе модели отклонены")

    rows, raw = [], []
    tin = tout = 0
    for i, r in pary.iterrows():
        state = {"faza": r["faza"], "opisanie_en": r["opisanie_en"]}
        resp = resp0 if i == 0 else ask(key, model, state)
        raw.append({"state": state, "response": resp})
        a = resp["answers"]
        tin += resp["usage"]["input_tokens"]
        tout += resp["usage"]["output_tokens"]
        keys = []
        row = {"faza": r["faza"], "opisanie_en": r["opisanie_en"]}
        for q in QUESTIONS:
            if q in NOUL_Q:
                row[f"{q}_noul"] = a[q]["noul"]
                if a[q]["noul"] >= 0.5:
                    keys.append(NOUL_Q[q])
            else:
                row[f"{q}_vybor"] = a[q]["choice"]
                row[f"{q}_confidence"] = a[q]["confidence"]
                if a[q]["choice"] != "not_stated":
                    keys.append(a[q]["choice"])
        row["klyuchi"] = " ".join(sorted(keys, key=ORDER.index))
        row["model"] = resp["model"]
        rows.append(row)
    dt = time.perf_counter() - t0

    cols = ["faza", "opisanie_en", "klyuchi"] + [c for c in rows[0] if c not in ("faza", "opisanie_en", "klyuchi", "model")] + ["model"]
    pd.DataFrame(rows)[cols].to_csv(V / "razmetka_jev.csv", index=False, encoding="utf-8")
    with open(V / "jev_otvety.jsonl", "w", encoding="utf-8") as f:
        for x in raw:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    print("zaprosov", len(rows), "models v otvetah", sorted({r["model"] for r in rows}))
    print("tokens in", tin, "out", tout, "vremya s", round(dt, 1))


if __name__ == "__main__":
    main()
