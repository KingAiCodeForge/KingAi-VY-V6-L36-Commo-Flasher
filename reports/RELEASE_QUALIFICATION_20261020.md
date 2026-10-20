# 0.2.0a1 experimental qualification candidate

This is software research qualification, not a published stable release. The
original public main was `ad18c2bf042a05d93811a091d80698f1e2193986`.
All nine original branch tips are preserved and reconciled; the exact refs,
trees and blob identities are in `SOURCE_RECONCILIATION_20261020.json`.
No original ref or prototype was deleted, forced or rewritten. No private
repository, real firmware, calibration input or machine-local research was
imported. The local preservation bundle is not a release asset.

Fresh Windows/Python 3.13 source verification: **477 passed, 11 subtests passed**
in 40.27 seconds, including PySide6 offscreen GUI tests. Reproduce from an
isolated checkout with test, GUI and serial extras installed:

```powershell
$env:QT_QPA_PLATFORM = 'offscreen'
$env:KINGAI_FLASHER_DATA_DIR = Join-Path $env:TEMP 'flasher-qualification-data'
$env:PYTHONIOENCODING = 'utf-8'
python -m pytest -q --basetemp .pytest-tmp-qualification --disable-warnings
python -m build --no-isolation
```

Use a new writable `--basetemp` and build temporary directory if the executor's
default temporary directory is restricted. Earlier collection failed because
an optional FTDI package lacked its native DLL; the optional import now reports
it unavailable. An initial newly authored test had a misplaced assertion; it
was corrected before the passing complete run. Neither failed attempt is
counted as qualification. Installed-package checks and exact final commit,
artifact member lists, dependency versions and SHA256 hashes are recorded in
the coordinating lane's separate receipt after building the final snapshot.

The changes enforce exact Mode 2 frames, bounded retries at the same address,
per-block retry reset, complete read admission, target/mode response matching,
declared response shape, exact chip identity, exact backup lengths and
cancellation before erase. Cleanup requires its acknowledgement. Disk outputs
are created exclusively; checksum fixes require a separate output. Missing or
malformed explicit images fail instead of becoming zero-filled virtual images.
The caller's original BIN is not modified by full-write checksum correction.

Incomplete reads retain actual bytes and each raw response. CLI failures save
these separately in an exclusive `.incomplete` directory with a range/hash
manifest; GUI failures use the configured runtime data directory. Successful
custom ranges are separate `.capture` diagnostics with explicit addresses,
never admitted as a complete BIN. No absent byte is synthesized in read or
backup evidence. Explicit CAL export/padding remains a documented generated
container transformation, not proof of reading a full image.

Pre-erase backups contain only captured address ranges in volatile RAM.
They are not durable, external, verified recovery images. Full/custom physical
programming and physical live-tuning are held; `custom_write` remains a virtual
prototype. Low-level protocol APIs and raw serial sender tools remain expert
research interfaces with no hardware qualification. No serial/USB device was
opened and no physical ECU access, write, erase or kernel execution occurred.

Script review scope is explicit in `SCRIPT_REVIEW_20261020.csv`,
`CORE_SOURCE_REVIEW_20261020.md` and `PORTABILITY_AND_PUBLIC_AUDIT_20261020.md`.
The remaining GUI section has aggregate tests, not individual inspection of
every control flow. Batch launchers were inspected but not executed. Linux,
macOS, other Python versions, live serial, native FTDI driver, actual TCP server
sessions, electrical timing, board/chip geometry, actual kernel execution,
independent opcode/table truth, on-PCM checksum correctness, power loss and
physical recovery were not validated. Virtual transports are functional test
doubles and do not execute the embedded HC11 kernel. The RAM-to-ROM capture
directory is historical design documentation without its proposed driver.

**Release publication HOLD:** the source identifies kernel arrays and retained
reference bytes as derived from OSE V1.5.1 decompilation and describes that tool
as closed-source. Existing project MIT text does not independently establish
third-party redistribution rights. Confirm provenance/permissions before
publishing new source or binary distribution assets. No stable version or
physical-flashing approval is implied by this alpha candidate or passing tests.
