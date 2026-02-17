# Kernel RAM-to-ROM Write Simulator — "Virtual EEPROM Output"

**Project:** KingAI Commie Flasher  
**Target:** Holden VY Ecotec V6 — Delco 68HC11F1, OS $060A (92118883)  
**Flash chip:** AMD Am29F010 (128KB NOR, 8×16KB sectors)

---

## What This Is

A tool that captures the **exact binary layout** produced by a flash write — whether in-car over ALDL or bench-flashing through a programmer — and saves it to an `output/` directory exactly as it would be stored in the PCM's physical EEPROM.

The output `.bin` file is a 1:1 byte-for-byte image of what the AMD 29F010 flash chip contains after a successful write operation. If you burned this file onto a blank Am29F010 with a chip programmer, inserted it into the PCM, and turned the key — it should boot.

## Why This Exists

Right now, there's no way to **see** what the EEPROM looks like after a flash write without reading the chip back. This tool gives you that visibility:

1. **Verification** — diff the output against your stock/intended bin to confirm exactly what was written, byte for byte
2. **Debugging** — if a write fails on real hardware, compare the partially-written output against the expected image to find exactly where it stopped
3. **Testing without hardware** — combined with `virtual_128kb_eeprom.py` (AMD29F010 simulator) and `virtual_aldl_frame_sender_and_vecu.py` (vECU), this creates a complete end-to-end test path: PC → ALDL frames → vECU → kernel → AMD flash sim → output bin
4. **Binary provenance** — every output is timestamped and logged, so you know exactly which source binary and which flash sequence produced it

## Is It Worth It?

**Yes.** The AMD 29F010 is a simple NOR flash chip with a documented command protocol. Everything about how data moves from the PC to the EEPROM is deterministic and fully specified — there are no hidden operations, no wear-leveling, no error correction, no filesystem. What you write is what you get.

The full data path is:

```
PC .bin file → ALDL serial → Mode 6 upload (kernel to RAM) → Mode 16 write frames
→ HC11 kernel in RAM → AMD command sequence (AA→$5555, 55→$2AAA, A0→$5555, data→addr)
→ Am29F010 NOR flash cell → stored bit pattern → EEPROM image
```

Every step in this chain is already implemented in this project. This tool just adds the final observability layer.

## Can We Make It 1:1?

**Yes — and here's exactly how the real hardware does it.**

### The Physical Data Path (what the PCM actually does)

#### Step 1 — Kernel Upload (Mode 6 over ALDL)

The PC sends 3 blocks of HC11 machine code over ALDL at 8192 baud. Each block is a 201-byte ALDL frame containing raw opcodes. The PCM's stock OS receives these via the SCI (serial) port and copies them to RAM at known addresses:

```
Block 0: 171 bytes → RAM $0100-$01AA  (main loop + SCI handler)
Block 1: 172 bytes → RAM $0200-$02AB  (flash read + data streaming)
Block 2: 156 bytes → RAM $0300-$039B  (interrupt vectors + init)
```

The stock OS then `JMP $0100` — the kernel takes over the CPU. From this point, the HC11's normal firmware is NOT running. The kernel owns the chip.

#### Step 2 — Bank Selection (kernel code)

The HC11F1 has a 16-bit address bus ($0000-$FFFF) but the Am29F010 holds 128KB. Bank switching maps 32KB windows into the CPU's $8000-$FFFF region:

```
Bank register at $1000 (PORTB on HC11F1):
  Write $48 → Bank 72: file $00000-$0FFFF → CPU $0000-$FFFF (64KB direct)
  Write $58 → Bank 88: file $10000-$17FFF → CPU $8000-$FFFF (32KB window)
  Write $50 → Bank 80: file $18000-$1FFFF → CPU $8000-$FFFF (32KB window)
```

The kernel sets the bank register before each write operation. This is a physical pin change on the HC11 — it drives address lines A16/A17 on the flash chip.

#### Step 3 — Sector Erase (kernel → AMD command sequence)

Before writing, each 16KB sector must be erased. NOR flash erases to all-1s ($FF). The kernel executes the AMD unlock + erase sequence by writing specific bytes to specific addresses:

```
$5555 ← $AA    ; First unlock
$2AAA ← $55    ; Second unlock
$5555 ← $80    ; Erase setup
$5555 ← $AA    ; First unlock (again)
$2AAA ← $55    ; Second unlock (again)
sector_base ← $30  ; Confirm sector erase
```

