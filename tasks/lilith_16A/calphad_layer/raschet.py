"""APP-304: солидус и ликвидус из произвольного химсостава (CALPHAD).

Что слой делает:
  solidus_likvidus({"Fe": 70.05, "Cr": 18, "Ni": 10, ...})
      -> Rezultat(solidus_K=..., likvidus_K=..., ...)  либо  Otkaz(...)

Чего слой НЕ делает и делать не будет: плотности, теплопроводности и
электросопротивления. В открытых TDB объёмных и транспортных параметров нет
вообще (проверено: `grep -c "PARAMETER V0\\|PARAMETER VS(\\|PARAMETER THCD"`
по всем трём базам даёт 0) — это товар платных TCFE/TCNI. Вывод APP-299,
подтверждён здесь.

Метод. Доля жидкости NP(LIQUID) при P=101325, N=1 и заданных мольных долях.
Солидус — температура появления жидкости, ликвидус — исчезновения твёрдого.
Поиск в три прохода: грубый свип по всей области базы, частый свип по
найденному окну, добивка до заданной точности. Свипы векторизованы (один
вызов equilibrium на массив T) — это в разы дешевле поточечных вызовов.

Сторож набора фаз. Свипы идут по «быстрому» набору фаз базы (granicy.py),
иначе один расчёт стоит десятки секунд. Поэтому КАЖДЫЙ ответ проверяется
полным активным набором фаз в четырёх точках вокруг найденных границ. Не
подтвердилось — весь поиск повторяется полным набором, и это записывается
в ответ полем polnyj_nabor_ponadobilsya.

Охрана обязана быть ПОЛНОЙ (APP-322). Успех сторожа — это «все обязательные
фазы проверены И ни одна не оказалась стабильной», а не «среди тех, что
удалось посчитать, плохих не нашлось». Фаза, которую посчитать не удалось,
даёт отказ storozh_ne_proveril_fazy с её именем: число без охраны выдавать
нельзя, а видимая строка «НЕ ПРОВЕРЕНЫ» рядом с числом — не охрана.

Плотность сетки — одна политика на весь слой (APP-322). Слой сам её не
снижает: полная всегда, сниженную навязывает только лесенка предрасчёта
после ЗАМЕРЕННОГО отказа по памяти и только на базах, где эквивалентность
приёма доказана (BAZY_SO_SNIZHENNOJ_SETKOJ).
"""
import contextlib
import io
import math
import time
import warnings
from dataclasses import dataclass, field
from fractions import Fraction

from . import granicy as gr
from . import pochinka

# Порог, ниже которого доля фазы считается нулём. 1e-9 — уровень
# численного шума солвера pycalphad, замеренный на чистом железе.
NOL_DOLI = 1e-9

# Порог следа — в МОЛЬНОЙ доле, а не в массовой. Элементы ниже него
# отбрасываются из расчёта с громкой записью в замечания.
#
# Почему в мольной. Сначала порог был массовым (0.05 масс.%) — и провалился:
# у 316L углерод 0.02 масс.% попадал под отброс, а он двигает солидус на
# 6.8 K, то есть на половину допуска слоя (замерено: 1681.8 K с углеродом
# против 1688.8 K без). В мольных долях тот же углерод — 9.3e-4, то есть
# ВЫШЕ порога и остаётся, а сера 0.005 масс.% = 8.7e-5 отбрасывается.
#
# Зачем вообще отбрасывать. Цена равновесия растёт комбинаторно с числом
# компонентов: та же сталь с серой (9 компонентов) съедала всю память
# песочницы и падала, без серы (8) считалась за 36 с. Замерено, а не
# предположено.
PREDEL_SLEDOV_X = 5e-4

# Каскад свипов: каждый следующий шаг ищет только внутри окна, найденного
# предыдущим. Все свипы векторизованы (один вызов equilibrium на массив T) —
# накладные расходы вызова амортизируются, и это главный выигрыш по времени.
SHAGI_KASKADA_K = (100.0, 20.0, 4.0, 0.5, 0.25)

# Длина куска первого свипа (см. _iskat).
TOCHEK_V_KUSKE = 14

# Плотность выборки составов в equilibrium (calc_opts pdens).
#
# ПОЛНАЯ — та, на которой посчитано и аттестовано всё в APP-304/304а.
# ГРУБАЯ — вынужденная: у составов от девяти компонентов сетка при 200
# растёт так, что процесс убивает OOM даже в одиночку с потолком 6,5 ГБ
# (замерено; при 30 та же марка считается за 60 с и 1,5 ГБ). Приём
# допущен мастером ТОЛЬКО с доказательством эквивалентности — оно в
# proverki/attestaciya_setki.py, критерий |Δ| <= 2 K по обеим величинам.
#
# Плотность, которой посчитана точка, едет в ответе полем pdens_poiska и
# пишется в каждую строку предрасчёта: число, посчитанное грубой сеткой и
# не помеченное, — это непрослеживаемое число.
PDENS_POISKA_POLNAYA = 200
PDENS_POISKA_GRUBAYA = 30

# ОДНА ПОЛИТИКА СНИЖЕННОЙ СЕТКИ (APP-322, ревью Codex 09.08 раздел 5).
#
# Слой САМ сетку не снижает никогда. Полная — всегда, если сниженную не
# навязали снаружи. Навязывает её ровно одно место: лесенка
# predraschet.poschitat_v_otdelnom_processe, и только после ЗАМЕРЕННОГО
# отказа по памяти на полной сетке, в изолированном процессе с потолком.
#
# Что было до APP-322 и почему это дефект. Плотность выбиралась порогом по
# числу компонентов (KOMPONENTOV_DO_GRUBOJ = 7), база в решение не входила.
# Получались ДВЕ несовместимые политики на один вопрос: предрасчёт шёл
# лесенкой «полная -> OOM -> сниженная, и только на аттестованной базе», а
# прямой продуктовый путь (kesh.poluchit -> solidus_likvidus) снижал сетку
# заранее и на любой базе. То есть тяжёлый состав на COST507, где приём НЕ
# аттестован, получал pdens 30 молча — при том что комментарий ниже обещает
# ему честный отказ. Порог был к тому же не про физику, а про память
# песочницы APP-312б: на этой машине девятикомпонентный АКМ идёт на полной
# сетке за 4,0 ГБ, то есть порог отправлял на сниженную сетку и то, что
# прекрасно помещалось.
#
# None — «не навязано», слой берёт полную. Значение ставит только
# calphad_layer/odna_tochka.py по ключу командной строки.
PDENS_NAVYAZANNYJ = None

# Разрешение считать сниженной сеткой на базе, где она ЕЩЁ НЕ аттестована.
# Нужно ровно одному потребителю — самой аттестации (proverki/
# attestaciya_setki.py): без него список BAZY_SO_SNIZHENNOJ_SETKOJ стал бы
# замкнутым кругом (чтобы попасть в список, базу надо померить обеими
# сетками; чтобы померить сниженной, надо уже быть в списке). Тот же приём
# и та же оговорка, что у ключа bez-storozha: в боевом расчёте это
# выключено, и число, посчитанное с этим флагом, публиковать нельзя —
# оно материал доказательства, а не ответ слоя.
SETKA_TOLKO_DLYA_ATTESTACII = False

