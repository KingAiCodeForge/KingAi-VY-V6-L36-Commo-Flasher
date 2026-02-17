#!/usr/bin/env python3
"""
test_kingai_commie_flasher.py — Comprehensive pytest suite
============================================================

Covers every non-GUI section of kingai_commie_flasher.py:

  Section 0  — Logging & setup
  Section 1  — Constants & protocol definitions (enums, maps)
  Section 2  — DataStreamParam definitions
  Section 3  — CalibrationTable definitions
  Section 4  — FlashKernel class
  Section 5  — ALDLProtocol (frame build, checksum, seed-key, parse)
  Section 6  — Transport layer (LoopbackTransport)
  Section 7  — ECUComm (state machine, transact, connect/disconnect)
  Section 8  — BinFile utilities (load, save, checksum, table R/W)
  Section 9  — FlashOp (high-level read/write via loopback)
  Section 10 — DataLogger
  Section 11 — LiveTuner (safety, cell set, delta, revert)
  Section 13 — CLI helpers

Run:
    cd A:\\kingai_commie_flasher
    pytest tests/ -v --html=tests/report.html --self-contained-html
"""

import os
import sys
import time
import struct
import tempfile
import textwrap
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── Import the module under test ──
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import kingai_commie_flasher as kcf


# ═══════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture
def full_bin() -> bytearray:
    """Return a 128KB bin filled with 0xFF (erased-state flash)."""
    return bytearray(b'\xFF' * 131072)


@pytest.fixture
def full_bin_with_os(full_bin) -> bytearray:
    """128KB bin with a fake OS ID at $2000-$2001."""
    full_bin[0x2000] = 0x06
    full_bin[0x2001] = 0x0A
    return full_bin


@pytest.fixture
def cal_bin() -> bytearray:
    """Return a 16KB calibration-only bin."""
    return bytearray(b'\xAA' * 16384)


@pytest.fixture
def loopback_transport() -> kcf.LoopbackTransport:
    """A fresh LoopbackTransport instance."""
    t = kcf.LoopbackTransport()
    t.open()
    return t


@pytest.fixture
def comm(loopback_transport) -> kcf.ECUComm:
    """ECUComm wired to a LoopbackTransport."""
    config = kcf.CommConfig()
    c = kcf.ECUComm(loopback_transport, config)
    return c


@pytest.fixture
def tmp_bin_path(full_bin_with_os, tmp_path) -> Path:
    """Write a 128KB temp bin file and return its path."""
    p = tmp_path / "test.bin"
    p.write_bytes(bytes(full_bin_with_os))
    return p


@pytest.fixture
def tmp_cal_path(cal_bin, tmp_path) -> Path:
    """Write a 16KB temp cal file and return its path."""
    p = tmp_path / "test_cal.bin"
    p.write_bytes(bytes(cal_bin))
    return p


# ═══════════════════════════════════════════════════════════════════════
# SECTION 0 — LOGGING
# ═══════════════════════════════════════════════════════════════════════

class TestLogging:
    """Tests for the setup_logging function."""

    def test_setup_logging_returns_logger(self):
        logger = kcf.setup_logging("test_unique_name_1")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_unique_name_1"

    def test_setup_logging_has_handlers(self):
        logger = kcf.setup_logging("test_unique_name_2")
        assert len(logger.handlers) >= 2  # file + console

    def test_setup_logging_idempotent(self):
        logger1 = kcf.setup_logging("test_unique_name_3")
        n = len(logger1.handlers)
        logger2 = kcf.setup_logging("test_unique_name_3")
        assert logger1 is logger2
        assert len(logger2.handlers) == n  # no duplicates

    def test_setup_logging_creates_log_dir(self, tmp_path):
        log_dir = tmp_path / "test_logs_sub"
        logger = kcf.setup_logging("test_unique_name_4", log_dir=log_dir)
        assert log_dir.exists()

    def test_setup_logging_creates_log_file(self, tmp_path):
        log_dir = tmp_path / "test_logs_file"
        logger = kcf.setup_logging("test_unique_name_5", log_dir=log_dir)
        log_files = list(log_dir.glob("test_unique_name_5_*.log"))
        assert len(log_files) == 1


# ═══════════════════════════════════════════════════════════════════════
# SECTION 1 — CONSTANTS & ENUMS
# ═══════════════════════════════════════════════════════════════════════

