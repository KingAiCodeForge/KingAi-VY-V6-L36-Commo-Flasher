## Flash tool for Holden VY Ecotec V6 — in-car and bench

you will need python (most likely installed to path), and pyserial. 

then after python is installed, you need pypi wheel pip installer for terminal.
run:
run_me_first_dependancie_installer.bat
run_second_launch_kingai_commie_flasher_gui.bat


# KingAI Commie Flasher v0.1.0

> **The first open-source Python flash tool for 68HC11 Delco ECUs.**
> No other Python tool on GitHub — or anywhere public — has ever written to flash on these ECUs.

> **STATUS: VIRTUAL TESTING — NOT YET TESTED ON REAL HARDWARE**
>
> The flash protocol is implemented and matches the OSE Enhanced Flash Tool V1.5.1 algorithm exactly.
> All code paths have been verified against the decompiled OSE source and tested with a Virtual ECU
> (LoopbackTransport loaded with real 128KB bin files). The kernel bytecodes, bank switching, sector
> erase sequences, and Mode 16 write framing are all confirmed correct in simulation.
>
> **First successful virtual read/write session completed 2026-02-17** — 20-minute session with
> multiple 128KB reads and writes through the full protocol stack (silence → unlock → kernel upload →
> bank-switched read/write → verify → cleanup). Read speed: ~0.6–1.4 KB/s (uncapped virtual).
>
> **Transport reliability hardened 2026-02-18** — Root cause analysis of RX stream desync bugs.
> Echo consumption eating response headers would shift the entire byte stream, causing cascading
> `Invalid length byte` / `Incomplete frame` / `Checksum error` failures across all subsequent retries.
> Fixed with bus resync (flush + delay) between retries, per-block read retries, and write retry
> bus flush. Off-by-one retry counting (`retry 11/10`) also fixed.
>
> **UI safety lockout implemented 2026-02-18** — During flash operations the GUI locks to the
> Log tab (event bus), disabling all other tabs, file operations, and flash-menu toggles.
> Disconnect during an active write requires explicit confirmation through a danger dialog.
> Window close is blocked entirely during writes. Reads can be cancelled safely at any time.
>
> **Open questions for hardware testing:**
> - PySerial throughput over real wire — cap at 5 KB/s with 64-byte blocks, or lower?
> - Minimum reliable block size (32 vs 64 bytes) before retry overhead dominates
> - Power stability during sector erase (~1 second per 16 KB sector)
>
> **This tool has not yet been connected to a physical ECU.**
> Until real-hardware testing is complete, use at your own risk. Keep a bench programmer (T48/TL866)
> as backup. If you flash before I do and want to report results, open an issue.

In-car flash read/write tool for the **Holden VY Ecotec V6** (Delco 68HC11F1, OS `$060A`, part number `92118883`).

1:1 port to Python of the OSE Enhanced Flash Tool V1.5.1 — VY in-car flash functionality as a single
Python script (~5720 lines) with PySide6 GUI and full CLI backend. Supports PySerial and FTDI D2XX
transports, with detailed logging and error handling.

Can be used in CLI mode or opened as a desktop app on Windows 10/11.

If anyone wants a `.bat` launcher or a `.exe` with all dependencies bundled, just ask.
The tool now includes a built-in 68HC11 disassembler, datalogger, table editor, and virtual ECU for
offline testing.

## Target Hardware

| Detail | Value |
|---|---|
| ECU | Delco/Delphi 68HC11F1 |
| OS ID | `$060A` |
| Part Number | `92118883` |
| Flash Chip | AMD 29F010 — 128 KB NOR, 8 x 16 KB sectors |
| Protocol | ALDL 8192 baud half-duplex serial |
| Device ID | `0xF7` (VX/VY) |

## What It Does

### Read

- **Full BIN read** — reads the entire 128 KB flash via the uploaded HC11 kernel and dumps to a `.bin` file
- **Sector-level progress** with bank switching across Bank 72 / 88 / 80
- **Per-block retries** — each 64-byte block retried up to 3 times with bus flush before skipping (no silent zero-fill)

### Write

