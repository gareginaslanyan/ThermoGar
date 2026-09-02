"""Compatibility entry point for the single-page ThermoGar product."""
from __future__ import annotations

from pathlib import Path
import runpy


def render() -> None:
    """Run the one-page product without adding routes or navigation."""
    runpy.run_path(
        str(Path(__file__).with_name("ThermoGar_app.py")),
        run_name="__thermogar_product__",
    )


if __name__ == "__main__":
    render()