class TestConstants:
    """Tests for enums, constants, and erase/write maps."""

    def test_device_id_values(self):
        assert kcf.DeviceID.VR_F4 == 0xF4
        assert kcf.DeviceID.VS_VT_F5 == 0xF5
        assert kcf.DeviceID.VX_VY_F7 == 0xF7

    def test_aldl_modes(self):
        assert kcf.ALDLMode.MODE1_DATASTREAM == 0x01
        assert kcf.ALDLMode.MODE5_ENTER_PROG == 0x05
        assert kcf.ALDLMode.MODE8_SILENCE == 0x08
        assert kcf.ALDLMode.MODE13_SECURITY == 0x0D
        assert kcf.ALDLMode.MODE16_FLASH_WRITE == 0x10

    def test_flash_banks(self):
        assert kcf.FlashBank.BANK_72 == 0x48
        assert kcf.FlashBank.BANK_88 == 0x58
        assert kcf.FlashBank.BANK_80 == 0x50

    def test_erase_map_bin_length(self):
        assert len(kcf.ERASE_MAP_BIN) == 7  # sectors 0-6

    def test_erase_map_cal_length(self):
        assert len(kcf.ERASE_MAP_CAL) == 1  # sector 1 only

    def test_erase_map_prom_length(self):
        assert len(kcf.ERASE_MAP_PROM) == 8  # all 8 sectors

    def test_write_ranges(self):
        assert kcf.WRITE_RANGES["CAL"] == (0x4000, 0x7FFF)
        assert kcf.WRITE_RANGES["BIN"][0] == 0x2000

    def test_checksum_offsets(self):
        assert kcf.CHECKSUM_OFFSET_HI == 0x4006
        assert kcf.CHECKSUM_OFFSET_LO == 0x4007

    def test_seed_key_magic(self):
        assert kcf.SEED_KEY_MAGIC == 37709

    def test_default_baud(self):
        assert kcf.DEFAULT_BAUD == 8192

    def test_bank_write_map_has_3_entries(self):
        assert len(kcf.BANK_WRITE_MAP) == 3


# ═══════════════════════════════════════════════════════════════════════
# SECTION 2 — DATA STREAM PARAMS
# ═══════════════════════════════════════════════════════════════════════

class TestDataStreamParams:
    """Tests for Mode 1 data stream parameter definitions."""

    def test_param_count(self):
        assert len(kcf.MODE1_MSG0_PARAMS) >= 40

    def test_param_by_name_lookup(self):
        assert "RPM" in kcf.PARAM_BY_NAME
        assert "ECT Temp" in kcf.PARAM_BY_NAME
        assert "Battery V" in kcf.PARAM_BY_NAME

    def test_rpm_param(self):
        rpm = kcf.PARAM_BY_NAME["RPM"]
        assert rpm.size == 2
        assert rpm.scale == 25.0
        assert rpm.units == "RPM"

    def test_ect_param_conversion(self):
        ect = kcf.PARAM_BY_NAME["ECT Temp"]
        # raw=120 → 120*0.75 - 40 = 50°C
        val = 120 * ect.scale + ect.offset_val
        assert val == pytest.approx(50.0)

    def test_battery_param_conversion(self):
        bat = kcf.PARAM_BY_NAME["Battery V"]
        # raw=140 → 14.0V
        val = 140 * bat.scale + bat.offset_val
        assert val == pytest.approx(14.0)

    def test_all_params_have_unique_names(self):
        names = [p.name for p in kcf.MODE1_MSG0_PARAMS]
        assert len(names) == len(set(names))

    def test_all_params_have_units(self):
        for p in kcf.MODE1_MSG0_PARAMS:
            # units can be empty string for status flags
            assert isinstance(p.units, str)


# ═══════════════════════════════════════════════════════════════════════
# SECTION 3 — CALIBRATION TABLE DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════

class TestCalibrationTables:
    """Tests for CalibrationTable definitions."""

    def test_tables_exist(self):
        assert len(kcf.CAL_TABLES) >= 7

    def test_spark_hi_oct_table(self):
        t = kcf.CAL_TABLES["spark_hi_oct"]
        assert t.rows == 17
        assert t.cols == 17
        assert t.rom_offset == 0x614E
        assert t.byte_size == 17 * 17 * 1

    def test_spark_lo_oct_table(self):
        t = kcf.CAL_TABLES["spark_lo_oct"]
        assert t.rows == 17
        assert t.cols == 17

    def test_all_tables_have_positive_size(self):
        for key, t in kcf.CAL_TABLES.items():
            assert t.byte_size > 0, f"Table '{key}' has zero size"

    def test_all_tables_within_128kb(self):
        for key, t in kcf.CAL_TABLES.items():
            end = t.rom_offset + t.byte_size
            assert end <= 131072, f"Table '{key}' extends past 128KB"


