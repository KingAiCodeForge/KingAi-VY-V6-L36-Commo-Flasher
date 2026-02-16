#!/usr/bin/env python3
"""
test_gui_functions.py — Comprehensive pytest suite for all GUI widgets,
menu actions, toolbar buttons, options tab, and flash checkboxes.
============================================================================

Tests every GUI class and action in kingai_commie_flasher.py Section 12:

  LogWidget          — append_log, level colouring
  SensorGaugeWidget  — value update, clamping
  DashboardWidget    — update_data routing
  TableEditorWidget  — load_table, cell edit, highlight
  DisassemblerWidget — UI build, clear
  OptionsWidget      — load/apply/reset, scrollbar
  FlashWorker        — setup_read, setup_write
  MainWindow         — build_ui, menu bar, connect_signals,
                       flash checkbox toggles, state updates,
                       load/save bin, refresh ports, options tab,
                       about dialog, close event

Run:
    cd A:\\kingai_commie_flasher
    pytest tests/test_gui_functions.py -v --html=tests/gui_report.html --self-contained-html
"""

import os
import sys
import time
import tempfile
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# ── Import the module under test ──
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import kingai_commie_flasher as kcf

# ── Conditional skip if PySide6 is not installed ──
pytestmark = pytest.mark.skipif(
    not kcf.GUI_AVAILABLE,
    reason="PySide6 not installed — GUI tests skipped",
)

# ── Ensure QApplication exists (one per process) ──
_app = None

def get_app():
    global _app
    if _app is None:
        from PySide6.QtWidgets import QApplication
        _app = QApplication.instance() or QApplication(sys.argv)
    return _app


# ═══════════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="session", autouse=True)
def qapp():
    """Session-scoped QApplication for all GUI tests."""
    return get_app()


@pytest.fixture
def full_bin() -> bytearray:
    """128KB bin filled with 0xFF."""
    data = bytearray(b'\xFF' * 131072)
    data[0x2000] = 0x06
    data[0x2001] = 0x0A
    return data


@pytest.fixture
def main_window():
    """Create a MainWindow instance for testing."""
    from PySide6.QtWidgets import QApplication
    app = get_app()
    win = kcf.MainWindow()
    yield win
    win.close()


@pytest.fixture
def loopback_comm():
    """ECUComm wired to LoopbackTransport."""
    t = kcf.LoopbackTransport()
    t.open()
    config = kcf.CommConfig()
    return kcf.ECUComm(t, config)


# ═══════════════════════════════════════════════════════════════════════
# LOG WIDGET
# ═══════════════════════════════════════════════════════════════════════

class TestLogWidget:
    """Tests for the LogWidget (QTextEdit subclass)."""

    def test_instantiation(self):
        w = kcf.LogWidget()
        assert w is not None

    def test_append_log_info(self):
        w = kcf.LogWidget()
        w.append_log("Test info message", "info")
        text = w.toPlainText()
        assert "Test info message" in text

    def test_append_log_warning(self):
        w = kcf.LogWidget()
        w.append_log("Warning message", "warning")
        text = w.toPlainText()
        assert "Warning message" in text

    def test_append_log_error(self):
        w = kcf.LogWidget()
        w.append_log("Error message", "error")
        text = w.toPlainText()
        assert "Error message" in text

    def test_append_log_success(self):
        w = kcf.LogWidget()
        w.append_log("Success!", "success")
        text = w.toPlainText()
        assert "Success!" in text

    def test_multiple_messages(self):
        w = kcf.LogWidget()
        w.append_log("Line 1", "info")
        w.append_log("Line 2", "warning")
        w.append_log("Line 3", "error")
        text = w.toPlainText()
        assert "Line 1" in text
        assert "Line 2" in text
        assert "Line 3" in text

    def test_widget_is_read_only(self):
        w = kcf.LogWidget()
        assert w.isReadOnly()


# ═══════════════════════════════════════════════════════════════════════
# SENSOR GAUGE WIDGET
# ═══════════════════════════════════════════════════════════════════════

