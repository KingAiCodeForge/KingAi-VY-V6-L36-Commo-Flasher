"""Fault-injected reads with fake communication only; no serial or ECU access."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import kingai_commie_flasher as kcf


class FakeComm:
    def __init__(self):
        self.cancelled = False
        self.config = SimpleNamespace(baud=8192, high_speed_read=False)
        self.transport = SimpleNamespace(flush_input=Mock())
        self.emit = Mock()
        self.disable_chatter = Mock(return_value=True)
        self.unlock_security = Mock(return_value=True)
        self.enter_programming = Mock(return_value=True)
        self.upload_kernel = Mock(return_value=True)
        self.read_flash_info = Mock(return_value=(1, 0x20))
        self.cleanup_and_reset = Mock(return_value=True)
        self.enable_chatter = Mock(return_value=True)
        self.read_ram = Mock(side_effect=self.good_block)

    @staticmethod
    def good_block(address, count=64, extended=False):
        assert extended
        return bytes((address + index) & 255 for index in range(count))


@pytest.fixture
def scenario(monkeypatch):
    monkeypatch.setattr(kcf.BinFile, "BIN_SIZE", 128)
    monkeypatch.setattr(kcf, "READ_BLOCK_MAX_RETRIES", 3)
    monkeypatch.setattr(kcf.time, "sleep", lambda _: None)
    comm = FakeComm()
    return comm, kcf.FlashOp(comm)


def assert_no_complete_message(comm):
    assert not any("READ COMPLETE" in str(call.kwargs.get("msg", ""))
                   for call in comm.emit.call_args_list)


def test_complete_read_returns_exact_bytes(scenario):
    comm, operation = scenario
    assert operation.full_read() == bytes(range(128))
    assert operation._stats["complete"] is True
    assert operation._stats["bytes_transferred"] == 128
    assert operation._stats["missing_ranges"] == []
    assert comm.read_ram.call_count == 2
    comm.cleanup_and_reset.assert_called_once()
    comm.enable_chatter.assert_called_once()


@pytest.mark.parametrize("bad", [None, b"", bytes(63), bytes(65), [0] * 64])
def test_failed_or_wrong_length_block_cannot_be_a_complete_backup(scenario, bad):
    comm, operation = scenario
    comm.read_ram.side_effect = [bytes(range(64)), bad, bad, bad]
    assert operation.full_read() is None
    assert operation._stats["complete"] is False
    assert operation._stats["status"] == "INCOMPLETE"
    assert operation._stats["bytes_transferred"] == 64
    assert operation._stats["missing_ranges"] == [[64, 128]]
    assert [call.args[0] for call in comm.read_ram.call_args_list] == [0, 64, 64, 64]
    comm.cleanup_and_reset.assert_called_once()
    comm.enable_chatter.assert_called_once()
    assert_no_complete_message(comm)


def test_short_block_retries_at_same_address_and_can_recover(scenario):
    comm, operation = scenario
    comm.read_ram.side_effect = [bytes(5), bytes(range(64)), bytes(range(64, 128))]
    assert operation.full_read() == bytes(range(128))
    assert [call.args[0] for call in comm.read_ram.call_args_list] == [0, 0, 64]
    assert operation._stats["failed_frames"] == 1
    assert operation._stats["successful_frames"] == 2


def test_transport_exception_cannot_return_the_zero_initialized_tail(scenario):
    comm, operation = scenario
    comm.read_ram.side_effect = [bytes(range(64)), OSError("synthetic disconnect")]
    assert operation.full_read() is None
    assert operation._stats["bytes_transferred"] == 64
    assert "synthetic disconnect" in operation._stats["error"]
    comm.cleanup_and_reset.assert_called_once()
    comm.enable_chatter.assert_called_once()
    assert_no_complete_message(comm)


def test_cancel_before_start_performs_no_session_or_read(scenario):
    comm, operation = scenario
    comm.cancelled = True
    assert operation.full_read() is None
    comm.disable_chatter.assert_not_called()
    comm.read_ram.assert_not_called()
    assert operation._stats["status"] == "CANCELLED"
    assert_no_complete_message(comm)


def test_cancel_after_one_block_preserves_missing_range(scenario):
    comm, operation = scenario
    def read(address, count=64, extended=False):
        comm.cancelled = True
        return FakeComm.good_block(address, count, extended)
    comm.read_ram.side_effect = read
    assert operation.full_read() is None
    assert operation._stats["status"] == "CANCELLED"
    assert operation._stats["bytes_transferred"] == 64
    assert operation._stats["missing_ranges"] == [[64, 128]]
    assert_no_complete_message(comm)


@pytest.mark.parametrize("step", ["disable_chatter", "unlock_security", "enter_programming", "upload_kernel"])
def test_failed_setup_never_reads_or_reports_completion(scenario, step):
    comm, operation = scenario
    getattr(comm, step).return_value = False
    assert operation.full_read() is None
    comm.read_ram.assert_not_called()
    assert operation._stats["complete"] is False
    assert operation._stats["bytes_transferred"] == 0
    assert_no_complete_message(comm)


@pytest.mark.parametrize("method", ["cleanup_and_reset", "enable_chatter"])
@pytest.mark.parametrize("failure", [False, OSError("synthetic restoration failure")])
def test_cleanup_failure_is_not_reported_as_success(scenario, method, failure):
    comm, operation = scenario
    if isinstance(failure, Exception):
        getattr(comm, method).side_effect = failure
    else:
        getattr(comm, method).return_value = failure
    assert operation.full_read() is None
    assert operation._stats["data_complete"] is True
    assert operation._stats["complete"] is False
    assert operation._stats["missing_ranges"] == []
    comm.enable_chatter.assert_called_once()
    assert_no_complete_message(comm)
