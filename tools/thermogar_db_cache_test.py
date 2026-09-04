from __future__ import annotations

import hashlib
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
sys.path.insert(0, str(APP))

import thermogar_db_cache as db_cache


PAYLOAD = b"$ ELEMENT AL\nPHASE FCC_A1 % 1 1 !\n"
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()
OTHER_DIGEST = hashlib.sha256(b"different bytes").hexdigest()


class _Parsed:
    """Заглушка разобранной базы: сравнима по значению и переживает pickle."""

    def __init__(self, marker: str) -> None:
        self.marker = marker

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _Parsed) and other.marker == self.marker

    def __hash__(self) -> int:
        return hash(self.marker)


class _Counter:
    def __init__(self, marker: str = "parsed") -> None:
        self.calls = 0
        self.marker = marker

    def __call__(self) -> _Parsed:
        self.calls += 1
        return _Parsed(self.marker)


class DatabaseCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = TemporaryDirectory()
        self.state_root = Path(self._temporary.name) / "ThermoGar"
        self._environment = mock.patch.dict(
            os.environ,
            {"THERMOGAR_STATE_ROOT": str(self.state_root)},
            clear=False,
        )
        self._environment.start()
        self.addCleanup(self._environment.stop)
        self.addCleanup(self._temporary.cleanup)

    def load(self, parse, *, expected=DIGEST, snapshot=DIGEST, payload=PAYLOAD):
        return db_cache.load_or_parse(
            expected_sha256=expected,
            snapshot_sha256=snapshot,
            snapshot_bytes=payload,
            parse=parse,
        )

    def entry_path(self) -> Path:
        return db_cache.cache_root() / db_cache.entry_name(DIGEST)

    def test_001_miss_parses_once_and_writes_the_entry(self):
        parse = _Counter()
        result = self.load(parse)
        self.assertEqual(result, _Parsed("parsed"))
        self.assertEqual(parse.calls, 1)
        entry = self.entry_path()
        self.assertTrue(entry.is_file())
        self.assertTrue(entry.stat().st_size > 0)
        # Каталог кэша лежит внутри состояния пользователя, а не рядом с кодом.
        self.assertEqual(entry.parent.parent, self.state_root.resolve())
        # Ключ несёт SHA-256 базы, версию pycalphad и версию формата.
        self.assertIn(DIGEST, entry.name)
        self.assertIn("pycalphad-", entry.name)
        self.assertIn(f"-v{db_cache.CACHE_FORMAT_VERSION}.", entry.name)

    def test_002_hit_returns_the_stored_value_without_parsing(self):
        first = _Counter()
        self.load(first)
        self.assertEqual(first.calls, 1)

        second = _Counter(marker="must-not-be-called")
        result = self.load(second)
        self.assertEqual(second.calls, 0)
        self.assertEqual(result, _Parsed("parsed"))

    def test_003_corrupt_entry_falls_back_to_a_fresh_parse(self):
        self.load(_Counter())
        entry = self.entry_path()
        entry.write_bytes(b"\x80\x05 not a pickle at all")

        parse = _Counter(marker="reparsed")
        result = self.load(parse)
        self.assertEqual(parse.calls, 1)
        self.assertEqual(result, _Parsed("reparsed"))
        # Битый файл заменён пригодным, следующий запуск снова попадает в кэш.
        again = _Counter(marker="must-not-be-called")
        self.assertEqual(self.load(again), _Parsed("reparsed"))
        self.assertEqual(again.calls, 0)

    def test_004_truncated_entry_falls_back_to_a_fresh_parse(self):
        self.load(_Counter())
        entry = self.entry_path()
        entry.write_bytes(entry.read_bytes()[:7])

        parse = _Counter(marker="reparsed")
        self.assertEqual(self.load(parse), _Parsed("reparsed"))
        self.assertEqual(parse.calls, 1)

    def test_005_another_pycalphad_version_is_a_different_entry(self):
        self.load(_Counter())
        stored = self.entry_path()
        with mock.patch.object(db_cache, "_pycalphad_version", return_value="0.0.0"):
            parse = _Counter(marker="reparsed")
            self.assertEqual(self.load(parse), _Parsed("reparsed"))
            self.assertEqual(parse.calls, 1)
            other = db_cache.cache_root() / db_cache.entry_name(DIGEST)
        self.assertNotEqual(other, stored)
        self.assertTrue(stored.is_file())
        self.assertTrue(other.is_file())

    def test_006_unverified_bytes_never_reach_the_cache(self):
        # Снимок, чей SHA-256 не совпадает с закреплённым, идёт мимо кэша: не
        # ищется в нём и не сохраняется. Разбор при этом вызывается и сам решает,
        # чем закончиться.
        for expected, snapshot, payload in (
            (DIGEST, OTHER_DIGEST, PAYLOAD),
            (OTHER_DIGEST, OTHER_DIGEST, PAYLOAD),
            (DIGEST, DIGEST, b"tampered payload"),
        ):
            with self.subTest(expected=expected[:8], snapshot=snapshot[:8]):
                parse = _Counter()
                self.load(parse, expected=expected, snapshot=snapshot, payload=payload)
                self.assertEqual(parse.calls, 1)
        root = db_cache.cache_root()
        self.assertFalse(root.exists() and any(root.iterdir()))

    def test_007_parse_failure_propagates_and_stores_nothing(self):
        def explode():
            raise RuntimeError("Database snapshot is not strict UTF-8 text.")

        with self.assertRaises(RuntimeError):
            self.load(explode)
        root = db_cache.cache_root()
        self.assertFalse(root.exists() and any(root.iterdir()))

    def test_008_unwritable_cache_directory_still_returns_a_parsed_database(self):
        # Каталог не создаётся — кэш молча выключается, старт не ломается.
        with mock.patch.object(db_cache, "cache_root", return_value=None):
            parse = _Counter()
            self.assertEqual(self.load(parse), _Parsed("parsed"))
            self.assertEqual(parse.calls, 1)

    def test_009_no_state_root_disables_the_cache_quietly(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(db_cache.cache_root())
            parse = _Counter()
            self.assertEqual(self.load(parse), _Parsed("parsed"))
            self.assertEqual(parse.calls, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
