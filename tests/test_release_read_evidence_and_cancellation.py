"""Synthetic qualification for exact reads, cancellation and evidence preservation."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import kingai_commie_flasher as f


def comm():
    c = Mock()
    c.cancelled = False
    c.config = f.CommConfig()
    c.config.auto_checksum_fix = False
    c.transport = Mock()
    for name in ("disable_chatter", "unlock_security", "enter_programming", "upload_kernel",
                 "cleanup_and_reset", "enable_chatter"):
        getattr(c, name).return_value = True
    c.read_flash_info.return_value = f.FLASH_AMD_29F010
    c.read_ram.return_value = bytes(range(64))
    c.erase_sectors.return_value = False
    return c


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(f.time, "sleep", lambda _: None)


@pytest.mark.parametrize("operation", ["FULL", "CUSTOM"])
@pytest.mark.parametrize("point", ["last_read", "last_progress", "cleanup", "restore"])
def test_final_cancellation_never_returns_a_complete_read(monkeypatch, operation, point):
    monkeypatch.setattr(f.BinFile, "BIN_SIZE", 128)
    c = comm()
    if point == "last_read":
        def read(address, **kwargs):
            if address == 64:
                c.cancelled = True
            return bytes(range(64))
        c.read_ram.side_effect = read
    elif point == "last_progress":
        def emit(event, **kwargs):
            if event == "progress" and kwargs.get("current") == 2:
                c.cancelled = True
        c.emit.side_effect = emit
    else:
        def cancel():
            c.cancelled = True
            return True
        getattr(c, "cleanup_and_reset" if point == "cleanup" else "enable_chatter").side_effect = cancel
    op = f.FlashOp(c)
    result = op.full_read() if operation == "FULL" else op.custom_read(0, 127)
    assert result is None
    assert op._stats["status"] == "CANCELLED"
    assert op._stats["complete"] is False
    assert op._partial_read == bytes(range(64)) * 2
    assert op._stats["missing_ranges"] == []
    c.cleanup_and_reset.assert_called_once()
    c.enable_chatter.assert_called_once()


@pytest.mark.parametrize("invalid", [None, b"", bytes(63), bytes(65), [1] * 64])
def test_custom_read_rejects_wrong_wire_size_and_preserves_raw_evidence(invalid):
    c = comm()
    c.read_ram.side_effect = [b"A" * 64] + [invalid] * f.READ_BLOCK_MAX_RETRIES
    op = f.FlashOp(c)
    assert op.custom_read(0x2000, 0x207F) is None
    assert op._partial_read == b"A" * 64
    assert op._stats["missing_ranges"] == [[0x2040, 0x2080]]
    assert [x.args[0] for x in c.read_ram.call_args_list] == [0x2000] + [0x2040] * f.READ_BLOCK_MAX_RETRIES
    assert op._read_evidence[-1]["accepted"] is False
    assert op._read_evidence[-1]["data"] == (invalid if isinstance(invalid, bytes) else None)


def test_custom_tail_validates_the_fixed_wire_frame_then_slices_requested_bytes():
    c = comm()
    op = f.FlashOp(c)
    assert op.custom_read(0x2000, 0x2044) == bytes(range(64)) + bytes(range(5))
    assert c.read_ram.call_args_list[-1].kwargs["count"] == 64
    assert op._read_evidence[-1]["data"] == bytes(range(64))
    assert op._read_evidence[-1]["requested"] == 5
    assert op._read_evidence[-1]["wire_expected"] == 64


@pytest.mark.parametrize("range_", [(-1, 8), (9, 8), (0, 0x20000), (True, 5), ("0", 5)])
def test_invalid_custom_range_has_no_session_or_allocation(range_):
    c = comm()
    assert f.FlashOp(c).custom_read(*range_) is None
    c.disable_chatter.assert_not_called()
    c.read_ram.assert_not_called()


def write(op):
    return op.full_write(bytearray(f.BinFile.BIN_SIZE), "CAL")


@pytest.fixture
def checksum_ok(monkeypatch):
    monkeypatch.setattr(f.BinFile, "verify_checksum", lambda _: True)


@pytest.mark.parametrize("step", ["disable_chatter", "unlock_security", "enter_programming", "upload_kernel",
                                  "read_flash_info", "read_ram"])
def test_preerase_exception_clears_stale_backup_and_never_erases(step, checksum_ok):
    c = comm()
    getattr(c, step).side_effect = OSError("synthetic failure")
    op = f.FlashOp(c)
    op._backup_bin = b"stale"
    assert write(op) is False
    assert op._backup_bin is None
    c.erase_sectors.assert_not_called()
    c.write_flash_data.assert_not_called()
    c.enable_chatter.assert_called_once()


@pytest.mark.parametrize("step", ["disable_chatter", "unlock_security", "enter_programming", "upload_kernel", "read_flash_info"])
def test_setup_cancellation_stops_before_next_stage(step, checksum_ok):
    c = comm()
    value = f.FLASH_AMD_29F010 if step == "read_flash_info" else True
    def cancel():
        c.cancelled = True
        return value
    getattr(c, step).side_effect = cancel
    op = f.FlashOp(c)
    assert write(op) is False
    c.erase_sectors.assert_not_called()
    c.read_ram.assert_not_called()
    assert op._backup_bin is None


def test_sparse_backup_contains_captured_bytes_only(checksum_ok):
    c = comm()
    op = f.FlashOp(c)
    assert write(op) is False
    assert len(op._backup_bin) == 0x4000
    assert op._backup_bin[0x4000:0x8000] == bytes(range(64)) * 256
    with pytest.raises(ValueError, match="uncaptured"):
        op._backup_bin[0:0x8000]
    assert len(op._backup_evidence) == 256


def test_incomplete_backup_retains_actual_short_frame_evidence(checksum_ok):
    c = comm()
    c.read_ram.side_effect = [b"A" * 64] + [b"B" * 3] * f.READ_BLOCK_MAX_RETRIES
    op = f.FlashOp(c)
    assert write(op) is False
    assert op._backup_bin is None
    assert op._backup_evidence[0]["data"] == b"A" * 64
    assert op._backup_evidence[-1]["data"] == b"B" * 3
    assert op._stats["backup_bytes_captured"] == 64
    c.erase_sectors.assert_not_called()


def test_auto_checksum_fix_does_not_mutate_original_input(monkeypatch):
    c = comm()
    c.config.auto_checksum_fix = True
    monkeypatch.setattr(f.BinFile, "verify_checksum", lambda _: False)
    def fix(image):
        image[0] = 42
        return 0, 42
    monkeypatch.setattr(f.BinFile, "fix_checksum", fix)
    image = bytearray(f.BinFile.BIN_SIZE)
    op = f.FlashOp(c)
    assert op.full_write(image, "CAL") is False
    assert image[0] == 0


def test_physical_transport_hold_performs_no_communications(checksum_ok):
    c = comm()
    c.transport = f.PySerialTransport("UNUSED")
    op = f.FlashOp(c)
    assert write(op) is False
    assert op.custom_write(bytearray(f.BinFile.BIN_SIZE), [1]) is False
    c.disable_chatter.assert_not_called()
    c.erase_sectors.assert_not_called()
    c.read_ram.assert_not_called()


def test_cleanup_exception_does_not_skip_bus_restoration(checksum_ok):
    c = comm()
    c.read_ram.return_value = None
    c.cleanup_and_reset.side_effect = OSError("cleanup failed")
    op = f.FlashOp(c)
    assert write(op) is False
    c.enable_chatter.assert_called_once()
    c.erase_sectors.assert_not_called()