class TestSensorGaugeWidget:
    """Tests for the SensorGaugeWidget."""

    def test_instantiation(self):
        param = kcf.PARAM_BY_NAME["RPM"]
        w = kcf.SensorGaugeWidget(param)
        assert w is not None

    def test_update_value(self):
        param = kcf.PARAM_BY_NAME["RPM"]
        w = kcf.SensorGaugeWidget(param)
        w.update_value(800.0)
        # Should not crash; visual check would require screenshot

    def test_update_value_zero(self):
        param = kcf.PARAM_BY_NAME["ECT Temp"]
        w = kcf.SensorGaugeWidget(param)
        w.update_value(0.0)

    def test_update_value_negative(self):
        param = kcf.PARAM_BY_NAME["ECT Temp"]
        w = kcf.SensorGaugeWidget(param)
        w.update_value(-40.0)  # should not crash


# ═══════════════════════════════════════════════════════════════════════
# DASHBOARD WIDGET
# ═══════════════════════════════════════════════════════════════════════

class TestDashboardWidget:
    """Tests for the DashboardWidget (grid of gauges)."""

    def test_instantiation(self):
        w = kcf.DashboardWidget()
        assert w is not None

    def test_update_data_with_sensor_values(self):
        w = kcf.DashboardWidget()
        data = {"RPM": 800.0, "ECT Temp": 50.0, "Battery V": 14.0}
        w.update_data(data)

    def test_update_data_empty(self):
        w = kcf.DashboardWidget()
        w.update_data({})

    def test_update_data_unknown_param(self):
        w = kcf.DashboardWidget()
        w.update_data({"Unknown Param XYZ": 42.0})


# ═══════════════════════════════════════════════════════════════════════
# TABLE EDITOR WIDGET
# ═══════════════════════════════════════════════════════════════════════

class TestTableEditorWidget:
    """Tests for the TableEditorWidget."""

    def test_instantiation(self):
        w = kcf.TableEditorWidget()
        assert w is not None

    def test_load_table(self, full_bin):
        w = kcf.TableEditorWidget()
        w.load_table("spark_hi_oct", full_bin)
        t = kcf.CAL_TABLES["spark_hi_oct"]
        assert w.grid.rowCount() == t.rows
        assert w.grid.columnCount() == t.cols

    def test_load_table_different(self, full_bin):
        w = kcf.TableEditorWidget()
        w.load_table("spark_lo_oct", full_bin)
        t = kcf.CAL_TABLES["spark_lo_oct"]
        assert w.grid.rowCount() == t.rows

    def test_highlight_cell(self, full_bin):
        w = kcf.TableEditorWidget()
        w.load_table("spark_hi_oct", full_bin)
        w.highlight_cell(0, 0)
        # Should not crash

    def test_highlight_out_of_bounds(self, full_bin):
        w = kcf.TableEditorWidget()
        w.load_table("spark_hi_oct", full_bin)
        w.highlight_cell(999, 999)  # should handle gracefully


# ═══════════════════════════════════════════════════════════════════════
# DISASSEMBLER WIDGET
# ═══════════════════════════════════════════════════════════════════════

class TestDisassemblerWidget:
    """Tests for the DisassemblerWidget."""

    def test_instantiation(self):
        w = kcf.DisassemblerWidget()
        assert w is not None

    def test_clear(self):
        w = kcf.DisassemblerWidget()
        w._on_clear()
        assert w.asm_output.toPlainText() == ""

    def test_has_hex_input(self):
        w = kcf.DisassemblerWidget()
        assert hasattr(w, 'hex_input')

    def test_has_disassemble_button(self):
        w = kcf.DisassemblerWidget()
        assert hasattr(w, 'btn_disasm')


# ═══════════════════════════════════════════════════════════════════════
# OPTIONS WIDGET (NEW)
# ═══════════════════════════════════════════════════════════════════════

