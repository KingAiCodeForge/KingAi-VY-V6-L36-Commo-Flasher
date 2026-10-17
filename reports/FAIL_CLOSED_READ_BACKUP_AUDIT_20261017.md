# Fail-closed read and pre-erase backup audit — 17 October 2026

**Research branch only. No live ECU/ALDL/J2534/serial testing was performed.**

The initial source audit identified three definite control-flow hazards in
`kingai_commie_flasher.py`:

1. `FlashOp.full_read()` could exhaust a block's retries, skip 64 bytes and
   still return a 128 KiB `bytearray` with default zero bytes in the unread
   region. The CLI could then save it as a successful BIN.
2. `FlashOp.custom_read()` likewise skipped exhausted blocks, returning a
   potentially zero-padded buffer. Its cross-block `_cread_retries` state was
   not reset on a successful block.
3. `FlashOp.full_write()` logged a failed/incomplete pre-erase backup but
   proceeded into `erase_sectors()`. A partial nonempty block was counted as
   success.

## Actual code changes

- Full read: require a **complete requested block**; after the final failed
  attempt, log an error, perform kernel cleanup and chatter restore, and
  return `None` rather than return a partial/zero-filled image.
- Custom read: reject truncated data blocks, reset retry count after each
  successfully completed block, abort on exhaustion and clean up even when
  cancelled.
- Full write: count each pre-erase backup chunk complete only when it meets
  its expected byte size. If any chunk fails, clear the in-memory backup,
  clean up and return `False` **before sector erase**.

A 9-case mock-controller regression file was added at
`tests/test_failclosed_incomplete_reads_and_preerase_backup.py` for
missing/short read blocks, full successful synthetic reads, retry reset,
missing/short backup refusal and successful-backup erase admission.

## Independent testing required before merge

From the repository root, with pytest installed:

```powershell
py -m pytest tests/test_failclosed_incomplete_reads_and_preerase_backup.py -v
py -m pytest tests/test_kingai_commie_flasher.py tests/test_vecu.py -v
```

The new tests are **written but not yet run against the actual GitHub
checkout**. Mock tests do not qualify ALDL framing, kernel behaviour, sector
erase, per-chip programming, flash recovery or physical vehicle safety.

This PR does not make writes safe. It only prevents several known false
success/unsafe-proceed conditions. **Keep live writes disabled pending** exact
ECU identification, stable voltage, repeated real reads, known-good external
backup, checksum profile, bench recovery and scope observations.

Follow-up unresolved tasks:

- `custom_write()` still lacks a corresponding verified before-erase backup
  gate and requires separate scrutiny.
- The stored full-write backup is only in process memory, not a durable
  recovery image; physical power loss will discard it.
- Individual hardware variants, NOR part and voltage/flash timing remain
  unverified; not every part with a similar part number shares programming
  characteristics.
- Confirm `read_ram()` returned lengths with independent wire captures on a
  spare target before enabling a physical flash session.
- Separate offline `checksum` and `ports` command flows from the
  connection phase of `run_cli()`; they currently connect unnecessarily.