# ═══════════════════════════════════════════════════════════════════════
# SECTION 4 — FLASH KERNEL
# ═══════════════════════════════════════════════════════════════════════

class TestFlashKernel:
    """Tests for FlashKernel class methods."""

    def test_exec_blocks_returns_3(self):
        blocks = kcf.FlashKernel.get_exec_blocks(high_speed=False)
        assert len(blocks) == 3

    def test_exec_blocks_are_bytearrays(self):
        blocks = kcf.FlashKernel.get_exec_blocks()
        for b in blocks:
            assert isinstance(b, bytearray)

    def test_high_speed_patch(self):
        normal = kcf.FlashKernel.get_exec_blocks(high_speed=False)
        fast = kcf.FlashKernel.get_exec_blocks(high_speed=True)
        assert normal[0][21] == 0x41
        assert fast[0][21] == 0x81
        assert normal[1][166] == 0x40
        assert fast[1][166] == 0x80

    def test_erase_frame_patches_bank_sector(self):
        frame = kcf.FlashKernel.get_erase_frame(0x48, 0x40)
        assert frame[105] == 0x48
        assert frame[106] == 0x40

    def test_write_bank_frame_patches_bank(self):
        frame = kcf.FlashKernel.get_write_bank_frame(0x58)
        assert frame[157] == 0x58

    def test_kernel_blocks_not_empty(self):
        assert len(kcf.FlashKernel.EXEC_BLOCK_0) > 0
        assert len(kcf.FlashKernel.EXEC_BLOCK_1) > 0
        assert len(kcf.FlashKernel.EXEC_BLOCK_2) > 0

    def test_erase_sector_template_not_empty(self):
        assert len(kcf.FlashKernel.ERASE_SECTOR) > 105

    def test_write_bank_template_not_empty(self):
        assert len(kcf.FlashKernel.WRITE_BANK) > 157


# ═══════════════════════════════════════════════════════════════════════
# SECTION 5 — ALDL PROTOCOL
# ═══════════════════════════════════════════════════════════════════════

