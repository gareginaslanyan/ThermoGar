"""Single authoritative atomic-mass table for chemistry routing and CALPHAD.

Values are deliberately stored as decimal strings.  Every consumer derives
its Decimal or legacy float view from this object; a second hand-written table
is forbidden because a difference at an attested mole-fraction boundary can
change the selected database.
"""
from __future__ import annotations

import hashlib
from decimal import Decimal


ATOMIC_MASSES_VERSION = "CALPHAD_ATOMIC_MASSES_DECIMAL_V1"

# Existing CALPHAD-layer values, frozen without adding false precision.
ATOMIC_MASS_DECIMAL_TEXT = {
    "AG": "107.868", "AL": "26.982", "AS": "74.922", "AU": "196.967",
    "B": "10.811", "BA": "137.327", "BE": "9.012", "BI": "208.980",
    "C": "12.011", "CA": "40.078", "CD": "112.414", "CE": "140.116",
    "CO": "58.933", "CR": "51.996", "CU": "63.546", "FE": "55.845",
    "GA": "69.723", "GE": "72.630", "H": "1.008", "HF": "178.49",
    "IN": "114.818", "LA": "138.905", "LI": "6.941", "MG": "24.305",
    "MN": "54.938", "MO": "95.95", "N": "14.007", "NA": "22.990",
    "NB": "92.906", "ND": "144.242", "NI": "58.693", "O": "15.999",
    "P": "30.974", "PB": "207.2", "PD": "106.42", "PT": "195.084",
    "RE": "186.207", "RH": "102.906", "RU": "101.07", "S": "32.06",
    "SB": "121.760", "SC": "44.956", "SE": "78.971", "SI": "28.085",
    "SN": "118.71", "TA": "180.948", "TE": "127.60", "TI": "47.867",
    "V": "50.942", "W": "183.84", "Y": "88.906", "ZN": "65.38",
    "ZR": "91.224",
}


def atomic_mass_decimal(element: str) -> Decimal:
    """Return an exact Decimal view of the frozen table entry."""
    return Decimal(ATOMIC_MASS_DECIMAL_TEXT[element.upper()])


def atomic_masses_sha256() -> str:
    """Hash the complete table and its version with context-free bytes."""
    lines = [ATOMIC_MASSES_VERSION]
    lines.extend(
        f"{element}={ATOMIC_MASS_DECIMAL_TEXT[element]}"
        for element in sorted(ATOMIC_MASS_DECIMAL_TEXT))
    return hashlib.sha256(("\n".join(lines) + "\n").encode("ascii")).hexdigest()


ATOMIC_MASSES_SHA256 = atomic_masses_sha256()


__all__ = [
    "ATOMIC_MASSES_VERSION",
    "ATOMIC_MASS_DECIMAL_TEXT",
    "ATOMIC_MASSES_SHA256",
    "atomic_mass_decimal",
]