# БАЗЫ, НА КОТОРЫХ СНИЖЕННАЯ СЕТКА АТТЕСТОВАНА. Список — не удобство, а
# запрет: на базе, которой в этом списке нет, снижать сетку нельзя, и
# тяжёлая марка получает честный отказ «не хватило памяти» (требование
# мастера: отдельного, более мягкого порога ни у одной базы нет — не
# прошла, значит отказ). Список обязан совпадать с выводом
# proverki/attestaciya_setki.py — это стережёт сторож
# snizhennaya_setka_primenyaetsya_tolko_na_attestovannyh_bazah.
#
# cost507 в списке НЕТ, и это не пропуск. Довод APP-322 был такой: медных
# составов тяжелее шести компонентов в каталоге нет, сниженная сетка на этой
# базе не нужна и потому не аттестовывалась. APP-355 довод сузила, и это
# надо назвать вслух: с припиской COST507 основе AL на эту базу пошли и
# литейные Al-Si сплавы, а они тяжёлые — у AlSi10Mg (EOS) одиннадцать
# компонентов, десять после отброса свинца-следа. Полной сеткой он считается
# (замер APP-355: 837,5 / 866,5 K, pdens 200), но состав тяжелее может в
# память и не поместиться. Тогда он получит честный отказ «не хватило
# памяти», а НЕ молча посчитается сниженной сеткой: аттестации сниженной
# сетки на COST507 нет, и до неё этой базе снижать сетку нельзя.
BAZY_SO_SNIZHENNOJ_SETKOJ = ("mc_fe", "mc_al", "mc_ni")
TOCHNOST_K = 0.25


@dataclass(frozen=True)
class Otkaz:
    """Честный отказ. Никаких чисел: их нет, и подставлять их нельзя."""
    kod: str                     # машинный код причины
    prichina: str                # человеческая причина с числами
    chego_ne_hvataet: tuple = ()

    def __bool__(self):
        return False


# APP-368 п.3: сборка модели фаз в pycalphad не состоялась. Свой код, а не
# `net_bazy` и не `element_ne_pokryt`: база есть и элементы ею описаны —
# не строится именно МОДЕЛЬ на этом сочетании фаз и элементов.
MODEL_NE_POSTROENA = "model_ne_postroena"

# Элементы, которые в CALPHAD-базах сидят в отдельной (междоузельной)
# подрешётке. Их присутствие — самая частая причина, по которой связка
# «порядок/беспорядок» (BCC_B2 над BCC_A2) не собирается. Список нужен не
# для решения, а для того, чтобы отказ назвал подозреваемых поимённо.
VNEDRYONNYE = ("B", "C", "H", "N", "O")


def _iz_pycalphad(oshibka):
    """Исключение поднято кадром pycalphad, а не кодом слоя."""
    sled = oshibka.__traceback__
    while sled is not None:
        imya = sled.tb_frame.f_globals.get("__name__", "")
        if imya == "pycalphad" or imya.startswith("pycalphad."):
            return True
        sled = sled.tb_next
    return False


def _otkaz_model_ne_postroena(sostav_mass, oshibka):
    try:
        nayden = tuple(e for e in VNEDRYONNYE
                       if float(sostav_mass.get(e, sostav_mass.get(
                           e.lower(), 0)) or 0) > 0)
    except (AttributeError, TypeError, ValueError):
        nayden = ()
    hvost = (f" В составе есть внедрённые элементы: {', '.join(nayden)}."
             if nayden else "")
    ne_hvataet = ((f"описание фаз базы, совместимое с внедрёнными "
                   f"{', '.join(nayden)}",) if nayden else
                  ("модель фаз базы для этого состава",))
    return Otkaz(
        MODEL_NE_POSTROENA,
        f"CALPHAD-модель для этого состава не построена: "
        f"{type(oshibka).__name__}: {oshibka}.{hvost} Числа нет и "
        f"подставить его нельзя.",
        ne_hvataet)


@dataclass(frozen=True)
class Rezultat:
    solidus_K: float
    likvidus_K: float
    baza: str
    versiya_bazy: str
    licenziya_bazy: str
    sha256_bazy: str
    sostav_mass: dict
    tochnost_K: float
    pdens_poiska: int
    setka_polnaya: bool
    nabor_faz: tuple
    polnyj_nabor_ponadobilsya: bool
    fazy_pod_solidusom: tuple
    vremya_s: float
    istochnik: str = "CALPHAD"
    zamechaniya: tuple = field(default_factory=tuple)
    phase_guard_evidence: dict = field(default_factory=dict)

    def __bool__(self):
        return True

    @property
    def interval_K(self):
        return self.likvidus_K - self.solidus_K


# --------------------------------------------------------------------------
# Проверка границ
# --------------------------------------------------------------------------

def vybrat_bazu(sostav_mass):
    """Вернуть OpisanieBazy или Otkaz.

    У основы может быть НЕСКОЛЬКО баз (gr.BAZY_PO_OSNOVE). Тогда они
    пробуются по порядку, и берётся первая, чьи границы состав проходит.
    Порядок записан в granicy.py и не косметический: родная база основы
    стоит первой, поэтому состав, который она считает, считает по-прежнему
    она — приписка второй базы не двигает ни одного прежнего числа
    (APP-355, приписка COST507 основе AL).

    Если не подошла ни одна и баз было несколько, отказ НАЗЫВАЕТ КАЖДУЮ
    пробу со своей причиной. Иначе вышло бы вранье умолчанием: человек
    прочитал бы «база mc_al не содержит O» и не узнал, что вторая база
    основы тоже пробовалась и тоже отказала. Машинный код берётся от
    первой пробы — по родной базе основы, как и до APP-355.
    """
    osnova = gr.osnova_sostava(sostav_mass)
    klyuchi = gr.BAZY_PO_OSNOVE.get(osnova, ())
    if not klyuchi:
        if osnova in gr.OSNOVY_BEZ_BAZY:
            return Otkaz("net_bazy",
                         f"основа состава — {osnova}; "
                         f"{gr.OSNOVY_BEZ_BAZY[osnova]}",
                         (f"база для основы {osnova}",))
        return Otkaz("net_bazy",
                     f"основа состава — {osnova}; открытой базы для этой "
                     f"основы в слое нет (есть: "
                     f"{', '.join(sorted(gr.BAZY_PO_OSNOVE))})",
                     (f"база для основы {osnova}",))
    otkazy = []
    for klyuch in klyuchi:
        opis = gr.BAZY[klyuch]
        proverka = proverit_granicy(sostav_mass, opis)
        if not isinstance(proverka, Otkaz):
            return opis
        otkazy.append((opis, proverka))
    if len(otkazy) == 1:
        # База у основы одна: возвращается она сама, а отказ выдаст
        # вызывающий, разобрав границы. Так было до APP-355, и текст
        # отказа от появления второй базы у ДРУГОЙ основы не меняется.
        return otkazy[0][0]
    pervyj = otkazy[0][1]
    return Otkaz(
        pervyj.kod,
        f"основа состава — {osnova}, ни одна из баз этой основы состав не "
        f"берёт: " + "; ".join(f"{o.klyuch} — {p.prichina}"
                               for o, p in otkazy),
        pervyj.chego_ne_hvataet)