class TestOptionsWidget:
    """Tests for the scrollable OptionsWidget tab."""

    def test_instantiation(self):
        config = kcf.CommConfig()
        w = kcf.OptionsWidget(config)
        assert w is not None

    def test_loads_default_values(self):
        config = kcf.CommConfig()
        w = kcf.OptionsWidget(config)
        assert w.spin_baud.value() == kcf.DEFAULT_BAUD
        assert w.spin_timeout.value() == kcf.DEFAULT_TIMEOUT_MS
        assert w.spin_retries.value() == kcf.DEFAULT_MAX_RETRIES
        assert w.spin_chunk.value() == kcf.DEFAULT_WRITE_CHUNK_SIZE
        assert w.chk_ignore_echo.isChecked() is True
        assert w.chk_auto_checksum.isChecked() is True

    def test_apply_to_config(self):
        config = kcf.CommConfig()
        w = kcf.OptionsWidget(config)
        w.spin_baud.setValue(9600)
        w.spin_timeout.setValue(5000)
        w.spin_retries.setValue(20)
        w.spin_chunk.setValue(64)
        w.chk_high_speed.setChecked(True)
        w.chk_ignore_echo.setChecked(False)
        w.apply_to_config(config)

        assert config.baud == 9600
        assert config.timeout_ms == 5000
        assert config.max_retries == 20
        assert config.write_chunk_size == 64
        assert config.high_speed_read is True
        assert config.ignore_echo is False

    def test_reset_to_defaults(self):
        config = kcf.CommConfig()
        w = kcf.OptionsWidget(config)
        # Change some values
        w.spin_baud.setValue(115200)
        w.spin_retries.setValue(99)
        # Reset
        w._on_reset()
        assert w.spin_baud.value() == kcf.DEFAULT_BAUD
        assert w.spin_retries.value() == kcf.DEFAULT_MAX_RETRIES

    def test_device_id_combo_items(self):
        config = kcf.CommConfig()
        w = kcf.OptionsWidget(config)
        ids = [w.combo_device_id.itemData(i) for i in range(w.combo_device_id.count())]
        assert 0xF7 in ids
        assert 0xF5 in ids
        assert 0xF4 in ids

    def test_has_scroll_area(self):
        """Options tab must contain a QScrollArea."""
        from PySide6.QtWidgets import QScrollArea
        config = kcf.CommConfig()
        w = kcf.OptionsWidget(config)
        scrolls = w.findChildren(QScrollArea)
        assert len(scrolls) >= 1

    def test_config_changed_signal(self):
        config = kcf.CommConfig()
        w = kcf.OptionsWidget(config)
        signal_received = []
        w.config_changed.connect(lambda: signal_received.append(True))
        w._on_apply()
        assert len(signal_received) == 1

    def test_checkboxes_exist(self):
        config = kcf.CommConfig()
        w = kcf.OptionsWidget(config)
        assert hasattr(w, 'chk_auto_checksum')
        assert hasattr(w, 'chk_verify_write')
        assert hasattr(w, 'chk_high_speed')
        assert hasattr(w, 'chk_ignore_echo')


# ═══════════════════════════════════════════════════════════════════════
# FLASH WORKER
# ═══════════════════════════════════════════════════════════════════════

class TestFlashWorker:
    """Tests for the FlashWorker QObject."""

    def test_instantiation(self, loopback_comm):
        loopback_comm.connect()
        w = kcf.FlashWorker(loopback_comm)
        assert w is not None

    def test_setup_read(self, loopback_comm):
        loopback_comm.connect()
        w = kcf.FlashWorker(loopback_comm)
        w.setup_read()
        assert w._task == "read"

    def test_setup_write(self, loopback_comm):
        loopback_comm.connect()
        data = bytearray(b'\xFF' * 131072)
        w = kcf.FlashWorker(loopback_comm)
        w.setup_write(data, "BIN")
        assert w._task == "write"
        assert w._mode == "BIN"

    def test_setup_write_cal_mode(self, loopback_comm):
        loopback_comm.connect()
        data = bytearray(b'\xFF' * 131072)
        w = kcf.FlashWorker(loopback_comm)
        w.setup_write(data, "CAL")
        assert w._mode == "CAL"


# ═══════════════════════════════════════════════════════════════════════
# MAIN WINDOW — STRUCTURE
# ═══════════════════════════════════════════════════════════════════════

