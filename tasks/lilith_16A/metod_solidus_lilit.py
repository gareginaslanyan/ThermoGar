"""Метод солидуса/ликвидуса «Лилит» для задачи ThermoGar 16-А.

Это НЕ второй решатель. Считает сам слой «Лилит»: рядом лежит побайтовая
копия его модулей (`calphad_layer/`, снята `git archive` с main d469cf2f,
sha256 в `calphad_layer.sha256`), а скрипт подменяет только три вещи,
которые ThermoGar должен варьировать:

  * файл базы        — `--tdb mc_al=путь` (кладётся в кэш разбора слоя
                       `raschet._KESH_BAZ`, минуя проверку sha слоя);
  * порог жидкости   — `--porog` (`raschet.NOL_DOLI`, у слоя 1e-9);
  * набор фаз        — `--nabor sloj` (быстрый набор слоя + сторож движущей
                       силы, как в заморозке) или `--nabor polnyj` (все
                       активные фазы системы минус исключения слоя).

Метод слоя (raschet.py), кратко:
  доля жидкости = NP(LIQUID) из equilibrium(P=101325, N=1, X(i)), pdens 200;
  солидус — первый переход NP(LIQUID) через порог снизу, ликвидус — первый
  переход через 1 − порог; каскад векторных свипов 100 → 20 → 4 → 0,5 →
  0,25 K по сужающимся окнам, ответ — середина последнего окна (0,25 K),
  округлён до 0,1 K. Сторож: в точках (T_sol + 1 K) и (T_liq − 1 K)
  считается движущая сила каждой фазы вне быстрого набора (calculate,
  pdens 20); фаза ниже −10 Дж/моль добавляется в набор и поиск
  повторяется, до 6 раундов; непроверенная фаза — отказ. Если быстрый
  набор интервала не нашёл — поиск повторяется всем активным набором.

Запуск (pycalphad 0.11.2):

    python metod_solidus_lilit.py --tdb mc_al=mc_al_v2037.thermogar.tdb \
        --tdb mc_ni=mc_ni_v2036.garcalc.tdb --tdb mc_fe=mc_fe_v2062.thermogar.tdb \
        [--marki "IN718,316L"] [--porog 1e-4] [--nabor polnyj] [--bez-granic] \
        [--vyvod rez.csv]

Без `--porog`/`--nabor` скрипт работает как проверка: каждое число
сверяется с замороженным из `marki_16A.csv`, расхождение больше
`--dopusk` (0,5 K) даёт код возврата 1.
"""
import argparse
import copy
import csv
import hashlib
import io
import sys
import time
import warnings
from pathlib import Path

TUT = Path(__file__).resolve().parent


def argumenty():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--csv", default=str(TUT / "marki_16A.csv"))
    p.add_argument("--tdb", action="append", default=[], metavar="БАЗА=ПУТЬ",
                   help="mc_al / mc_ni / mc_fe / cost507; строки без базы в этом списке пропускаются")
    p.add_argument("--marki", default="", help="через запятую: marka или klyuch_zamorozki")
    p.add_argument("--porog", type=float, default=None, help="порог NP(LIQUID); у слоя 1e-9")
    p.add_argument("--nabor", choices=("sloj", "polnyj"), default="sloj")
    p.add_argument("--bez-granic", action="store_true",
                   help="не проверять пределы шапки базы (для строк status_v_sloe=otkaz_sloya)")
    p.add_argument("--dopusk", type=float, default=0.5, help="K, для сверки с заморозкой")
    p.add_argument("--kanon", default=str(TUT), help="папка, в которой лежит calphad_layer/")
    p.add_argument("--vyvod", default="")
    return p.parse_args()


def sha256(put):
    return hashlib.sha256(Path(put).read_bytes()).hexdigest()


def zagruzit_bazu(put, pochinka):
    """Байты файла -> Database. Файл слоя mc_fe 2.059 (зеркало A) чинится тем же кодом слоя."""
    from pycalphad import Database
    syrye = Path(put).read_bytes()
    sha = hashlib.sha256(syrye).hexdigest()
    tekst = None
    for imya, (fn, sha_ish, _) in pochinka.POCHINKI.items():
        if fn is not None and sha_ish == sha:
            tekst = fn(syrye.decode(pochinka.KODIROVKA_ISHODNIKA.get(imya, "utf-8")))
    if tekst is None:
        tekst = syrye.decode("utf-8")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return Database.from_file(io.StringIO(tekst, newline=None), fmt="tdb"), sha


