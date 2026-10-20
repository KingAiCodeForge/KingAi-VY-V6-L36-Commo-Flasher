"""Synthetic release-gate tests: no serial, hardware, or flash erase calls.

These tests exercise FlashOp with a mocked communication backend. Passing them
does not qualify a physical read/write, checksum algorithm, or recovery path.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import kingai_commie_flasher as kcf


def fake_comm(*, chip=kcf.FLASH_AMD_29F010):
    comm = MagicMock(spec=kcf.ECUComm)
    comm.config = kcf.CommConfig()
    comm.config.auto_checksum_fix = False
    comm.config.high_speed_read = False
    comm.cancelled = False
    comm.transport = MagicMock()
    comm.disable_chatter.return_value = True
    comm.unlock_security.return_value = True
    comm.enter_programming.return_value = True
    comm.upload_kernel.return_value = True
    comm.read_flash_info.return_value = chip
    comm.read_ram.return_value = b"\x5a" * 64
    comm.cleanup_and_reset.return_value = True
    comm.enable_chatter.return_value = True
    comm.erase_sectors.return_value = False  # prevent advancing into write stage
    return comm


def checksum_valid_dummy_bin():
    data = bytearray(b"\xff" * kcf.BinFile.BIN_SIZE)
    kcf.BinFile.fix_checksum(data)
    assert kcf.BinFile.verify_checksum(data)
    return data


@pytest.mark.parametrize("response", [None, b"", b"\x5a" * 63, b"\x5a" * 65])
def test_full_read_rejects_failed_or_wrong_sized_mode2_blocks(
    monkeypatch, response
):
    monkeypatch.setattr(kcf.time, "sleep", lambda _secs: None)
    comm = fake_comm()
    comm.read_ram.return_value = response
    op = kcf.FlashOp(comm)
    result = op.full_read()
    assert result is None, "A gap/shift must never become a plausible full BIN"
    assert comm.read_ram.call_count == kcf.READ_BLOCK_MAX_RETRIES
    comm.cleanup_and_reset.assert_called_once()
    comm.enable_chatter.assert_called_once()


def test_full_read_accepts_full_sized_64_byte_mock_blocks():
    comm = fake_comm()
    op = kcf.FlashOp(comm)
    output = op.full_read()
    assert output == bytearray(b"\x5a" * kcf.BinFile.BIN_SIZE)
    assert comm.read_ram.call_count == kcf.BinFile.BIN_SIZE // 64
    assert op._stats["failed_frames"] == 0
    comm.cleanup_and_reset.assert_called_once()


@pytest.mark.parametrize(
    "chip",
    [None, (0x01, 0xA4), (0x31, 0xB4), (0x00, 0x00)],
)
def test_unknown_or_different_flash_chip_refuses_write_before_backup(chip):
    comm = fake_comm(chip=chip)
    op = kcf.FlashOp(comm)
    assert op.full_write(checksum_valid_dummy_bin(), mode="CAL") is False
    comm.read_ram.assert_not_called()
    comm.erase_sectors.assert_not_called()
    comm.write_flash_data.assert_not_called()
    comm.cleanup_and_reset.assert_called_once()
    comm.enable_chatter.assert_called_once()


@pytest.mark.parametrize("chunk", [None, b"", b"\x5a" * 63, b"\x5a" * 65])
def test_partial_preerase_backup_refuses_erase(chunk):
    comm = fake_comm()
    comm.read_ram.return_value = chunk
    op = kcf.FlashOp(comm)
    assert op.full_write(checksum_valid_dummy_bin(), mode="CAL") is False
    assert op._backup_bin is None
    comm.erase_sectors.assert_not_called()
    comm.write_flash_data.assert_not_called()
    comm.cleanup_and_reset.assert_called_once()


def test_cancelled_preerase_backup_refuses_erase():
    comm = fake_comm()
    comm.cancelled = True
    op = kcf.FlashOp(comm)
    assert op.full_write(checksum_valid_dummy_bin(), mode="CAL") is False
    comm.erase_sectors.assert_not_called()
    comm.read_ram.assert_not_called()
    assert op._backup_bin is None


def test_complete_preerase_backup_advances_only_to_mock_erase():
    comm = fake_comm()
    op = kcf.FlashOp(comm)
    assert op.full_write(checksum_valid_dummy_bin(), mode="CAL") is False
    comm.erase_sectors.assert_called_once()
    comm.write_flash_data.assert_not_called()
    assert op._backup_bin is not None
    assert op._backup_bin[0x4000:0x8000] == b"\x5a" * 0x4000