class TestMainWindowStructure:
    """Tests for MainWindow widget creation and structure."""

    def test_window_title(self, main_window):
        assert kcf.__app_name__ in main_window.windowTitle()

    def test_has_tabs(self, main_window):
        assert hasattr(main_window, 'tabs')
        assert main_window.tabs.count() == 5  # Dashboard, Table Editor, Disassembler, Log, Options

    def test_tab_names(self, main_window):
        names = [main_window.tabs.tabText(i) for i in range(main_window.tabs.count())]
        assert "Dashboard" in names
        assert "Table Editor" in names
        assert "Disassembler" in names
        assert "Log" in names
        assert "Options" in names

    def test_has_port_combo(self, main_window):
        assert hasattr(main_window, 'port_combo')

    def test_has_transport_combo(self, main_window):
        assert hasattr(main_window, 'transport_combo')
        # Loopback should always be present
        items = [main_window.transport_combo.itemText(i)
                 for i in range(main_window.transport_combo.count())]
        assert any("Loopback" in i for i in items)

    def test_has_connect_button(self, main_window):
        assert hasattr(main_window, 'connect_btn')
        assert main_window.connect_btn.text() == "Connect"

    def test_has_load_button(self, main_window):
        assert hasattr(main_window, 'load_btn')

    def test_has_save_button(self, main_window):
        assert hasattr(main_window, 'save_btn')
        assert not main_window.save_btn.isEnabled()

    def test_has_read_button(self, main_window):
        assert hasattr(main_window, 'read_btn')
        assert not main_window.read_btn.isEnabled()

    def test_has_write_button(self, main_window):
        assert hasattr(main_window, 'write_btn')
        assert not main_window.write_btn.isEnabled()

    def test_has_cancel_button(self, main_window):
        assert hasattr(main_window, 'cancel_btn')
        assert not main_window.cancel_btn.isEnabled()

    def test_has_write_mode_combo(self, main_window):
        assert hasattr(main_window, 'write_mode_combo')
        modes = [main_window.write_mode_combo.itemText(i)
                 for i in range(main_window.write_mode_combo.count())]
        assert "BIN" in modes
        assert "CAL" in modes

    def test_has_progress_bar(self, main_window):
        assert hasattr(main_window, 'progress_bar')

    def test_has_status_bar(self, main_window):
        assert hasattr(main_window, 'state_label')
        assert main_window.state_label.text() == "DISCONNECTED"

    def test_has_options_tab_widget(self, main_window):
        assert hasattr(main_window, 'options_tab')
        assert isinstance(main_window.options_tab, kcf.OptionsWidget)


# ═══════════════════════════════════════════════════════════════════════
# MAIN WINDOW — MENU BAR
# ═══════════════════════════════════════════════════════════════════════