def main():
    a = argumenty()
    sys.path.insert(0, str(Path(a.kanon).resolve()))
    from calphad_layer import granicy as gr, pochinka, raschet
    import pycalphad

    proverka = a.porog is None and a.nabor == "sloj"
    if a.porog is not None:
        raschet.NOL_DOLI = a.porog
    tdb = dict(x.split("=", 1) for x in a.tdb)
    sloj = Path(raschet.__file__).parent
    print(f"pycalphad {pycalphad.__version__}; слой {sloj}")
    for f in sorted(sloj.glob("*.py")) + [sloj / "manifest.json"]:
        print(f"  {sha256(f)}  {f.name}")
    print(f"порог NP(LIQUID) {raschet.NOL_DOLI:g}; набор {a.nabor}; "
          f"пределы шапки {'ВЫКЛ' if a.bez_granic else 'вкл'}; "
          f"режим {'сверка с заморозкой' if proverka else 'счёт'}")

    nuzhnye = {m.strip() for m in a.marki.split(",") if m.strip()}
    stroki = [r for r in csv.DictReader(open(a.csv, encoding="utf-8", newline=""))
              if r["sostav_kolonok_w"] == "v_reshatel"
              and (not nuzhnye or r["marka"] in nuzhnye or r["klyuch_zamorozki"] in nuzhnye)
              and (r["status_v_sloe"] == "schitaetsya" or a.bez_granic)]
    bazy, vyvod, plohih = {}, [], 0
    for r in stroki:
        baza = r["baza_zamorozki"] or r["baza_sloya_segodnya"]
        if baza not in tdb:
            continue
        if baza not in bazy:
            bazy[baza] = zagruzit_bazu(tdb[baza], pochinka)
            print(f"база {baza}: {tdb[baza]} sha256 {bazy[baza][1]}")
        db, sha = bazy[baza]
        mass = {k[2:]: float(v) for k, v in r.items() if k.startswith("w_") and v}

        opis = copy.copy(gr.BAZY[baza])
        if a.bez_granic:
            opis.predely_mass = {}
            opis.molnaya_dolya_osnovy_ne_menee = None
        if a.nabor == "polnyj":
            opis.bystryj_nabor_faz = tuple(raschet._aktivnye_fazy(db, sorted(mass) + ["VA"], opis))
        # Строка, замороженная сниженной сеткой, пересчитывается той же сеткой.
        raschet.PDENS_NAVYAZANNYJ = None if int(r["pdens"] or 200) >= 200 else int(r["pdens"])
        staraya = gr.BAZY[baza]
        gr.BAZY[baza] = opis
        raschet._KESH_BAZ[baza] = db
        t0 = time.time()
        try:
            res = raschet.solidus_likvidus(mass, baza_klyuch=baza)
        finally:
            gr.BAZY[baza] = staraya
        s = dict(marka=r["marka"], klyuch_zamorozki=r["klyuch_zamorozki"], baza=baza,
                 sha256_tdb=sha, porog=raschet.NOL_DOLI, nabor=a.nabor,
                 pdens=raschet.plotnost_setki(opis), vremya_s=round(time.time() - t0, 1),
                 T_sol_zamorozka_K=r["T_sol_K"], T_liq_zamorozka_K=r["T_liq_K"])
        if isinstance(res, raschet.Otkaz):
            s.update(otkaz=res.kod, prichina=res.prichina)
            itog = f"ОТКАЗ {res.kod}"
        else:
            s.update(T_sol_K=res.solidus_K, T_liq_K=res.likvidus_K,
                     polnyj_nabor_ponadobilsya=res.polnyj_nabor_ponadobilsya,
                     nabor_faz=" ".join(res.nabor_faz),
                     fazy_pod_solidusom=" ".join(res.fazy_pod_solidusom),
                     zamechaniya=" | ".join(res.zamechaniya))
            itog = f"{res.solidus_K} / {res.likvidus_K} K"
            try:
                ds = round(res.solidus_K - float(r["T_sol_K"]), 2)
                dl = round(res.likvidus_K - float(r["T_liq_K"]), 2)
                s.update(dT_sol_K=ds, dT_liq_K=dl)
                itog += f"; к заморозке {ds:+} / {dl:+} K"
                if proverka and max(abs(ds), abs(dl)) > a.dopusk:
                    plohih += 1
                    itog += "  <-- РАСХОЖДЕНИЕ"
            except ValueError:
                pass
        print(f"{r['marka']:32} {baza:8} {s['vremya_s']:7.1f} с  {itog}", flush=True)
        vyvod.append(s)

    if a.vyvod:
        polya = list(dict.fromkeys(k for s in vyvod for k in s))
        with open(a.vyvod, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, polya, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
            w.writeheader()
            w.writerows(vyvod)
    if not vyvod:
        print("ни одной строки не посчитано: проверьте --tdb и --marki")
        return 2
    if proverka:
        print(f"сверка: {len(vyvod) - plohih} из {len(vyvod)} в пределах {a.dopusk} K")
    return 1 if plohih else 0


if __name__ == "__main__":
    sys.exit(main())
