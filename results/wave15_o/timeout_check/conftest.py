"""Подключить хуки tools/conftest.py к синтетической проверке таймаута."""
import importlib.util
from pathlib import Path

_path = Path(__file__).resolve().parents[3] / "tools" / "conftest.py"
_spec = importlib.util.spec_from_file_location("tools_conftest", _path)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
for _name in dir(_module):
    if _name.startswith("pytest_"):
        globals()[_name] = getattr(_module, _name)
