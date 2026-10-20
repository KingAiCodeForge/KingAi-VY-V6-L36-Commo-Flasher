"""Deterministic synthetic vECU regressions; no owned firmware or serial adapter.

The original import-time five-scenario diagnostic used unavailable private BINs
and printed PASS without assertions. Those scenarios are executable tests here.
"""
from pathlib import Path

import pytest
import kingai_commie_flasher as f
from tools.hc11_disassembler import HC11Disassembler


@pytest.fixture
def virtual_ecu(tmp_path):
    image = bytearray((i * 17 + i // 256) & 255 for i in range(f.BinFile.BIN_SIZE))
    image[0x77DE:0x77E0] = bytes([0xC0, 0xB8])
    image[0x1FFFE:0x20000] = bytes([0xC0, 0x11])
    image[0x1C011:0x1C015] = bytes([0x86, 0x42, 0x01, 0x39])  # LDAA #42; NOP; RTS
    f.BinFile.fix_checksum(image)
    source = tmp_path / 'synthetic ECU image.bin'
    source.write_bytes(image)
    transport = f.LoopbackTransport(str(source))
    transport.open()
    transport.flush_input()
    config = f.CommConfig()
    config.ignore_echo = False
    config.high_speed_read = False
    ecu = f.ECUComm(transport, config)
    yield ecu, transport, image, source
    transport.close()
    assert source.read_bytes() == image


def test_mode2_reads_calibration_fields_exactly(virtual_ecu):
    ecu, _, image, _ = virtual_ecu
    data = ecu.read_ram(0x77C0)
    assert data == image[0x77C0:0x7800]
    assert data[0x1E:0x20] == bytes([0xC0, 0xB8])


def test_extended_mode2_maps_all_three_banks(virtual_ecu):
    ecu, _, image, _ = virtual_ecu
    for address in (0, 0x4000, 0xFFC0, 0x10000, 0x17FC0, 0x18000, 0x1FFC0):
        assert ecu.read_ram(address, extended=True) == image[address:address + 64]


def test_reset_vector_is_read_from_synthetic_image(virtual_ecu):
    ecu, _, image, _ = virtual_ecu
    vectors = ecu.read_ram(0x1FFC0, extended=True)
    assert vectors == image[0x1FFC0:0x20000]
    assert int.from_bytes(vectors[-2:], 'big') == 0xC011


def test_reset_entry_can_be_disassembled(virtual_ecu):
    ecu, _, _, _ = virtual_ecu
    code = ecu.read_ram(0x1C011, extended=True)
    instructions = HC11Disassembler().disassemble(code[:4], base_addr=0xC011)
    assert len(instructions) == 3
    rendered = '\n'.join(item.format() for item in instructions).upper()
    assert 'LDAA' in rendered
    assert 'NOP' in rendered
    assert 'RTS' in rendered


def test_variant_comparison_preserves_sources_and_reports_changed_sector(virtual_ecu, tmp_path):
    _, transport, original, source = virtual_ecu
    variant = bytearray(original)
    variant[0x77DE] ^= 1
    variant_path = tmp_path / 'synthetic second variant.bin'
    variant_path.write_bytes(variant)
    other = f.LoopbackTransport(str(variant_path))
    assert f.BinFile.diff_sectors(transport.export_flash(), other.export_flash()) == [1]
    assert source.read_bytes() == original
    assert variant_path.read_bytes() == variant


def test_full_and_tail_custom_reads_return_original_bytes(virtual_ecu, monkeypatch):
    ecu, _, image, _ = virtual_ecu
    monkeypatch.setattr(f.time, 'sleep', lambda _: None)
    op = f.FlashOp(ecu)
    assert op.full_read() == image
    assert op._stats['complete'] is True
    assert op.custom_read(0x1FF80, 0x1FFC4) == image[0x1FF80:0x1FFC5]
    assert op._stats['bytes_transferred'] == 69
    assert op._stats['missing_ranges'] == []


def test_custom_read_last_twelve_bytes_uses_a_complete_in_bounds_frame(virtual_ecu):
    ecu, _, image, _ = virtual_ecu
    op = f.FlashOp(ecu)
    assert op.custom_read(0x1FFF4, 0x1FFFF) == image[-12:]
    assert len(op._read_evidence) == 1
    assert op._read_evidence[0]['wire_address'] == 0x1FFC0
    assert op._read_evidence[0]['address'] == 0x1FFF4
    assert len(op._read_evidence[0]['data']) == 64