class TestMainWindowMenuBar:
    """Tests for all menu bar items and their properties."""

    # ── File menu ──
    def test_has_action_load(self, main_window):
        assert hasattr(main_window, 'action_load')
        assert main_window.action_load.shortcut().toString() == "Ctrl+O"

    def test_has_action_save(self, main_window):
        assert hasattr(main_window, 'action_save')
        assert not main_window.action_save.isEnabled()

    def test_has_action_save_as(self, main_window):
        assert hasattr(main_window, 'action_save_as')

    def test_has_action_exit(self, main_window):
        assert hasattr(main_window, 'action_exit')

    # ── Connection menu ──
    def test_has_action_connect(self, main_window):
        assert hasattr(main_window, 'action_connect')
        assert main_window.action_connect.shortcut().toString() == "Ctrl+K"

    def test_has_action_refresh_ports(self, main_window):
        assert hasattr(main_window, 'action_refresh_ports')
        assert main_window.action_refresh_ports.shortcut().toString() == "F5"

    # ── Flash menu ──
    def test_has_action_read_ecu(self, main_window):
        assert hasattr(main_window, 'action_read_ecu')
        assert not main_window.action_read_ecu.isEnabled()

    def test_has_action_write_bin(self, main_window):
        assert hasattr(main_window, 'action_write_bin')
        assert not main_window.action_write_bin.isEnabled()

    def test_has_action_write_cal(self, main_window):
        assert hasattr(main_window, 'action_write_cal')
        assert not main_window.action_write_cal.isEnabled()

    def test_has_action_cancel(self, main_window):
        assert hasattr(main_window, 'action_cancel')
        assert not main_window.action_cancel.isEnabled()

    # ── Flash checkboxes ──
    def test_has_auto_checksum_action(self, main_window):
        assert hasattr(main_window, 'action_auto_checksum')
        assert main_window.action_auto_checksum.isCheckable()
        assert main_window.action_auto_checksum.isChecked()

    def test_has_verify_after_write_action(self, main_window):
        assert hasattr(main_window, 'action_verify_after_write')
        assert main_window.action_verify_after_write.isCheckable()
        assert main_window.action_verify_after_write.isChecked()

    def test_has_high_speed_read_action(self, main_window):
        assert hasattr(main_window, 'action_high_speed_read')
        assert main_window.action_high_speed_read.isCheckable()
        assert not main_window.action_high_speed_read.isChecked()

    def test_has_ignore_echo_action(self, main_window):
        assert hasattr(main_window, 'action_ignore_echo')
        assert main_window.action_ignore_echo.isCheckable()
        assert main_window.action_ignore_echo.isChecked()

    # ── Tools menu ──
    def test_has_action_checksum(self, main_window):
        assert hasattr(main_window, 'action_checksum')

    def test_has_action_ecu_info(self, main_window):
        assert hasattr(main_window, 'action_ecu_info')

    def test_has_action_options(self, main_window):
        assert hasattr(main_window, 'action_options')

    # ── View menu ──
    def test_has_action_view_dash(self, main_window):
        assert hasattr(main_window, 'action_view_dash')
        assert main_window.action_view_dash.shortcut().toString() == "Ctrl+1"

    def test_has_action_view_tables(self, main_window):
        assert hasattr(main_window, 'action_view_tables')
        assert main_window.action_view_tables.shortcut().toString() == "Ctrl+2"

    def test_has_action_view_disasm(self, main_window):
        assert hasattr(main_window, 'action_view_disasm')
        assert main_window.action_view_disasm.shortcut().toString() == "Ctrl+3"

    def test_has_action_view_log(self, main_window):
        assert hasattr(main_window, 'action_view_log')
        assert main_window.action_view_log.shortcut().toString() == "Ctrl+4"

    def test_has_action_view_options(self, main_window):
        assert hasattr(main_window, 'action_view_options')
        assert main_window.action_view_options.shortcut().toString() == "Ctrl+5"

    # ── Help menu ──
    def test_has_action_about(self, main_window):
        assert hasattr(main_window, 'action_about')


# ═══════════════════════════════════════════════════════════════════════
# MAIN WINDOW — FLASH CHECKBOX TOGGLES
# ═══════════════════════════════════════════════════════════════════════

class TestMainWindowFlashToggles:
    """Tests for the flash option checkbox toggle handlers."""

    def test_toggle_auto_checksum_off(self, main_window):
        main_window.action_auto_checksum.setChecked(False)
        assert main_window._config.auto_checksum_fix is False

    def test_toggle_auto_checksum_on(self, main_window):
        main_window.action_auto_checksum.setChecked(True)
        assert main_window._config.auto_checksum_fix is True

    def test_toggle_verify_after_write(self, main_window):
        main_window.action_verify_after_write.setChecked(False)
        assert main_window._verify_after_write is False
        main_window.action_verify_after_write.setChecked(True)
        assert main_window._verify_after_write is True

    def test_toggle_high_speed_read(self, main_window):
        main_window.action_high_speed_read.setChecked(True)
        assert main_window._config.high_speed_read is True
        main_window.action_high_speed_read.setChecked(False)
        assert main_window._config.high_speed_read is False

    def test_toggle_ignore_echo(self, main_window):
        main_window.action_ignore_echo.setChecked(False)
        assert main_window._config.ignore_echo is False
        main_window.action_ignore_echo.setChecked(True)
        assert main_window._config.ignore_echo is True


# ═══════════════════════════════════════════════════════════════════════
# MAIN WINDOW — ACTIONS
# ═══════════════════════════════════════════════════════════════════════

