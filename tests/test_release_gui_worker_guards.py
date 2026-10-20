"""Offline GUI worker regressions for cancellation and full-image admission."""
from unittest.mock import Mock

import pytest
import kingai_commie_flasher as f

pytestmark = pytest.mark.skipif(not f.GUI_AVAILABLE, reason='PySide6 unavailable')


@pytest.fixture
def app():
    instance = f.QApplication.instance() or f.QApplication([])
    yield instance


def test_worker_preserves_cancel_requested_after_setup(app):
    comm = f.ECUComm(f.LoopbackTransport())
    worker = f.FlashWorker(comm)
    worker.setup_read()
    comm.disable_chatter = Mock(return_value=True)
    comm.read_ram = Mock(return_value=bytes(64))
    outcomes = []
    worker.finished.connect(outcomes.append)
    comm.cancel()  # Scheduled work must not discard this new cancellation.
    worker.run()
    assert outcomes == [False]
    comm.disable_chatter.assert_not_called()
    comm.read_ram.assert_not_called()
    assert comm.cancelled is True


def test_short_read_cannot_replace_main_window_complete_image(app, monkeypatch):
    monkeypatch.setattr(f.MainWindow, '_refresh_ports', lambda self: None)
    monkeypatch.setattr(f.SettingsManager, 'load', lambda: (f.CommConfig(), f.LogConfig()))
    window = f.MainWindow()
    window._persist_on_close = False
    original = bytearray([0xA5]) * f.BinFile.BIN_SIZE
    window._bin_data = original
    window._bin_path = 'original source.bin'
    try:
        window._on_read_data(bytearray([0x42]) * 69)
        assert window._bin_data is original
        assert window._bin_path == 'original source.bin'
    finally:
        window.close()
        window.deleteLater()


def test_custom_range_does_not_emit_full_image_signal(app):
    comm = f.ECUComm(f.LoopbackTransport())
    worker = f.FlashWorker(comm)
    worker.setup_custom_read(0x4000, 0x4006)
    worker._op.custom_read = Mock(return_value=bytearray(b'capture'))
    full_images = []
    outcomes = []
    worker.read_data.connect(full_images.append)
    worker.finished.connect(outcomes.append)
    worker.run()
    assert full_images == []
    assert outcomes == [True]


def test_chaos_cancel_before_any_cycle_cannot_report_success(app):
    comm = f.ECUComm(f.LoopbackTransport())
    worker = f.FlashWorker(comm)
    worker.setup_chaos({'cycles': 1, 'mode': 'CAL', 'delay': 0,
                        'stop_on_fail': True, 'compare_bytes': True},
                       bytearray(f.BinFile.BIN_SIZE))
    worker._op.full_write = Mock(return_value=True)
    comm.cancel()
    assert worker._run_chaos() is False
    worker._op.full_write.assert_not_called()
