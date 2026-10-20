# Portability and public-content audit, 20 October 2026

This is a software research qualification record. No serial port was opened, no
physical ECU accessed, and no physical program/erase/recovery test was performed.
The per-script inspection and execution scopes are in `SCRIPT_REVIEW_20261020.csv`.
An entry that says source scan or standalone demo does not establish full semantic
coverage of that module.

## Runtime configuration and files

`KINGAI_FLASHER_DATA_DIR` selects a user-owned runtime directory, including paths
with spaces. Without it, the application uses the platform user data location:
`LOCALAPPDATA/kingai-flasher` on Windows and
`XDG_DATA_HOME/kingai-flasher` (or `~/.local/share/kingai-flasher`) elsewhere.
Logs, saved GUI settings and recovery metadata no longer write to the source or
installed package. Recovery metadata is a progress record, not a durable firmware
backup or a proven resume/recovery procedure. An unwritable log location prints a
warning; it does not silently claim a log was persisted.

The root `settings.json` is a sanitized generic example. Installed defaults come
from the configuration dataclasses; an existing user settings file is read from
the runtime directory. No legacy settings or firmware is automatically moved.

The checksum CLI is local and never opens a transport. `checksum --fix` requires
`--output` for a separate corrected copy. CLI output collisions are refused before
connection, and new file creation uses exclusive writes. Source BINs are preserved.
A failed standalone read with `--output` saves only its actually received prefix
to `.partial` plus explicitly incomplete JSON metadata, including the failed raw
response. It never saves a complete-looking BIN on failure.
The two image comparison diagnostics require explicit paths, recognize length
differences, and never write their inputs. Explicit missing or malformed virtual
ECU image paths fail instead of substituting a zero-filled image.

The dependency installer creates/uses a project `.venv`, installs the local
package with GUI and serial extras, and returns nonzero on failure. The launcher
quotes paths and supports an explicit full interpreter path through
`KINGAI_FLASHER_PYTHON`. The package can also be installed into a separately chosen
virtual environment with `python -m pip install ".[gui,serial]"`. Neither batch
file was executed during this audit; their review was static. Installing Python
dependencies does not qualify the underlying ECU operations.

## Executed checks

- `python -m pytest tests/test_portability.py -q`: **16 passed** on Windows,
  Python 3.13. The successful run used a fresh explicit workspace `--basetemp`.
  It covers arbitrary working directories, spaces in paths, missing optional
  dependencies using `-S`, invalid arguments before connection, exclusive output,
  preserved input bytes, strict standalone read frames, exact partial-prefix/raw-frame
  evidence and explicit image errors.
- `tests/_audit_sizes.py`: exit 0 after correcting project-root lookup.
- `tools/_verify_bytecodes.py`: exit 0; eight actual `FlashKernel` constants match
  retained reference arrays. The old script compared duplicate static arrays and
  could print success despite a mismatch; it now uses actual code and fails on a
  mismatch. Equality is not hardware or rights validation.
- `tools/hc11_disassembler.py`: bundled standalone demonstration exits 0.
- `virtual_128kb_eeprom.py`: seven-case software self-test exits 0.

The first portability invocation hit the executor's inaccessible default temp
directory (one passed, ten fixture errors); correcting the test temp directory
resolved that environment issue. A later source build initially encountered the
same executor temp restriction; a preliminary wheel/sdist build succeeded after using an explicit writable
temp directory. Final package build/install results belong to the coordinating
release lane after all concurrent source changes.

A preliminary wheel installed offline with `--no-index --no-deps` into a clean
virtual environment whose path contained spaces. Installed `kingai-flasher --help`
and `kingai-aldl-read --loopback --address 0x4000 --count 1 --no-hexdump`
exited 0 from a different working directory. Import location was confirmed inside
that environment; serial, GUI and FTDI extras were all absent. This is an installed
entrypoint smoke check of a preliminary build, not final artifact qualification.

These results are distinct from the coordinating lane's full source/GUI/installed
suite. No Linux/macOS, actual FTDI driver, real serial transport, physical hardware,
or recovery qualification is claimed. The optional FTDI import now handles a
missing native DLL as unavailable instead of crashing all CLI/test collection.

## Exclusions and exposure review

The fresh public clone contained no tracked raw BIN/CAL/XDL capture, credentials,
account logs, private/customer inputs or machine configuration. Its local
`info/exclude` contained only Git's template comments and no global excludes file
was configured. Existing source `settings.json` contains generic protocol/logging
defaults only. No other repository or private source was read or copied.

Ignore rules remain protective. Added exclusions cover raw `.cal`, `.partial`
evidence and legacy local recovery/settings metadata. Existing exclusions for
BINs, captures, environment secrets, local research, runtime logs, and build output
remain. The ignored machine-specific debug script names are absent from this fresh
clone, so there were no local files to sanitize or promote. Existing public image
diagnostics were sanitized in place; no broad unignore was performed.

The package configuration uses an explicit module/package list and source manifest
patterns. Release assets still require a final member-by-member review after the
last source changes; generated logs and raw firmware must not become assets.

## Remaining model and rights holds

The standalone virtual ECU is a functional test double. It acknowledges uploaded
kernel data without executing HC11 instructions. This audit added malformed-frame,
short-key, out-of-range read and malformed write refusal, but that does not make the
model equivalent to a physical ECU. The flash model completes polling immediately;
its reset/data-byte handling and protected whole-chip erase behavior require a
separate fidelity review. Historical statements of cycle accuracy, exact physical
capture or bootability are not established by these tests.

The main module identifies the implementation and retained reference bytecode as
derived from OSE Enhanced Flash Tool / decompiled VB.NET. The repository's MIT
notice describes the public project, but it does not independently establish the
third party's permission for every derived component. No proprietary firmware or
new third-party content was added. Confirm provenance and redistribution rights
before treating a new binary/source release as rights-cleared. This audit cannot
certify that question.