def _strict_mole_vector(molnye_doli, mass):
    """Validate, but never renormalize, the adapter-attested mole vector."""
    if not isinstance(molnye_doli, dict) or set(molnye_doli) != set(mass):
        return None
    try:
        vector = {element.upper(): float(value)
                  for element, value in molnye_doli.items()}
    except (TypeError, ValueError, OverflowError):
        return None
    if (set(vector) != set(mass)
            or any(not math.isfinite(value) or value <= 0
                   for value in vector.values())
            or not math.isclose(math.fsum(vector.values()), 1.0,
                                rel_tol=0.0, abs_tol=2e-15)):
        return None
    return vector


def _strict_exact_vector(exact, observed, target):
    """Bind exact rational authority to its binary64 solver transport."""
    if not isinstance(exact, dict) or set(exact) != set(observed):
        return None
    vector = {}
    for element, value in exact.items():
        if not isinstance(value, Fraction) or value <= 0:
            return None
        if float(value) != float(observed[element]):
            return None
        vector[element] = value
    if sum(vector.values(), Fraction(0, 1)) != target:
        return None
    return vector


def _strict_exact_transport_vector(exact, observed, target):
    """As above, but observed mapping may use lower/upper-case keys."""
    if not isinstance(observed, dict):
        return None
    try:
        normalized = {str(key).upper(): float(value)
                      for key, value in observed.items()}
    except (TypeError, ValueError, OverflowError):
        return None
    return _strict_exact_vector(exact, normalized, target)


def proverit_granicy(sostav_mass, opis, sohranit_sledi=False,
                     molnye_doli=None, exact_mass_percent=None,
                     exact_mole_fraction=None):
    """Вернуть (mass, zamechaniya) или Otkaz с названной причиной.

    В legacy-пути следовые элементы, вышедшие за предел оптимизации базы,
    ОТБРАСЫВАЮТСЯ
    из расчёта и громко записываются в замечания ответа. Почему так, а не
    отказ: у mc_fe предел по фосфору P<0.005 масс.%, а в любой реальной
    марочной стали P до 0.045 — строгий отказ закрыл бы слой для всех
    сталей сразу. Отбрасывание СЛЕДА (<= PREDEL_SLEDOV_MASS) — это
    модельное допущение, и оно едет вместе с числом, а не прячется.
    Всё, что крупнее следа, по-прежнему даёт честный отказ.

    ``sohranit_sledi=True`` — строгий вход APP-358 для фактического состава.
    Он не удаляет ни одного положительного компонента. Этот режим включается
    только lossless-адаптером после проверки COMPOSITION_INPUT_V1 и домена
    SUPPORT_MANIFEST_V1; legacy-вызовы сохраняют прежнее поведение.
    """
    mass_exact = x_exact = None
    if sohranit_sledi:
        # APP-358 уже создал и записал solver mass representation. Повторная
        # нормализация здесь была бы второй, скрытой трансформацией. Строгий
        # путь принимает только конечную положительную смесь с суммой 100 и
        # сохраняет переданные float-значения байт-в-байт как числа Python.
        try:
            mass = {e.upper(): float(w) for e, w in sostav_mass.items()
                    if float(w) > 0}
        except (TypeError, ValueError, OverflowError):
            return Otkaz(
                "strict_mass_invalid",
                "строгое расчётное представление содержит нечисловое или "
                "непредставимое значение",
                ("конечные положительные mass%",))
        if (not mass or len(mass) != len(sostav_mass)
                or any(not math.isfinite(w) for w in mass.values())):
            return Otkaz(
                "strict_mass_invalid",
                "строгое расчётное представление содержит ноль, отрицательное "
                "или неконечное значение",
                ("только конечные положительные mass%",))
        total = math.fsum(mass.values())
        if not math.isclose(total, 100.0, rel_tol=0.0, abs_tol=1e-10):
            return Otkaz(
                "strict_mass_not_normalized",
                "строгое расчётное представление не даёт 100 масс.% и не "
                "будет нормализовано внутри CALPHAD-слоя",
                ("явно нормализованное representation с reverse proof",))
        x_vse = _strict_mole_vector(molnye_doli, mass)
        if x_vse is None:
            return Otkaz(
                "strict_mole_invalid",
                "строгий путь требует полный конечный положительный мольный "
                "вектор того же representation; повторно вычислять его по "
                "другой таблице атомных масс запрещено",
                ("аттестованный mole_fraction vector",))
        exact_route = (exact_mass_percent is not None
                       or exact_mole_fraction is not None)
        if exact_route:
            mass_exact = _strict_exact_vector(
                exact_mass_percent, mass, Fraction(100, 1))
            x_exact = _strict_exact_vector(
                exact_mole_fraction, x_vse, Fraction(1, 1))
            if mass_exact is None or x_exact is None:
                return Otkaz(
                    "strict_exact_route_invalid",
                    "точные rational-векторы маршрута не связаны с "
                    "binary64-векторами решателя",
                    ("exact mass/mole route authority",))
        else:
            mass_exact = x_exact = None
    else:
        mass = gr.normirovat_mass(sostav_mass)
        try:
            x_vse = gr.v_molnye_doli(mass)
        except gr.NetAtomnojMassy as e:
            # Не падаем: незнакомый элемент — это честный отказ с именем
            # элемента, а не исключение посреди предрасчёта на 553 марки.
            return Otkaz(
                "net_atomnoj_massy",
                f"в таблице атомных масс слоя нет элемента(ов) {e.args[0]} — "
                f"мольные доли не считаются, состав в расчёт не берётся",
                tuple(str(e.args[0]).split(", ")))
    osnova_sost = max(
        mass_exact if sohranit_sledi and mass_exact is not None else mass,
        key=(mass_exact if sohranit_sledi and mass_exact is not None
             else mass).get)

    # Следы отбрасываются ПЕРВЫМ делом — до проверки покрытия.
    # Почему так, а не наоборот: в марочных составах ГОСТ сплошь попадаются
    # примеси вроде «церий не более 0,001» или «кальций не более 0,001».
    # Церия в открытых базах нет, и проверка «элемент не покрыт» первой
    # отказала бы почти каждой стали — с причиной, которая к делу не
    # относится: 0,001 масс.% церия это 4e-6 мольной доли, ниже порога
    # следа в сто раз. Порядок «сначала следы, потом покрытие» показывает
    # настоящую причину отказа, а не первую попавшуюся. Каждый отброс
    # по-прежнему называется поимённо в замечаниях ответа.
    otbrosheny = ([] if not sohranit_sledi else [
        "APP-358 strict: mass representation принято без повторной "
        f"нормализации; сохранены все {len(mass)} положительных компонента"])
    if not sohranit_sledi:
        for e in sorted(mass):
            if e != osnova_sost and x_vse[e] < PREDEL_SLEDOV_X:
                predel = opis.predely_mass.get(e)
                za_predelom = predel is not None and mass[e] >= predel
                otbrosheny.append(
                    f"{e} {mass[e]:.4g} масс.% (мольная доля {x_vse[e]:.2e}) "
                    f"отброшен из расчёта как след, порог {PREDEL_SLEDOV_X:g}"
                    + (f"; он и так вне предела оптимизации базы {opis.klyuch} "
                       f"(< {predel} масс.%)" if za_predelom else "")
                    + ("; в базе его нет вовсе" if e not in opis.elementy else ""))
        if otbrosheny:
            for stroka in otbrosheny:
                mass.pop(stroka.split()[0], None)
            mass = gr.normirovat_mass(mass)
            x_vse = gr.v_molnye_doli(mass)

    ne_pokryty = sorted(e for e in mass if e not in opis.elementy)
    if ne_pokryty:
        # Элемент, который в ФАЙЛЕ базы объявлен, а в перечень слоя взят не
        # был, отказывает по особой причине, и она обязана ехать вместе с
        # отказом (APP-355). Иначе человек, который видит этот элемент в
        # `pycalphad Database.elements`, прочтёт отказ как ошибку перечня и
        # «починит» его — а вместе с починкой снимет отказ, ради которого
        # элемент и выкинут (кислород COST507, REPORT_APP-354 §Б.5).
        osnovaniya = [f"{e}: {opis.elementy_ne_vzyaty_iz_fajla[e]}"
                      for e in ne_pokryty
                      if e in opis.elementy_ne_vzyaty_iz_fajla]
        return Otkaz(
            "element_ne_pokryt",
            f"база {opis.klyuch} v{opis.versiya} не содержит элемент(ы) "
            f"{', '.join(ne_pokryty)}; в базе есть только "
            f"{', '.join(sorted(opis.elementy))}"
            + ("; ВЗЯТ НЕ ИЗ ФАЙЛА НАМЕРЕННО — " + " ".join(osnovaniya)
               if osnovaniya else ""),
            tuple(ne_pokryty))

    vyshli = []
    for e, w in sorted(mass.items()):
        predel = opis.predely_mass.get(e)
        if predel is None:
            continue
        observed_mass = (mass_exact[e] if sohranit_sledi
                         and mass_exact is not None else w)
        outside = (observed_mass >= Fraction(str(predel))
                   if isinstance(observed_mass, Fraction)
                   else observed_mass >= predel)
        if outside:
            vyshli.append(f"{e} {w:.3g} масс.% при пределе оптимизации базы "
                          f"< {predel} масс.%")
    if vyshli:
        return Otkaz(
            "za_granicami_sostava",
            f"состав вне границ оптимизации базы {opis.klyuch} v{opis.versiya}: "
            + "; ".join(vyshli),
            tuple(vyshli))
    if opis.molnaya_dolya_osnovy_ne_menee is not None:
        x_osn = x_vse.get(opis.osnova, 0.0)
        if sohranit_sledi and x_exact is not None:
            exact_limit = Fraction(str(
                opis.molnaya_dolya_osnovy_ne_menee))
            outside = x_exact.get(opis.osnova, Fraction(0, 1)) <= exact_limit
        else:
            outside = x_osn < opis.molnaya_dolya_osnovy_ne_menee
        if outside:
            return Otkaz(
                "za_granicami_sostava",
                f"мольная доля основы {opis.osnova} = {x_osn:.4f}, а база "
                f"{opis.klyuch} v{opis.versiya} оптимизирована при "
                f"X({opis.osnova}) > {opis.molnaya_dolya_osnovy_ne_menee}",
                (f"X({opis.osnova}) >= {opis.molnaya_dolya_osnovy_ne_menee}",))
    return mass, tuple(otbrosheny)


