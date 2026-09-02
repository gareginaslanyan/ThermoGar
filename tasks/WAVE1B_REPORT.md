# Wave 1B — installer pipeline (Э5). Result: PASS

Worktree `ThermoGar-w1b`, branch `wave1b-installer`. One command builds, one runs the smoke.
NSIS 3.12 was already installed at `C:\Program Files (x86)\NSIS\makensis.exe` — nothing downloaded;
`build_installer.ps1 -NsisPath` falls back to a portable copy under `ThermoGar-Installer-Assets\nsis\`.

| Script | Change |
|---|---|
| `launcher.pyw` | `_validate_trust` (15035-row trust manifest + receipt, pinned P0/RUNTIME/NATIVE anchors) → `_validate_install`: 6 required files + 5 directories + at least one `.tdb`. Files still held open; their `path\|bytes\|sha256` rows hash into an install identity that binds the run record. LocalAppData, `THERMOGAR_STATE_ROOT`, `MPLCONFIGDIR`, TMP/TEMP, `-B`, control server, Job object unchanged. |
| `healthcheck.py` | Same replacement, same identity formula. |
| `stop.pyw` | Dropped the SHA-256 pin on `healthcheck.py`. |
| `stage_payload.ps1` | Rewritten as an allowlist stager, no `-Expected*` gates. Emits `manifests\payload-manifest.json` as output, not a gate. |
| `build_installer.ps1` | Rewritten: notices → stage → makensis → sha256 → dist. `-Version` from `product-version.json`. |
| `ThermoGar.nsi` | Rewritten: `/D` defines only, `$PROGRAMFILES64\ThermoGar`, one Start Menu shortcut, Programs-and-Features entry, `/S` silent. Uninstaller aborts unless `launcher.pyw` is present and never touches `%LOCALAPPDATA%\ThermoGar`. |
| `generate_notices.ps1` | Was a 226-byte stub calling `verify_distribution_evidence.ps1`. Now builds `THIRD_PARTY_NOTICES.txt` (695 630 B) from 99 dist-info dirs plus a MatCalc open-databases section. |
| `smoke_installed.ps1` | New, replaces `test_lifecycle_synthetic.ps1`. |
| `product-version.json` | 0.3.0 / 0.3.0.0; the old SHA-pin fields are gone. |

**Payload** 15 084 files, 555.7 MB (`app\*.py`, `style.css`, `configs\`, `databases\converted|physical`, `.streamlit\config.toml`, 3 helpers, icon, docs, notices, whole runtime). **Installer** `dist\ThermoGar-0.3.0-win64.exe`, 118 626 778 B, SHA-256 `B5356FAEE34EE212570496A2FA723D3655C6822424DBFC262905505385D3E358`, build 1091.6 s.

**Smoke — all 7 PASS** (`dist\smoke-20260902T143452Z.json`): 1 install exit 0 · 2 files/shortcut/registry, 0 missing · 3 launcher from an unrelated cwd · 4 HEALTHY after 25.2 s · 5 `GET /` 200 + `/_stcore/script-health-check` 200 · 6 stop exit 0, 0 processes, ports free · 7 uninstall exit 0, 0 leftover files, registry and shortcut gone, `%LOCALAPPDATA%\ThermoGar` kept.

**Three pre-existing hangs, found only because the smoke uses a real install.** (a) `_cleanup` gave shutdown 5 s then called `_guard_forever()` — an unbounded sleep; a normal stop left a zombie supervisor holding the install open (now 60 s, `stop.pyw` waits 90 s). (b) Clearing `run.json` raced `stop.pyw`'s polling and lost on the first exclusive open → `_guard_forever()` again; now retried for 30 s (stop returns in 0.9 s). (c) A run record from a different install made the launcher permanently unstartable; `_recover_stale` now reads it with `allow_foreign` and still requires it be proved dead before rotating. Stalls now log to `%LOCALAPPDATA%\ThermoGar\logs\cleanup-stall.log` instead of hanging silently.

**Manual action needed:** two UAC clicks per smoke run (install, uninstall). Everything else is unattended; there is no non-interactive path without an elevated shell.

**Deviation:** step 5 cannot assert `"ThermoGar"` in the served HTML — Streamlit serves a shell titled `Streamlit` and applies the app title client-side, so that string is never present server-side. Substituted `/_stcore/script-health-check` → 200, which the launcher enables and which returns 200 only if `ThermoGar_app.py` ran without an uncaught exception. Strictly stronger.

**Archived, not deleted** — `_archive_codex\packaging\`: `build_installer.codex.ps1`, `stage_payload.codex.ps1`, `ThermoGar.codex.nsi`, `payload-policy.json`, 6 × `verify_*.ps1`, `generate_runtime_trust_manifest.ps1`, `generate_sbom.ps1`, `generate_payload_manifest.ps1`, `test_lifecycle_synthetic.ps1`, `clean_smoke.ps1`, `c15_fake_probe.py`, `stage_runtime_helpers.ps1`, `AppData\`. `_archive_codex\dist\`: `ThermoGar-0.2.0-ne02-win64.exe`, its receipt, `P4_R13_*\`.

**Commits** `3420cea` archive · `5361bd1` pipeline rewrite · `679c2ad` notes + LegalCopyright · `7294026` shutdown fixes. Not merged.

**Open questions.** Built from `app\` as-is while Wave 1A edits it — rebuild after 1A lands. Not yet tested on a clean PC/VM without Python (Э5 acceptance criterion). Upgrade-over-existing-install was exercised incidentally but is not a smoke step. `.venv-windows` was used only to run patch scripts; the runtime was untouched.