- **BIN write** — erases sectors 0-6 (skips boot sector 7), writes 104 KB (`$2000`-`$1BFFF`)
- **CAL-only write** — erases sector 1 only, writes 16 KB calibration area (`$4000`-`$7FFF`). The CAL is padded to 128 KB in the file (same as OSE does it)
- **PROM write** — full 120 KB recovery write including boot sector (`$2000`-`$1FFFF`) — CLI only, not in GUI menu (dangerous)
- On-PCM checksum verification after every write
- Seed/key security unlock before any flash operation
- **Write retry with bus flush** — failed write chunks flush the RX buffer + 50ms settle before retrying, logs failing sector boundary address

### Flash Protocol Sequence (1:1 with OSE)

1. Mode 8 — silence ECU normal traffic
2. Mode 13 — seed/key security handshake (magic constant `37709`)
3. Mode 5 — enter programming mode
4. Mode 6 — upload HC11 flash kernel (3 blocks + erase/write/checksum routines)
5. Sector erase via uploaded kernel (bank + sector byte patching)
6. Mode 16 — stream write data in 32-byte chunks with bank remapping
7. On-PCM checksum verify
8. Cleanup — kernel sends `0xBB`, clears RAM, ECU resets

### Bank Mapping

```
Bank 72 (0x48) → Sectors 0-3 → File $0000-$FFFF   (1:1 mapping)
Bank 88 (0x58) → Sectors 4-5 → File $10000-$17FFF  (remapped to PCM $8000-$FFFF)
Bank 80 (0x50) → Sectors 6-7 → File $18000-$1FFFF  (remapped to PCM $8000-$FFFF)
```

### Additional Features
need to add this:
mode 1 datastream/acquistions, gets disabled when read or write when read or write is clicked for cal or bin. we will ahve the option in a checkbox with a WARNING and popout warning box to press yes or no, and then before it even starts that process of flashing it must stop the mode1 as key will be set to ign2, not running hopefully, when you flash. checkboxs in chaos tests for letting mode1 be active while the flash starts to see what happens. it will most likely brick as the flash erases the eeprom and then writes 32-64 blocks at a time, mode 1 wont exist when flash begins so it is needed to be off and then turned off automaticly when flash or read starts..
it also doesnt start with this on, there will be a button to connect mode1 datastream. default off. checkbox to choose if it checks the battery voltage before flashing if it is below 12.2v a popout do you want to flash battery is medium to low. after a flash is done it can be turned on again with its dedicated button.
a cant flash warning, that has a checkbox to turn this warning off and set the voltage number, stock is 12.0v or lower. wont start flash will ask yes or no. voltage to low.
this below is added, but untested in car. 
- **Mode 1 datalog** — 57-parameter live data stream to CSV (RPM, ECT, IAT, MAF, TPS, O2s, fuel trims, spark, knock, etc.)
- **Live tune** — Mode 10 RAM shadow writes for real-time calibration changes, patch of a bin would be needed and then testing. i think 250bytes is the max ram can handle? which would only be 5x5 but we could figure something out if this works.
- **Bin checksum** — verify or fix the 16-bit checksum at `$4006`-`$4007`
- **Calibration table viewer** — reads key tables (spark maps, fuel trim, OL AFR, TCC duty) from the bin
- **vEEPROM** — Virtual EEPROM management for the Virtual ECU (load/unload/erase/export/info)

## Safety Features (Implemented 2026-02-18)

### UI Lockout During Flash Operations

When a read or write is started (via menu or toolbar buttons):

1. **Switches to Log tab** — only the event bus / log output is visible
2. **All other tabs disabled** — Dashboard, Table Editor, Disassembler, Options greyed out and unclickable
3. **File menu locked** — Load, Save, Save As, Save Cal, Checksum all disabled
4. **Flash toggles locked** — Auto-checksum, Verify, High-speed, Ignore Echo cannot be toggled mid-operation
5. **View menu shortcuts disabled** — Ctrl+1 through Ctrl+8 won't switch tabs
6. **Connect/Disconnect and Refresh Port remain active** — you can always see your port state

