"""Offline disk preservation and response-origin regressions; no ports are opened."""
from unittest.mock import MagicMock
import json

import pytest
import kingai_commie_flasher as kcf
from virtual_128kb_eeprom import AMD29F010


def test_image_save_cannot_replace_original_or_publish_partial(tmp_path):
    path = tmp_path / "original evidence.bin"
    original = bytes(range(256)) * 512
    path.write_bytes(original)
    with pytest.raises(FileExistsError):
        kcf.BinFile.save(path, bytearray(kcf.BinFile.BIN_SIZE))
    assert path.read_bytes() == original
    output = tmp_path / "partial.bin"
    with pytest.raises(ValueError, match="exactly"):
        kcf.BinFile.save(output, bytearray(63))
    assert not output.exists()


def test_cal_export_requires_complete_source_and_preserves_destination(tmp_path):
    path = tmp_path / "cal evidence.cal"
    path.write_bytes(b"original")
    with pytest.raises(FileExistsError):
        kcf.BinFile.save_cal(path, bytearray(kcf.BinFile.BIN_SIZE), padded=False)
    with pytest.raises(ValueError, match="exactly"):
        kcf.BinFile.save_cal(tmp_path / "invalid.cal", bytearray(63))
    assert path.read_bytes() == b"original"
    assert not (tmp_path / "invalid.cal").exists()


@pytest.mark.parametrize("size", [0, 1, 63, 131071, 131073])
def test_explicit_bad_virtual_image_never_silently_becomes_zeros(tmp_path, size):
    path = tmp_path / "malformed image.bin"
    path.write_bytes(b"x" * size)
    with pytest.raises(ValueError):
        kcf.LoopbackTransport(str(path))
    assert path.read_bytes() == b"x" * size


def test_explicit_missing_virtual_image_fails(tmp_path):
    with pytest.raises(FileNotFoundError):
        kcf.LoopbackTransport(str(tmp_path / "missing.bin"))


def test_virtual_flash_export_does_not_replace_input(tmp_path):
    path = tmp_path / "flash original.bin"
    data = bytes(range(256)) * 512
    path.write_bytes(data)
    flash = AMD29F010()
    flash.load_from_file(str(path))
    flash.erase_sector_by_index(1)  # in-memory simulator only
    with pytest.raises(FileExistsError):
        flash.save_to_file(str(path))
    assert path.read_bytes() == data


def test_datalog_never_truncates_existing_log(tmp_path):
    path = tmp_path / "account independent evidence.csv"
    path.write_text("original\n")
    logger = kcf.DataLogger(MagicMock())
    with pytest.raises(FileExistsError):
        logger.start(str(path))
    assert path.read_text() == "original\n"
    assert not logger.running


@pytest.mark.parametrize("device,mode", [(0x08, 2), (0xF7, 1), (0xF7, 6)])
def test_mode2_cannot_accept_unrelated_frame(device, mode):
    comm = kcf.ECUComm(MagicMock())
    comm._transact = MagicMock(return_value=kcf.ALDLProtocol.build_simple_frame(device, mode, bytes(64)))
    assert comm.read_ram(0, extended=True) is None


def test_mode2_accepts_exact_target_payload():
    comm = kcf.ECUComm(MagicMock())
    raw = bytes(range(64))
    comm._transact = MagicMock(return_value=kcf.ALDLProtocol.build_simple_frame(0xF7, 2, raw))
    assert comm.read_ram(0, extended=True) == raw


@pytest.mark.parametrize("device,mode,payload", [(0x08, 6, b"\x01\x20"),
    (0xF7, 2, b"\x01\x20"), (0xF7, 6, b"\x01")])
def test_chip_identity_requires_target_mode_and_two_declared_bytes(device, mode, payload):
    comm = kcf.ECUComm(MagicMock())
    comm._transact = MagicMock(return_value=kcf.ALDLProtocol.build_simple_frame(device, mode, payload))
    assert comm.read_flash_info() is None


def test_overlong_transport_body_is_rejected_without_buffer_overrun():
    transport = MagicMock()
    transport.read.side_effect = [b"\xf7", b"\x56", b"\x08" + bytes(300)]
    assert kcf.ECUComm(transport)._rx_frame() is None