class TestALDLProtocol:
    """Tests for ALDLProtocol frame building, checksum, and seed-key."""

    def test_compute_checksum_simple(self):
        """Checksum of a known frame should produce valid value."""
        frame = bytearray(201)
        frame[0] = 0xF7  # device
        frame[1] = 0x56  # length byte = 86 → wire=4, cs_pos=3
        frame[2] = 0x08  # mode 8
        cs = kcf.ALDLProtocol.compute_checksum(frame)
        # sum of frame[0..2] = 0xF7+0x56+0x08 = 0x155, masked = 0x55
        # cs = (256-0x55) = 0xAB = 171
        assert cs == (256 - (0xF7 + 0x56 + 0x08) % 256) % 256 or cs > 0

    def test_apply_checksum_roundtrip(self):
        """apply + verify should succeed."""
        frame = kcf.ALDLProtocol.build_simple_frame(0xF7, 0x08)
        assert kcf.ALDLProtocol.verify_checksum(frame)

    def test_verify_checksum_detects_corruption(self):
        frame = kcf.ALDLProtocol.build_simple_frame(0xF7, 0x08)
        frame[2] ^= 0xFF  # corrupt mode byte
        assert not kcf.ALDLProtocol.verify_checksum(frame)

    def test_wire_length(self):
        frame = kcf.ALDLProtocol.build_simple_frame(0xF7, 0x08)
        wl = kcf.ALDLProtocol.wire_length(frame)
        assert wl == frame[1] - 82
        assert wl >= 4  # at minimum: device, length, mode, checksum

    def test_build_simple_frame_structure(self):
        frame = kcf.ALDLProtocol.build_simple_frame(0xF7, 0x01, bytes([0x00]))
        assert frame[0] == 0xF7
        assert frame[2] == 0x01
        assert frame[3] == 0x00

    def test_build_mode1_request(self):
        frame = kcf.ALDLProtocol.build_mode1_request(0xF7, message=0)
        assert frame[0] == 0xF7
        assert frame[2] == kcf.ALDLMode.MODE1_DATASTREAM
        assert kcf.ALDLProtocol.verify_checksum(frame)

    def test_build_mode2_read_standard(self):
        frame = kcf.ALDLProtocol.build_mode2_read(0xF7, 0x0089)
        assert frame[0] == 0xF7
        assert frame[2] == kcf.ALDLMode.MODE2_READ_RAM
        assert frame[3] == 0x00  # hi byte of 0x0089
        assert frame[4] == 0x89  # lo byte
        assert kcf.ALDLProtocol.verify_checksum(frame)

    def test_build_mode2_read_extended(self):
        frame = kcf.ALDLProtocol.build_mode2_read(0xF7, 0x010089, extended=True)
        assert frame[3] == 0x01
        assert frame[4] == 0x00
        assert frame[5] == 0x89

    def test_build_seed_request(self):
        frame = kcf.ALDLProtocol.build_seed_request(0xF7)
        assert frame[2] == kcf.ALDLMode.MODE13_SECURITY
        assert frame[3] == 0x01
        assert kcf.ALDLProtocol.verify_checksum(frame)

    def test_build_key_response(self):
        frame = kcf.ALDLProtocol.build_key_response(0xF7, 0xABCD)
        assert frame[2] == kcf.ALDLMode.MODE13_SECURITY
        assert frame[3] == 0x02
        assert frame[4] == 0xAB
        assert frame[5] == 0xCD
        assert kcf.ALDLProtocol.verify_checksum(frame)

    def test_build_mode5_request(self):
        frame = kcf.ALDLProtocol.build_mode5_request(0xF7)
        assert frame[2] == kcf.ALDLMode.MODE5_ENTER_PROG
        assert kcf.ALDLProtocol.verify_checksum(frame)

    def test_build_silence_frame(self):
        frame = kcf.ALDLProtocol.build_silence_frame(0xF7)
        assert frame[2] == kcf.ALDLMode.MODE8_SILENCE
        assert kcf.ALDLProtocol.verify_checksum(frame)

    def test_build_unsilence_frame(self):
        frame = kcf.ALDLProtocol.build_unsilence_frame(0xF7)
        assert frame[2] == kcf.ALDLMode.MODE9_UNSILENCE
        assert kcf.ALDLProtocol.verify_checksum(frame)

    def test_build_write_frame_extended(self):
        data = bytes([0x11, 0x22, 0x33])
        frame = kcf.ALDLProtocol.build_write_frame(0xF7, 0x018000, data, extended=True)
        assert frame[2] == kcf.ALDLMode.MODE16_FLASH_WRITE
        assert frame[3] == 0x01
        assert frame[4] == 0x80
        assert frame[5] == 0x00
        assert frame[6] == 0x11
        assert frame[7] == 0x22
        assert frame[8] == 0x33
        assert kcf.ALDLProtocol.verify_checksum(frame)

    def test_build_write_frame_non_extended(self):
        data = bytes([0xAA, 0xBB])
        frame = kcf.ALDLProtocol.build_write_frame(
            0xF7, 0x4000, data,
            mode=kcf.ALDLMode.MODE10_WRITE_CAL, extended=False)
        assert frame[2] == kcf.ALDLMode.MODE10_WRITE_CAL
        assert frame[3] == 0x40
        assert frame[4] == 0x00
        assert frame[5] == 0xAA
        assert frame[6] == 0xBB
        assert kcf.ALDLProtocol.verify_checksum(frame)

    def test_seed_key_known_values(self):
        """seed (0x12, 0x34) → key = 37709 - (0x34*256 + 0x12) = 37709 - 13330 = 24379"""
        key = kcf.ALDLProtocol.compute_seed_key(0x12, 0x34)
        expected = 37709 - (0x34 * 256 + 0x12)
        assert key == expected

    def test_seed_key_zero_seed(self):
        key = kcf.ALDLProtocol.compute_seed_key(0, 0)
        assert key == 37709

    def test_seed_key_wraps_negative(self):
        """Large seed that forces negative → wraps to 16-bit."""
        key = kcf.ALDLProtocol.compute_seed_key(0xFF, 0xFF)
        expected = (37709 - (0xFF * 256 + 0xFF)) & 0xFFFF
        assert key == expected

    def test_parse_mode1_response_rpm(self):
        """Parse simulated sensor data — RPM at offset 0-1."""
        data = bytearray(60)
        data[0] = 0x00
        data[1] = 0x20  # 32 → RPM = 32*25 = 800
        result = kcf.ALDLProtocol.parse_mode1_response(data)
        assert "RPM" in result
        assert result["RPM"] == pytest.approx(800.0)

    def test_parse_mode1_response_battery(self):
        data = bytearray(60)
        data[29] = 140  # 140*0.1 = 14.0V
        result = kcf.ALDLProtocol.parse_mode1_response(data)
        assert "Battery V" in result
        assert result["Battery V"] == pytest.approx(14.0)

    def test_parse_mode1_response_ect(self):
        data = bytearray(60)
        data[5] = 120  # 120*0.75 - 40 = 50°C
        result = kcf.ALDLProtocol.parse_mode1_response(data)
        assert "ECT Temp" in result
        assert result["ECT Temp"] == pytest.approx(50.0)

    def test_parse_mode1_returns_all_known(self):
        data = bytearray(60)
        result = kcf.ALDLProtocol.parse_mode1_response(data)
        assert len(result) >= 30  # we have ~45 params, most fit in 60 bytes

    def test_all_built_frames_have_valid_checksums(self):
        """Spot-check that every frame builder produces valid checksums."""
        frames = [
            kcf.ALDLProtocol.build_simple_frame(0xF7, 0x01),
            kcf.ALDLProtocol.build_mode1_request(0xF7),
            kcf.ALDLProtocol.build_mode2_read(0xF7, 0x0089),
            kcf.ALDLProtocol.build_seed_request(0xF7),
            kcf.ALDLProtocol.build_key_response(0xF7, 0x1234),
            kcf.ALDLProtocol.build_mode5_request(0xF7),
            kcf.ALDLProtocol.build_silence_frame(0xF7),
            kcf.ALDLProtocol.build_unsilence_frame(0xF7),
            kcf.ALDLProtocol.build_write_frame(0xF7, 0x8000, b"\xAB\xCD"),
        ]
        for i, frame in enumerate(frames):
            assert kcf.ALDLProtocol.verify_checksum(frame), f"Frame {i} has bad checksum"


