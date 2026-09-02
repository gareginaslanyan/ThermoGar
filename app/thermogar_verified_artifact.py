"""Strict immutable text/JSON views over held verified file snapshots."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Iterator

from thermogar_secure_io import held_verified_snapshot


@dataclass(frozen=True, slots=True)
class VerifiedTextArtifact:
    text: str
    sha256: str
    size: int


def strict_utf8_text(data: bytes) -> str:
    if type(data) is not bytes:
        raise TypeError("Verified artifact data must be immutable bytes.")
    encoding = "utf-8-sig" if data.startswith(b"\xef\xbb\xbf") else "utf-8"
    try:
        text = data.decode(encoding, errors="strict")
    except UnicodeDecodeError as error:
        raise ValueError("Verified artifact is not strict UTF-8 text.") from error
    if text.encode(encoding) != data:
        raise ValueError("Verified UTF-8 artifact does not round-trip exactly.")
    return text


@contextmanager
def held_verified_utf8_text(
    path: str | Path,
    *,
    expected_sha256: str,
    maximum_bytes: int,
    canonical_root: str | Path,
) -> Iterator[VerifiedTextArtifact]:
    with held_verified_snapshot(
        path,
        expected_sha256=expected_sha256,
        maximum_bytes=maximum_bytes,
        canonical_root=canonical_root,
    ) as snapshot:
        yield VerifiedTextArtifact(
            text=strict_utf8_text(snapshot.data),
            sha256=snapshot.sha256,
            size=snapshot.size,
        )


def read_verified_utf8_text(
    path: str | Path,
    *,
    expected_sha256: str,
    maximum_bytes: int,
    canonical_root: str | Path,
) -> VerifiedTextArtifact:
    with held_verified_utf8_text(
        path,
        expected_sha256=expected_sha256,
        maximum_bytes=maximum_bytes,
        canonical_root=canonical_root,
    ) as artifact:
        return artifact


def duplicate_reject_json(text: str) -> Any:
    if type(text) is not str:
        raise TypeError("JSON artifact must be strict text.")

    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if type(key) is not str or key in result:
                raise ValueError("JSON artifact contains a duplicate object key.")
            result[key] = value
        return result

    def reject_constant(token: str) -> None:
        raise ValueError(f"JSON artifact contains non-finite constant {token}.")

    return json.loads(
        text,
        object_pairs_hook=object_pairs,
        parse_constant=reject_constant,
    )