class TestMainWindowActions:
    """Tests for MainWindow action handlers that can be tested without hardware."""

    def test_update_state_connected(self, main_window):
        main_window._update_state("CONNECTED")
        assert main_window.state_label.text() == "CONNECTED"

    def test_update_state_disconnected(self, main_window):
        main_window._update_state("DISCONNECTED")
        assert main_window.state_label.text() == "DISCONNECTED"

    def test_update_state_flashing(self, main_window):
        main_window._update_state("FLASHING")
        assert main_window.state_label.text() == "FLASHING"

    def test_update_menu_state_disconnected(self, main_window):
        main_window._update_menu_state(False)
        assert not main_window.action_read_ecu.isEnabled()
        assert not main_window.action_write_bin.isEnabled()
        assert not main_window.action_ecu_info.isEnabled()

    def test_update_menu_state_connected_no_bin(self, main_window):
        main_window._bin_data = None
        main_window._update_menu_state(True)
        assert main_window.action_read_ecu.isEnabled()
        assert not main_window.action_write_bin.isEnabled()

    def test_update_menu_state_connected_with_bin(self, main_window, full_bin):
        main_window._bin_data = full_bin
        main_window._update_menu_state(True)
        assert main_window.action_read_ecu.isEnabled()
        assert main_window.action_write_bin.isEnabled()
        assert main_window.action_write_cal.isEnabled()
        assert main_window.action_save.isEnabled()

    def test_verify_checksum_no_bin(self, main_window):
        main_window._bin_data = None
        main_window._verify_checksum()  # should log warning, not crash

    def test_verify_checksum_with_bin(self, main_window, full_bin):
        kcf.BinFile.fix_checksum(full_bin)
        main_window._bin_data = full_bin
        main_window._verify_checksum()
        # Should log success

    def test_verify_checksum_with_bad_bin(self, main_window, full_bin):
        full_bin[0x2000] = 0x00  # corrupt
        main_window._bin_data = full_bin
        main_window._verify_checksum()
        # Should auto-fix and log

    def test_show_options_switches_tab(self, main_window):
        main_window._show_options()
        assert main_window.tabs.currentIndex() == 4

    def test_view_menu_switches_tabs(self, main_window):
        main_window.action_view_dash.trigger()
        assert main_window.tabs.currentIndex() == 0
        main_window.action_view_tables.trigger()
        assert main_window.tabs.currentIndex() == 1
        main_window.action_view_disasm.trigger()
        assert main_window.tabs.currentIndex() == 2
        main_window.action_view_log.trigger()
        assert main_window.tabs.currentIndex() == 3
        main_window.action_view_options.trigger()
        assert main_window.tabs.currentIndex() == 4

    def test_refresh_ports(self, main_window):
        main_window._refresh_ports()
        # Should not crash; port list may be empty

    def test_cancel_op_no_comm(self, main_window):
        """Cancel without a connection should not crash."""
        main_window._comm = None
        main_window._cancel_op()

    def test_close_event(self, main_window):
        from PySide6.QtGui import QCloseEvent
        event = QCloseEvent()
        main_window.closeEvent(event)
        assert event.isAccepted()

    def test_on_flash_progress(self, main_window):
        main_window._on_flash_progress(50, 100, "Writing")
        assert main_window.progress_bar.value() == 50

    def test_on_flash_finished_success(self, main_window, full_bin):
        main_window._bin_data = full_bin
        main_window._on_flash_finished(True)
        assert main_window.progress_bar.value() == 100

    def test_on_flash_finished_failure(self, main_window):
        main_window._on_flash_finished(False)
        assert main_window.progress_bar.value() == 0


# ═══════════════════════════════════════════════════════════════════════
# MAIN WINDOW — LOOPBACK CONNECTION
# ═══════════════════════════════════════════════════════════════════════

class TestMainWindowLoopbackConnect:
    """Tests for connecting via the Loopback transport."""

    def test_connect_loopback(self, main_window):
        """Select loopback transport and connect."""
        # Select Loopback
        for i in range(main_window.transport_combo.count()):
            if main_window.transport_combo.itemData(i) == "loopback":
                main_window.transport_combo.setCurrentIndex(i)
                break
        main_window._connect()
        assert main_window.connect_btn.text() == "Disconnect"
        assert main_window.read_btn.isEnabled()

    def test_disconnect_after_loopback(self, main_window):
        for i in range(main_window.transport_combo.count()):
            if main_window.transport_combo.itemData(i) == "loopback":
                main_window.transport_combo.setCurrentIndex(i)
                break
        main_window._connect()
        main_window._disconnect()
        assert main_window.connect_btn.text() == "Connect"
        assert not main_window.read_btn.isEnabled()

    def test_toggle_connect(self, main_window):
        for i in range(main_window.transport_combo.count()):
            if main_window.transport_combo.itemData(i) == "loopback":
                main_window.transport_combo.setCurrentIndex(i)
                break
        main_window._toggle_connect()  # connects
        assert main_window.connect_btn.text() == "Disconnect"
        main_window._toggle_connect()  # disconnects
        assert main_window.connect_btn.text() == "Connect"


