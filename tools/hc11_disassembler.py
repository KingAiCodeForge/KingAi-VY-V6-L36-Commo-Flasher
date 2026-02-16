#!/usr/bin/env python3
"""
HC11 Disassembler — Standalone API Module for KingAI Commie Flasher
====================================================================
Complete Motorola 68HC11 instruction decoder with VY V6 $060A annotations.

Merged from:
  - core/opcodes.py          (HC11InstructionSet — best opcode architecture)
  - hc11_opcodes_complete.py  (decode_opcode / format_instruction driver)
  - core/vy_v6_constants.py   (verified RAM, registers, vectors)

API Usage:
    from tools.hc11_disassembler import HC11Disassembler

    dis = HC11Disassembler()

    # Disassemble raw bytes
    results = dis.disassemble(b'\\xB6\\x77\\xDE', base_addr=0x8000)
    for r in results:
        print(r.format())   # "$8000: B6 77 DE  LDAA $77DE  ; Rev Limit High"

    # Disassemble hex string
    results = dis.disassemble_hex("86 A4 91 A4 26 05", base_addr=0xADD0)

    # Single instruction
    inst = dis.decode_one(data, offset=0, base_addr=0x8000)

Author: Jason King (pcmhacking.net: kingaustraliagg)
Source: MC68HC11 Reference Manual + community reverse engineering
Date: February 2026
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# INSTRUCTION METADATA
# ═══════════════════════════════════════════════════════════════════════

# Addressing mode constants
MODE_IMPLIED   = "imp"
MODE_IMMEDIATE = "imm"
MODE_DIRECT    = "dir"
MODE_EXTENDED  = "ext"
MODE_INDEXED_X = "idx"
MODE_INDEXED_Y = "idy"
MODE_RELATIVE  = "rel"
MODE_BIT_DIR   = "bit_dir"
MODE_BIT_IDX   = "bit_idx"
MODE_BIT_IDY   = "bit_idy"
MODE_PREFIX    = "prefix"
MODE_DATA      = "data"


@dataclass
class Instruction:
    """HC11 instruction metadata from the opcode table."""
    mnemonic: str
    length: int       # Total bytes including opcode (NOT including prebyte)
    cycles: int
    mode: str
    prebyte: int = 0x00
    description: str = ""

    def __str__(self) -> str:
        return f"{self.mnemonic:6s} ({self.length}B, {self.cycles}cy, {self.mode})"


@dataclass
class DisassembledInstruction:
    """One decoded instruction with all formatting data."""
    address: int            # ROM/CPU address
    raw_bytes: bytes        # All bytes including prebyte
    mnemonic: str
    operand_str: str        # Formatted operand (e.g. "#$A4", "$77DE", "$05,X")
    mode: str               # Addressing mode
    description: str        # Opcode description
    cycles: int
    comment: str = ""       # VY V6 annotation or branch target note
    length: int = 0         # Total instruction length (set in post-init)

    def __post_init__(self):
        self.length = len(self.raw_bytes)

    @property
    def hex_str(self) -> str:
        """Hex bytes formatted like 'B6 77 DE'."""
        return " ".join(f"{b:02X}" for b in self.raw_bytes)

    def format(self, show_description: bool = False, hex_width: int = 14) -> str:
        """Format as a single disassembly line."""
        addr_s = f"${self.address:04X}"
        hex_s  = self.hex_str.ljust(hex_width)
        asm_s  = f"{self.mnemonic} {self.operand_str}".strip()
        line   = f"{addr_s}: {hex_s} {asm_s}"
        if self.comment:
            line += f"  ; {self.comment}"
        if show_description and self.description and not self.comment:
            line += f"  ; {self.description}"
        return line

    def format_compact(self) -> str:
        """Shorter format for GUI display."""
        asm = f"{self.mnemonic} {self.operand_str}".strip()
        cmt = f"  ; {self.comment}" if self.comment else ""
        return f"${self.address:04X}: {self.hex_str:14s} {asm}{cmt}"


# ═══════════════════════════════════════════════════════════════════════
# COMPLETE OPCODE TABLES  (224 total: 148 base + 65 page2 + 7 page3 + 4 page4)
# ═══════════════════════════════════════════════════════════════════════

def _base_opcodes() -> Dict[int, Instruction]:
    """Main (single-byte) opcode map — ~148 entries."""
    I = Instruction
    m = MODE_IMPLIED; i = MODE_IMMEDIATE; d = MODE_DIRECT
    e = MODE_EXTENDED; x = MODE_INDEXED_X; r = MODE_RELATIVE
    bd = MODE_BIT_DIR; bx = MODE_BIT_IDX; p = MODE_PREFIX
    return {
        # 0x00-0x0F  Miscellaneous / Control
        0x00: I("TEST",  1, 1, m, description="Test mode (factory only)"),
        0x01: I("NOP",   1, 2, m, description="No operation"),
        0x02: I("IDIV",  1,41, m, description="Integer divide D/X → X rem D"),
        0x03: I("FDIV",  1,41, m, description="Fractional divide D/X"),
        0x04: I("LSRD",  1, 3, m, description="Logical shift right D"),
        0x05: I("ASLD",  1, 3, m, description="Arithmetic shift left D"),
        0x06: I("TAP",   1, 2, m, description="Transfer A → CCR"),
        0x07: I("TPA",   1, 2, m, description="Transfer CCR → A"),
        0x08: I("INX",   1, 3, m, description="Increment X"),
        0x09: I("DEX",   1, 3, m, description="Decrement X"),
        0x0A: I("CLV",   1, 2, m, description="Clear overflow flag"),
        0x0B: I("SEV",   1, 2, m, description="Set overflow flag"),
        0x0C: I("CLC",   1, 2, m, description="Clear carry flag"),
        0x0D: I("SEC",   1, 2, m, description="Set carry flag"),
        0x0E: I("CLI",   1, 2, m, description="Clear interrupt mask"),
        0x0F: I("SEI",   1, 2, m, description="Set interrupt mask"),
        # 0x10-0x1F  Arithmetic / bit ops / prefixes
        0x10: I("SBA",   1, 2, m, description="A − B → A"),
        0x11: I("CBA",   1, 2, m, description="Compare B to A"),
        0x12: I("BRSET", 4, 6, bd, description="Branch if bits set (dir)"),
        0x13: I("BRCLR", 4, 6, bd, description="Branch if bits clear (dir)"),
        0x14: I("BSET",  3, 6, bd, description="Set bits (direct)"),
        0x15: I("BCLR",  3, 6, bd, description="Clear bits (direct)"),
        0x16: I("TAB",   1, 2, m, description="Transfer A → B"),
        0x17: I("TBA",   1, 2, m, description="Transfer B → A"),
        0x18: I("PAGE2", 1, 0, p, description="Y-register prefix"),
        0x19: I("DAA",   1, 2, m, description="Decimal adjust A"),
        0x1A: I("PAGE3", 1, 0, p, description="CPD prefix"),
        0x1B: I("ABA",   1, 2, m, description="A + B → A"),
        0x1C: I("BSET",  3, 7, bx, description="Set bits (indexed X)"),
        0x1D: I("BCLR",  3, 7, bx, description="Clear bits (indexed X)"),
        0x1E: I("BRSET", 4, 7, bx, description="Branch if bits set (idx)"),
        0x1F: I("BRCLR", 4, 7, bx, description="Branch if bits clear (idx)"),
        # 0x20-0x2F  Branches
        0x20: I("BRA",  2, 3, r, description="Branch always"),
        0x21: I("BRN",  2, 3, r, description="Branch never"),
        0x22: I("BHI",  2, 3, r, description="Branch if higher"),
        0x23: I("BLS",  2, 3, r, description="Branch if lower/same"),
        0x24: I("BCC",  2, 3, r, description="Branch if carry clear (BHS)"),
        0x25: I("BCS",  2, 3, r, description="Branch if carry set (BLO)"),
        0x26: I("BNE",  2, 3, r, description="Branch if not equal"),
        0x27: I("BEQ",  2, 3, r, description="Branch if equal"),
        0x28: I("BVC",  2, 3, r, description="Branch if overflow clear"),
        0x29: I("BVS",  2, 3, r, description="Branch if overflow set"),
        0x2A: I("BPL",  2, 3, r, description="Branch if plus"),
        0x2B: I("BMI",  2, 3, r, description="Branch if minus"),
        0x2C: I("BGE",  2, 3, r, description="Branch ≥ (signed)"),
        0x2D: I("BLT",  2, 3, r, description="Branch < (signed)"),
        0x2E: I("BGT",  2, 3, r, description="Branch > (signed)"),
        0x2F: I("BLE",  2, 3, r, description="Branch ≤ (signed)"),
        # 0x30-0x3F  Stack / special
        0x30: I("TSX",  1, 3, m, description="SP → X"),
        0x31: I("INS",  1, 3, m, description="Increment SP"),
        0x32: I("PULA", 1, 4, m, description="Pull A from stack"),
        0x33: I("PULB", 1, 4, m, description="Pull B from stack"),
        0x34: I("DES",  1, 3, m, description="Decrement SP"),
        0x35: I("TXS",  1, 3, m, description="X → SP"),
        0x36: I("PSHA", 1, 3, m, description="Push A to stack"),
        0x37: I("PSHB", 1, 3, m, description="Push B to stack"),
        0x38: I("PULX", 1, 5, m, description="Pull X from stack"),
        0x39: I("RTS",  1, 5, m, description="Return from subroutine"),
        0x3A: I("ABX",  1, 3, m, description="B + X → X"),
        0x3B: I("RTI",  1,12, m, description="Return from interrupt"),
        0x3C: I("PSHX", 1, 4, m, description="Push X to stack"),
        0x3D: I("MUL",  1,10, m, description="A × B → D"),
        0x3E: I("WAI",  1, 9, m, description="Wait for interrupt"),
        0x3F: I("SWI",  1,14, m, description="Software interrupt"),
        # 0x40-0x4F  Acc A inherent
        0x40: I("NEGA", 1, 2, m, description="Negate A"),
        0x43: I("COMA", 1, 2, m, description="Complement A"),
        0x44: I("LSRA", 1, 2, m, description="Logical shift right A"),
        0x46: I("RORA", 1, 2, m, description="Rotate right A"),
        0x47: I("ASRA", 1, 2, m, description="Arithmetic shift right A"),
        0x48: I("ASLA", 1, 2, m, description="Arithmetic shift left A"),
        0x49: I("ROLA", 1, 2, m, description="Rotate left A"),
        0x4A: I("DECA", 1, 2, m, description="Decrement A"),
        0x4C: I("INCA", 1, 2, m, description="Increment A"),
        0x4D: I("TSTA", 1, 2, m, description="Test A"),
        0x4F: I("CLRA", 1, 2, m, description="Clear A"),
        # 0x50-0x5F  Acc B inherent
        0x50: I("NEGB", 1, 2, m, description="Negate B"),
        0x53: I("COMB", 1, 2, m, description="Complement B"),
        0x54: I("LSRB", 1, 2, m, description="Logical shift right B"),
        0x56: I("RORB", 1, 2, m, description="Rotate right B"),
        0x57: I("ASRB", 1, 2, m, description="Arithmetic shift right B"),
        0x58: I("ASLB", 1, 2, m, description="Arithmetic shift left B"),
        0x59: I("ROLB", 1, 2, m, description="Rotate left B"),
        0x5A: I("DECB", 1, 2, m, description="Decrement B"),
        0x5C: I("INCB", 1, 2, m, description="Increment B"),
        0x5D: I("TSTB", 1, 2, m, description="Test B"),
        0x5F: I("CLRB", 1, 2, m, description="Clear B"),
        # 0x60-0x6F  Memory indexed X (2 bytes)
        0x60: I("NEG", 2, 6, x, description="Negate memory (idx)"),
        0x63: I("COM", 2, 6, x, description="Complement memory (idx)"),
        0x64: I("LSR", 2, 6, x, description="Logical shift right (idx)"),
        0x66: I("ROR", 2, 6, x, description="Rotate right (idx)"),
        0x67: I("ASR", 2, 6, x, description="Arithmetic shift right (idx)"),
        0x68: I("ASL", 2, 6, x, description="Arithmetic shift left (idx)"),
        0x69: I("ROL", 2, 6, x, description="Rotate left (idx)"),
        0x6A: I("DEC", 2, 6, x, description="Decrement memory (idx)"),
        0x6C: I("INC", 2, 6, x, description="Increment memory (idx)"),
        0x6D: I("TST", 2, 6, x, description="Test memory (idx)"),
        0x6E: I("JMP", 2, 3, x, description="Jump (idx)"),
        0x6F: I("CLR", 2, 6, x, description="Clear memory (idx)"),
        # 0x70-0x7F  Memory extended (3 bytes)
        0x70: I("NEG", 3, 6, e, description="Negate memory (ext)"),
        0x73: I("COM", 3, 6, e, description="Complement memory (ext)"),
        0x74: I("LSR", 3, 6, e, description="Logical shift right (ext)"),
        0x76: I("ROR", 3, 6, e, description="Rotate right (ext)"),
        0x77: I("ASR", 3, 6, e, description="Arithmetic shift right (ext)"),
        0x78: I("ASL", 3, 6, e, description="Arithmetic shift left (ext)"),
        0x79: I("ROL", 3, 6, e, description="Rotate left (ext)"),
        0x7A: I("DEC", 3, 6, e, description="Decrement memory (ext)"),
        0x7C: I("INC", 3, 6, e, description="Increment memory (ext)"),
        0x7D: I("TST", 3, 6, e, description="Test memory (ext)"),
        0x7E: I("JMP", 3, 3, e, description="Jump (ext)"),
        0x7F: I("CLR", 3, 6, e, description="Clear memory (ext)"),
        # 0x80-0x8F  Acc A immediate / 16-bit immediate / BSR
        0x80: I("SUBA", 2, 2, i, description="A − M → A (imm)"),
        0x81: I("CMPA", 2, 2, i, description="Compare A (imm)"),
        0x82: I("SBCA", 2, 2, i, description="A − M − C → A (imm)"),
        0x83: I("SUBD", 3, 4, i, description="D − M:M+1 → D (imm)"),
        0x84: I("ANDA", 2, 2, i, description="A AND M → A (imm)"),
        0x85: I("BITA", 2, 2, i, description="Bit test A (imm)"),
        0x86: I("LDAA", 2, 2, i, description="Load A (imm)"),
        0x88: I("EORA", 2, 2, i, description="A XOR M → A (imm)"),
        0x89: I("ADCA", 2, 2, i, description="A + M + C → A (imm)"),
        0x8A: I("ORAA", 2, 2, i, description="A OR M → A (imm)"),
        0x8B: I("ADDA", 2, 2, i, description="A + M → A (imm)"),
        0x8C: I("CPX",  3, 4, i, description="Compare X (imm)"),
        0x8D: I("BSR",  2, 6, r, description="Branch to subroutine"),
        0x8E: I("LDS",  3, 3, i, description="Load SP (imm)"),
        0x8F: I("XGDX", 1, 3, m, description="Exchange D ↔ X"),
        # 0x90-0x9F  Acc A direct / 16-bit direct
        0x90: I("SUBA", 2, 3, d, description="A − M → A (dir)"),
        0x91: I("CMPA", 2, 3, d, description="Compare A (dir)"),
        0x92: I("SBCA", 2, 3, d, description="A − M − C → A (dir)"),
        0x93: I("SUBD", 2, 5, d, description="D − M:M+1 → D (dir)"),
        0x94: I("ANDA", 2, 3, d, description="A AND M → A (dir)"),
        0x95: I("BITA", 2, 3, d, description="Bit test A (dir)"),
        0x96: I("LDAA", 2, 3, d, description="Load A (dir)"),
        0x97: I("STAA", 2, 3, d, description="Store A (dir)"),
        0x98: I("EORA", 2, 3, d, description="A XOR M → A (dir)"),
        0x99: I("ADCA", 2, 3, d, description="A + M + C → A (dir)"),
        0x9A: I("ORAA", 2, 3, d, description="A OR M → A (dir)"),
        0x9B: I("ADDA", 2, 3, d, description="A + M → A (dir)"),
        0x9C: I("CPX",  2, 5, d, description="Compare X (dir)"),
        0x9D: I("JSR",  2, 5, d, description="Jump to subroutine (dir)"),
        0x9E: I("LDS",  2, 4, d, description="Load SP (dir)"),
        0x9F: I("STS",  2, 4, d, description="Store SP (dir)"),
        # 0xA0-0xAF  Acc A indexed X / 16-bit indexed X
        0xA0: I("SUBA", 2, 4, x, description="A − M → A (idx)"),
        0xA1: I("CMPA", 2, 4, x, description="Compare A (idx)"),
        0xA2: I("SBCA", 2, 4, x, description="A − M − C → A (idx)"),
        0xA3: I("SUBD", 2, 6, x, description="D − M:M+1 → D (idx)"),
        0xA4: I("ANDA", 2, 4, x, description="A AND M → A (idx)"),
        0xA5: I("BITA", 2, 4, x, description="Bit test A (idx)"),
        0xA6: I("LDAA", 2, 4, x, description="Load A (idx)"),
        0xA7: I("STAA", 2, 4, x, description="Store A (idx)"),
        0xA8: I("EORA", 2, 4, x, description="A XOR M → A (idx)"),
        0xA9: I("ADCA", 2, 4, x, description="A + M + C → A (idx)"),
        0xAA: I("ORAA", 2, 4, x, description="A OR M → A (idx)"),
        0xAB: I("ADDA", 2, 4, x, description="A + M → A (idx)"),
        0xAC: I("CPX",  2, 6, x, description="Compare X (idx)"),
        0xAD: I("JSR",  2, 6, x, description="Jump to subroutine (idx)"),
        0xAE: I("LDS",  2, 5, x, description="Load SP (idx)"),
        0xAF: I("STS",  2, 5, x, description="Store SP (idx)"),
        # 0xB0-0xBF  Acc A extended / 16-bit extended
        0xB0: I("SUBA", 3, 4, e, description="A − M → A (ext)"),
        0xB1: I("CMPA", 3, 4, e, description="Compare A (ext)"),
        0xB2: I("SBCA", 3, 4, e, description="A − M − C → A (ext)"),
        0xB3: I("SUBD", 3, 6, e, description="D − M:M+1 → D (ext)"),
        0xB4: I("ANDA", 3, 4, e, description="A AND M → A (ext)"),
        0xB5: I("BITA", 3, 4, e, description="Bit test A (ext)"),
        0xB6: I("LDAA", 3, 4, e, description="Load A (ext)"),
        0xB7: I("STAA", 3, 4, e, description="Store A (ext)"),
        0xB8: I("EORA", 3, 4, e, description="A XOR M → A (ext)"),
        0xB9: I("ADCA", 3, 4, e, description="A + M + C → A (ext)"),
        0xBA: I("ORAA", 3, 4, e, description="A OR M → A (ext)"),
        0xBB: I("ADDA", 3, 4, e, description="A + M → A (ext)"),
        0xBC: I("CPX",  3, 6, e, description="Compare X (ext)"),
        0xBD: I("JSR",  3, 6, e, description="Jump to subroutine (ext)"),
        0xBE: I("LDS",  3, 5, e, description="Load SP (ext)"),
        0xBF: I("STS",  3, 5, e, description="Store SP (ext)"),
        # 0xC0-0xCF  Acc B immediate / 16-bit immediate
        0xC0: I("SUBB", 2, 2, i, description="B − M → B (imm)"),
        0xC1: I("CMPB", 2, 2, i, description="Compare B (imm)"),
        0xC2: I("SBCB", 2, 2, i, description="B − M − C → B (imm)"),
        0xC3: I("ADDD", 3, 4, i, description="D + M:M+1 → D (imm)"),
        0xC4: I("ANDB", 2, 2, i, description="B AND M → B (imm)"),
        0xC5: I("BITB", 2, 2, i, description="Bit test B (imm)"),
        0xC6: I("LDAB", 2, 2, i, description="Load B (imm)"),
        0xC8: I("EORB", 2, 2, i, description="B XOR M → B (imm)"),
        0xC9: I("ADCB", 2, 2, i, description="B + M + C → B (imm)"),
        0xCA: I("ORAB", 2, 2, i, description="B OR M → B (imm)"),
        0xCB: I("ADDB", 2, 2, i, description="B + M → B (imm)"),
        0xCC: I("LDD",  3, 3, i, description="Load D (imm)"),
        0xCD: I("PAGE4",1, 0, p, description="Y-indexed CPD/CPX prefix"),
        0xCE: I("LDX",  3, 3, i, description="Load X (imm)"),
        0xCF: I("STOP", 1, 2, m, description="Stop clocks"),
        # 0xD0-0xDF  Acc B direct / 16-bit direct
        0xD0: I("SUBB", 2, 3, d, description="B − M → B (dir)"),
        0xD1: I("CMPB", 2, 3, d, description="Compare B (dir)"),
        0xD2: I("SBCB", 2, 3, d, description="B − M − C → B (dir)"),
        0xD3: I("ADDD", 2, 5, d, description="D + M:M+1 → D (dir)"),
        0xD4: I("ANDB", 2, 3, d, description="B AND M → B (dir)"),
        0xD5: I("BITB", 2, 3, d, description="Bit test B (dir)"),
        0xD6: I("LDAB", 2, 3, d, description="Load B (dir)"),
        0xD7: I("STAB", 2, 3, d, description="Store B (dir)"),
        0xD8: I("EORB", 2, 3, d, description="B XOR M → B (dir)"),
        0xD9: I("ADCB", 2, 3, d, description="B + M + C → B (dir)"),
        0xDA: I("ORAB", 2, 3, d, description="B OR M → B (dir)"),
        0xDB: I("ADDB", 2, 3, d, description="B + M → B (dir)"),
        0xDC: I("LDD",  2, 4, d, description="Load D (dir)"),
        0xDD: I("STD",  2, 4, d, description="Store D (dir)"),
        0xDE: I("LDX",  2, 4, d, description="Load X (dir)"),
        0xDF: I("STX",  2, 4, d, description="Store X (dir)"),
        # 0xE0-0xEF  Acc B indexed X / 16-bit indexed X
        0xE0: I("SUBB", 2, 4, x, description="B − M → B (idx)"),
        0xE1: I("CMPB", 2, 4, x, description="Compare B (idx)"),
        0xE2: I("SBCB", 2, 4, x, description="B − M − C → B (idx)"),
        0xE3: I("ADDD", 2, 6, x, description="D + M:M+1 → D (idx)"),
        0xE4: I("ANDB", 2, 4, x, description="B AND M → B (idx)"),
        0xE5: I("BITB", 2, 4, x, description="Bit test B (idx)"),
        0xE6: I("LDAB", 2, 4, x, description="Load B (idx)"),
        0xE7: I("STAB", 2, 4, x, description="Store B (idx)"),
        0xE8: I("EORB", 2, 4, x, description="B XOR M → B (idx)"),
        0xE9: I("ADCB", 2, 4, x, description="B + M + C → B (idx)"),
        0xEA: I("ORAB", 2, 4, x, description="B OR M → B (idx)"),
        0xEB: I("ADDB", 2, 4, x, description="B + M → B (idx)"),
        0xEC: I("LDD",  2, 5, x, description="Load D (idx)"),
        0xED: I("STD",  2, 5, x, description="Store D (idx)"),
        0xEE: I("LDX",  2, 5, x, description="Load X (idx)"),
        0xEF: I("STX",  2, 5, x, description="Store X (idx)"),
        # 0xF0-0xFF  Acc B extended / 16-bit extended
        0xF0: I("SUBB", 3, 4, e, description="B − M → B (ext)"),
        0xF1: I("CMPB", 3, 4, e, description="Compare B (ext)"),
        0xF2: I("SBCB", 3, 4, e, description="B − M − C → B (ext)"),
        0xF3: I("ADDD", 3, 6, e, description="D + M:M+1 → D (ext)"),
        0xF4: I("ANDB", 3, 4, e, description="B AND M → B (ext)"),
        0xF5: I("BITB", 3, 4, e, description="Bit test B (ext)"),
        0xF6: I("LDAB", 3, 4, e, description="Load B (ext)"),
        0xF7: I("STAB", 3, 4, e, description="Store B (ext)"),
        0xF8: I("EORB", 3, 4, e, description="B XOR M → B (ext)"),
        0xF9: I("ADCB", 3, 4, e, description="B + M + C → B (ext)"),
        0xFA: I("ORAB", 3, 4, e, description="B OR M → B (ext)"),
        0xFB: I("ADDB", 3, 4, e, description="B + M → B (ext)"),
        0xFC: I("LDD",  3, 5, e, description="Load D (ext)"),
        0xFD: I("STD",  3, 5, e, description="Store D (ext)"),
        0xFE: I("LDX",  3, 5, e, description="Load X (ext)"),
        0xFF: I("STX",  3, 5, e, description="Store X (ext)"),
    }


def _page2_opcodes() -> Dict[int, Instruction]:
    """Prebyte 0x18 — Y-register variants (65 entries).
    Length values are the byte count AFTER the 0x18 prefix byte."""
    I = Instruction; y = MODE_INDEXED_Y; by = MODE_BIT_IDY
    m = MODE_IMPLIED; i = MODE_IMMEDIATE; d = MODE_DIRECT; e = MODE_EXTENDED
    return {
        # Inherent Y ops
        0x08: I("INY",  1, 4, m, 0x18, "Increment Y"),
        0x09: I("DEY",  1, 4, m, 0x18, "Decrement Y"),
        0x30: I("TSY",  1, 4, m, 0x18, "SP → Y"),
        0x35: I("TYS",  1, 4, m, 0x18, "Y → SP"),
        0x38: I("PULY", 1, 5, m, 0x18, "Pull Y from stack"),
        0x3A: I("ABY",  1, 4, m, 0x18, "B + Y → Y"),
        0x3C: I("PSHY", 1, 5, m, 0x18, "Push Y to stack"),
        0x8F: I("XGDY", 1, 4, m, 0x18, "Exchange D ↔ Y"),
        # CPY
        0x8C: I("CPY",  3, 5, i, 0x18, "Compare Y (imm)"),
        0x9C: I("CPY",  2, 6, d, 0x18, "Compare Y (dir)"),
        0xAC: I("CPY",  2, 7, y, 0x18, "Compare Y (idy)"),
        0xBC: I("CPY",  3, 7, e, 0x18, "Compare Y (ext)"),
        # LDY
        0xCE: I("LDY",  3, 4, i, 0x18, "Load Y (imm)"),
        0xDE: I("LDY",  2, 5, d, 0x18, "Load Y (dir)"),
        0xEE: I("LDY",  2, 6, y, 0x18, "Load Y (idy)"),
        0xFE: I("LDY",  3, 6, e, 0x18, "Load Y (ext)"),
        # STY
        0xDF: I("STY",  2, 5, d, 0x18, "Store Y (dir)"),
        0xEF: I("STY",  2, 6, y, 0x18, "Store Y (idy)"),
        0xFF: I("STY",  3, 6, e, 0x18, "Store Y (ext)"),
        # Memory ops (offset,Y)
        0x60: I("NEG",  2, 7, y, 0x18, "Negate memory (idy)"),
        0x63: I("COM",  2, 7, y, 0x18, "Complement memory (idy)"),
        0x64: I("LSR",  2, 7, y, 0x18, "Logical shift right (idy)"),
        0x66: I("ROR",  2, 7, y, 0x18, "Rotate right (idy)"),
        0x67: I("ASR",  2, 7, y, 0x18, "Arithmetic shift right (idy)"),
        0x68: I("ASL",  2, 7, y, 0x18, "Arithmetic shift left (idy)"),
        0x69: I("ROL",  2, 7, y, 0x18, "Rotate left (idy)"),
        0x6A: I("DEC",  2, 7, y, 0x18, "Decrement memory (idy)"),
        0x6C: I("INC",  2, 7, y, 0x18, "Increment memory (idy)"),
        0x6D: I("TST",  2, 7, y, 0x18, "Test memory (idy)"),
        0x6E: I("JMP",  2, 4, y, 0x18, "Jump (idy)"),
        0x6F: I("CLR",  2, 7, y, 0x18, "Clear memory (idy)"),
        # A-register ops (offset,Y)
        0xA0: I("SUBA", 2, 5, y, 0x18, "A − M → A (idy)"),
        0xA1: I("CMPA", 2, 5, y, 0x18, "Compare A (idy)"),
        0xA2: I("SBCA", 2, 5, y, 0x18, "A − M − C → A (idy)"),
        0xA3: I("SUBD", 2, 7, y, 0x18, "D − M:M+1 → D (idy)"),
        0xA4: I("ANDA", 2, 5, y, 0x18, "A AND M → A (idy)"),
        0xA5: I("BITA", 2, 5, y, 0x18, "Bit test A (idy)"),
        0xA6: I("LDAA", 2, 5, y, 0x18, "Load A (idy)"),
        0xA7: I("STAA", 2, 5, y, 0x18, "Store A (idy)"),
        0xA8: I("EORA", 2, 5, y, 0x18, "A XOR M → A (idy)"),
        0xA9: I("ADCA", 2, 5, y, 0x18, "A + M + C → A (idy)"),
        0xAA: I("ORAA", 2, 5, y, 0x18, "A OR M → A (idy)"),
        0xAB: I("ADDA", 2, 5, y, 0x18, "A + M → A (idy)"),
        0xAD: I("JSR",  2, 7, y, 0x18, "Jump to subroutine (idy)"),
        0xAE: I("LDS",  2, 6, y, 0x18, "Load SP (idy)"),
        0xAF: I("STS",  2, 6, y, 0x18, "Store SP (idy)"),
        # B-register ops (offset,Y)
        0xE0: I("SUBB", 2, 5, y, 0x18, "B − M → B (idy)"),
        0xE1: I("CMPB", 2, 5, y, 0x18, "Compare B (idy)"),
        0xE2: I("SBCB", 2, 5, y, 0x18, "B − M − C → B (idy)"),
        0xE3: I("ADDD", 2, 7, y, 0x18, "D + M:M+1 → D (idy)"),
        0xE4: I("ANDB", 2, 5, y, 0x18, "B AND M → B (idy)"),
        0xE5: I("BITB", 2, 5, y, 0x18, "Bit test B (idy)"),
        0xE6: I("LDAB", 2, 5, y, 0x18, "Load B (idy)"),
        0xE7: I("STAB", 2, 5, y, 0x18, "Store B (idy)"),
        0xE8: I("EORB", 2, 5, y, 0x18, "B XOR M → B (idy)"),
        0xE9: I("ADCB", 2, 5, y, 0x18, "B + M + C → B (idy)"),
        0xEA: I("ORAB", 2, 5, y, 0x18, "B OR M → B (idy)"),
        0xEB: I("ADDB", 2, 5, y, 0x18, "B + M → B (idy)"),
        0xEC: I("LDD",  2, 6, y, 0x18, "Load D (idy)"),
        0xED: I("STD",  2, 6, y, 0x18, "Store D (idy)"),
        # Bit ops (Y-indexed)
        0x1C: I("BSET", 3, 8, by, 0x18, "Set bits (idy)"),
        0x1D: I("BCLR", 3, 8, by, 0x18, "Clear bits (idy)"),
        0x1E: I("BRSET",4, 8, by, 0x18, "Branch if bits set (idy)"),
        0x1F: I("BRCLR",4, 8, by, 0x18, "Branch if bits clear (idy)"),
    }


def _page3_opcodes() -> Dict[int, Instruction]:
    """Prebyte 0x1A — CPD modes + CPY/LDY/STY indexed,X (7 entries)."""
    I = Instruction; x = MODE_INDEXED_X
    i = MODE_IMMEDIATE; d = MODE_DIRECT; e = MODE_EXTENDED
    return {
        0x83: I("CPD",  3, 5, i, 0x1A, "Compare D (imm)"),
        0x93: I("CPD",  2, 6, d, 0x1A, "Compare D (dir)"),
        0xA3: I("CPD",  2, 7, x, 0x1A, "Compare D (idx)"),
        0xB3: I("CPD",  3, 7, e, 0x1A, "Compare D (ext)"),
        0xAC: I("CPY",  2, 7, x, 0x1A, "Compare Y (idx)"),
        0xEE: I("LDY",  2, 6, x, 0x1A, "Load Y (idx)"),
        0xEF: I("STY",  2, 6, x, 0x1A, "Store Y (idx)"),
    }


def _page4_opcodes() -> Dict[int, Instruction]:
    """Prebyte 0xCD — Y-indexed CPD/CPX/LDX/STX (4 entries)."""
    I = Instruction; y = MODE_INDEXED_Y
    return {
        0xA3: I("CPD",  2, 7, y, 0xCD, "Compare D (idy)"),
        0xAC: I("CPX",  2, 7, y, 0xCD, "Compare X (idy)"),
        0xEE: I("LDX",  2, 6, y, 0xCD, "Load X (idy)"),
        0xEF: I("STX",  2, 6, y, 0xCD, "Store X (idy)"),
    }


# ═══════════════════════════════════════════════════════════════════════
# VY V6 $060A ANNOTATIONS  (verified RAM + registers + scalars)
# ═══════════════════════════════════════════════════════════════════════

# HC11F register names ($1000-$103F)
HC11_REGISTERS: Dict[int, str] = {
    0x1000: "PORTA",  0x1001: "DDRA",   0x1002: "PORTG",  0x1003: "DDRG",
    0x1004: "PORTB",  0x1005: "PORTF",  0x1006: "PORTC",  0x1007: "DDRC",
    0x1008: "PORTD",  0x1009: "DDRD",   0x100A: "PORTE",
    0x100E: "TCNT",   0x1010: "TIC1",   0x1012: "TIC2",   0x1014: "TIC3",
    0x1016: "TOC1",   0x1018: "TOC2",   0x101A: "TOC3",   0x101C: "TOC4",
    0x101E: "TOC5",   0x1020: "TCTL1",  0x1021: "TCTL2",
    0x1022: "TMSK1",  0x1023: "TFLG1",  0x1024: "TMSK2",  0x1025: "TFLG2",
    0x1026: "PACTL",  0x1027: "PACNT",
    0x1028: "SPCR",   0x1029: "SPSR",   0x102A: "SPDR",
    0x102B: "BAUD",   0x102C: "SCCR1",  0x102D: "SCCR2",
    0x102E: "SCSR",   0x102F: "SCDR",
    0x1030: "ADCTL",  0x1031: "ADR1",   0x1032: "ADR2",
    0x1033: "ADR3",   0x1034: "ADR4",
    0x103C: "INIT",   0x103D: "TEST1",  0x103F: "CONFIG",
}

# Known RAM variable names (zero-page + extended)
VY_RAM_LABELS: Dict[int, str] = {
    0x00A2: "RPM",
    0x00A3: "RPM_HIGH",
    0x0080: "ENGINE_STATUS",
    0x0199: "DWELL_RAM",
    0x017B: "DWELL_INTERMED",
    0x194C: "CRANK_PERIOD_24X",
}

# Known calibration/scalar addresses and their meanings
VY_CAL_LABELS: Dict[int, Tuple[str, str, float]] = {
    0x77DE: ("Rev Limit High", "RPM", 25),
    0x77DF: ("Rev Limit Low", "RPM", 25),
    0x77DD: ("Rev Limit Low (alt)", "RPM", 25),
    0x77E0: ("Fuel Cut Enable", "flag", 1),
    0x77E2: ("Speed Limit", "km/h", 1),
    0x6776: ("Delta Cylair Dwell Threshold", "MG/CYL", 3.90625),
}

# Known code entry points (jump table targets, ISRs)
VY_CODE_LABELS: Dict[int, str] = {
    0x2000: "DEFAULT_ISR",
    0x2003: "SCI_ISR_JMP",
    0x2006: "TOC4_ISR_JMP",
    0x2009: "TOC3_EST_JMP",
    0x200C: "TOC1_ISR_JMP",
    0x200F: "TIC3_24X_JMP",
    0x2012: "TIC2_CAM_JMP",
    0x2015: "TIC1_ISR_JMP",
    0x2018: "IRQ_ISR_JMP",
    0x201B: "XIRQ_ISR_JMP",
    0x201E: "SWI_ISR_JMP",
    0x2021: "ILLOP_ISR_JMP",
    0x29D3: "SCI_ISR",
    0x2BAF: "DEFAULT_HANDLER",
    0x35BD: "TOC3_EST_ISR",
    0x35DE: "TOC4_ISR",
    0x35FF: "TIC3_24X_ISR",
    0x358A: "TIC2_CAM_ISR",
    0x301F: "TIC1_ISR",
    0x30BA: "IRQ_ISR",
    0x37A6: "TOC1_ISR",
    0xC011: "RESET_ENTRY",
    0xC015: "COP_HANDLER",
    0xC019: "CME_HANDLER",
}


# ═══════════════════════════════════════════════════════════════════════
# DISASSEMBLER ENGINE
# ═══════════════════════════════════════════════════════════════════════

PREBYTES = frozenset((0x18, 0x1A, 0xCD))


class HC11Disassembler:
    """
    Complete 68HC11 disassembler with VY V6 $060A annotation support.

    Usage:
        dis = HC11Disassembler()
        results = dis.disassemble(raw_bytes, base_addr=0x8000)
        results = dis.disassemble_hex("B6 77 DE 39", base_addr=0x8000)
        single  = dis.decode_one(data, offset=0, base_addr=0x8000)
    """

    def __init__(self, annotate_vy: bool = True):
        self.annotate_vy = annotate_vy
        self._base   = _base_opcodes()
        self._page2  = _page2_opcodes()
        self._page3  = _page3_opcodes()
        self._page4  = _page4_opcodes()

    # ── public API ──

    def disassemble(self, data: bytes, base_addr: int = 0,
                    max_instructions: int = 0) -> List[DisassembledInstruction]:
        """Disassemble a block of bytes. Returns list of DisassembledInstruction."""
        data = bytes(data)
        results: List[DisassembledInstruction] = []
        offset = 0
        count = 0
        while offset < len(data):
            inst = self.decode_one(data, offset, base_addr + offset)
            if inst is None:
                break
            results.append(inst)
            offset += inst.length
            count += 1
            if max_instructions and count >= max_instructions:
                break
        return results

    def disassemble_hex(self, hex_string: str, base_addr: int = 0,
                        max_instructions: int = 0) -> List[DisassembledInstruction]:
        """Disassemble a hex string like 'B6 77 DE 39' or 'B677DE39'."""
        data = self._parse_hex(hex_string)
        return self.disassemble(data, base_addr, max_instructions)

    def decode_one(self, data: bytes, offset: int = 0,
                   base_addr: int = 0) -> Optional[DisassembledInstruction]:
        """Decode exactly one instruction at the given offset."""
        if offset >= len(data):
            return None

        opcode = data[offset]
        prebyte = 0x00
        table = self._base
        prefix_len = 0

        # Handle prebyte pages
        if opcode in PREBYTES:
            if offset + 1 >= len(data):
                return self._make_db(data, offset, base_addr, 1)
            prebyte = opcode
            opcode = data[offset + 1]
            prefix_len = 1
            if prebyte == 0x18:
                table = self._page2
            elif prebyte == 0x1A:
                table = self._page3
            elif prebyte == 0xCD:
                table = self._page4

        inst_meta = table.get(opcode)
        if inst_meta is None or inst_meta.mode == MODE_PREFIX:
            # Unknown opcode or bare prefix — emit as DB
            return self._make_db(data, offset, base_addr, 1 + prefix_len)

        total_len = prefix_len + inst_meta.length
        if offset + total_len > len(data):
            return self._make_db(data, offset, base_addr, len(data) - offset)

        raw = bytes(data[offset: offset + total_len])
        # Operand bytes are everything after the opcode (and prebyte)
        operand_start = prefix_len + 1
        operand_bytes = raw[operand_start:]

        operand_str = self._format_operand(
            inst_meta.mnemonic, inst_meta.mode, operand_bytes,
            base_addr + total_len,  # address AFTER instruction (for rel branches)
        )

        comment = self._annotate(inst_meta, operand_bytes, base_addr) if self.annotate_vy else ""

        return DisassembledInstruction(
            address=base_addr,
            raw_bytes=raw,
            mnemonic=inst_meta.mnemonic,
            operand_str=operand_str,
            mode=inst_meta.mode,
            description=inst_meta.description,
            cycles=inst_meta.cycles,
            comment=comment,
        )

    def get_stats(self) -> Dict[str, int]:
        return {
            "base": len(self._base),
            "page2_0x18": len(self._page2),
            "page3_0x1A": len(self._page3),
            "page4_0xCD": len(self._page4),
            "total": len(self._base) + len(self._page2) + len(self._page3) + len(self._page4),
        }

    # ── operand formatting ──

    @staticmethod
    def _format_operand(mnemonic: str, mode: str, operand_bytes: bytes,
                        next_addr: int) -> str:
        """Format the operand string for a given addressing mode."""
        ob = operand_bytes
        if mode == MODE_IMPLIED:
            return ""
        if mode == MODE_IMMEDIATE:
            if len(ob) == 1:
                return f"#${ob[0]:02X}"
            if len(ob) == 2:
                return f"#${(ob[0] << 8) | ob[1]:04X}"
            return ""
        if mode == MODE_DIRECT:
            return f"${ob[0]:02X}" if ob else ""
        if mode == MODE_EXTENDED:
            if len(ob) >= 2:
                return f"${(ob[0] << 8) | ob[1]:04X}"
            return ""
        if mode == MODE_INDEXED_X:
            return f"${ob[0]:02X},X" if ob else ""
        if mode == MODE_INDEXED_Y:
            return f"${ob[0]:02X},Y" if ob else ""
        if mode == MODE_RELATIVE:
            if ob:
                rel = ob[0] if ob[0] < 128 else ob[0] - 256
                target = next_addr + rel
                return f"${target & 0xFFFF:04X}"
            return ""
        if mode == MODE_BIT_DIR:
            if len(ob) == 2:
                return f"${ob[0]:02X},#${ob[1]:02X}"
            if len(ob) == 3:
                rel = ob[2] if ob[2] < 128 else ob[2] - 256
                target = next_addr + rel
                return f"${ob[0]:02X},#${ob[1]:02X},${target & 0xFFFF:04X}"
            return ""
        if mode == MODE_BIT_IDX:
            if len(ob) == 2:
                return f"${ob[0]:02X},X,#${ob[1]:02X}"
            if len(ob) == 3:
                rel = ob[2] if ob[2] < 128 else ob[2] - 256
                target = next_addr + rel
                return f"${ob[0]:02X},X,#${ob[1]:02X},${target & 0xFFFF:04X}"
            return ""
        if mode == MODE_BIT_IDY:
            if len(ob) == 2:
                return f"${ob[0]:02X},Y,#${ob[1]:02X}"
            if len(ob) == 3:
                rel = ob[2] if ob[2] < 128 else ob[2] - 256
                target = next_addr + rel
                return f"${ob[0]:02X},Y,#${ob[1]:02X},${target & 0xFFFF:04X}"
            return ""
        return ""

    # ── VY V6 annotation ──

    def _annotate(self, inst: Instruction, operand_bytes: bytes,
                  addr: int) -> str:
        """Generate VY V6 annotation comment for known addresses."""
        parts: List[str] = []
        mode = inst.mode
        ob = operand_bytes

        # Extended mode — full 16-bit address
        if mode == MODE_EXTENDED and len(ob) >= 2:
            ea = (ob[0] << 8) | ob[1]
            lbl = self._label_for(ea)
            if lbl:
                parts.append(lbl)

        # Direct mode — zero-page ($00xx)
        elif mode == MODE_DIRECT and ob:
            ea = ob[0]
            lbl = VY_RAM_LABELS.get(ea)
            if lbl:
                parts.append(lbl)

        # Branch / BSR / JSR targets — annotate known code labels
        if mode == MODE_RELATIVE and ob:
            rel = ob[0] if ob[0] < 128 else ob[0] - 256
            # next_addr = addr + inst.length + prefix overhead already included
            # but we get the base_addr here, not next_addr. Recalculate:
            prefix_len = 1 if inst.prebyte else 0
            next_addr = addr + prefix_len + inst.length
            target = (next_addr + rel) & 0xFFFF
            lbl = VY_CODE_LABELS.get(target)
            if lbl:
                parts.append(f"→ {lbl}")

        if mode == MODE_EXTENDED and len(ob) >= 2:
            ea = (ob[0] << 8) | ob[1]
            if inst.mnemonic in ("JSR", "JMP"):
                lbl = VY_CODE_LABELS.get(ea)
                if lbl:
                    parts.append(f"→ {lbl}")

        # RPM comparison annotation
        if inst.mnemonic in ("CMPA", "CMPB", "LDAA", "LDAB") and mode == MODE_IMMEDIATE and ob:
            val = ob[0]
            rpm = val * 25
            if rpm >= 1000:
                parts.append(f"{rpm} RPM")

        return " | ".join(parts)

    @staticmethod
    def _label_for(addr: int) -> str:
        """Look up a human label for a 16-bit address."""
        # HC11 registers
        reg = HC11_REGISTERS.get(addr)
        if reg:
            return reg
        # Calibration scalars
        cal = VY_CAL_LABELS.get(addr)
        if cal:
            return cal[0]
        # RAM variables (extended addressing hits $00xx)
        ram = VY_RAM_LABELS.get(addr)
        if ram:
            return ram
        # Code labels
        code = VY_CODE_LABELS.get(addr)
        if code:
            return code
        return ""

    # ── helpers ──

    @staticmethod
    def _make_db(data: bytes, offset: int, base_addr: int,
                 count: int) -> DisassembledInstruction:
        """Create a DB (data byte) pseudo-instruction for unknown bytes."""
        raw = bytes(data[offset: offset + count])
        hex_vals = " ".join(f"${b:02X}" for b in raw)
        return DisassembledInstruction(
            address=base_addr,
            raw_bytes=raw,
            mnemonic="DB",
            operand_str=hex_vals,
            mode=MODE_DATA,
            description="Data byte(s)",
            cycles=0,
            comment="",
        )

    @staticmethod
    def _parse_hex(hex_string: str) -> bytes:
        """Parse flexible hex input: 'B6 77DE', 'B6,77,DE', '0xB6 0x77 0xDE', etc."""
        s = hex_string.strip()
        # Remove common prefixes/separators
        s = s.replace("0x", "").replace("0X", "")
        s = s.replace(",", " ").replace(";", " ").replace("\n", " ").replace("\t", " ")
        # If no spaces → treat as continuous hex
        tokens = s.split()
        if not tokens:
            return b""
        if len(tokens) == 1 and len(tokens[0]) > 2:
            # Continuous hex like "B677DE39"
            return bytes.fromhex(tokens[0])
        return bytes.fromhex("".join(tokens))


# ═══════════════════════════════════════════════════════════════════════
# CONVENIENCE / CLI
# ═══════════════════════════════════════════════════════════════════════

def disassemble_hex(hex_string: str, base_addr: int = 0,
                    annotate: bool = True) -> List[DisassembledInstruction]:
    """Module-level convenience function."""
    return HC11Disassembler(annotate_vy=annotate).disassemble_hex(hex_string, base_addr)


def disassemble_bytes(data: bytes, base_addr: int = 0,
                      annotate: bool = True) -> List[DisassembledInstruction]:
    """Module-level convenience function."""
    return HC11Disassembler(annotate_vy=annotate).disassemble(data, base_addr)


if __name__ == "__main__":
    dis = HC11Disassembler()
    stats = dis.get_stats()
    print("=" * 72)
    print("HC11 Disassembler — Standalone Module")
    print("=" * 72)
    print(f"Opcodes: {stats['base']} base + {stats['page2_0x18']} page2"
          f" + {stats['page3_0x1A']} page3 + {stats['page4_0xCD']} page4"
          f" = {stats['total']} total")
    print()

    # Test with VY V6 kernel snippet
    test_hex = "B6 77 DE 91 A4 26 05 18 CE 12 34 BD 35 FF 39"
    print(f"Input hex: {test_hex}")
    print(f"Base addr: $8000")
    print("-" * 72)
    for r in dis.disassemble_hex(test_hex, base_addr=0x8000):
        print(r.format(show_description=True))
    print()

    # Test prebyte decoding
    test2 = "18 08 1A 83 00 A4 CD A3 10 39"
    print(f"Input hex: {test2}")
    print(f"Base addr: $C000")
    print("-" * 72)
    for r in dis.disassemble_hex(test2, base_addr=0xC000):
        print(r.format(show_description=True))