# --------------------------------------------------------------------------
# Расчёт
# --------------------------------------------------------------------------

_KESH_BAZ = {}


def _zagruzit(opis):
    if opis.klyuch not in _KESH_BAZ:
        from pycalphad import Database
        # APP-502 п. 2 (в): парсер получает ТЕ ЖЕ байты, по которым взят
        # sha256 эффективной базы (pochinka.effektivnye_bajty читает
        # исходник один раз и чинит его в памяти). Раньше здесь стояло
        # `Database(путь)` — второе чтение с диска, уже после проверки
        # хеша: в этот зазор подставлялся любой файл.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            # StringIO(..., newline=None) — та же универсальная развёртка
            # переводов строки, что делал open() внутри Database(путь):
            # в mc_ni 10687 пар CRLF, и без развёртки парсер падает.
            # Байты при этом остаются теми, по которым взят sha256.
            tekst = pochinka.effektivnye_bajty(opis.fajl).decode("utf-8")
            _KESH_BAZ[opis.klyuch] = Database.from_file(
                io.StringIO(tekst, newline=None), fmt="tdb")
    return _KESH_BAZ[opis.klyuch]


def _aktivnye_fazy(db, komponenty, opis=None):
    """Активные фазы системы МИНУС явно исключённые (granicy.isklyuchennye_fazy)."""
    from pycalphad.core.utils import filter_phases, unpack_species
    vse = set(filter_phases(db, unpack_species(db, komponenty)))
    if opis is not None:
        vse -= set(opis.isklyuchennye_fazy)
    return sorted(vse)


def plotnost_setki(opis, navyazannyj=None):
    """Плотность сетки для этого расчёта. -> int или Otkaz.

    Решение принимает БАЗУ, а не число компонентов, и оно fail-closed:
    сниженная сетка допускается только на базах, где её эквивалентность
    доказана (BAZY_SO_SNIZHENNOJ_SETKOJ = вывод attestaciya_setki.py).
    На любой другой базе сниженная сетка отвергается — тяжёлая марка
    получает честный отказ по памяти, а не непрослеживаемое число.

    Сторож двусторонний, и вторая его половина живёт снаружи, в лесенке
    predraschet.poschitat_v_otdelnom_processe: она вообще не спускается на
    сниженную сетку вне списка аттестации. Внешней половины мало — прямой
    продуктовый путь шёл мимо неё, это и был дефект APP-322.
    """
    zapros = PDENS_NAVYAZANNYJ if navyazannyj is None else navyazannyj
    if zapros is None:
        return PDENS_POISKA_POLNAYA
    if zapros >= PDENS_POISKA_POLNAYA:
        return zapros
    baza = getattr(opis, "klyuch", None)
    if SETKA_TOLKO_DLYA_ATTESTACII:
        return zapros
    if baza not in BAZY_SO_SNIZHENNOJ_SETKOJ:
        return Otkaz(
            "setka_ne_attestovana",
            f"запрошена сниженная сетка pdens {zapros} вместо "
            f"{PDENS_POISKA_POLNAYA}, но на базе {baza} она НЕ аттестована "
            f"(доказательство эквивалентности есть только для "
            f"{', '.join(BAZY_SO_SNIZHENNOJ_SETKOJ)}, см. "
            f"proverki/attestaciya_setki.py, критерий |Δ| <= 2 K). Снижать "
            f"сетку без доказательства нельзя: это изменение метода, а не "
            f"настройка. Полная сетка на этом составе в память не "
            f"поместилась — значит честный отказ, а не число погрубее.",
            (f"аттестация сниженной сетки на базе {baza}",))
    return zapros


