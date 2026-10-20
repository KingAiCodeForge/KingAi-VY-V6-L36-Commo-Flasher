"""Inert regression tests: no serial transport, ECU or hardware writes."""
from unittest.mock import MagicMock

import pytest

import kingai_commie_flasher as kcf


def fake_comm():
    comm = MagicMock()
    comm.config.auto_checksum_fix = False
    comm.config.ignore_echo = False
    comm.config.baud = 8192
    comm.config.high_speed_read = False
    comm.disable_chatter.return_value = True
    comm.unlock_security.return_value = True
    comm.enter_programming.return_value = True
    comm.upload_kernel.return_value = True
    comm.cleanup_and_reset.return_value = True
    comm.enable_chatter.return_value = True
    comm.read_flash_info.return_value = kcf.FLASH_AMD_29F010
    comm.read_ram.return_value = bytes([0xA5]) * 64
    comm.cancelled = False
    return comm


@pytest.mark.parametrize("chip", [None, (0x31, 0xB4), (0x01, 0xA4), (0xFF, 0xFF)])
def test_unqualified_chip_refused_before_erase(chip, monkeypatch):
    monkeypatch.setattr(kcf.BinFile, "verify_checksum", lambda image: True)
    comm = fake_comm()
    comm.read_flash_info.return_value = chip
    assert not kcf.FlashOp(comm).full_write(bytearray(kcf.BinFile.BIN_SIZE), mode="CAL")
    comm.erase_sectors.assert_not_called()
    comm.read_ram.assert_not_called()
    comm.cleanup_and_reset.assert_called_once()
    comm.enable_chatter.assert_called_once()


@pytest.mark.parametrize("block", [None, b"", bytes([0xA5]) * 63])
def test_incomplete_backup_refused_before_erase(block, monkeypatch):
    monkeypatch.setattr(kcf.BinFile, "verify_checksum", lambda image: True)
    comm = fake_comm()
    comm.read_ram.return_value = block
    operation = kcf.FlashOp(comm)
    assert not operation.full_write(bytearray(kcf.BinFile.BIN_SIZE), mode="CAL")
    comm.erase_sectors.assert_not_called()
    assert operation._backup_bin is None
    comm.cleanup_and_reset.assert_called_once()
    comm.enable_chatter.assert_called_once()


@pytest.mark.parametrize("block", [None, bytes([0x5A]) * 63])
def test_incomplete_full_read_never_returns_zero_padded_bin(block):
    comm = fake_comm()
    comm.read_ram.return_value = block
    result = kcf.FlashOp(comm).full_read()
    assert result is None
    assert comm.read_ram.call_count == kcf.READ_BLOCK_MAX_RETRIES
    comm.cleanup_and_reset.assert_called_once()
    comm.enable_chatter.assert_called_once()


def test_complete_mocked_read_remains_exactly_128k():
    comm = fake_comm()
    data = kcf.FlashOp(comm).full_read()
    assert data is not None
    assert len(data) == kcf.BinFile.BIN_SIZE
    assert data == bytes([0xA5]) * kcf.BinFile.BIN_SIZE
    comm.erase_sectors.assert_not_called()


@pytest.mark.parametrize("reply", [None, b"", b"\x01\x02\x03", b"\x01\x02\x03\x04"])
def test_truncated_flash_id_response_is_rejected(reply):
    comm = object.__new__(kcf.ECUComm)
    comm.config = kcf.CommConfig()
    comm.emit = MagicMock()
    comm._transact = MagicMock(return_value=reply)
    assert comm.read_flash_info() is None
