# VY $060A flasher: fail-closed offline read/write gates

17 October 2026 — **REVIEW ONLY / NOT HARDWARE QUALIFIED**.

This branch changes `FlashOp.full_read` and the pre-erase phase of
`FlashOp.full_write`. It does not modify kernel bytecodes, flash routines,
sector maps, tuning calibration, flash protocol, or the vehicle.

## Changes

1. A full read requires **exactly 64 bytes per block**. A missing, short or
   overlong Mode 2 block gets the configured number of retries and then aborts
   with `None`. It no longer skips that block and returns a plausible
   128 KiB BIN containing zero-filled gaps.
2. A write now compares `read_flash_info()` to the exact
   `FLASH_AMD_29F010` identifier **before** any erase or backup operation.
   Missing or different IDs are refused. This is a basic software gate, **not
   qualification of Am29F010 hardware**, much less CAT28F010 or Am29F040.
3. Every pre-erase backup response must contain its expected 64 bytes. A
   missing, short, long or cancelled backup aborts before `erase_sectors`,
   clears the partial in-memory copy and attempts cleanup/reset.
4. Source-preserving, mocked-communication pytest regressions cover rejected
   reads, a complete synthetic read, rejected chip IDs, incomplete backups,
   cancellation and the permitted progression *only as far as a mocked,
   deliberately failed erase stage*.

## Manual reproduction

```powershell
python -m pytest -q tests/test_flash_failclosed_gates.py
python -m pytest -q tests/test_kingai_commie_flasher.py tests/test_vecu.py
```

The code was compared to GitHub source and underwent static replacement /
presence checks when authored. **The complete Python suite and live Windows
tests have not been executed in this environment.** GitHub Actions is not a
substitute for vehicle hardware validation.

## Remaining safety blockers

- Backup exists **only in volatile memory**, not a durable exact-hash file with
  independent write/readback recovery. Unknown transport failure semantics
  remain.
- A recognised chip ID does not prove programming voltage/sector geometry,
  flash-write support, watchdog timing, protected boot sectors or recovery.
- Test/calibration image identity, write/erase boundaries, power supervision,
  asynchronous GUI-state handling, cancellation and rollback must be separately
  validated.
- Real ECU/bench read and destructive write/recovery testing remain unperformed.
- No physical flash should be attempted based on this branch.

Related: docs-only [safety disclosure PR #2](https://github.com/KingAiCodeForge/KingAi-VY-V6-L36-Commo-Flasher/pull/2).