def _dolya_zhidkosti(db, komponenty, fazy, x, temperatury, pdens):
    """Доли жидкости и списки фаз для массива температур. Один вызов."""
    from pycalphad import equilibrium, variables as v
    osnova = max(x, key=x.get)
    usloviya = {v.P: 101325, v.N: 1, v.T: list(temperatury)}
    for e, xe in x.items():
        if e != osnova:
            usloviya[v.X(e)] = xe
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        eq = equilibrium(db, komponenty, list(fazy), usloviya,
                         calc_opts={"pdens": pdens})
    imena = eq.Phase.squeeze(drop=True).values
    doli = eq.NP.squeeze(drop=True).values
    if imena.ndim == 1:                      # одна температура
        imena, doli = imena[None, :], doli[None, :]
    out_fl, out_fazy = [], []
    for i in range(imena.shape[0]):
        pary = [(str(a), float(b)) for a, b in zip(imena[i], doli[i]) if str(a)]
        fl = sum(b for a, b in pary if a == "LIQUID")
        out_fl.append(fl)
        out_fazy.append(tuple(sorted({a for a, b in pary if b > NOL_DOLI})))
    return out_fl, out_fazy


def _granicy_po_svipu(temperatury, doli):
    """(окно солидуса, окно ликвидуса) по свипу; None, если не поймано."""
    sol = lik = None
    for i in range(len(temperatury) - 1):
        a, b = doli[i], doli[i + 1]
        if sol is None and a <= NOL_DOLI < b:
            sol = (temperatury[i], temperatury[i + 1])
        if a < 1.0 - NOL_DOLI <= b:
            lik = (temperatury[i], temperatury[i + 1])
    return sol, lik


def _svip(T_ot, T_do, shag):
    tochki, t = [], T_ot
    while t <= T_do + 1e-9:
        tochki.append(round(t, 4))
        t += shag
    if tochki[-1] < T_do - 1e-9:
        tochki.append(round(T_do, 4))
    return tochki


def _iskat(db, komponenty, fazy, x, T_min, T_max, tochnost, pdens):
    """Каскад свипов: 100 K -> 20 K -> 4 K -> 0.5 K по сужающимся окнам.

    Возвращает (солидус, ликвидус, фазы под солидусом) или None.
    """
    okno_s = okno_l = None
    fazy_pod_sol = ()
    lo, hi = float(T_min), float(T_max)
    for nomer, shag in enumerate(SHAGI_KASKADA_K):
        if shag < tochnost:
            break
        tochki = _svip(lo, hi, shag)
        if nomer == 0 and len(tochki) > TOCHEK_V_KUSKE:
            # Первый свип идёт по всей области базы, а у mc_al и COST507
            # она объявлена до 6000 K — это 58 точек, из которых полсотни
            # заведомо в жидкости. Считаем кусками и останавливаемся, как
            # только доля жидкости дошла до единицы: оба окна к этому
            # моменту уже найдены, дальше искать нечего. Точки те же, что
            # и при сплошном свипе, — экономится только хвост.
            fl, fz, tochki = [], [], []
            for nachalo in range(0, len(_svip(lo, hi, shag)), TOCHEK_V_KUSKE):
                kusok = _svip(lo, hi, shag)[nachalo:nachalo + TOCHEK_V_KUSKE]
                fl_k, fz_k = _dolya_zhidkosti(db, komponenty, fazy, x, kusok,
                                              pdens)
                fl += fl_k
                fz += fz_k
                tochki += kusok
                if fl and fl[-1] >= 1.0 - NOL_DOLI and any(
                        v <= NOL_DOLI for v in fl):
                    break
        else:
            fl, fz = _dolya_zhidkosti(db, komponenty, fazy, x, tochki, pdens)
        s, l = _granicy_po_svipu(tochki, fl)
        if s is None or l is None:
            return None
        okno_s, okno_l = s, l
        fazy_pod_sol = fz[tochki.index(s[0])]
        lo, hi = s[0], l[1]
    return 0.5 * (okno_s[0] + okno_s[1]), 0.5 * (okno_l[0] + okno_l[1]), fazy_pod_sol


# Порог движущей силы, Дж/моль. Отрицательная движущая сила означает, что
# фаза лежит НИЖЕ равновесной гиперплоскости, то есть должна была быть в
# наборе. 10 Дж/моль — запас на дискретность выборки составов в calculate().
PREDEL_DVIZHUSHCHEJ_SILY = -10.0

# Плотность выборки составов для сторожа. Это СКРИНИНГ, а не равновесие:
# pdens=20 хватает, чтобы отделить фазу с движущей силой в тысячи Дж/моль от
# фазы у нуля. Больше брать нельзя: у многоподрешёточных фаз (SIGMA, CHI_A12,
# карбиды) сетка растёт комбинаторно, и при pdens=100 на семикомпонентной
# стали процесс съедал 7 ГБ и падал по памяти — замерено, а не предположено.
PDENS_STOROZHA = 20

# Сколько раз слой готов добавить названную сторожем фазу и пересчитать.
#
# APP-504: было 4, стало 6 — ВЫБРАНО ЗАМЕРОМ (APP-500 п.2), а не запасом
# на всякий случай. На базах ThermoGar тринадцать замороженных марок Al
# отказывали кодом `storozh_ne_podtverdil`: сторож называл фазу, четырёх
# раундов не хватало добрать набор, и ответа не было вовсе. При шести
# раундах сошлись ВСЕ ТРИНАДЦАТЬ, и все — на пятом раунде: не хватало
# ровно одного. На полном проходе по каталогу (352 позиции Al + Ni) шесть
# раундов вернули 57 отказов из 60.
#
# Цена названа тем же замером: ×1,44 времени на тех марках, где сторож
# добирает фазы (60 позиций прохода A: 6227 с при 4 раундах, 8997 с при 6).
# Марки, которым хватало четырёх, не дорожают и не меняются: пять
# контрольных (F357, Aheadd CP1, АК9ч, 1161, АК4-2ч) останавливаются на
# том же 2-4 раунде и дают те же числа до последнего знака.
#
# Восемь раундов проверены и ОТКЛОНЕНЫ: у двенадцати марок из тринадцати
# числа совпали с шестью до последнего знака, а тринадцатая (1379) при
# восьми раундах вообще отказала по памяти — пик 7004 МБ при потолке 7000.
# Лишние раунды съели память, а ответа не добавили.
RAUNDOV_STOROZHA = 6

