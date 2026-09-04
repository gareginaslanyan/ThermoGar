"""Кэш разобранной базы TDB на диске.

Разбор одной релизной базы стоит 3,4–6,4 с (`Database.from_file`, формат TDB),
и это самая дорогая часть первого старта. Pickle уже разобранного объекта
читается за ~0,15 с, поэтому результат разбора кладётся в
``%LOCALAPPDATA%\\ThermoGar\\cache\\`` и при следующем запуске берётся оттуда.

Кэш не решает, можно ли доверять базе. Вызывающая сторона сначала читает файл
через ``held_verified_snapshot`` с закреплённым SHA-256, и уже проверенные байты
попадают сюда; ключ записи содержит тот же SHA-256, а перед любым обращением к
диску байты сверяются ещё раз здесь. Снимок с чужим SHA-256 не ищется в кэше и
не сохраняется в него — он идёт прежним путём и падает, как падал.

Любая ошибка на стороне кэша — нет каталога, обрезанный pickle, запись от другой
версии pycalphad, нет прав на запись — гасится и превращается в обычный разбор.
Кэш не может уронить запуск.

Оговорка по доверию: `pickle.loads` исполняет код, а `%LOCALAPPDATA%` доступен
на запись тому же пользователю, от которого работает программа. Границы прав это
не пересекает (программа и так работает в его сессии и читает его проекты из
того же каталога), но каталог кэша не является доверенным хранилищем и ничего,
кроме результата разбора наших же баз, в нём быть не должно.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
import hashlib
import os
import pickle
import re
import tempfile


# Растёт, когда меняется смысл содержимого записи. Старые файлы при этом просто
# перестают находиться и остаются мусором до очистки каталога.
CACHE_FORMAT_VERSION = 1

CACHE_DIRECTORY_NAME = "cache"
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_VERSION_SANITISER = re.compile(r"[^0-9A-Za-z._-]")


def _pycalphad_version() -> str:
    """Версия pycalphad; при неудаче — метка, не совпадающая ни с одной версией."""

    try:
        from importlib.metadata import version

        return _VERSION_SANITISER.sub("-", str(version("pycalphad")))
    except Exception:
        try:
            import pycalphad

            return _VERSION_SANITISER.sub("-", str(pycalphad.__version__))
        except Exception:
            return "unknown"


def cache_root() -> Path | None:
    """Каталог кэша внутри состояния пользователя или ``None``, если его нет."""

    root = os.environ.get("THERMOGAR_STATE_ROOT")
    if not root:
        local_app_data = os.environ.get("LOCALAPPDATA")
        if not local_app_data:
            return None
        root = str(Path(local_app_data) / "ThermoGar")
    try:
        return Path(root).resolve(strict=False) / CACHE_DIRECTORY_NAME
    except Exception:
        return None


def entry_name(expected_sha256: str) -> str:
    """Имя записи: SHA-256 базы, версия pycalphad, версия формата кэша."""

    return f"tdb-{expected_sha256}-pycalphad-{_pycalphad_version()}-v{CACHE_FORMAT_VERSION}.pickle"


def _entry_path(expected_sha256: str) -> Path | None:
    root = cache_root()
    if root is None:
        return None
    return root / entry_name(expected_sha256)


def _read_entry(path: Path) -> Any:
    """Прочитать запись или вернуть ``None``, если она непригодна."""

    try:
        payload = path.read_bytes()
    except Exception:
        return None
    try:
        return pickle.loads(payload)
    except Exception:
        # Битый, обрезанный или несовместимый файл. Удаляем, чтобы следующая
        # запись легла на его место, и разбираем базу заново.
        try:
            path.unlink()
        except Exception:
            pass
        return None


def _write_entry(path: Path, database: Any) -> None:
    """Записать запись атомарно; молча ничего не делать при любой ошибке."""

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = pickle.dumps(database, protocol=pickle.HIGHEST_PROTOCOL)
        descriptor, temporary = tempfile.mkstemp(
            dir=str(path.parent), prefix=path.name + ".", suffix=".partial"
        )
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        except Exception:
            try:
                os.unlink(temporary)
            except Exception:
                pass
            raise
    except Exception:
        return


def canonical(database: Any) -> Any:
    """Объект базы в том же виде, в каком он выходит из кэша.

    ``pickle`` не сохраняет внутреннюю раскладку множеств: у восстановленной
    базы порядок обхода составляющих подрешёток другой, а значит другой и
    порядок переменных у солвера — равновесие сходится в те же доли, но
    последние 8 знаков расходятся. Пока попадание в кэш возвращало
    восстановленный объект, а промах — только что разобранный, числа зависели
    от того, лежит ли уже файл кэша на диске; после этой нормализации оба пути
    (и пул процессов, который берёт базу из того же кэша) дают один объект.
    Перенос стоит ~0,15 с и платится только при промахе.
    """

    try:
        return pickle.loads(pickle.dumps(database, protocol=pickle.HIGHEST_PROTOCOL))
    except Exception:
        return database


def load_or_parse(
    *,
    expected_sha256: str,
    snapshot_sha256: str,
    snapshot_bytes: bytes,
    parse: Callable[[], Any],
) -> Any:
    """Вернуть разобранную базу из кэша или разобрать её и запомнить.

    ``parse`` вызывается ровно один раз при промахе и остаётся единственным
    путём разбора: кэш только избавляет от повторного вызова. Результат всегда
    приводится к канонической форме (см. ``canonical``), поэтому числа не
    зависят от того, был ли кэш холодным.
    """

    if (
        type(snapshot_bytes) is not bytes
        or not _SHA256_PATTERN.fullmatch(str(expected_sha256))
        or not _SHA256_PATTERN.fullmatch(str(snapshot_sha256))
        or expected_sha256 != snapshot_sha256
        or hashlib.sha256(snapshot_bytes).hexdigest() != expected_sha256
    ):
        # Байты не те, за которые себя выдают: кэш к ним не прикасается,
        # разбор пойдёт прежним путём и сам сообщит об ошибке.
        return canonical(parse())

    path = _entry_path(expected_sha256)
    if path is None:
        return canonical(parse())

    cached = _read_entry(path)
    if cached is not None:
        return cached

    database = parse()
    _write_entry(path, database)
    return canonical(database)
