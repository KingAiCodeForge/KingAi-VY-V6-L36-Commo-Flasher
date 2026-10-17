"""Additional fail-closed regressions atop PR #3, using mock comms only.

No serial devices, kernel writes, sector erases, ECU hardware or networks.
"""
from unittest.mock import MagicMock

import pytest

import kingai_commie_flasher as kcf


def comm_fixture():
    c = MagicMock()
    c.config.auto_checksum_fix = False
    c.config.high_speed_read = False
    c.config.baud = 8192
    c.disable_chatter.return_value = True
    c.unlock_security.return_value = True
    c.enter_programming.return_value = True
    c.upload_kernel.return_value = True
    c.read_flash_info.return_value = kcf.FLASH_AMD_29F010
    c.read_ram.return_value = bytes([0x5A]) * 64
    c.cancelled = False
    c.erase_sectors.return_value = False
    return c


def run_mock_cal_write(monkeypatch, comm):
    monkeypatch.setattr(kcf.BinFile, "verify_checksum", lambda image: True)
    result = kcf.FlashOp(comm).full_write(
        bytearray(kcf.BinFile.BIN_SIZE), mode="CAL"
    )
    assert result is False
    return result


def test_cancel_before_first_backup_read_prevents_erase(monkeypatch):
    comm = comm_fixture()
    comm.cancelled = True
    run_mock_cal_write(monkeypatch, comm)
    comm.read_ram.assert_not_called()
    comm.erase_sectors.assert_not_called()
    comm.write_flash_data.assert_not_called()
    comm.cleanup_and_reset.assert_called_once()


def test_cancel_during_backup_prevents_erase(monkeypatch):
    comm = comm_fixture()

    def read_and_cancel(address, extended=True):
        if comm.read_ram.call_count == 2:
            comm.cancelled = True
        return bytes([0x5A]) * 64

    comm.read_ram.side_effect = read_and_cancel
    run_mock_cal_write(monkeypatch, comm)
    assert comm.read_ram.call_count == 2
    comm.erase_sectors.assert_not_called()
    comm.write_flash_data.assert_not_called()


def test_cancel_after_last_backup_block_prevents_erase(monkeypatch):
    comm = comm_fixture()

    def read_and_cancel(address, extended=True):
        if address == 0x7FC0:
            comm.cancelled = True
        return bytes([0x5A]) * 64

    comm.read_ram.side_effect = read_and_cancel
    run_mock_cal_write(monkeypatch, comm)
    assert comm.read_ram.call_count == 0x4000 // 64
    comm.erase_sectors.assert_not_called()
    comm.write_flash_data.assert_not_called()


@pytest.mark.parametrize("length", [0, 63, 65])
def test_bad_size_preerase_read_cannot_be_treated_as_backup(monkeypatch, length):
    comm = comm_fixture()
    comm.read_ram.return_value = bytes([0x5A]) * length
    run_mock_cal_write(monkeypatch, comm)
    comm.erase_sectors.assert_not_called()
    comm.write_flash_data.assert_not_called()


@pytest.mark.parametrize("length", [63, 65])
def test_short_or_oversized_full_read_returns_no_bin(monkeypatch, length):
    monkeypatch.setattr(kcf.time, "sleep", lambda _seconds: None)
    comm = comm_fixture()
    comm.read_ram.return_value = bytes([0x5A]) * length
    result = kcf.FlashOp(comm).full_read()
    assert result is None
    assert comm.read_ram.call_count == kcf.READ_BLOCK_MAX_RETRIES
    comm.cleanup_and_reset.assert_called_once()