# Потолок памяти на время работы сторожа. Нужен по делу: у части фаз mc_al
# (четырёхподрешёточные тау-фазы) выборка составов на восьмикомпонентном
# сплаве вырастает так, что процесс убивает OOM целиком — предрасчёт так и
# упал на Scalmalloy (в dmesg: anon-rss 7.6 ГБ, Killed process). С потолком
# та же ситуация даёт MemoryError на одной фазе, и фаза попадает в список
# «не проверено».
#
# ПРАВКА APP-322. Раньше расчёт после этого ПРОДОЛЖАЛСЯ, а непроверенная
# фаза ехала видимой строкой примечания. Так нельзя: видимая строка — это
# не охрана, а извинение, и число всё равно уходило неохраняемым. Теперь
# непроверенная фаза делает сторож неуспешным, и марка получает честный
# отказ storozh_ne_proveril_fazy. Потолок при этом нужен по-прежнему: он
# превращает разгон одной фазы в ловимое исключение вместо смерти всего
# процесса, то есть в НАЗВАННЫЙ отказ вместо «процесс упал».
# Потолок задан по АДРЕСНОМУ ПРОСТРАНСТВУ, а не по RSS, и оно у numpy/BLAS
# кратно больше занятой памяти: 2 ГБ оказалось так тесно, что валился
# нормальный расчёт 316L (3 ГБ RSS). 6 ГБ ловит настоящие разгоны и не
# мешает рабочим составам — замерено.
PAMYAT_STOROZHA_BAJT = 6 * 1024 ** 3


@contextlib.contextmanager
def _potolok_pamyati(bajt):
    """Ограничить адресное пространство процесса на время блока.

    НА macOS ЭТО НЕ РАБОТАЕТ, и молчать об этом нельзя (замер финиша
    APP-312б): `setrlimit(RLIMIT_AS)` на Darwin падает с ValueError, а
    принятый лимит всё равно не действует — под потолком 2 ГБ numpy
    спокойно выделяет 3 ГБ. Здесь это не ломает ничего: блок просто
    выполняется без потолка, а фазу-разгон ловит потолок ПРОЦЕССА
    (calphad_layer/odna_tochka.py), который на Darwin поставлен
    сторожевым потоком по RSS. Разница в том, что там, где на Linux
    выпадала одна фаза в «не проверено», на Darwin честный отказ «не
    хватило памяти» получает вся марка. Это строже, а не мягче.
    """
    try:
        import resource
        staryj = resource.getrlimit(resource.RLIMIT_AS)
    except (ImportError, ValueError, OSError):
        yield
        return
    novyj = bajt if staryj[1] in (resource.RLIM_INFINITY,) else min(bajt, staryj[1])
    try:
        resource.setrlimit(resource.RLIMIT_AS, (novyj, staryj[1]))
    except (ValueError, OSError):
        yield
        return
    try:
        yield
    finally:
        try:
            resource.setrlimit(resource.RLIMIT_AS, staryj)
        except (ValueError, OSError):
            pass


def _mu_v_tochke(db, komponenty, fazy, x, T, pdens=PDENS_POISKA_POLNAYA):
    """Химпотенциалы из быстрого равновесия при T.

    Плотность сетки — та же, которой шёл поиск: сторож обязан мериться
    теми же условиями, в которых получено охраняемое число.
    """
    import numpy as np
    from pycalphad import equilibrium, variables as v
    osnova = max(x, key=x.get)
    usloviya = {v.P: 101325, v.N: 1, v.T: T}
    for e, xe in x.items():
        if e != osnova:
            usloviya[v.X(e)] = xe
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        eq = equilibrium(db, komponenty, list(fazy), usloviya,
                         calc_opts={"pdens": pdens})
    # atleast_1d — не косметика. У ОДНОКОМПОНЕНТНОГО состава (чистый
    # алюминий: марки АД, АД1пл, 1145, AW-Al 99,0, EN AW-Al 99,35 — после
    # отбрасывания следов от них остаётся ровно AL) squeeze() схлопывает и
    # ось компонентов тоже, MU становится 0-мерным, и zip по нему падает
    # с TypeError: iteration over a 0-d array. Найдено прогоном финиша
    # APP-312б: пять марок гибли в сторожевом расчёте уже ПОСЛЕ того, как
    # интервал плавления был найден, и попадали в таблицу как «процесс
    # упал» — то есть настоящий дефект слоя прятался за причиной,
    # похожей на нехватку памяти.
    return {str(s): float(m)
            for s, m in zip(np.atleast_1d(eq.component.values),
                            np.atleast_1d(eq.MU.squeeze().values))}


@dataclass(frozen=True)
class VerdiktStorozha:
    """Что сторож на самом деле сделал. Успех — только полная проверка.

    APP-322. Раньше здесь был кортеж, и первым его членом стояло
    `min_df >= PREDEL_DVIZHUSHCHEJ_SILY` — то есть «ни одна ПРОВЕРЕННАЯ
    фаза не оказалась стабильной». У этого выражения есть тихий изъян:
    при нуле проверенных фаз min_df остаётся `inf`, и «ничего плохого не
    нашли» неотличимо от «ничего и не смотрели». Поэтому вердикт теперь
    несёт и полноту, а `ok` требует ОБОИХ условий сразу.
    """
    ok: bool                     # проверено всё И ничего стабильного нет
    polno: bool                  # проверены ВСЕ обязательные пары «фаза-T»
    min_df: float                # минимальная движущая сила, Дж/моль
    hudshaya: object             # фаза с этим минимумом (None, если нет)
    provereno: int               # пар «фаза-температура» посчитано
    ozhidalos: int               # пар «фаза-температура» обязательных
    ne_vyshlo: tuple             # фазы, которые посчитать не удалось