Everything unlocks automatically when the operation finishes (success or fail).

### Disconnect Safety Gate

- **During a WRITE:** Big red warning dialog — "WRITE IN PROGRESS — DANGER" — explains the PCM will be bricked. Default button is **No**. User must deliberately click **Yes** to force disconnect. The operation is cancelled first, and the forced disconnect is logged as a critical event.
- **During a READ:** Cancels cleanly with a warning log — reads don't modify flash, PCM is safe.

### Window Close Protection

- **During a WRITE:** `closeEvent` is **blocked entirely** — the X button shows a critical dialog and `event.ignore()`. The window cannot be closed mid-write.
- **During a READ:** Cancels the read and closes normally.

### Transport Resilience (2026-02-18)

Fixes to the `_transact` / `_rx_frame` transport layer to prevent cascading desync:

| Bug | Root Cause | Fix |
|---|---|---|
| Cascading `Invalid length byte` errors | Echo consume ate response header bytes, shifting entire RX stream | `flush_input()` + 50ms `INTER_RETRY_DELAY_MS` between every retry in `_transact` |
| `retry 11/10` log message | `range(retries + 1)` = 11 iterations for `max_retries=10` | Changed to `range(retries)` — exactly N attempts |
| Write retries hammer same garbage | No bus flush between write chunk retries | `flush_input()` + delay in `write_flash_data` error path |
| Read silently inserts zeros on failure | `full_read` did `address += read_block` on first failure | Per-block retry up to `READ_BLOCK_MAX_RETRIES` (3) with bus flush, only skips after exhausted |
| No pause between retries | Retries fired immediately | `INTER_RETRY_DELAY_MS = 50` inserted between all retry attempts |

## Transports

All operations work through a swappable transport layer selected via CLI flag or GUI dropdown:

| Transport | Flag | Notes |
|---|---|---|
| PySerial | `--transport pyserial` | Default. Any USB-serial adapter (FTDI recommended) |
| FTDI D2XX | `--transport d2xx` | Direct FTDI driver, lower latency |
| Loopback | `--transport loopback` | Offline testing, simulated ECU (zeros) |
| Virtual ECU | `--transport vecu` | Load a real .bin as simulated ECU flash — full read/write cycle |

## Usage

### GUI

```
python kingai_commie_flasher.py
python kingai_commie_flasher.py gui
```

### CLI

```bash
# Read full bin from ECU
python kingai_commie_flasher.py read --port COM3 --output read.bin

# Write bin (sectors 0-6)
python kingai_commie_flasher.py write --port COM3 --input tune.bin

# Write cal only (sector 1, 16KB padded to 128KB file)
python kingai_commie_flasher.py write --port COM3 --input tune.bin --mode CAL

# Full recovery write (all 8 sectors)
python kingai_commie_flasher.py write --port COM3 --input tune.bin --mode PROM

# Live datalog to CSV
python kingai_commie_flasher.py datalog --port COM3

# Show ECU sensor info
python kingai_commie_flasher.py info --port COM3

# Verify/fix bin checksum
python kingai_commie_flasher.py checksum --input file.bin --fix

# List serial ports
python kingai_commie_flasher.py ports
```

### Common Options

```
--port COM3           Serial port (default: COM3)
--baud 8192           Baud rate (default: 8192)
--transport pyserial  Transport backend
--high-speed          Use high-speed read mode (kernel byte patch)
--retries 10          Max retry count
--chunk-size 32       Bytes per flash write frame
--ignore-echo         Strip echo bytes (default: on)
--no-ignore-echo      Disable echo stripping
--inter-frame-delay   Inter-frame delay in ms (default: 10)
--vecu-bin path.bin   .bin file for virtual ECU transport
```

## Dependencies

```
pip install pyserial PySide6
```

Optional: `ftd2xx` for D2XX transport, `PySide6` for GUI (CLI works without it).

## File Structure