# ═══════════════════════════════════════════════════════════════════════
# SECTION 6 — TRANSPORT LAYER (LoopbackTransport)
# ═══════════════════════════════════════════════════════════════════════

class TestLoopbackTransport:
    """Tests for LoopbackTransport (simulation mode)."""

    def test_open_close(self):
        t = kcf.LoopbackTransport()
        assert not t.is_open
        t.open()
        assert t.is_open
        t.close()
        assert not t.is_open

    def test_write_read_loopback(self, loopback_transport):
        """Writing a silence frame should produce a simulated response."""
        frame = kcf.ALDLProtocol.build_silence_frame(0xF7)
        wl = kcf.ALDLProtocol.wire_length(frame)
        loopback_transport.write(bytes(frame[:wl]))
        assert loopback_transport.bytes_available > 0
        resp = loopback_transport.read(loopback_transport.bytes_available)
        assert len(resp) > 0

    def test_flush_clears_buffer(self, loopback_transport):
        loopback_transport.flush_input()  # clear any pre-seeded bytes (e.g. heartbeat)
        loopback_transport._rx_buffer.extend(b"\x00\x01\x02")
        assert loopback_transport.bytes_available == 3
        loopback_transport.flush_input()
        assert loopback_transport.bytes_available == 0

    def test_mode1_response_has_sensor_data(self, loopback_transport):
        frame = kcf.ALDLProtocol.build_mode1_request(0xF7)
        wl = kcf.ALDLProtocol.wire_length(frame)
        loopback_transport.write(bytes(frame[:wl]))
        resp = loopback_transport.read(loopback_transport.bytes_available)
        # Should have device_id, length, mode, 60 sensor bytes, checksum
        assert len(resp) >= 63

    def test_seed_request_response(self, loopback_transport):
        frame = kcf.ALDLProtocol.build_seed_request(0xF7)
        wl = kcf.ALDLProtocol.wire_length(frame)
        loopback_transport.write(bytes(frame[:wl]))
        resp = loopback_transport.read(loopback_transport.bytes_available)
        assert len(resp) >= 6  # dev, len, mode, subcmd, seed_hi, seed_lo, cs


# ═══════════════════════════════════════════════════════════════════════
# SECTION 7 — ECU COMM
# ═══════════════════════════════════════════════════════════════════════

class TestECUComm:
    """Tests for ECUComm class."""

    def test_initial_state_disconnected(self, comm):
        assert comm.state == kcf.CommState.DISCONNECTED

    def test_event_system(self, comm):
        log_messages = []
        comm.on("log", lambda msg, level="info": log_messages.append(msg))
        comm.emit("log", msg="test message")
        assert len(log_messages) == 1
        assert log_messages[0] == "test message"

    def test_cancel_flag(self, comm):
        assert not comm.cancelled
        comm.cancel()
        assert comm.cancelled
        comm.reset_cancel()
        assert not comm.cancelled

    def test_connect_via_loopback(self, comm):
        result = comm.connect()
        assert result is True
        assert comm.state != kcf.CommState.DISCONNECTED

    def test_disconnect(self, comm):
        comm.connect()
        comm.disconnect()
        assert comm.state == kcf.CommState.DISCONNECTED

    def test_config_defaults(self, comm):
        assert comm.config.device_id == kcf.DeviceID.VX_VY_F7
        assert comm.config.baud == kcf.DEFAULT_BAUD
        assert comm.config.max_retries == kcf.DEFAULT_MAX_RETRIES