def _storozh_dvizhushchej_siloj(db, komponenty, bystryj, polnyj, x, tochki,
                                pdens=PDENS_POISKA_POLNAYA):
    """Проверить, не должна ли быть стабильна фаза ВНЕ быстрого набора.

    Сравнивать наборы фаз, пересчитывая равновесие по всем 60+ фазам, нельзя:
    на многокомпонентной стали это съедает память целиком (проверено — OOM).
    Поэтому проверяется то же самое, но дёшево и по одной фазе за раз:
    движущая сила каждой исключённой фазы относительно равновесной
    гиперплоскости, min(G_ф(x) - sum mu_i x_i). Отрицательная — фаза должна
    была быть в наборе, и быстрый ответ недействителен.

    Обязательными считаются ВСЕ пары «исключённая фаза — точка проверки».
    Пара, которая не посчиталась, не «пропускается»: она делает вердикт
    неполным, а неполный вердикт — не успех (VerdiktStorozha).
    """
    import numpy as np
    from pycalphad import calculate
    isklyuchennye = [f for f in polnyj if f not in bystryj]
    ozhidalos = len(isklyuchennye) * len(tochki)
    hudshaya, min_df, provereno = None, float("inf"), 0
    ne_vyshlo = []
    import gc

    def ne_vyshla(faza):
        if faza not in ne_vyshlo:
            ne_vyshlo.append(faza)

    with _potolok_pamyati(PAMYAT_STOROZHA_BAJT):
        for T in tochki:
            try:
                mu = _mu_v_tochke(db, komponenty, bystryj, x, T, pdens)
            except Exception:                         # noqa: BLE001
                # Химпотенциалы в точке не посчитались — значит в этой
                # точке не проверена НИ ОДНА исключённая фаза. Молча
                # уронить весь расчёт исключением тоже нельзя: причина
                # обязана доехать до вызывающего названной.
                for faza in isklyuchennye:
                    ne_vyshla(faza)
                continue
            for faza in isklyuchennye:
                res = None
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        res = calculate(db, komponenty, faza, T=T, P=101325,
                                        pdens=PDENS_STOROZHA, output="GM")
                    gm = np.asarray(res.GM.values).ravel()
                    komp = [str(c) for c in res.component.values]
                    X = np.asarray(res.X.values).reshape(-1, len(komp))
                    muv = np.array([mu[c] for c in komp])
                    df = float((gm - X.dot(muv)).min())
                except (MemoryError, Exception):      # noqa: BLE001
                    ne_vyshla(faza)
                    continue
                finally:
                    del res
                    gc.collect()
                provereno += 1
                if df < min_df:
                    min_df, hudshaya = df, faza
    polno = not ne_vyshlo and provereno == ozhidalos
    return VerdiktStorozha(
        ok=polno and min_df >= PREDEL_DVIZHUSHCHEJ_SILY,
        polno=polno, min_df=min_df, hudshaya=hudshaya, provereno=provereno,
        ozhidalos=ozhidalos, ne_vyshlo=tuple(ne_vyshlo))


def solidus_likvidus(sostav_mass, tochnost_K=TOCHNOST_K, storozh=True,
                     sohranit_sledi=False, baza_klyuch=None,
                     molnye_doli=None, exact_mass_percent=None,
                     exact_mole_fraction=None):
    """Солидус и ликвидус сплава по химсоставу в масс.%.

    Возвращает Rezultat или Otkaz. Никогда не возвращает число «примерно»:
    если базы нет, элемент не покрыт, состав вне границ оптимизации или
    равновесие не сошлось — это Otkaz с названной причиной (правило 6).

    APP-368 п.3 (открытая находка APP-363 §7.1). Обещание выше держалось
    не везде: сборка модели фаз внутри pycalphad может упасть на составе,
    который слой пропустил по своим границам, — например
    ``ValueError: Order (BCC_B2) and disorder (BCC_A2) model must have no
    interstitial sublattice or a single matching one`` на AlSi7Mg0.6 с
    внедрёнными C и N. Падение — не отказ: у вызывающего нет ни кода
    причины, ни списка того, чего не хватает, и продуктовый слой видит
    голое исключение вместо решения. Здесь оно переводится в
    типизированный Otkaz.

    Ловится ТОЛЬКО исключение, поднятое кадром самого pycalphad: своя
    ошибка слоя обязана падать громко, а не превращаться в «честный
    отказ», под которым спрятан наш собственный дефект.
    """
    try:
        return _schitat(sostav_mass, tochnost_K, storozh, sohranit_sledi,
                        baza_klyuch, molnye_doli, exact_mass_percent,
                        exact_mole_fraction)
    except Exception as oshibka:                       # noqa: BLE001
        if not _iz_pycalphad(oshibka):
            raise
        return _otkaz_model_ne_postroena(sostav_mass, oshibka)


