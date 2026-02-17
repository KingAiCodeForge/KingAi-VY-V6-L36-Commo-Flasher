## Flash tool for Holden VY Ecotec V6 — in-car and bench

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
> All 6 "Transaction failed" errors in that session were caused by a missing Mode 9 handler in the
> LoopbackTransport — fixed in commit `84e3953`.
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
Python script with PySide6 GUI and full CLI backend. Supports PySerial and FTDI D2XX transports, with
detailed logging and error handling.

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

### Write

- **BIN write** — erases sectors 0-6 (skips boot sector 7), writes 104 KB (`$2000`-`$1BFFF`)
- **CAL-only write** — erases sector 1 only, writes 16 KB calibration area (`$4000`-`$7FFF`). The CAL is padded to 128 KB in the file (same as OSE does it)
- **PROM write** — full 120 KB recovery write including boot sector (`$2000`-`$1FFFF`)
- On-PCM checksum verification after every write
- Seed/key security unlock before any flash operation

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

- **Mode 1 datalog** — 57-parameter live data stream to CSV (RPM, ECT, IAT, MAF, TPS, O2s, fuel trims, spark, knock, etc.)
- **Live tune** — Mode 10 RAM shadow writes for real-time calibration changes
- **Bin checksum** — verify or fix the 16-bit checksum at `$4006`-`$4007`
- **Calibration table viewer** — reads key tables (spark maps, fuel trim, OL AFR, TCC duty) from the bin

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
```

## Dependencies

```
pip install pyserial PySide6
```

Optional: `ftd2xx` for D2XX transport, `PySide6` for GUI (CLI works without it).

## File Structure

```
kingai_commie_flasher/
├── kingai_commie_flasher.py       # Main tool — GUI + CLI backend (~4200 lines, everything in one file)
├── virtual_128kb_eeprom.py        # AMD 29F010 simulator — full state machine, byte program, sector erase
├── readme.md
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
│   ├── test_kingai_commie_flasher.py  # 118 tests — protocol, framing, transport, kernel, vECU
│   ├── test_vecu.py               # Virtual ECU integration tests
│   ├── test_gui_functions.py      # GUI widget tests
│   └── conftest.py                # Shared test fixtures
└── ignore/                        # Research notes, bin files, algorithm comparison docs
    ├── FLASH_TOOL_ALGORITHM_COMPARISON.md  # 6-tool algorithm extraction (OSE, PcmHammer, etc.)
    ├── OSE_FLASH_TOOL_COMPLETE_ANALYSIS.md # Full 28,985-line decompilation analysis
    ├── Live_tuning_ram_patch_plan.md       # Mode 10 RAM shadow write design
    ├── ose_flash_tool_improvements_found.md # Weaknesses and improvement plan
    ├── plan.md                             # Master plan — all protocols, roadmap, constants
    └── gui_snippets.md                     # PySide6/Qt patterns and snippets
```

## GUI

PySide6 dark-theme desktop app with:

- **Toolbar** — Connection (port, transport), Bin File (load/save), Flash controls (Read ECU, Write ECU, write mode combo)
- **Tab 1: Dashboard** — 18 live sensor gauges (RPM, ECT, IAT, TPS, MAF, Spark, Knock, AFR, O2, STFT, LTFT, Battery, IAC, Injector PW, Wheel Speed)
- **Tab 2: Table Editor** — Calibration table viewer (spark maps, fuel trim, OL AFR, TCC duty) from loaded bin
- **Tab 3: Disassembler** — Built-in 68HC11 disassembler with VY V6 address annotations, paste hex or load from bin
- **Tab 4: Log** — Real-time log viewer (same output as the log file, filterable)
- **Tab 5: Options** — Connection settings, timing, retry/write settings, flash behaviour checkboxes

Menu bar: File, Connection, Flash, Tools, View, Help

## Logging

Every session writes a timestamped log to `logs/` with full frame-level detail — every byte sent and
received, timing, retries, and errors. Log filenames include the timestamp so parallel sessions don't
collide. Console shows WARNING+ by default; log file records DEBUG+ (every TX/RX frame).

## Status

### What's Working (2026-02-17)

- Core flash read/write protocol — 1:1 match with OSE V1.5.1 algorithm
- Kernel upload (3 blocks → RAM $0100/$0200/$0300), sector erase, bank-switched write
- On-PCM checksum verify after write
- Virtual ECU transport — load a real .bin, simulate full read/write/erase cycles
- LoopbackTransport with all ALDL modes handled (1, 2, 3, 4, 5, 6, 8, 9, 10, 13, 16)
- Heartbeat pre-seeded for instant virtual connect
- Built-in 68HC11 disassembler (311 opcodes + VY V6 address annotations)
- PySide6 GUI with 5 tabs (Dashboard, Table Editor, Disassembler, Log, Options)
- Full CLI backend for headless operation
- 118 automated tests passing
- Mode 1 datalog (57 parameters → CSV)
- Tested with 20-minute virtual session — multiple complete read/write cycles confirmed working
- Read speed (virtual, uncapped): 0.6–1.4 KB/s across 128KB

### What's NOT Done Yet

- **Real ECU hardware test** (the big one)
- **KB/s rate logging** — log throughput for every read/write operation
- **Virtual baud rate cap** — throttle LoopbackTransport to realistic speeds (default 5 KB/s, configurable)
- **Baud ramp after kernel upload** — 8192 → higher baud for faster data transfer
- **Chaos test mode** — automated read→write→read→write loop until failure with configurable variables
- **RAM flash tab** — Mode 10 live tune writes to RAM shadow (real-time calibration)
- **Send ALDL command tab** — manual frame builder/sender like OSE's frmSendALDLFrame
- **EEPROM write support** ($0E00-$0EFF — VIN/immobilizer area)
- **Pre-write backup read** (safety feature)
- **Diff-write** (flash only changed sectors)
- **Partial CAL checksum** for padded calibration files
- **Voltage monitoring** during flash operations

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

Other open-source tools for Delco 68HC11 ECU development by [KingAiCodeForge](https://github.com/KingAiCodeForge):

| Repo | Description |
|---|---|
| [KingAi_68HC11_C_Compiler](https://github.com/KingAiCodeForge/KingAi_68HC11_C_Compiler) | C compiler targeting Motorola 68HC11 — write ECU patches in C instead of hand-assembled hex |
| [kingaustraliagg-vy-l36-060a-enhanced-asm-patches](https://github.com/KingAiCodeForge/kingaustraliagg-vy-l36-060a-enhanced-asm-patches) | Assembly patches and reverse-engineered address map for VY V6 L36 $060A (92118883) |
| [TunerPro-XDF-BIN-Universal-Exporter](https://github.com/KingAiCodeForge/TunerPro-XDF-BIN-Universal-Exporter) | Universal exporter for TunerPro XDF definitions and BIN data |