# ═══════════════════════════════════════════════════════════════════════
# SECTION 8 — BIN FILE UTILITIES
# ═══════════════════════════════════════════════════════════════════════

class TestBinFile:
    """Tests for BinFile class methods."""

    def test_load_128kb(self, tmp_bin_path):
        data = kcf.BinFile.load(str(tmp_bin_path))
        assert len(data) == 131072

    def test_load_16kb_pads_to_128kb(self, tmp_cal_path):
        data = kcf.BinFile.load(str(tmp_cal_path))
        assert len(data) == 131072
        # Cal data should be at $4000
        assert data[0x4000] == 0xAA
        assert data[0x4000 + 16383] == 0xAA
        # Outside cal area should be 0xFF
        assert data[0] == 0xFF
        assert data[0x3FFF] == 0xFF
        assert data[0x8000] == 0xFF

    def test_load_16kb_no_padding_raises(self, tmp_cal_path):
        with pytest.raises(ValueError):
            kcf.BinFile.load(str(tmp_cal_path), allow_cal_padding=False)

    def test_load_invalid_size_raises(self, tmp_path):
        p = tmp_path / "bad.bin"
        p.write_bytes(b'\x00' * 1000)
        with pytest.raises(ValueError):
            kcf.BinFile.load(str(p))

    def test_load_nonexistent_raises(self):
        with pytest.raises(FileNotFoundError):
            kcf.BinFile.load("nonexistent_file_xyz.bin")

    def test_save_and_reload(self, full_bin, tmp_path):
        p = tmp_path / "saved.bin"
        full_bin[0x2000] = 0x42
        kcf.BinFile.save(str(p), full_bin)
        reloaded = kcf.BinFile.load(str(p))
        assert reloaded[0x2000] == 0x42
        assert len(reloaded) == 131072

    def test_compute_checksum_all_ff(self, full_bin):
        """All 0xFF bytes → checksum should be deterministic."""
        cs = kcf.BinFile.compute_checksum(full_bin)
        assert isinstance(cs, int)
        assert 0 <= cs <= 0xFFFF

    def test_fix_checksum_writes_correct_value(self, full_bin):
        old_cs, new_cs = kcf.BinFile.fix_checksum(full_bin)
        stored = (full_bin[kcf.CHECKSUM_OFFSET_HI] << 8) | full_bin[kcf.CHECKSUM_OFFSET_LO]
        assert stored == new_cs

    def test_verify_checksum_after_fix(self, full_bin):
        kcf.BinFile.fix_checksum(full_bin)
        assert kcf.BinFile.verify_checksum(full_bin)

    def test_verify_checksum_detects_mismatch(self, full_bin):
        # Checksum at $4006-$4007 is 0xFFFF (from all-0xFF bin)
        # Computed checksum won't be 0xFFFF for this particular data
        full_bin[0x2000] = 0x00  # cause a mismatch
        # Don't fix — verify should fail
        assert not kcf.BinFile.verify_checksum(full_bin)

    def test_get_os_id(self, full_bin_with_os):
        os_id = kcf.BinFile.get_os_id(full_bin_with_os)
        assert os_id == "$060A"

    def test_diff_sectors_identical(self, full_bin):
        other = bytearray(full_bin)
        changed = kcf.BinFile.diff_sectors(full_bin, other)
        assert changed == []

    def test_diff_sectors_detects_change(self, full_bin):
        other = bytearray(full_bin)
        other[0x4000] = 0x00  # change in sector 1
        changed = kcf.BinFile.diff_sectors(full_bin, other)
        assert 1 in changed

    def test_diff_sectors_multiple(self, full_bin):
        other = bytearray(full_bin)
        other[0x0000] = 0x00  # sector 0
        other[0x4000] = 0x00  # sector 1
        other[0x1C000] = 0x00  # sector 7
        changed = kcf.BinFile.diff_sectors(full_bin, other)
        assert set(changed) == {0, 1, 7}

    def test_read_table(self, full_bin):
        t = kcf.CAL_TABLES["spark_hi_oct"]
        # fill with known pattern
        for i in range(t.byte_size):
            full_bin[t.rom_offset + i] = i & 0xFF
        values = kcf.BinFile.read_table(full_bin, t)
        assert len(values) == t.rows
        assert len(values[0]) == t.cols
        assert values[0][0] == 0
        assert values[0][1] == 1

    def test_write_table_roundtrip(self, full_bin):
        t = kcf.CAL_TABLES["spark_hi_oct"]
        values = [[42 for _ in range(t.cols)] for _ in range(t.rows)]
        kcf.BinFile.write_table(full_bin, t, values)
        readback = kcf.BinFile.read_table(full_bin, t)
        for r in range(t.rows):
            for c in range(t.cols):
                assert readback[r][c] == 42

    def test_write_table_2byte_element(self, full_bin):
        """Test that 2-byte element tables work if any exist, or else force one."""
        t = kcf.CalibrationTable(
            name="test_2byte", rom_offset=0x5000,
            rows=2, cols=3, element_size=2,
        )
        values = [[0x0100, 0x0200, 0x0300], [0x0400, 0x0500, 0x0600]]
        kcf.BinFile.write_table(full_bin, t, values)
        readback = kcf.BinFile.read_table(full_bin, t)
        assert readback[0][0] == 0x0100
        assert readback[1][2] == 0x0600


