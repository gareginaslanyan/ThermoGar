#!/usr/bin/env python3
"""Волна 16, задача 16-В — плотность против датащитов «Лилит».

Отчёт ``tasks/WAVE16_V_REPORT.md``. Входы — пакет «Лилит» ``tasks/lilith_16A/``:
``plotnosti_izmerennye.csv`` (плотности датащитов), ``marki_16A.csv`` (составы, столбцы
``w_*`` — элементы, поданные решателю, как в 16-А).

Цепочка — вкладка «Плотность» приложения: ``make_physical_inputs`` →
``prepare_feature_request`` → ``acquire_execution`` → ``execute_verified_physical`` →
бэкенд (``buildable_phases``, ``equilibrium``, ``calculate_physical_properties``,
``physical_projection``). Базы — привязка приложения ``bind_selected_database``
(файлы ``*_with_mobility``, Fe — слитый файл с патчем ``thermogar_patch``), PDB —
``physical_data_v103.pdb``. Бэкенд — копия ``_default_backend`` с двумя отличиями:
``pdens`` 50 по заданию (во вкладке 500) и запись служебных сведений (доля фаз с
оценкой по правилу смеси, вызовы ``DTCRBCC``) — на расчёт они не влияют.

Варианты на марку:

* ``A``  — быстрый набор приложения (``compatible_phases_for_components`` с
  ``PHASE_MODE_FAST``, режим стали ``metastable``, как в 16-А), поправки PDB включены;
* ``A0`` — то же, поправки выключены галочкой BL-14 (``physical_overrides=False``);
* ``B``  — полный набор: автоматические фазы вкладки (все допустимые политикой);
* ``C``  — одна матричная фаза: FCC_A1 (Al, Ni, 316L), BCC_A2 (17-4 PH, 18Ni300;
  мартенсит приближён ферритом);
* ``D``  — правило смеси по элементам ``estimate_density_by_mixture``, без равновесия.

Температура: 20 °C по заданию и 25 °C — нижняя граница DP-параметров PDB (298,15 K);
при 20 °C вкладка отказывает (см. отчёт, отступление 1).

Шаги::

    set THERMOGAR_STATE_ROOT=D:\\Pets\\ThermoGar\\results\\validation\\wave16_v_state
    .venv-windows\\Scripts\\python.exe -B -X utf8 tools\\study_wave16_v_plotnost.py run
    ... table          # 16V_plotnost.csv и 16V_sravnenie.md из raw/, без счёта

18-А: тот же сценарий с ``--out-dir results\\wave18_a`` (до подкоманды) — 16-В не
перезаписывается; вариант D берёт эталонные фазы элементов из TDB (BL-47).

Память: вход — ``--min-free-gib`` (3,0); аварийный — ``E1_ABORT_FREE_GIB`` модуля
волны 12, читается из исходника и не меняется. Один расчётный поток: задания идут
по одному, каждое — отдельным процессом под сторожем 16-А.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import time
import traceback
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
APP = ROOT / "app"
PAKET = ROOT / "tasks" / "lilith_16A"
PLOTNOSTI_CSV = PAKET / "plotnosti_izmerennye.csv"
OUT = ROOT / "results" / "wave16_v"
RAW = OUT / "raw"
LOGS = OUT / "logs"
STATE_ROOT_DEFAULT = ROOT / "results" / "validation" / "wave16_v_state"

for _entry in (APP, TOOLS):
    if str(_entry) not in sys.path:
        sys.path.insert(0, str(_entry))

import study_wave16_a_lilith as a16  # noqa: E402  составы, шапка, сторож памяти

SISTEMY = {
    "Al": {"key": "al", "balance": "AL", "baza": "mc_al 2.037", "lilit_key": "mc_al"},
    "Ni": {"key": "ni", "balance": "NI", "baza": "mc_ni 2.036", "lilit_key": "mc_ni"},
    "Fe": {"key": "fe", "balance": "FE", "baza": "mc_fe 2.062 thermogar_patch (слитый)",
           "lilit_key": "mc_fe"},
}
MARKI = ("RS320", "AlSi10Mg", "VJ159", "IN718", "17-4 PH", "18Ni300", "316L")
MATRICA = {"RS320": "FCC_A1", "AlSi10Mg": "FCC_A1", "VJ159": "FCC_A1", "IN718": "FCC_A1",
           "316L": "FCC_A1", "17-4 PH": "BCC_A2", "18Ni300": "BCC_A2"}
NE_SCHITAT = {
    "Copper": "нет Cu-базы",
    "CuCrZr": "нет Cu-базы",
    "Ti6Al4V": "нет Ti-базы",
    "IN738": "в mc_ni нет Ta: 1,75 % Ta без замены не считается",
}
VARIANTY = ("A", "A0", "B", "C", "D")
NABOR = {"A": "быстрый", "A0": "быстрый", "B": "полный (автоматические фазы вкладки)",
         "D": "нет (правило смеси по элементам)"}
TEMPERATURY_K = (293.15, 298.15)
PDENS = 50
POROG_LILIT_PCT = 1.0
STEEL_MODE = "metastable"
DTCRBCC = "DTCRBCC"


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def nabor_label(marka: str, variant: str) -> str:
    if variant == "C":
        faza = MATRICA[marka]
        extra = " (мартенсит приближён ферритом BCC_A2)" if faza == "BCC_A2" else ""
        return f"одна фаза {faza}{extra}"
    return NABOR[variant]


def job_id(job: dict[str, Any]) -> str:
    text = json.dumps({k: job[k] for k in ("marka", "variant", "temperatury_K", "pdens")},
                      ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def plan() -> list[dict[str, Any]]:
    jobs = []
    for marka in MARKI:
        for variant in VARIANTY:
            job = {"marka": marka, "variant": variant,
                   "temperatury_K": list(TEMPERATURY_K), "pdens": PDENS}
            job["id"] = job_id(job)
            jobs.append(job)
    return jobs


def read_plotnosti() -> dict[str, dict[str, str]]:
    with PLOTNOSTI_CSV.open(encoding="utf-8-sig", newline="") as handle:
        return {row["marka"]: row for row in csv.DictReader(handle)}


def marka_row(marka: str) -> dict[str, str]:
    with a16.MARKI_CSV.open(encoding="utf-8", newline="") as handle:
        return next(r for r in csv.DictReader(handle) if r["marka"] == marka)


# --------------------------------------------------------------------------- #
# Потомок: одна марка, один вариант, обе температуры
# --------------------------------------------------------------------------- #


def bind(sistema: str):
    import thermogar_verified_loaders as vl
    from thermogar_paths import ThermoGarPaths

    paths = ThermoGarPaths()
    paths.configure_process_environment()
    # Тот же разбор объявлений PHASE, что _verified_tdb_declared_phases приложения.
    declaration = re.compile(r"(?m)^\s*PHASE\s+([A-Z][A-Z0-9_]*)\s")
    catalog = vl.ArtifactCatalog.from_policy(
        ROOT, vl.canonical_release_manifest(),
        phase_provider=lambda a: tuple(sorted(set(declaration.findall(a.verified_text())))),
    )
    selector: dict[str, Any] = {"database_key": SISTEMY[sistema]["key"],
                                "include_physical_pdb": True}
    if sistema == "Fe":
        selector["profile_key"] = "thermogar_patch"
    return vl.bind_selected_database(selector, catalog, paths), paths


def tdb_spec(key: str) -> tuple[str, str]:
    import thermogar_verified_loaders as vl

    spec = vl.canonical_release_manifest()["databases"][key]["tdb"]
    return spec["logical_path"], spec["sha256"]


def fast_phases(sistema: str, entered: dict[str, float]) -> list[str]:
    """Быстрый набор приложения: compatible_phases_for_components(PHASE_MODE_FAST)."""

    ns = a16.app_namespace()
    key = SISTEMY[sistema]["key"]
    path, sha = tdb_spec(key)
    data = (ROOT / path).read_bytes()
    if hashlib.sha256(data).hexdigest() != sha:
        raise RuntimeError(f"{path}: sha256 не совпал с политикой приложения")
    db = ns["_parse_database_snapshot"](sha, sha, data)
    available = sorted(el for el in db.elements if el != "VA")
    components, _, _, _ = ns["build_input"](db, available, entered, "wt",
                                            SISTEMY[sistema]["balance"])
    return list(ns["compatible_phases_for_components"](
        db, key, components, STEEL_MODE, ns["PHASE_MODE_FAST"]))


def child(job: dict[str, Any], out_path: Path) -> None:
    import thermogar_physical as physical
    import thermogar_verified_loaders as vl
    import thermogar_verified_physical as vp

    started = time.perf_counter()
    result: dict[str, Any] = {"job": job, "status": "ok", "tochki": []}
    try:
        marka, variant = job["marka"], job["variant"]
        row = marka_row(marka)
        sistema = row["sistema"]
        balance = SISTEMY[sistema]["balance"]
        mass = a16.sostav_mass(row)
        entered = {el: val for el, val in mass.items() if el != balance}
        result["sostav_wt_pct"] = mass
        context, paths = bind(sistema)
        path, sha = tdb_spec(SISTEMY[sistema]["key"])
        result["tdb"] = {"fajl": path, "sha256": sha}
        result["pdb_sha256"] = context.physical_pdb.sha256
        eligible = tuple(context.phase_policy.eligible_phases)

        if variant in ("A", "A0"):
            requested = tuple(fast_phases(sistema, entered))
        elif variant == "C":
            requested = (MATRICA[marka],)
        else:
            requested = ()
        result["zaprosheny_fazy"] = list(requested)

        for temperature_k in job["temperatury_K"]:
            t0 = time.perf_counter()
            tochka: dict[str, Any] = {"T_K": temperature_k}
            try:
                if variant == "D":
                    tochka.update(mixture_point(context, entered, balance, temperature_k))
                else:
                    tochka.update(verified_point(
                        vl, vp, physical, context, paths, entered, balance, temperature_k,
                        requested, eligible, overrides=(variant != "A0")))
            except Exception as error:
                tochka["otkaz"] = f"{type(error).__name__}: {error}"
            tochka["vremya_s"] = time.perf_counter() - t0
            result["tochki"].append(tochka)
    except Exception as error:
        result["status"] = "oshibka"
        result["oshibka"] = f"{type(error).__name__}: {error}"
        result["traceback"] = traceback.format_exc()
    result["vsego_s"] = time.perf_counter() - started
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=1, default=str), "utf-8")


def verified_point(vl, vp, physical, context, paths, entered, balance, temperature_k,
                   requested, eligible, *, overrides: bool) -> dict[str, Any]:
    inputs = vp.make_physical_inputs(
        "property_density_single", balance=balance, units="wt",
        composition_pct=dict(entered), pressure_pa=101325.0,
        temperatures_k=(float(temperature_k),))
    decision = vl.prepare_feature_request(
        "property_density_single", context, inputs, requested, candidate_phases=eligible)
    if type(decision) is not vl.FeatureRequest:
        raise RuntimeError(f"запрос отклонён: {decision}")
    service: dict[str, Any] = {}

    def backend(database, physical_database, call):
        # Копия _default_backend приложения; отличия — pdens и служебная запись.
        from pycalphad import equilibrium, variables as v

        conditions = {v.N: 1.0, v.P: call.pressure_pa, v.T: call.temperature_k}
        conditions.update({v.X(el): x for el, x in call.atomic_fractions
                           if el != call.balance})
        missing = vp._elements_absent_from(database, call.components)
        if missing:
            raise ValueError("база не описывает элементы: " + ", ".join(missing))
        phases, removed = vp.buildable_phases(database, call.components, call.phases)
        service["fazy_v_raschete"] = list(phases)
        service["snyato_detektorom"] = sorted(removed)
        calls: list[float] = []
        original = physical_database.function_value

        def watched(name, t):
            if str(name).upper() == DTCRBCC:
                calls.append(float(t))
            return original(name, t)

        physical_database.function_value = watched
        try:
            eq = equilibrium(database, list(call.components), list(phases), conditions,
                             calc_opts={"pdens": PDENS})
            res = physical.calculate_physical_properties(
                database, eq, list(call.components), call.temperature_k, physical_database)
        finally:
            del physical_database.function_value
        service["estimated_mole_pct"] = float(res.estimated_mole_pct)
        service["dtcrbcc_vyzovov"] = len(calls)
        service["dtcrbcc_znachenie"] = (
            original(DTCRBCC, call.temperature_k) if calls else None)
        service["popravki_primeneny"] = [e.name for e in physical_database.applied_overrides]
        service["popravki_vyklyucheny"] = [
            e.name for e in physical_database.suppressed_overrides]
        return vp.physical_projection(res, excluded_phases=removed)

    with vl.acquire_execution(decision, paths) as lease:
        execution = vp.execute_verified_physical(
            context, decision, lease, backend=backend, physical_overrides=overrides)
    return {"effektivnye_fazy": list(decision.effective_phases),
            "proekciya": execution.points[0].projection, **service}


def mixture_point(context, entered, balance, temperature_k) -> dict[str, Any]:
    """Правило смеси по элементам всего состава; PDB и массы — те же, что во вкладке."""

    import thermogar_physical as physical
    import thermogar_verified_physical as vp

    pdb_path = ROOT / context.physical_pdb.logical_path
    data = pdb_path.read_bytes()
    if hashlib.sha256(data).hexdigest() != context.physical_pdb.sha256:
        raise RuntimeError("PDB: sha256 не совпал с привязкой")
    pdb = physical.PhysicalDensityDatabase.from_verified_bytes(data)
    tdb_path, tdb_sha = tdb_spec(context.database_key)
    tdb_bytes = (ROOT / tdb_path).read_bytes()
    if hashlib.sha256(tdb_bytes).hexdigest() != tdb_sha:
        raise RuntimeError("TDB: sha256 не совпал с политикой")
    from pycalphad import Database

    database = Database(tdb_bytes.decode("utf-8"))
    inputs = vp.make_physical_inputs(
        "property_density_single", balance=balance, units="wt",
        composition_pct=dict(entered), pressure_pa=101325.0,
        temperatures_k=(float(temperature_k),))
    atomic, _mass = vp.composition_fractions(database, inputs)
    masses = vp._database_masses(database, [el for el, _ in atomic])
    # 18-А (BL-47): эталонные фазы элементов из той же TDB, как в приложении.
    references = physical.element_reference_phases(database)
    density, coverage, notes = pdb.estimate_density_by_mixture(
        dict(atomic), float(temperature_k), masses, references)
    notes = list(notes) + pdb.mixture_element_notes(
        dict(atomic), float(temperature_k), references)
    out = {"plotnost_kg_m3": density, "pokrytie_mass_pct": 100.0 * coverage,
           "predupr": notes + list(pdb.override_notes)}
    if density is None:
        out["otkaz"] = "правило смеси не дало плотности: " + "; ".join(notes)
    return out


# --------------------------------------------------------------------------- #
# Родитель
# --------------------------------------------------------------------------- #


def run_job(job: dict[str, Any], args, abort_gib: float) -> dict[str, Any]:
    free = a16.wait_for_memory(args.min_free_gib)
    if free is None:
        return {"job": job, "status": "net_pamyati"}
    child_out = RAW / f"{job['id']}.child.json"
    if child_out.exists():
        child_out.unlink()
    command = [sys.executable, "-B", "-X", "utf8", str(Path(__file__).resolve()), "child",
               "--job", json.dumps(job, ensure_ascii=False), "--out", str(child_out)]
    record = a16.run_process(command, LOGS / f"{job['id']}.log", abort_gib, args.limit_s)
    record["porog_vhoda_GiB"] = args.min_free_gib
    if record.get("snyat"):
        return {"job": job, "status": "snyat_po_pamyati", "popytka": record}
    if record.get("timeout"):
        return {"job": job, "status": "timeout", "popytka": record}
    if not child_out.is_file():
        tail = (LOGS / f"{job['id']}.log").read_text("utf-8", errors="replace")[-3000:]
        return {"job": job, "status": "oshibka", "popytka": record,
                "oshibka": f"потомок завершился с кодом {record['kod']} без результата",
                "traceback": tail}
    data = json.loads(child_out.read_text("utf-8"))
    child_out.unlink()
    data["popytka"] = record
    return data


def command_run(args) -> None:
    os.environ.setdefault("THERMOGAR_STATE_ROOT", str(STATE_ROOT_DEFAULT))
    Path(os.environ["THERMOGAR_STATE_ROOT"]).mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    abort_gib = a16.abort_free_gib()
    jobs = plan()
    if args.only_marki:
        wanted = {m.strip() for m in args.only_marki.split(";") if m.strip()}
        jobs = [j for j in jobs if j["marka"] in wanted]
    if args.variant:
        jobs = [j for j in jobs if j["variant"] in args.variant.split(",")]
    todo = [j for j in jobs if not (RAW / f"{j['id']}.json").is_file()
            or json.loads((RAW / f"{j['id']}.json").read_text("utf-8")).get("status")
            == "net_pamyati"]
    log(f"заданий {len(jobs)}, из кэша {len(jobs) - len(todo)}, считать {len(todo)}; "
        f"вход {args.min_free_gib:.1f} ГиБ, аварийный {abort_gib:.1f} ГиБ, "
        f"лимит {args.limit_s:.0f} с")
    for index, job in enumerate(todo, 1):
        log(f"{index}/{len(todo)} {job['marka']} · {job['variant']}")
        data = run_job(job, args, abort_gib)
        (RAW / f"{job['id']}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=1, default=str), "utf-8")
        brief = []
        for t in data.get("tochki", []):
            rho = (t.get("proekciya") or {}).get("alloy_density_kg_m3", t.get("plotnost_kg_m3"))
            brief.append(f"{t['T_K']:.2f} K: {rho if rho is not None else t.get('otkaz', '')[:80]}")
        rec = data.get("popytka", {})
        log(f"   {data.get('status')} · {' ; '.join(brief)} · {rec.get('sekund', 0):.0f} с · "
            f"пик {rec.get('pik_MiB', 0):.0f} МиБ")


# --------------------------------------------------------------------------- #
# Таблица и сравнение
# --------------------------------------------------------------------------- #

COLUMNS = (
    "marka", "sistema", "baza", "fajl_tdb", "sha256_tdb", "variant", "nabor", "popravki",
    "T_C", "plotnost_kg_m3", "plotnost_datashit_g_sm3", "otklonenie_pct",
    "pokrytie_mass_pct", "dolya_pryamyh", "dolya_unasledovannyh", "dolya_ocenennyh",
    "fazy_i_obemnye_doli", "fazy_bez_modeli", "predupr", "popravka_zadejstvovana",
    "vne_shapki", "vremya_s", "pik_pamyati_MiB", "otkaz", "prichina", "job_id",
)


def fmt(value: Any, digits: int) -> str:
    if value in (None, ""):
        return ""
    return f"{float(value):.{digits}f}"


def popravki_label(variant: str) -> str:
    if variant == "A0":
        return "выключены (BL-14, physical_overrides=False)"
    return "включены (умолчание)"


def korotko(text: str, limit: int = 160) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def build_rows() -> list[dict[str, Any]]:
    plotnosti = read_plotnosti()
    shapka: dict[str, str] = {}
    rows: list[dict[str, Any]] = []
    for job in plan():
        path = RAW / f"{job['id']}.json"
        if not path.is_file():
            continue
        data = json.loads(path.read_text("utf-8"))
        marka, variant = job["marka"], job["variant"]
        row = marka_row(marka)
        sistema = row["sistema"]
        if marka not in shapka:
            shapka[marka] = a16.vne_predelov(row, SISTEMY[sistema]["lilit_key"])
        ds = float(plotnosti[marka]["plotnost_g_sm3"])
        rec = data.get("popytka", {})
        base = {
            "marka": marka, "sistema": sistema, "baza": SISTEMY[sistema]["baza"],
            "fajl_tdb": (data.get("tdb") or {}).get("fajl", ""),
            "sha256_tdb": (data.get("tdb") or {}).get("sha256", ""),
            "variant": variant, "nabor": nabor_label(marka, variant),
            "popravki": popravki_label(variant), "plotnost_datashit_g_sm3": f"{ds:g}",
            "vne_shapki": shapka[marka], "pik_pamyati_MiB": fmt(rec.get("pik_MiB"), 0),
            "job_id": job["id"],
        }
        tochki = data.get("tochki") or []
        if not tochki:
            out = dict(base, otkaz=data.get("status"),
                       prichina=korotko(data.get("oshibka", ""), 400),
                       vremya_s=fmt(rec.get("sekund"), 1))
            rows.append(out)
            continue
        for t in tochki:
            out = dict(base, T_C=fmt(t["T_K"] - 273.15, 0), vremya_s=fmt(t.get("vremya_s"), 1))
            pr = t.get("proekciya")
            if pr is not None:
                rho = pr["alloy_density_kg_m3"]
                total = sum(float(r["Мольная доля, %"]) for r in pr["phase_rows"]) or 1.0
                fazy = []
                for r in sorted(pr["phase_rows"], key=lambda r: -float(r["Мольная доля, %"])):
                    vol = r.get("Объёмная доля, %")
                    fazy.append(f"{r['Фаза']} {float(vol):.2f}" if vol is not None
                                else f"{r['Фаза']} — (мол. {float(r['Мольная доля, %']):.2f})")
                bez = sorted({str(r.get("Фаза") or r.get("phase") or "")
                              for r in pr["missing_rows"]} - {""})
                bez += [r["Фаза"] for r in pr["phase_rows"]
                        if r.get("Статус данных") == "нет данных" and r["Фаза"] not in bez]
                est = t.get("estimated_mole_pct", 0.0)
                out.update({
                    "plotnost_kg_m3": fmt(rho, 3),
                    "pokrytie_mass_pct": fmt(pr["mass_coverage_pct"], 2),
                    "dolya_pryamyh": fmt(pr["direct_mole_pct"], 2),
                    "dolya_unasledovannyh": fmt(pr["inherited_mole_pct"], 2),
                    "dolya_ocenennyh": fmt(est, 2),
                    "fazy_i_obemnye_doli": "; ".join(fazy),
                    "fazy_bez_modeli": " ".join(bez),
                    "predupr": " | ".join(korotko(w) for w in pr["warnings"]),
                    "popravka_zadejstvovana": (
                        f"да: DTCRBCC вычислена {t['dtcrbcc_vyzovov']} раз"
                        if t.get("dtcrbcc_vyzovov") else "нет"),
                })
                del total
            elif t.get("plotnost_kg_m3") is not None:
                rho = t["plotnost_kg_m3"]
                out.update({"plotnost_kg_m3": fmt(rho, 3),
                            "pokrytie_mass_pct": fmt(t.get("pokrytie_mass_pct"), 2),
                            "predupr": " | ".join(korotko(w) for w in t.get("predupr", []))})
            else:
                rho = None
            if rho is not None:
                out["otklonenie_pct"] = f"{(rho / 1000.0 - ds) / ds * 100.0:+.2f}"
            if t.get("otkaz"):
                out["otkaz"] = "да"
                out["prichina"] = korotko(t["otkaz"], 400)
            elif rho is None and pr is not None and not pr["phase_rows"]:
                out["otkaz"] = "да"
                out["prichina"] = ("равновесие не дало ни одной фазы (решатель pycalphad при "
                                   f"pdens {PDENS} не сошёлся), плотности нет")
            elif rho is None:
                out["otkaz"] = "да"
                out["prichina"] = ("плотность сплава не рассчитана: покрытие PDB < 100 %, "
                                   "без модели: " + out.get("fazy_bez_modeli", ""))
            rows.append(out)
    for marka, prichina in NE_SCHITAT.items():
        p = plotnosti[marka]
        rows.append({"marka": marka, "sistema": p["sistema"],
                     "plotnost_datashit_g_sm3": p["plotnost_g_sm3"], "otkaz": "не считается",
                     "prichina": prichina})
    return rows


def command_table(args) -> None:
    rows = build_rows()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "16V_plotnost.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, COLUMNS, quoting=csv.QUOTE_ALL, lineterminator="\r\n",
                                extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    log(f"{path}: строк {len(rows)}")
    lines = proverka_a0()
    (OUT / "16V_proverka_A_A0.txt").write_text("\n".join(lines) + "\n", "utf-8")
    for line in lines:
        log(line)


def proverka_a0(rows: list[dict[str, Any]] | None = None) -> list[str]:
    """Ожидание задания: A0 и A различаются только там, где поправка задействована.

    Сравнение по сырым числам raw/: плотность сплава и плотности фаз (у 18Ni300 и
    316L плотности сплава нет — покрытие PDB < 100 %). «Задействована» — функция
    DTCRBCC вычислялась в расчёте варианта A.
    """

    raw = {(j["marka"], j["variant"]): json.loads((RAW / f"{j['id']}.json").read_text("utf-8"))
           for j in plan() if j["variant"] in ("A", "A0") and (RAW / f"{j['id']}.json").is_file()}
    out = []
    for marka in MARKI:
        if (marka, "A") not in raw or (marka, "A0") not in raw:
            continue
        for ta, t0 in zip(raw[(marka, "A")]["tochki"], raw[(marka, "A0")]["tochki"]):
            pa, p0 = ta.get("proekciya"), t0.get("proekciya")
            tc = ta["T_K"] - 273.15
            if pa is None or p0 is None:
                out.append(f"A−A0 {marka} {tc:.0f} °C: нет результата (отказ) — не сравнивается")
                continue
            ra, r0 = pa["alloy_density_kg_m3"], p0["alloy_density_kg_m3"]
            d_alloy = (ra - r0) if ra is not None and r0 is not None else None
            fa = {r["Фаза"]: r["Плотность фазы, кг/м³"] for r in pa["phase_rows"]}
            f0 = {r["Фаза"]: r["Плотность фазы, кг/м³"] for r in p0["phase_rows"]}
            d_phase = max((abs(fa[k] - f0[k]) for k in fa if k in f0
                           and fa[k] is not None and f0[k] is not None), default=0.0)
            engaged = bool(ta.get("dtcrbcc_vyzovov"))
            differ = (d_alloy not in (None, 0.0)) or d_phase > 0.0
            verdict = "СТОП" if differ and not engaged else "ok"
            out.append(
                f"A−A0 {marka} {tc:.0f} °C: сплав "
                f"{'—' if d_alloy is None else f'{d_alloy:+.6f}'} кг/м³, фазы max "
                f"{d_phase:.6f} кг/м³, DTCRBCC {'вычислялась' if engaged else 'не вычислялась'}"
                f" — {verdict}")
    return out


def command_child(args) -> None:
    child(json.loads(args.job), Path(args.out))


def main() -> None:
    global OUT, RAW, LOGS
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out-dir", default="",
                        help="каталог результатов вместо results/wave16_v (18-А: results/wave18_a)")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--only-marki", default="", help="через ;")
    run.add_argument("--variant", default="", help="через запятую")
    run.add_argument("--min-free-gib", type=float, default=3.0)
    run.add_argument("--limit-s", type=float, default=3600.0)
    ch = sub.add_parser("child")
    ch.add_argument("--job", required=True)
    ch.add_argument("--out", required=True)
    sub.add_parser("table")
    args = parser.parse_args()
    if args.out_dir:
        OUT = Path(args.out_dir).resolve()
        RAW, LOGS = OUT / "raw", OUT / "logs"
    {"run": command_run, "child": command_child, "table": command_table}[args.command](args)


if __name__ == "__main__":
    main()
