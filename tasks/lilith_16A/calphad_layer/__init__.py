"""APP-304: слой открытых баз свойств (CALPHAD).

Публичное:
    solidus_likvidus(sostav_mass)  -> Rezultat | Otkaz
    znachenie(marka, velichina)    -> ответ по иерархии слоёв (ierarhiya.py)

Слой не импортирует `advisor/db`, `ingest`, `models`, `inverse`, `planner`
или `transfer`; связь проходит только через его публичный расчётный API.
"""
from .raschet import Otkaz, Rezultat, solidus_likvidus, vybrat_bazu, proverit_granicy

__all__ = ["Otkaz", "Rezultat", "solidus_likvidus", "vybrat_bazu",
           "proverit_granicy"]