```
kingai_commie_flasher/
├── kingai_commie_flasher.py       # Main tool — GUI + CLI backend (~5720 lines, everything in one file)
├── virtual_128kb_eeprom.py        # AMD 29F010 simulator — full state machine, byte program, sector erase
├── readme.md
├── settings.json                  # Persisted CommConfig + LogConfig (auto-saved on exit)
├── tools/
│   ├── hc11_disassembler.py       # Standalone 68HC11 disassembler (311 opcodes, VY V6 annotations)
│   ├── _verify_bytecodes.py       # Kernel bytecode verification tool
│   ├── virtual_aldl_frame_sender_and_vecu.py  # Standalone vECU ALDL server (for external testing)
│   └── ALDL_read_RAM_commands.py  # ALDL RAM read reference tool
├── kernel_ram_to_rom_write/
│   ├── README.md                  # How the kernel→flash data path works, byte-for-byte
│   └── output/                    # Captured flash images from write operations
├── logs/                          # Timestamped session logs (auto-created)
├── tests/
│   ├── test_kingai_commie_flasher.py  # 118 tests — protocol, framing, transport, kernel, vECU, events
│   ├── test_gui_functions.py      # 157 tests — GUI widgets, new tabs, view actions, FlashWorker setup
│   ├── test_vecu.py               # 5 tests — virtual ECU integration with real bin files
│   └── conftest.py                # Shared test fixtures (sys.path, QApplication, offscreen platform)
└── ignore/                        # Research notes, bin files, algorithm comparison docs
    ├── FLASH_TOOL_ALGORITHM_COMPARISON.md  # 7-tool algorithm extraction (OSE, PcmHammer, BMW, etc.)
    ├── OSE_FLASH_TOOL_COMPLETE_ANALYSIS.md # Full 28,985-line decompilation analysis
    ├── Live_tuning_ram_patch_plan.md       # Mode 10 RAM shadow write design
    ├── ose_flash_tool_improvements_found.md # Weaknesses and improvement plan + implementation status
    ├── plan.md                             # Master plan — all protocols, roadmap, constants
    ├── readme_wip.md                       # Historical design decisions, GUI wiring audit, safety interlock design
    └── gui_snippets.md                     # PySide6/Qt patterns and snippets
```

## GUI

PySide6 dark-theme desktop app with:

- **Toolbar** — Connection (port, transport), Bin File (load/save), Flash controls (Read ECU, Write ECU, write mode combo BIN/CAL)
- **Tab 1: Dashboard** — 18 live sensor gauges (RPM, ECT, IAT, TPS, MAF, Spark, Knock, AFR, O2, STFT, LTFT, Battery, IAC, Injector PW, Wheel Speed)
- **Tab 2: Table Editor** — Calibration table viewer (spark maps, fuel trim, OL AFR, TCC duty) from loaded bin
- **Tab 3: Disassembler** — Built-in 68HC11 disassembler with VY V6 address annotations, paste hex or load from bin
- **Tab 4: Log** — Real-time log viewer (same output as the log file, filterable). **This is the event bus — the only tab active during flash operations.**
- **Tab 5: Options** — Connection settings, timing, retry/write settings, flash behaviour checkboxes, persist on exit
- **Tab 6: Custom Flash** — Sector-level brick recovery: select individual 16KB sectors (0-7) to erase+write, or enter a custom hex address range for targeted reads/writes. **UNTESTED — implemented but not validated on real hardware.**
- **Tab 7: Chaos Test** — Automated stress test: read→write→readback→compare loop. Configurable cycles, write mode (BIN/CAL), inter-cycle delay, stop-on-fail. **UNTESTED — implemented but not validated on real hardware.**
- **Tab 8: Transport** — PySerial (top) and FTDI D2XX (bottom, scrollable) low-level settings: latency timer, USB timeouts, read buffer, flow control, timing offset sliders, vehicle presets. **UNTESTED — implemented from OSE analysis + FTDI specs, may need tuning.**

### Menu Bar (32 actions, all wired)

