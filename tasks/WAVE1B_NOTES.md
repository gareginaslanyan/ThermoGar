# Wave 1B — reconnaissance notes (installer pipeline as inherited from Codex)

Worktree: `C:\Users\gareg\Desktop\ThermoGar-w1b`, branch `wave1b-installer`.
Runtime and installer assets: `C:\Users\gareg\Desktop\ThermoGar\ThermoGar-Installer-Assets\`.

## Toolchain

- NSIS **is** installed: `C:\Program Files (x86)\NSIS\makensis.exe`. No portable NSIS needed.
  `build_installer.ps1` now takes `-NsisPath` and falls back through
  `Program Files (x86)` → `Program Files` → `ThermoGar-Installer-Assets\nsis\makensis.exe`
  (both in the worktree and in the main checkout), so a zip NSIS can be dropped in later
  without editing the script.
- Runtime `runtime-clean-3119`: CPython 3.11.9 embeddable, 15 003 files, ~549 MB.
  `python311._pth` = `python311.zip`, `.`, `Lib\site-packages`, `import site`.
- site-packages check: pycalphad 0.11.2, kawin 0.5.0, scheil 0.3.0, streamlit 1.62.0,
  symengine 0.13.0, numpy 2.4.6, scipy 1.17.1, matplotlib 3.11.1, pandas 3.0.5,
  openpyxl 3.1.5, xarray 2026.7.0 — **all present**. Nothing had to be copied from
  `.venv-windows`.

## Codex build chain (before this wave)

```
build_installer.ps1                 52 KB
  ├─ Read-StableBytes on makensis.exe itself, pinned to 2560 bytes / SHA B043E5…
  ├─ Add-Type ThermoGar.P4.OwnedPath  (~700 lines of P/Invoke: NtCreateFile,
  │     handle-authority publication, rollback)
  ├─ Invoke-UpgradePreflight
  ├─ stage_payload.ps1 (mandatory -Expected* args)
  ├─ generate_runtime_trust_manifest.ps1
  ├─ verify_runtime_trust_manifest.ps1
  ├─ verify_native_closure.ps1
  ├─ verify_distribution_evidence.ps1   (generate_sbom / generate_notices /
  │     generate_payload_manifest were 226-byte stubs dot-sourcing this file)
  └─ makensis with 12 mandatory /DEXPECTED_* defines
```

## Hard-coded roots and expected counts (all removed from the live path)

| Location | Constant | Value |
|---|---|---|
| `launcher.pyw:22-29` | `P0_ROOT` / `RUNTIME_ROOT` / `NATIVE_ROOT` | `42455F51…` / `58F81C01…` / `A08EC907…` |
| `launcher.pyw:25-29` | `EXPECTED_EXECUTION_ROWS` … | 15035 / 29 / 2674489 / 15003 / 575844438 |
| `launcher.pyw:483` | `_validate_trust` | reads `manifests/runtime-trust-manifest.json` + `.receipt.json` |
| `healthcheck.py:18-27` | same three roots + same five counts | identical values |
| `healthcheck.py:319` | `_validate_trust(caller_file, role)` | same manifest + receipt |
| `stop.pyw:15-16` | `COMMON_BYTES` / `COMMON_SHA256` | healthcheck.py pinned to 38059 bytes / `ABCDE7BD…` |
| `build_installer.ps1:8-15` | `$FixedNsisPath/Bytes/Sha256`, `$FixedProductVersion*`, `$FixedIcon*`, `$FixedReleasePolicySha256` | pins makensis.exe, product-version.json, the icon and `thermogar_release_policy.py` |
| `stage_payload.ps1:20-35` | `$P0Root`, `$RuntimeLiteralRoot`, `$RuntimeFileCount`, `$RuntimeTotalBytes`, `$RuntimeDistInfoCount`, `$RuntimeNoticeCount`, `$StageContentFileCount`, `$PolicySha256`, `$PolicyVerifierSha256` | `$RuntimeLiteralRoot` still pointed at `C:\Users\gareg\Documents\Codex\…` |
| `ThermoGar.nsi:37-63` | `EXPECTED_PAYLOAD_MANIFEST_SHA256`, `EXPECTED_DISTRIBUTION_RECEIPT_SHA256`, `EXPECTED_PAYLOAD_ROWS/BYTES/ROOT_SHA256`, `EXPECTED_PRODUCT_VERSION_SHA256`, `EXPECTED_ICON_SHA256` | 12 mandatory `!define`s |
| `payload-policy.json` | 29 rows, each pinning an `app\*.py` SHA-256 | breaks on every application edit |

Why this blocked progress: `payload-policy.json`, `launcher.pyw`, `healthcheck.py` and
`ThermoGar.nsi` all pinned SHA-256 values of application source. Any change under `app\`
invalidated the payload policy root, which invalidated the trust manifest, which
invalidated the receipt, which invalidated the NSIS defines — so a one-line product fix
required regenerating and re-auditing the whole chain.

## New chain

```
build_installer.ps1 -Version <from product-version.json>
  1. generate_notices.ps1   → THIRD_PARTY_NOTICES.txt   (99 dist-info dirs + MatCalc section)
  2. stage_payload.ps1      → dist\stage\ + manifests\payload-manifest.json
  3. makensis               → dist\ThermoGar-<version>-win64.exe
  4. Get-FileHash           → SHA-256
  5. summary                → dist\ThermoGar-<version>-win64.build.json
```

Runtime integrity is now a presence check plus held file handles (`_validate_install` in
both `launcher.pyw` and `healthcheck.py`), and the install identity is the SHA-256 of the
`path|bytes|sha256` rows of the six required files. That still stops a run record from a
different install being reused, without pinning anything at author time.

## Archived, not deleted

`_archive_codex\packaging\`: `build_installer.codex.ps1`, `stage_payload.codex.ps1`,
`ThermoGar.codex.nsi`, `payload-policy.json`, `verify_*.ps1` (6),
`generate_runtime_trust_manifest.ps1`, `generate_sbom.ps1`, `generate_payload_manifest.ps1`,
`test_lifecycle_synthetic.ps1`, `clean_smoke.ps1`, `c15_fake_probe.py`,
`stage_runtime_helpers.ps1`, `AppData\`.
`_archive_codex\dist\`: `ThermoGar-0.2.0-ne02-win64.exe`, its build receipt, `P4_R13_*\`.
