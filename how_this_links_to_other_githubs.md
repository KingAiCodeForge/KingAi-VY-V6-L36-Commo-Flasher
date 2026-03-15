# How KingAI Commie Flasher Links to Other Repos

> All repos by [KingAiCodeForge](https://github.com/KingAiCodeForge) — same target ECU, same person, different tools.
>
> **⚠️ ADDRESS NOTE (Feb 20, 2026):** `$0C468`/`$0FFBF` below are **file offsets**, not CPU addresses.
> CPU addresses are `$C468`–`$FFBF` (bank1 overlay, 4-digit HC11 max). See `FREE_SPACE_ANALYSIS_DEFINITIVE.md`.

---

## The Big Picture

Three repos form a complete toolchain for the Holden VY V6 Ecotec L36 Delco ECU ($060A, 92118883, 68HC11F1, AMD Am29F010 128KB NOR flash):

```
┌──────────────────────────────────────────────────────────────────────┐
│  VY_V6_Assembly_Modding                                              │
│  (Research + Patches)                                                │
│  50+ hand-written 68HC11 ASM patches, address maps, XDFs,           │
│  bank-split disassemblies, hardware docs, wiring diagrams            │
│                                                                      │
│  Outputs: .asm patch files, validated hook addresses, RAM map,       │
│           free space map (CPU $C468–$FFBF, file 0x0C468), Enhanced v1.0a bin │
└──────────────┬────────────────────────────┬──────────────────────────┘
               │                            │
    addresses, research,             .asm patches to compile
    hook points, memory map          into C equivalents
               │                            │
               ▼                            ▼
┌──────────────────────────┐  ┌──────────────────────────────────────┐
│  KingAI Commie Flasher   │  │  KingAI 68HC11 C Compiler            │
│  (Flash Tool)            │  │  (Compiler + Assembler + Patcher)    │
│                          │  │                                      │
│  Reads/writes the ECU    │  │  Compiles C → HC11 ASM → binary      │
│  over ALDL serial using  │  │  Patches code into ROM images        │
│  the real flash protocol │  │  Built-in assembler (146 mnemonics)  │
│                          │  │  Built-in disassembler               │
│  Outputs: .bin files     │  │  Outputs: .bin / .s19 / patched ROMs │
│  read from / written to  │  │                                      │
│  real or virtual ECU     │  │  hc11kit: asm, disasm, compile,      │
│                          │  │  patch, free, checksum, addr, xdf    │
└──────────────────────────┘  └──────────────────────────────────────┘
               │                            │
               └──────────┬─────────────────┘
                          │
                 both produce / consume
                   128KB .bin files
                          │
                          ▼
              ┌───────────────────────┐
              │  TunerPro-XDF-BIN-    │
              │  Universal-Exporter   │
              │                       │
              │  Exports XDF tables   │
              │  + BIN data to        │
              │  TXT / JSON / MD      │
              │  (fixes TunerPro's    │
              │  zero-export bug)     │
              └───────────────────────┘
```

---

each patch will be different and most patchs wont be able to be together due to space limitations, moveing code and removing code wont stop us coming into hardware limits like stack overflow and ram max bytes per 128 1 bits in the 128kb bin,

we could find out what really isnt used in the first 64kb. 


against other components in the ecu board. 

## Repo-by-Repo — What Flows Where

### 1. VY_V6_Assembly_Modding → Commie Flasher

**GitHub:** [kingaustraliagg-vy-l36-060a-enhanced-asm-patches](https://github.com/KingAiCodeForge/kingaustraliagg-vy-l36-060a-enhanced-asm-patches)

| What flows | Direction | How |
|------------|-----------|-----|
| Hook addresses ($101E1, $13618, etc.) | ASM → Flasher | Flasher's kernel upload targets the same RAM addresses ($0100/$0200/$0300) documented in the ASM repo |
| Bank mapping (48/58/50) | ASM → Flasher | Flasher's `FlashBank` enum and sector erase map match the ASM repo's `VY_V6_128KB_BINARY_SPLITTING_AND_PATCHING_GUIDE.md` |
| AMD 29F010 sector layout | ASM → Flasher | 8×16KB sectors 0-7, same offsets in both repos — Flasher's Custom Flash tab maps these exactly |
| Enhanced v1.0a .bin | ASM → Flasher | The `.bin` files the flasher reads/writes are the same ones the ASM repo patches |
| RAM variable map | ASM → Flasher | Mode 1 data stream offsets ($00A2=RPM, $00A6=ECT, etc.) used by Flasher's DataLogger come from ASM repo's `RAM_VARIABLE_COMPLETE_MAP_V2.csv` |
| ALDL protocol research | ASM → Flasher | OSE flash protocol analysis in both repos — Flasher implements what ASM repo documents |
| XDF definitions | ASM → Flasher | Flasher's `CalibrationTable` definitions (spark maps, fuel trims) come from Enhanced v2.09a XDF analysis in the ASM repo |
| Free space map | ASM → Flasher | CPU `$C468`–`$FFBF` / file `0x0C468`–`0x0FFBF` (15,192 bytes, bank1 overlay) + Tier 1: `$5D05` (504B always-visible) — verified in ASM repo, used by compiler for patch injection |

**Key connection:** The ASM repo is the *research lab*. It maps every address, every interrupt vector, every RAM variable. The flasher is the *delivery mechanism* — it writes the final .bin onto the ECU's flash chip.

### 2. KingAI 68HC11 C Compiler → Commie Flasher

**GitHub:** [KingAi_68HC11_C_Compiler](https://github.com/KingAiCodeForge/KingAi_68HC11_C_Compiler)

| What flows | Direction | How |
|------------|-----------|-----|
| Compiled .bin patches | Compiler → Flasher | Compiler outputs patched ROM images → Flasher writes them to ECU |
| 128KB .bin files | Flasher → Compiler | Flasher reads ECU → saves .bin → Compiler uses as base image for `hc11kit patch` |
| 68HC11 disassembler | Shared | Both repos have independent HC11 disassemblers. Flasher's is built into the GUI (Tab 3, 311 opcodes + VY V6 annotations). Compiler's is in `68hc11_disassembler_tool_for_vy_v6/` (standalone scripts + `hc11kit disasm` CLI). Same opcode table, different implementations. |
| Checksum logic | Shared | Both implement GM ROM checksum verify/fix. Flasher has `BinFile.verify_checksum()` / `fix_checksum()`. Compiler has `hc11kit checksum`. Same algorithm (sum of bytes at specific region = complement). |
| Target profiles | Shared | Compiler's `--target vy_v6` profile uses the same memory map ($2000-$FFFF mapped, bank-switched at $4000+) that the Flasher's erase/write logic uses |

**Key connection:** The compiler produces the .bin files. The flasher burns them onto the ECU. The workflow is: write C → `hc11kit compile` → `hc11kit patch` into stock bin → Flasher writes patched bin to ECU over ALDL.

### 3. Compiler ↔ VY_V6_Assembly_Modding

| What flows | Direction | How |
|------------|-----------|-----|
| .asm patches | ASM → Compiler | Compiler was built to replace hand-written assembly with C equivalents of ASM repo patches |
| Hook points | ASM → Compiler | `hc11kit patch --hook 0x101E1:3` — the hook addresses come from ASM repo's TIC3 ISR analysis |
| Free space offsets | ASM → Compiler | `hc11kit patch --at 0xC468` — inject address from ASM repo's free space map |
| Bank-split disassemblies | ASM → Compiler | ASM repo has `bank_split_output/Enhanced_v1.0a_bank{1,2,3}.asm` — used to validate compiler output |
| Target memory map | ASM → Compiler | VY V6 target profile in compiler comes from ASM repo address research |

**Key connection:** The ASM repo did 38 versions of a spark cut patch by hand. The compiler exists so that same patch can be written as a C function and compiled in one command instead.

### 4. TunerPro-XDF-BIN-Universal-Exporter

**GitHub:** [TunerPro-XDF-BIN-Universal-Exporter](https://github.com/KingAiCodeForge/TunerPro-XDF-BIN-Universal-Exporter)

| What flows | Direction | How |
|------------|-----------|-----|
| XDF table definitions | Exporter → All repos | Parses Enhanced v2.09a XDF (334 tables, 1546 constants, 68 DTCs) — data used by ASM repo for address mapping and Flasher for CalibrationTable definitions |
| .bin data extraction | Exporter → All repos | Correctly reads cell values from .bin that TunerPro exports as zeros |
| Table documentation | Exporter → ASM repo | Exported markdown of every spark/fuel/timing table used in ASM repo research |

**Key connection:** This tool reads the same XDF and .bin files that the other three repos work with. It's the documentation layer — exports human-readable table data that TunerPro fails to export correctly.

---

## Shared Concepts Across All Repos

| Concept | Flasher | Compiler | ASM Repo | Exporter |
|---------|---------|----------|----------|----------|
| 68HC11 opcode table | ✅ Built-in disassembler (GUI Tab 3) | ✅ `hc11kit disasm` + codegen backend | ✅ `68HC11_Reference/` | — |
| AMD 29F010 sector map | ✅ Custom Flash tab, erase logic | ✅ Free space finder matches sectors | ✅ `VY_V6_128KB_BINARY_SPLITTING_AND_PATCHING_GUIDE.md` | — |
| ALDL protocol (8192 baud) | ✅ Full implementation (13 modes) | — (not a comms tool) | ✅ Protocol research + wiring | — |
| GM ROM checksum | ✅ `BinFile.verify/fix_checksum()` | ✅ `hc11kit checksum` | ✅ Documented addresses | — |
| Bank switching (48/58/50) | ✅ `FlashBank` enum, erase map | ✅ `--target vy_v6` profile | ✅ `bank_split_output/` | ✅ XDF bank-aware parsing |
| Enhanced v1.0a binary | ✅ Read/write target | ✅ Patch injection base | ✅ Primary research target | ✅ Data extraction source |
| Mode 1 data stream (57 params) | ✅ DataLogger + Dashboard | — | ✅ `RAM_VARIABLE_COMPLETE_MAP_V2.csv` | — |
| VY V6 address annotations | ✅ Disassembler tab | ✅ `hc11kit disasm` VY mode | ✅ Every `.md` doc | ✅ XDF offset mapping |

---

## Companion Tools Inside the Compiler Repo

The compiler repo contains sub-projects that also connect to the flasher:

| Folder | What It Is | Link to Flasher |
|--------|-----------|-----------------|
| `68hc11_disassembler_tool_for_vy_v6/` | Standalone disassembler scripts (25+ files) | Flasher has its own built-in disassembler — same opcodes, different implementation |
| `hc11_virtual_emulator/` | Software-only 68HC11 CPU emulator (46 tests passing) | Flasher has `LoopbackTransport` which simulates the *protocol* but not the CPU. The emulator simulates the *CPU* but not the protocol. Together they cover the full stack. |
| `hc11_bench_incar_emulator/` | Hardware bench test rig (planning stage) | Would use Flasher's ALDL cable + serial transport to communicate with real PCM during bench tests |
| `hc11_esp32_arduino_raspberri_code/` | Embedded ALDL tools for ESP32/Arduino/RPi | Shares ALDL protocol constants and security key calc with Flasher's `ALDLProtocol` class |
| `nvram_realtimetuning_emulator_and_flashonline_BT_protocols.md/` | Live tuning over Bluetooth research | Flasher's `LiveTuner` class (RAM shadow writes) implements a similar concept — both write to RAM while engine is running |

---

## The End-to-End Workflow

What a complete tune cycle looks like using all four repos:

```
Step 1: RESEARCH (VY_V6_Assembly_Modding)
   │  Study disassembly, find hook points, map RAM variables
   │  Write test patches in hand-assembled .asm
   │  Validate addresses against Enhanced v1.0a binary
   │
Step 2: COMPILE (KingAI 68HC11 C Compiler)
   │  Rewrite the .asm patch as a C function
   │  hc11kit compile spark_cut.c -o spark_cut.bin --target vy_v6
   │  hc11kit patch enhanced.bin spark_cut.c --at 0xC468 --hook 0x101E1:3
   │  Output: patched 128KB .bin
   │  (OR: skip this step and use a pre-patched .bin from hex editing)
   │
Step 3: DOCUMENT (TunerPro XDF/BIN Exporter)
   │  Export XDF tables + BIN data for before/after comparison
   │  Verify calibration tables look correct in the patched binary
   │
Step 4: FLASH (KingAI Commie Flasher)
   │  Connect to ECU (ALDL cable → PySerial / FTDI D2XX)
   │  Load the patched .bin
   │  Write ECU (full BIN or CAL-only)
   │  Read back and verify
   │
Step 5: VALIDATE
   │  DataLogger (Flasher) — live Mode 1 data stream to CSV
   │  Check that patched code is executing correctly
   │  Compare dashboard sensor values against expected behavior
   │
Step 6: ITERATE
      If wrong → Read ECU → modify .c → recompile → re-flash
      Custom Flash tab for sector-level recovery if something goes wrong
```

---

## What's NOT Shared (and Why)

| Thing | Why it's separate |
|-------|------------------|
| Flash kernel byte arrays | Only in Flasher. The kernel runs in ECU RAM during flash operations. The compiler doesn't need it — it compiles *application* code, not flash kernels. |
| ALDL transport layer | Only in Flasher. The compiler doesn't communicate with ECUs — it produces offline .bin files. |
| C lexer/parser/AST | Only in Compiler. The flasher doesn't compile anything — it just reads/writes binary data. |
| XDF XML parsing (full) | Only in Exporter. The flasher has `CalibrationTable` definitions hardcoded from XDF analysis. The compiler's `hc11kit xdf` does basic XDF search. The exporter does full-fidelity extraction. |
| 50+ ASM patches | Only in ASM repo. The flasher doesn't patch binaries. The compiler could compile C equivalents. The patches stay in the ASM repo as the research record. |
| Virtual ECU (LoopbackTransport) | Only in Flasher. Simulates the *protocol* (ALDL framing, seed/key, kernel upload, sector erase, write) against a 128KB in-memory NOR flash model. Not a CPU emulator. |
| CPU emulator (hc11_virtual_emulator) | Only in Compiler repo. Executes actual 68HC11 instructions. Tests compiler output correctness. Not an ALDL protocol simulator. |

---

## GitHub URLs

| Repo | GitHub URL |
|------|-----------|
| KingAI Commie Flasher | *Not yet published — this repo* |
| KingAI 68HC11 C Compiler | https://github.com/KingAiCodeForge/KingAi_68HC11_C_Compiler |
| VY V6 Assembly Modding | https://github.com/KingAiCodeForge/kingaustraliagg-vy-l36-060a-enhanced-asm-patches |
| TunerPro XDF/BIN Exporter | https://github.com/KingAiCodeForge/TunerPro-XDF-BIN-Universal-Exporter |