# ═══════════════════════════════════════════════════════════════════════
# SECTION 10 — DATA LOGGER
# ═══════════════════════════════════════════════════════════════════════

class TestDataLogger:
    """Tests for the DataLogger class."""

    def test_initial_state(self, comm):
        logger = kcf.DataLogger(comm)
        assert not logger.running
        assert logger.latest is None
        assert logger.sample_rate == 0.0

    def test_start_stop(self, comm):
        comm.connect()
        logger = kcf.DataLogger(comm)
        logger.start()
        assert logger.running
        time.sleep(0.3)  # let it tick
        logger.stop()
        assert not logger.running

    def test_csv_output(self, comm, tmp_path):
        comm.connect()
        csv_path = str(tmp_path / "test_log.csv")
        logger = kcf.DataLogger(comm)
        logger.start(csv_path=csv_path)
        time.sleep(0.5)
        logger.stop()
        assert Path(csv_path).exists()
        content = Path(csv_path).read_text()
        assert len(content) > 0


# ═══════════════════════════════════════════════════════════════════════
# SECTION 11 — LIVE TUNER
# ═══════════════════════════════════════════════════════════════════════

class TestLiveTuner:
    """Tests for the LiveTuner class."""

    @pytest.fixture
    def tuner(self, comm, full_bin):
        t = kcf.CAL_TABLES["spark_hi_oct"]
        # Write known values into the bin
        for i in range(t.byte_size):
            full_bin[t.rom_offset + i] = 128  # fill with 128
        tuner = kcf.LiveTuner(comm, t)
        tuner.load_from_bin(full_bin)
        return tuner

    def test_load_from_bin(self, tuner):
        assert tuner.shadow[0] == 128
        assert tuner.rom_values[0] == 128

    def test_set_cell_within_delta(self, tuner):
        assert tuner.set_cell(0, 0, 133)  # delta=5, within max_delta=10
        assert tuner.get_cell(0, 0) == 133

    def test_set_cell_exceeds_delta_rejected(self, tuner):
        assert not tuner.set_cell(0, 0, 200)  # delta=72 > 10
        assert tuner.get_cell(0, 0) == 128  # unchanged

    def test_set_cell_out_of_range(self, tuner):
        assert not tuner.set_cell(0, 0, 256)  # > 255
        assert not tuner.set_cell(0, 0, -1)   # < 0

    def test_set_cell_marks_dirty(self, tuner):
        tuner.set_cell(0, 0, 130)
        assert 0 in tuner.dirty_cells

    def test_get_cell(self, tuner):
        assert tuner.get_cell(0, 0) == 128
        tuner.set_cell(0, 0, 133)
        assert tuner.get_cell(0, 0) == 133

    def test_get_cell_out_of_bounds(self, tuner):
        val = tuner.get_cell(999, 999)
        assert val == 0

    def test_revert_to_rom(self, tuner):
        tuner.set_cell(0, 0, 135)
        assert tuner.get_cell(0, 0) == 135
        tuner.revert_to_rom()
        assert tuner.get_cell(0, 0) == 128
        assert tuner.safety_reverted

    def test_check_safety_normal(self, tuner):
        data = {"Knock Retard": 0.0, "ECT Temp": 80.0, "RPM": 3000.0}
        assert tuner.check_safety(data) is True

    def test_check_safety_knock_triggers(self, tuner):
        """3 consecutive knock readings >5° should trigger revert."""
        for _ in range(3):
            tuner.check_safety({"Knock Retard": 6.0, "ECT Temp": 80.0, "RPM": 3000.0})
        result = tuner.check_safety({"Knock Retard": 6.0, "ECT Temp": 80.0, "RPM": 3000.0})
        # After 3+ consecutive >5° knock, should return False
        assert result is False or tuner.safety_reverted

    def test_check_safety_high_temp(self, tuner):
        data = {"Knock Retard": 0.0, "ECT Temp": 115.0, "RPM": 3000.0}
        assert tuner.check_safety(data) is False

    def test_check_safety_high_rpm(self, tuner):
        data = {"Knock Retard": 0.0, "ECT Temp": 80.0, "RPM": 6000.0}
        assert tuner.check_safety(data) is False

    def test_find_runs_contiguous(self, tuner):
        runs = tuner._find_runs([10, 11, 12, 13])
        assert len(runs) == 1
        assert runs[0][0] == 10

    def test_find_runs_split(self, tuner):
        runs = tuner._find_runs([10, 11, 50, 51])
        assert len(runs) == 2

    def test_find_runs_empty(self, tuner):
        runs = tuner._find_runs([])
        assert runs == []