# ═══════════════════════════════════════════════════════════════════════
# MAIN WINDOW — BIN LOAD (mocked file dialog)
# ═══════════════════════════════════════════════════════════════════════

class TestMainWindowBinOps:
    """Tests for bin load/save with mocked file dialogs."""

    def test_load_bin_via_mock(self, main_window, full_bin, tmp_path):
        """Mock the file dialog and load a bin."""
        p = tmp_path / "test_load.bin"
        kcf.BinFile.fix_checksum(full_bin)
        kcf.BinFile.save(str(p), full_bin)

        with patch.object(kcf, 'QFileDialog') as mock_dlg:
            mock_dlg.getOpenFileName.return_value = (str(p), "")
            main_window._load_bin()
        assert main_window._bin_data is not None
        assert len(main_window._bin_data) == 131072
        assert main_window.save_btn.isEnabled()

    def test_load_bin_cancelled(self, main_window):
        """If file dialog is cancelled, nothing should change."""
        main_window._bin_data = None
        with patch.object(kcf, 'QFileDialog') as mock_dlg:
            mock_dlg.getOpenFileName.return_value = ("", "")
            main_window._load_bin()
        assert main_window._bin_data is None


# ═══════════════════════════════════════════════════════════════════════
# CLI ARGS — NEW FLAGS
# ═══════════════════════════════════════════════════════════════════════

class TestCLINewArgs:
    """Tests for the new CLI arguments matching GUI options."""

    def test_write_prom_mode(self):
        parser = kcf.build_parser()
        args = parser.parse_args(["write", "--port", "COM3", "--input", "f.bin", "--mode", "PROM"])
        assert args.write_mode == "PROM"

    def test_auto_checksum_default_on(self):
        parser = kcf.build_parser()
        args = parser.parse_args(["write", "--port", "COM3", "--input", "f.bin"])
        assert args.auto_checksum is True

    def test_no_auto_checksum(self):
        parser = kcf.build_parser()
        args = parser.parse_args(["write", "--port", "COM3", "--input", "f.bin", "--no-auto-checksum"])
        assert args.auto_checksum is False

    def test_verify_default_on(self):
        parser = kcf.build_parser()
        args = parser.parse_args(["write", "--port", "COM3", "--input", "f.bin"])
        assert args.verify_after_write is True

    def test_no_verify(self):
        parser = kcf.build_parser()
        args = parser.parse_args(["write", "--port", "COM3", "--input", "f.bin", "--no-verify"])
        assert args.verify_after_write is False

    def test_ignore_echo_default_on(self):
        parser = kcf.build_parser()
        args = parser.parse_args(["read", "--port", "COM3"])
        assert args.ignore_echo is True

    def test_no_ignore_echo(self):
        parser = kcf.build_parser()
        args = parser.parse_args(["read", "--port", "COM3", "--no-ignore-echo"])
        assert args.ignore_echo is False

    def test_inter_frame_delay(self):
        parser = kcf.build_parser()
        args = parser.parse_args(["read", "--port", "COM3", "--inter-frame-delay", "100"])
        assert args.inter_frame_delay == 100

    def test_inter_frame_delay_default(self):
        parser = kcf.build_parser()
        args = parser.parse_args(["read", "--port", "COM3"])
        assert args.inter_frame_delay == kcf.DEFAULT_INTER_FRAME_DELAY_MS

    def test_high_speed_flag(self):
        parser = kcf.build_parser()
        args = parser.parse_args(["read", "--port", "COM3", "--high-speed"])
        assert args.high_speed is True


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--html=gui_report.html", "--self-contained-html"])