def _schitat(sostav_mass, tochnost_K, storozh, sohranit_sledi, baza_klyuch,
             molnye_doli, exact_mass_percent, exact_mole_fraction):
    t0 = time.time()
    if baza_klyuch is None:
        opis = vybrat_bazu(sostav_mass)
    else:
        opis = gr.BAZY.get(baza_klyuch)
        if opis is None:
            return Otkaz(
                "net_bazy", f"запрошенная база {baza_klyuch} не установлена",
                (f"база {baza_klyuch}",))
        route_mass = (_strict_exact_transport_vector(
            exact_mass_percent, sostav_mass, Fraction(100, 1))
            if exact_mass_percent is not None else None)
        if exact_mass_percent is not None and route_mass is None:
            return Otkaz(
                "strict_exact_route_invalid",
                "точный mass-вектор маршрута не связан с solver transport",
                ("exact mass route authority",))
        osnova = (max(route_mass, key=route_mass.get) if route_mass is not None
                  else gr.osnova_sostava(sostav_mass))
        if baza_klyuch not in gr.BAZY_PO_OSNOVE.get(osnova, ()):
            return Otkaz(
                "net_bazy",
                f"база {baza_klyuch} не аттестована для основы {osnova}",
                (f"аттестованный маршрут {osnova}->{baza_klyuch}",))
    if isinstance(opis, Otkaz):
        return opis
    proverka = proverit_granicy(
        sostav_mass, opis, sohranit_sledi=sohranit_sledi,
        molnye_doli=molnye_doli, exact_mass_percent=exact_mass_percent,
        exact_mole_fraction=exact_mole_fraction)
    if isinstance(proverka, Otkaz):
        return proverka
    mass, otbrosheny = proverka
    # Плотность сетки решается ОДИН раз, до первого равновесия, и с базой
    # на руках: сниженная сетка вне списка аттестации — честный отказ, а
    # не число погрубее (APP-322).
    pdens = plotnost_setki(opis)
    if isinstance(pdens, Otkaz):
        return pdens
    x = (dict(molnye_doli) if sohranit_sledi
         else gr.v_molnye_doli(mass))
    db = _zagruzit(opis)
    komponenty = sorted(x) + ["VA"]
    bystryj = [f for f in opis.bystryj_nabor_faz
               if f in db.phases and f not in opis.isklyuchennye_fazy]
    polnyj = _aktivnye_fazy(db, komponenty, opis)
    if opis.isklyuchennye_fazy:
        otbrosheny = otbrosheny + tuple(
            f"фаза {f} исключена из расчёта: {prichina.split('.')[0]}."
            for f, prichina in sorted(opis.isklyuchennye_fazy.items()))

    najdeno = _iskat(db, komponenty, bystryj, x, opis.T_min, opis.T_max,
                     tochnost_K, pdens)
    polnym = False
    zamech = list(otbrosheny)
    if pdens != PDENS_POISKA_POLNAYA:
        zamech.append(
            f"СЕТКА СНИЖЕНА: pdens {pdens} вместо {PDENS_POISKA_POLNAYA} у "
            f"состава из {len([k for k in komponenty if k != 'VA'])} "
            f"компонентов. "
            + ("Считано ДЛЯ АТТЕСТАЦИИ (ключ dlya-attestacii): это материал "
               "доказательства эквивалентности, а не ответ слоя, и "
               "публиковать его нельзя."
               if SETKA_TOLKO_DLYA_ATTESTACII else
               f"Полная сетка на этом составе в память не поместилась, и это "
               f"ЗАМЕР, а не порог по числу компонентов: сниженную сетку "
               f"навязала лесенка изолированного процесса. База "
               f"{opis.klyuch} на сниженной сетке аттестована: "
               f"proverki/attestaciya_setki.py"))
    if najdeno is None:
        najdeno = _iskat(db, komponenty, polnyj, x, opis.T_min, opis.T_max,
                         tochnost_K, pdens)
        polnym = True
        zamech.append("быстрый набор фаз не поймал интервал плавления — "
                      "поиск повторён полным активным набором")
        if najdeno is None:
            return Otkaz(
                "ne_najden_interval",
                f"в области базы {opis.klyuch} ({opis.T_min}-{opis.T_max} K) "
                f"переход твёрдое->жидкое не найден: доля жидкости не проходит "
                f"ни через 0, ни через 1",
                ("интервал плавления внутри области базы",))
    sol, lik, fazy_pod_sol = najdeno

    # Сторож не просто краснеет, а ЧИНИТ набор: названную им фазу слой
    # добавляет к набору и пересчитывает. Это лучше ручной подгонки списка
    # фаз под каждую систему — набор определяется не догадкой, а тем, что
    # реально имеет отрицательную движущую силу. Раундов конечное число:
    # не сошлось — честный отказ, а не бесконечный цикл.
    dobavleno = []
    phase_guard_evidence = {
        "contract_version": "APP358_PHASE_EVIDENCE_V1",
        "mode": "full_active_phase_set" if polnym else "not_checked",
        "complete": bool(polnym),
        "checked_pairs": 0,
        "expected_pairs": 0,
        "unverified_phases": [],
        "added_phases": [],
    }
    if storozh and not polnym:
        for raund in range(RAUNDOV_STOROZHA):
            d = max(2.0 * tochnost_K, 1.0)
            tochki_storozha = [sol + d, lik - d]
            v = _storozh_dvizhushchej_siloj(db, komponenty, bystryj, polnyj, x,
                                            tochki_storozha, pdens)
            # НЕПОЛНАЯ проверка — это отказ, а не примечание (APP-322,
            # ревью Codex 09.08 раздел 4). Раньше непосчитавшаяся фаза
            # уезжала строкой «НЕ ПРОВЕРЕНЫ» вместе с численным ответом, и
            # при нуле проверенных фаз сторож возвращал «подтвердилось».
            # Разбирать этот случай надо ПЕРВЫМ: пока набор не проверен,
            # чинить его добавлением фазы нечем — сторож не назвал ни одной.
            if not v.polno:
                return Otkaz(
                    "storozh_ne_proveril_fazy",
                    f"набор фаз дал {sol:.1f}/{lik:.1f} K, но сторож движущей "
                    f"силы проверил только {v.provereno} из {v.ozhidalos} "
                    f"обязательных пар «фаза-температура»: не посчитались "
                    f"{len(v.ne_vyshlo)} фаз ({', '.join(v.ne_vyshlo)}). "
                    f"Непроверенная фаза может иметь отрицательную движущую "
                    f"силу, то есть должна была быть в наборе, — и тогда эти "
                    f"числа посчитаны не тем набором фаз. Число без охраны "
                    f"выдавать нельзя.",
                    tuple(f"проверка фазы {f}" for f in v.ne_vyshlo))
            if v.ok:
                # Число пар, а не число фаз: раньше в примечании стояло
                # «проверено N исключённых фаз», а N было парами «фаза-T»,
                # то есть вдвое больше самих фаз. Считать пары правильно —
                # проверка идёт в двух точках, — но называть их фазами
                # было неправдой.
                zamech.append(
                    f"сторож движущей силы: проверено {v.provereno} из "
                    f"{v.ozhidalos} пар «фаза-температура» ({len(tochki_storozha)} "
                    f"точки, {v.ozhidalos // len(tochki_storozha)} исключённых "
                    f"фаз); минимум {v.min_df:.0f} Дж/моль у {v.hudshaya}")
                phase_guard_evidence = {
                    "contract_version": "APP358_PHASE_EVIDENCE_V1",
                    "mode": ("driving_force_guard" if v.ozhidalos > 0
                             else "full_active_phase_set"),
                    "complete": True,
                    "checked_pairs": v.provereno,
                    "expected_pairs": v.ozhidalos,
                    "unverified_phases": [],
                    "added_phases": list(dobavleno),
                }
                break
            hudshaya, min_df = v.hudshaya, v.min_df
            if raund == RAUNDOV_STOROZHA - 1 or hudshaya in bystryj:
                return Otkaz(
                    "storozh_ne_podtverdil",
                    f"набор фаз дал {sol:.1f}/{lik:.1f} K, но фаза "
                    f"{hudshaya} вне набора имеет отрицательную движущую силу "
                    f"{min_df:.0f} Дж/моль — значит она должна быть в наборе. "
                    f"За {RAUNDOV_STOROZHA} раунда добавления фаз "
                    f"({', '.join(dobavleno) or 'ни одной'}) расчёт охрану не "
                    f"прошёл. Число без охраны выдавать нельзя.",
                    (f"фаза {hudshaya} в наборе для этой системы",))
            bystryj = list(bystryj) + [hudshaya]
            dobavleno.append(hudshaya)
            pereschet = _iskat(db, komponenty, bystryj, x, opis.T_min,
                               opis.T_max, tochnost_K, pdens)
            if pereschet is None:
                return Otkaz(
                    "ne_najden_interval",
                    f"после добавления фазы {hudshaya} по требованию сторожа "
                    f"интервал плавления в области базы не найден",
                    ("интервал плавления внутри области базы",))
            sol, lik, fazy_pod_sol = pereschet
        if dobavleno:
            zamech.append(
                "по требованию сторожа в набор добавлены фазы: "
                + ", ".join(dobavleno))

    return Rezultat(
        solidus_K=round(sol, 1),
        likvidus_K=round(lik, 1),
        baza=opis.klyuch,
        versiya_bazy=opis.versiya,
        licenziya_bazy=opis.licenziya,
        sha256_bazy=opis.sha256_ishodnika,
        sostav_mass=mass,
        tochnost_K=tochnost_K,
        pdens_poiska=pdens,
        setka_polnaya=pdens == PDENS_POISKA_POLNAYA,
        nabor_faz=tuple(polnyj if polnym else bystryj),
        polnyj_nabor_ponadobilsya=polnym,
        fazy_pod_solidusom=fazy_pod_sol,
        vremya_s=round(time.time() - t0, 2),
        zamechaniya=tuple(zamech),
        phase_guard_evidence=phase_guard_evidence,
    )