def test_incomplete_evidence_export_preserves_prefix_and_every_response_without_padding(tmp_path):
    op = kcf.FlashOp(MagicMock())
    op._partial_read = bytearray(b"\x01\x00\xff")
    op._stats = {"complete": False, "missing_ranges": [[3, 128]]}
    op._read_evidence = [{"address": 0, "data": b"\x01\x00\xff", "accepted": False},
                         {"address": 0, "data": b"", "accepted": False},
                         {"address": 0, "data": None, "accepted": False}]
    directory = tmp_path / "capture with spaces.incomplete"
    assert op.save_read_evidence(directory) == directory
    assert (directory / "accepted-prefix.partial").read_bytes() == b"\x01\x00\xff"

    assert (directory / "response-00000.capture").read_bytes() == b"\x01\x00\xff"
    assert (directory / "response-00001.capture").read_bytes() == b""
    manifest = json.loads((directory / "manifest.json").read_text())
    assert manifest["recovery_qualified"] is False
    assert manifest["prefix"]["size"] == 3
    assert manifest["stats"]["missing_ranges"] == [[3, 128]]
    assert "file" not in manifest["responses"][2]
    with pytest.raises(FileExistsError):
        op.save_read_evidence(directory)
    assert (directory / "accepted-prefix.partial").read_bytes() == b"\x01\x00\xff"


@pytest.mark.parametrize("response", [None, bytes(201),
    kcf.ALDLProtocol.build_simple_frame(0xF7, 2, b"\xbb"),
    kcf.ALDLProtocol.build_simple_frame(0xF7, 6, b"\xaa")])
def test_cleanup_cannot_claim_reset_without_exact_ack(response, monkeypatch):
    monkeypatch.setattr(kcf.time, "sleep", lambda _: None)
    comm = kcf.ECUComm(MagicMock())
    comm._transact = MagicMock(return_value=response)
    assert comm.cleanup_and_reset() is False


def test_short_padded_security_seed_cannot_appear_already_unlocked():
    comm = kcf.ECUComm(MagicMock())
    comm._transact = MagicMock(return_value=kcf.ALDLProtocol.build_simple_frame(0xF7, 13, b"\x01"))
    assert comm.unlock_security() is False
    assert comm.state != kcf.CommState.UNLOCKED


@pytest.mark.parametrize("bad", [0, -1, True, "32", None, 129])
def test_invalid_write_chunk_is_rejected_before_any_transaction(bad):
    comm = kcf.ECUComm(MagicMock())
    comm.config.write_chunk_size = bad
    comm._transact = MagicMock()
    assert comm.write_flash_data(bytes(kcf.BinFile.BIN_SIZE), 0x4000, 0x7FFF) is False
    comm._transact.assert_not_called()


def test_invalid_settings_fall_back_without_changing_original_bytes(tmp_path):
    path = tmp_path / "invalid settings.json"
    raw = b'{"comm":{"baud":9600,"write_chunk_size":0,"__dict__":{"bad":1}}}'
    path.write_bytes(raw)
    config, logging = kcf.SettingsManager.load(path)
    assert config.baud == kcf.DEFAULT_BAUD
    assert config.write_chunk_size == kcf.DEFAULT_WRITE_CHUNK_SIZE
    assert path.read_bytes() == raw


def test_live_tuning_unknown_transport_is_held_without_transacting():
    comm = kcf.ECUComm(MagicMock())
    comm._transact = MagicMock()
    tuner = kcf.LiveTuner(comm, kcf.CAL_TABLES["spark_hi_oct"])
    tuner.dirty_cells.add(0)
    assert tuner.send_updates() is False
    assert tuner.dirty_cells == {0}
    comm._transact.assert_not_called()


def test_logger_failure_clears_running_and_closes_file(tmp_path):
    comm = MagicMock()
    comm.cancelled = False
    comm.request_mode1.side_effect = OSError("synthetic read failure")
    logger = kcf.DataLogger(comm)
    logger._csv_file = (tmp_path / "log.csv").open("x")
    stream = logger._csv_file
    logger.running = True
    logger._log_loop()
    assert not logger.running
    assert stream.closed
    assert logger._csv_file is None