The flash chip internally erases the entire 16KB sector. The kernel polls DQ6 (toggle bit) until the erase completes (~1 second per sector). DQ5 indicates timeout/error.

#### Step 4 — Byte Programming (kernel → AMD command sequence, per byte)

Data arrives over ALDL in 32-byte chunks (Mode 16 frames). For each byte, the kernel executes:

```
$5555 ← $AA    ; First unlock
$2AAA ← $55    ; Second unlock
$5555 ← $A0    ; Program setup
target_addr ← data_byte  ; Actual data
```

The flash chip programs one byte. NOR flash rule: **can only clear bits (1→0), never set bits (0→1)**. The result is `existing_data AND new_data`. This is why you must erase first — erasing sets all bits to 1, then programming clears the ones you need to be 0.

The kernel polls DQ6 after each byte. If the programmed byte doesn't match the intended value (read-back mismatch), it retries up to 10 times before reporting failure.

#### Step 5 — Address Remapping (bank offset math)

The file offsets in the 128KB .bin don't map 1:1 to the CPU addresses the kernel uses for Banks 88 and 80:

```
Bank 72 ($48): file offset = CPU address     (no remap)
Bank 88 ($58): CPU address = file offset - $8000   ($10000 → $8000)
Bank 80 ($50): CPU address = file offset - $10000  ($18000 → $8000)
```

The PC does this remapping before sending each write frame. The kernel just writes to the CPU address it receives.

#### Step 6 — Checksum Verification (kernel computes, PC compares)

After all sectors are written, the kernel computes a 16-bit checksum across all 3 banks and reports it back. The PC compares this against the expected checksum stored at file offsets $4006-$4007. If they don't match, the flash is corrupt.

### What This Simulator Does

This tool replicates Steps 2-6 using `virtual_128kb_eeprom.py` (the AMD29F010 class):

1. Receives the same ALDL frames that would go to a real PCM
2. Passes them through the same bank selection and address remapping
3. Executes the same AMD command sequences (unlock → erase → program → poll)
4. Enforces the same NOR AND rule (can't set bits without erasing first)
5. Saves the final flash image to `output/` — identical to what a chip programmer would read back

The output binary is what would be on the physical chip. 1:1.

## Output Directory Structure

```
kernel_ram_to_rom_write/
├── README.md                          ← This file
├── output/                            ← Generated EEPROM images
│   ├── flash_20260217_143052.bin      ← 131072-byte (128KB) raw image
│   ├── flash_20260217_143052.log      ← Write log (every byte, every sector)
│   └── flash_20260217_143052.meta     ← Source file, checksum, sector map
└── (future: kernel_flash_writer.py)   ← The script that drives this
```

Each output set is timestamped. The `.bin` is the raw byte-for-byte EEPROM image. The `.log` captures every AMD command in sequence. The `.meta` records what went in and what came out.

## Relationship to Other Scripts

| Script | Role in the chain |
|--------|-------------------|
| `kingai_commie_flasher.py` | Sends ALDL frames (Mode 6 upload, Mode 16 write) |
| `virtual_aldl_frame_sender_and_vecu.py` | Receives frames, simulates ECU response (vECU) |
| `virtual_128kb_eeprom.py` | Simulates the Am29F010 flash chip (AMD29F010 class) |
| **This tool** | Captures the final flash image and saves to disk |
| `tools/ALDL_read_RAM_commands.py` | Reads back from the simulated (or real) flash |

## Flash Sector Map (for reference)

```
Am29F010 — 128KB = 8 × 16KB sectors

File Offset    Bank    Sector  Contents
──────────────────────────────────────────────────
$00000-$03FFF  72 ($48)  0    OS code (lower)
$04000-$07FFF  72 ($48)  1    Calibration data ($4006-$4007 = checksum)
$08000-$0BFFF  72 ($48)  2    OS code (upper)
$0C000-$0FFFF  72 ($48)  3    OS code (upper) — free space at $0C468-$0FFBF
$10000-$13FFF  88 ($58)  4    OS code (bank 2)
$14000-$17FFF  88 ($58)  5    OS code (bank 2)
$18000-$1BFFF  80 ($50)  6    OS code (bank 3)
$1C000-$1FFFF  80 ($50)  7    Boot sector ($1FFE0 = vectors, $1FFFE = RESET)
```

**BIN write** erases sectors 0-6 (skips boot sector 7).  
**CAL write** erases sector 1 only ($4000-$7FFF calibration area).  
**PROM write** erases all 8 sectors (full recovery, including boot).

---

2026 Jason King (pcmhacking.net: kingaustraliagg)*