| Menu | Actions |
|---|---|
| **File** (5) | Load .bin (Ctrl+O), Save .bin (Ctrl+S), Save .bin As (Ctrl+Shift+S), Save .cal, Exit (Alt+F4) |
| **Connection** (7) | Connect/Disconnect (Ctrl+K), Refresh Ports (F5), vEEPROM submenu (Load Ctrl+Shift+L / Unload Ctrl+Shift+U / Erase Ctrl+Shift+E / Export Ctrl+Shift+X / Info) |
| **Flash** (8) | Read ECU (Ctrl+R), Write BIN (Ctrl+W), Write CAL (Ctrl+Shift+W), Cancel (Esc), Auto-checksum ☑, Verify ☑, High-speed ☐, Ignore echo ☐ |
| **Tools** (3) | Verify/Fix Checksum, ECU Info (Mode 1 → QMessageBox), Options |
| **View** (8) | Dashboard (Ctrl+1), Table Editor (Ctrl+2), Disassembler (Ctrl+3), Log (Ctrl+4), Options (Ctrl+5), Custom Flash (Ctrl+6), Chaos Test (Ctrl+7), Transport (Ctrl+8) |
| **Help** (1) | About |

> Full action → button → handler wiring map: see [`ARCHITECTURE.md`](ARCHITECTURE.md)

### CLI Commands (7 commands)

| Command | Description |
|---|---|
| `gui` | Launch GUI (default if PySide6 available) |
| `read` | Read full bin from ECU (`--output`, `--cal`, `--cal-padded`) |
| `write` | Write bin to ECU (`--mode BIN\|CAL\|PROM`, `--verify`/`--no-verify`, `--auto-checksum`/`--no-auto-checksum`) |
| `datalog` | Live Mode 1 data stream to CSV (`--output`, `--params`) |
| `info` | Show ECU sensor values via Mode 1 |
| `checksum` | Verify or fix bin checksum (`--input`, `--fix`) |
| `ports` | List available serial ports |

## Logging

Every session writes a timestamped log to `logs/` with full frame-level detail — every byte sent and
received, timing, retries, and errors. Log filenames include the timestamp so parallel sessions don't
collide. Console shows WARNING+ by default; log file records DEBUG+ (every TX/RX frame).

## Status

### What's Working (2026-02-18)

**Core Protocol:**
- Flash read/write protocol — 1:1 match with OSE V1.5.1 algorithm
- Kernel upload (3 blocks → RAM $0100/$0200/$0300), sector erase, bank-switched write
- On-PCM checksum verify after write
- Virtual ECU transport — load a real .bin, simulate full read/write/erase cycles
- LoopbackTransport with all ALDL modes handled (1, 2, 3, 4, 5, 6, 8, 9, 10, 13, 16)
- Heartbeat pre-seeded for instant virtual connect
- Tested with 20-minute virtual session — multiple complete read/write cycles confirmed working

**Transport Reliability (2026-02-18):**
- `_transact` acquires thread lock + flushes RX buffer + 50ms inter-retry delay between all retry attempts
- Thread-safe serial access — DataLogger and FlashWorker cannot collide
- Write chunk retries flush the bus before re-sending
- Read blocks retry up to 3 times with bus flush before skipping — single `block_retries` local counter
- Retry counting fixed (no more `retry 11/10`)
- `INTER_RETRY_DELAY_MS = 50`, `READ_BLOCK_MAX_RETRIES = 3`, `SECTOR_SIZE = 0x4000`
- `enable_chatter()` returns False with warning when no ACK received (was silently returning True)

**GUI Safety (2026-02-18):**
- All tabs locked except Log during read/write ops (switch to event bus)
- Flash-menu toggles (auto-checksum, verify, high-speed, echo) locked during ops
- File menu (load/save/checksum) locked during ops
- UI lock/unlock extracted to `_lock_ui_for_flash()` / `_unlock_ui_after_flash()` — shared by `_start_flash_op` and `_start_custom_flash_op`
- FlashWorker + QThread cleaned up via `deleteLater()` on thread finish — no Qt object leaks
- Disconnect during write requires explicit danger confirmation
- Window close blocked during writes (`event.ignore()`)
- Reads can be cancelled/disconnected safely anytime
- Pre-write backup read stores sectors-to-be-erased in `_backup_bin` before erase (in-memory recovery data)