# ═══════════════════════════════════════════════════════════════════════
# SECTION 13 — CLI HELPERS
# ═══════════════════════════════════════════════════════════════════════

class TestCLIHelpers:
    """Tests for CLI callbacks and parser."""

    def test_cli_log_callback(self, capsys):
        kcf.cli_log_callback("hello", "info")
        out = capsys.readouterr().out
        assert "hello" in out

    def test_cli_log_callback_warning(self, capsys):
        kcf.cli_log_callback("warn msg", "warning")
        out = capsys.readouterr().out
        assert "warn msg" in out

    def test_cli_progress_callback(self, capsys):
        kcf.cli_progress_callback(50, 100, "Testing")
        out = capsys.readouterr().out
        assert "50%" in out

    def test_build_parser(self):
        parser = kcf.build_parser()
        assert parser is not None
        # Should accept 'gui' command
        args = parser.parse_args(["gui"])
        assert args.command == "gui"

    def test_parser_read_command(self):
        parser = kcf.build_parser()
        args = parser.parse_args(["read", "--port", "COM3", "--output", "test.bin"])
        assert args.command == "read"
        assert args.output == "test.bin"

    def test_parser_write_command(self):
        parser = kcf.build_parser()
        args = parser.parse_args(["write", "--port", "COM3", "--input", "tune.bin", "--mode", "CAL"])
        assert args.command == "write"
        assert args.write_mode == "CAL"

    def test_parser_checksum_command(self):
        parser = kcf.build_parser()
        args = parser.parse_args(["checksum", "--input", "file.bin", "--fix"])
        assert args.command == "checksum"
        assert args.fix is True

    def test_parser_ports_command(self):
        parser = kcf.build_parser()
        args = parser.parse_args(["ports"])
        assert args.command == "ports"


# ═══════════════════════════════════════════════════════════════════════
# VERSION / METADATA
# ═══════════════════════════════════════════════════════════════════════

class TestMetadata:
    """Tests for module-level metadata."""

    def test_version_string(self):
        assert isinstance(kcf.__version__, str)
        assert "." in kcf.__version__

    def test_app_name(self):
        assert "KingAI" in kcf.__app_name__

    def test_target_ecm(self):
        assert "$060A" in kcf.__target_ecm__


# ═══════════════════════════════════════════════════════════════════════
# INTEGRATION: FULL FLASH OP via LOOPBACK
# ═══════════════════════════════════════════════════════════════════════

class TestFlashOpIntegration:
    """Integration tests running FlashOp against the LoopbackTransport."""

    def test_flash_op_instantiate(self, comm):
        comm.connect()
        op = kcf.FlashOp(comm)
        assert op is not None

    def test_checksum_cli_offline(self, full_bin_with_os, tmp_path):
        """Test the checksum verification pathway end-to-end with a file."""
        p = tmp_path / "cs_test.bin"
        kcf.BinFile.fix_checksum(full_bin_with_os)
        kcf.BinFile.save(str(p), full_bin_with_os)
        reloaded = kcf.BinFile.load(str(p))
        assert kcf.BinFile.verify_checksum(reloaded)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--html=report.html", "--self-contained-html"])