**Features:**
- Built-in 68HC11 disassembler (311 opcodes + VY V6 address annotations)
- PySide6 GUI with 8 tabs (Dashboard, Table Editor, Disassembler, Log, Options, Custom Flash, Chaos Test, Transport)
- Full CLI backend for headless operation (7 commands, full arg parsing)
- 275 automated tests (118 protocol/core + 157 GUI + 5 vECU integration) — all passing
- Mode 1 datalog (57 parameters → CSV, line-buffered — no data loss on crash)
- ECU Info (Mode 1 → formatted QMessageBox with key parameters)
- 32 menu actions all wired to handlers (see [`ARCHITECTURE.md`](ARCHITECTURE.md) for full wiring map)
- vEEPROM management (load/unload/erase/export/info)
- Settings persistence on exit (CommConfig + LogConfig → JSON)
- Read speed (virtual, uncapped): 0.6–1.4 KB/s across 128KB
- Custom Flash widget: sector-level brick recovery (select sectors 0-7, custom hex range read/write)
- Chaos Test widget: automated stress test (configurable cycles, write mode, delay, stop-on-fail, byte compare)
- Transport Settings widget: PySerial + FTDI D2XX low-level config (latency, timeouts, flow control, vehicle presets)
- FlashWorker: setup_custom_write, setup_custom_read, setup_chaos methods for new tab operations
- Event system: timestamp injection (LogConfig.log_timestamps), all callbacks accept **kwargs

### What's NOT Done Yet

- **Real ECU hardware test** (the big one)
- **Live KB/s speed viewer** — real-time throughput in the status bar during flash ops
- **Elapsed time on progress bar** — `Writing $XXXX — 45% — 2.3 kbps — 0:34 elapsed`
- **Global crash/exception logging** — `sys.excepthook` + unhandled QThread exception catcher with reason (close button, OOM, script bug, hard crash)
- **Virtual baud rate cap** — throttle LoopbackTransport to realistic speeds (default 5 KB/s, configurable)
- **Baud ramp after kernel upload** — 8192 → higher baud for faster data transfer
- ~~**Chaos test tab**~~ — **IMPLEMENTED** (Tab 7)
- **RAM flash tab** — Mode 10 live tune writes to RAM shadow (real-time calibration)
- **Send ALDL command tab** — manual frame builder/sender like OSE's frmSendALDLFrame
- **EEPROM write support** ($0E00-$0EFF — VIN/immobilizer area)
- ~~**Pre-write backup read**~~ — **IMPLEMENTED** — reads sectors-to-be-erased into `_backup_bin` before erase
- **Backup to disk** — write `_backup_bin` to file so recovery survives app crash
- **Diff-write** (flash only changed sectors)
- **Partial CAL checksum** for padded calibration files
- **Voltage monitoring** during flash operations
- **Save As dialog** — `action_save_as` currently calls same handler as Save (no file picker)

### CAL-after-BIN Write — Not Needed

A BIN write already writes `$2000-$1BFFF` which includes the calibration area at `$4000-$7FFF`.
The cal is sector 1 of bank 72 — it's inside the BIN range. Writing a CAL on top of a fresh BIN
would just re-erase sector 1 and re-write the same 16KB you already wrote. Pointless and doubles
the sector wear. If you want a different cal on a stock BIN, merge it first — `BinFile.load()`
already auto-pads 16KB `.cal` files into a 128KB image at `$4000`.

### CLI Quick Reference

```
python kingai_commie_flasher.py gui                                    # Launch GUI
python kingai_commie_flasher.py read --port COM3 --output read.bin     # Read ECU to file
python kingai_commie_flasher.py write --port COM3 --input tune.bin     # Write bin to ECU  
python kingai_commie_flasher.py write --port COM3 --input tune.bin --mode CAL   # Cal-only write
python kingai_commie_flasher.py datalog --port COM3                     # Live datalog to CSV
python kingai_commie_flasher.py info --port COM3                        # Show ECU sensor values
python kingai_commie_flasher.py checksum --input file.bin               # Verify/fix checksum
python kingai_commie_flasher.py ports                                   # List serial ports
```

### First Hardware Test Checklist

If you want to be the first to test on real hardware:
1. Do a **Read ECU** first to verify comms work
2. Save that read as your backup
3. Keep a bench programmer (T48/TL866) handy
4. Start with a **CAL-only write** (1 sector, 16KB) before attempting a full BIN write (7 sectors, 104KB)



## Related Projects

### AMD 29F010 Flash Sector Map (128KB = 8 × 16KB)

The Custom Flash tab (Tab 6) works at the sector level. This is the mapping between file offsets, HC11 banks, and what GM/Holden stores in each sector:

| Sector | File Offset | Bank | Erase Byte | Contents | Erased by BIN? | Erased by PROM? |
|--------|------------|------|-----------|----------|---------------|----------------|
| 0 | `$00000-$03FFF` | 0x48 (72) | 0x20 | OS Vectors / Boot area | Yes | Yes |
| 1 | `$04000-$07FFF` | 0x48 (72) | 0x40 | **Calibration (CAL)** — fuel/spark maps, checksum | Yes (CAL mode) | Yes |
| 2 | `$08000-$0BFFF` | 0x48 (72) | 0x80 | OS Page 1 | Yes | Yes |
| 3 | `$0C000-$0FFFF` | 0x48 (72) | 0xC0 | OS Page 2 | Yes | Yes |
| 4 | `$10000-$13FFF` | 0x58 (88) | 0x80 | OS Page 3 (bank-switched) | Yes | Yes |
| 5 | `$14000-$17FFF` | 0x58 (88) | 0xC0 | OS Page 4 (bank-switched) | Yes | Yes |
| 6 | `$18000-$1BFFF` | 0x50 (80) | 0x80 | OS Page 5 (bank-switched) | Yes | Yes |
| 7 | `$1C000-$1FFFF` | 0x50 (80) | 0xC0 | **OS Page 6 + Reset Vectors (BOOT)** | **No** (skip) | Yes |

**Sector 7 is the boot sector.** Erasing it without a bench programmer (T48/TL866) = permanent brick. BIN mode deliberately skips sector 7. Only PROM mode (full recovery) erases it.

**Brick recovery example:** If a BIN write failed partway through sectors 3-5, use Custom Flash to select only sectors 3, 4, 5 and re-flash them from a known-good .bin without touching the rest.

### Transport Settings (Tab 8) — UNTESTED

The Transport tab exposes low-level PySerial and FTDI D2XX parameters derived from the OSE V1.5.1 analysis. Key values:

| Setting | Default | Effect |
|---------|---------|--------|
| FTDI Latency Timer | 2ms (vs FTDI's 16ms factory) | ~30% faster reads |
| D2XX Read/Write Timeout | 200ms | Aggressive — increase if reads fail |
| PySerial Read Timeout | 100ms | Lower = faster detection, may miss slow ECUs |
| Timing Offsets | All 0ms | Add +5-25ms if real hardware comms are flaky |
| Vehicle Presets | VR/VS=10ms IFD, VT/Bench=4ms, Logger=1ms | Inter-frame delay from OSE |

These have **not been tested on real hardware** — they're starting points from the OSE analysis. The timing offset sliders let you add extra delays if needed.

---

Other open-source tools for Delco 68HC11 ECU development by [KingAiCodeForge](https://github.com/KingAiCodeForge):

| Repo | Description |
|---|---|
| [KingAi_68HC11_C_Compiler](https://github.com/KingAiCodeForge/KingAi_68HC11_C_Compiler) | C compiler targeting Motorola 68HC11 — write ECU patches in C instead of hand-assembled hex |
| [kingaustraliagg-vy-l36-060a-enhanced-asm-patches](https://github.com/KingAiCodeForge/kingaustraliagg-vy-l36-060a-enhanced-asm-patches) | Assembly patches and reverse-engineered address map for VY V6 L36 $060A (92118883) |
| [TunerPro-XDF-BIN-Universal-Exporter](https://github.com/KingAiCodeForge/TunerPro-XDF-BIN-Universal-Exporter) | Universal exporter for TunerPro XDF definitions and BIN data |