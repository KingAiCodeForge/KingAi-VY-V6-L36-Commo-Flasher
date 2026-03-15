#!/usr/bin/env python3
"""
test_gui_functions.py — Comprehensive pytest suite for all GUI widgets,
menu actions, toolbar buttons, options tab, and flash checkboxes.
============================================================================

Tests every GUI class and action in kingai_commie_flasher.py Section 12:

  LogWidget               — append_log, level colouring
  SensorGaugeWidget       — value update, clamping
  DashboardWidget         — update_data routing
  TableEditorWidget       — load_table, cell edit, highlight
  DisassemblerWidget      — UI build, clear
  OptionsWidget           — load/apply/reset, scrollbar
  FlashWorker             — setup_read, setup_write, setup_custom_*, setup_chaos
  CustomFlashWidget       — sector table, address inputs, signals
  ChaosTestWidget         — cycle config, start/stop, results
  TransportSettingsWidget — PySerial/D2XX settings, presets, timing offsets
  MainWindow              — build_ui (8 tabs), menu bar, connect_signals,
                            flash checkbox toggles, state updates,
                            load/save bin, refresh ports, options tab,
                            new tab handlers, about dialog, close event

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
        assert main_window.tabs.count() == 8  # Dashboard, Table Editor, Disassembler, Log, Options, Custom Flash, Chaos Test, Transport

    def test_tab_names(self, main_window):
        names = [main_window.tabs.tabText(i) for i in range(main_window.tabs.count())]
        assert "Dashboard" in names
        assert "Table Editor" in names
        assert "Disassembler" in names
        assert "Log" in names
        assert "Options" in names
        assert "Custom Flash" in names
        assert "Chaos Test" in names
        assert "Transport" in names

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
        main_window.action_view_custom_flash.trigger()
        assert main_window.tabs.currentIndex() == 5
        main_window.action_view_chaos.trigger()
        assert main_window.tabs.currentIndex() == 6
        main_window.action_view_transport.trigger()
        assert main_window.tabs.currentIndex() == 7

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


# ═══════════════════════════════════════════════════════════════════════
# CUSTOM FLASH WIDGET
# ═══════════════════════════════════════════════════════════════════════

class TestCustomFlashWidget:
    """Tests for the CustomFlashWidget (sector-level brick recovery)."""

    def test_instantiation(self):
        w = kcf.CustomFlashWidget()
        assert w is not None

    def test_has_sector_input(self):
        w = kcf.CustomFlashWidget()
        assert hasattr(w, 'sector_input')
        assert hasattr(w, 'sector_checks')
        assert len(w.sector_checks) == 8  # 8 sectors in AMD 29F010

    def test_has_address_inputs(self):
        w = kcf.CustomFlashWidget()
        assert hasattr(w, 'start_addr_input')
        assert hasattr(w, 'end_addr_input')

    def test_has_buttons(self):
        w = kcf.CustomFlashWidget()
        assert hasattr(w, 'btn_custom_write')
        assert hasattr(w, 'btn_custom_read')
        assert hasattr(w, 'btn_range_write')

    def test_signals_exist(self):
        w = kcf.CustomFlashWidget()
        # Verify the signals are present (accessed as class attrs)
        assert hasattr(kcf.CustomFlashWidget, 'start_custom_write')
        assert hasattr(kcf.CustomFlashWidget, 'start_custom_read')

    def test_sector_checkboxes_exist(self):
        w = kcf.CustomFlashWidget()
        assert hasattr(w, 'sector_checks')
        assert len(w.sector_checks) == 8

    def test_default_no_sectors_selected(self):
        w = kcf.CustomFlashWidget()
        for chk in w.sector_checks:
            assert not chk.isChecked()


# ═══════════════════════════════════════════════════════════════════════
# CHAOS TEST WIDGET
# ═══════════════════════════════════════════════════════════════════════

class TestChaosTestWidget:
    """Tests for the ChaosTestWidget (stress-test loop)."""

    def test_instantiation(self):
        w = kcf.ChaosTestWidget()
        assert w is not None

    def test_has_cycle_spinner(self):
        w = kcf.ChaosTestWidget()
        assert hasattr(w, 'spin_cycles')
        assert w.spin_cycles.value() == 0  # default = infinite

    def test_has_mode_combo(self):
        w = kcf.ChaosTestWidget()
        assert hasattr(w, 'combo_write_mode')
        # Should have BIN and CAL options
        items = [w.combo_write_mode.itemText(i) for i in range(w.combo_write_mode.count())]
        assert any("BIN" in item for item in items)
        assert any("CAL" in item for item in items)

    def test_has_delay_spinner(self):
        w = kcf.ChaosTestWidget()
        assert hasattr(w, 'spin_delay')

    def test_has_stop_on_fail_checkbox(self):
        w = kcf.ChaosTestWidget()
        assert hasattr(w, 'chk_stop_on_fail')
        assert w.chk_stop_on_fail.isChecked()  # default ON

    def test_has_compare_checkbox(self):
        w = kcf.ChaosTestWidget()
        assert hasattr(w, 'chk_compare_bytes')
        assert w.chk_compare_bytes.isChecked()  # default ON

    def test_has_start_stop_buttons(self):
        w = kcf.ChaosTestWidget()
        assert hasattr(w, 'btn_start')
        assert hasattr(w, 'btn_stop')
        assert w.btn_start.isEnabled()
        assert not w.btn_stop.isEnabled()  # stop disabled until started

    def test_has_results_label(self):
        w = kcf.ChaosTestWidget()
        assert hasattr(w, 'results_label')

    def test_update_results(self):
        w = kcf.ChaosTestWidget()
        w.update_results(5, 4, 1, "mismatch at $4000")
        text = w.results_label.text()
        assert "5" in text
        assert "4" in text
        assert "1" in text

    def test_signals_exist(self):
        assert hasattr(kcf.ChaosTestWidget, 'start_chaos')
        assert hasattr(kcf.ChaosTestWidget, 'stop_chaos')


# ═══════════════════════════════════════════════════════════════════════
# TRANSPORT SETTINGS WIDGET
# ═══════════════════════════════════════════════════════════════════════

class TestTransportSettingsWidget:
    """Tests for the TransportSettingsWidget (PySerial / D2XX tuning)."""

    def test_instantiation(self):
        config = kcf.CommConfig()
        w = kcf.TransportSettingsWidget(config)
        assert w is not None

    def test_has_pyserial_read_timeout(self):
        config = kcf.CommConfig()
        w = kcf.TransportSettingsWidget(config)
        assert hasattr(w, 'spin_py_read_timeout')
        assert w.spin_py_read_timeout.value() == 100  # default

    def test_has_pyserial_write_timeout(self):
        config = kcf.CommConfig()
        w = kcf.TransportSettingsWidget(config)
        assert hasattr(w, 'spin_py_write_timeout')
        assert w.spin_py_write_timeout.value() == 1000  # default

    def test_has_flow_control_checkboxes(self):
        config = kcf.CommConfig()
        w = kcf.TransportSettingsWidget(config)
        assert hasattr(w, 'chk_py_rtscts')
        assert hasattr(w, 'chk_py_dsrdtr')
        assert hasattr(w, 'chk_py_xonxoff')
        # All OFF by default (ALDL doesn't use flow control)
        assert not w.chk_py_rtscts.isChecked()
        assert not w.chk_py_dsrdtr.isChecked()
        assert not w.chk_py_xonxoff.isChecked()

    def test_has_d2xx_latency_timer(self):
        config = kcf.CommConfig()
        w = kcf.TransportSettingsWidget(config)
        assert hasattr(w, 'spin_d2xx_latency')
        assert w.spin_d2xx_latency.value() == 2  # our recommended default

    def test_has_d2xx_timeouts(self):
        config = kcf.CommConfig()
        w = kcf.TransportSettingsWidget(config)
        assert hasattr(w, 'spin_d2xx_read_timeout')
        assert hasattr(w, 'spin_d2xx_write_timeout')
        assert w.spin_d2xx_read_timeout.value() == 200
        assert w.spin_d2xx_write_timeout.value() == 200

    def test_has_timing_offsets(self):
        config = kcf.CommConfig()
        w = kcf.TransportSettingsWidget(config)
        assert hasattr(w, 'spin_silence_offset')
        assert hasattr(w, 'spin_tx_delay_offset')
        assert hasattr(w, 'spin_retry_delay_offset')
        assert hasattr(w, 'spin_erase_timeout_offset')
        assert hasattr(w, 'spin_cleanup_delay_offset')
        # All 0 by default
        assert w.spin_silence_offset.value() == 0
        assert w.spin_tx_delay_offset.value() == 0
        assert w.spin_retry_delay_offset.value() == 0
        assert w.spin_erase_timeout_offset.value() == 0
        assert w.spin_cleanup_delay_offset.value() == 0

    def test_has_preset_combo(self):
        config = kcf.CommConfig()
        w = kcf.TransportSettingsWidget(config)
        assert hasattr(w, 'combo_preset')
        assert w.combo_preset.count() >= 5  # Custom + several presets

    def test_has_apply_and_reset_buttons(self):
        config = kcf.CommConfig()
        w = kcf.TransportSettingsWidget(config)
        assert hasattr(w, 'apply_btn')
        assert hasattr(w, 'reset_btn')

    def test_get_transport_settings_returns_dict(self):
        config = kcf.CommConfig()
        w = kcf.TransportSettingsWidget(config)
        settings = w.get_transport_settings()
        assert isinstance(settings, dict)
        assert "pyserial" in settings
        assert "d2xx" in settings
        assert "timing_offsets" in settings
        assert settings["d2xx"]["latency_timer_ms"] == 2
        assert settings["pyserial"]["rtscts"] is False

    def test_reset_restores_defaults(self):
        config = kcf.CommConfig()
        w = kcf.TransportSettingsWidget(config)
        # Change a value
        w.spin_d2xx_latency.setValue(16)
        assert w.spin_d2xx_latency.value() == 16
        # Reset
        w._on_reset()
        assert w.spin_d2xx_latency.value() == 2

    def test_config_changed_signal(self):
        config = kcf.CommConfig()
        w = kcf.TransportSettingsWidget(config)
        signal_received = []
        w.config_changed.connect(lambda: signal_received.append(True))
        w._on_apply()
        assert len(signal_received) == 1


# ═══════════════════════════════════════════════════════════════════════
# FLASH WORKER — NEW SETUP METHODS
# ═══════════════════════════════════════════════════════════════════════

class TestFlashWorkerNewMethods:
    """Tests for FlashWorker custom_write, custom_read, chaos setup."""

    def test_setup_custom_write(self, loopback_comm):
        loopback_comm.connect()
        data = bytearray(b'\xFF' * 131072)
        w = kcf.FlashWorker(loopback_comm)
        w.setup_custom_write(data, [0, 1, 2])
        assert w._task == "custom_write"
        assert w._sectors == [0, 1, 2]

    def test_setup_custom_read(self, loopback_comm):
        loopback_comm.connect()
        w = kcf.FlashWorker(loopback_comm)
        w.setup_custom_read(0x4000, 0x7FFF)
        assert w._task == "custom_read"
        assert w._custom_start == 0x4000
        assert w._custom_end == 0x7FFF

    def test_setup_chaos(self, loopback_comm):
        loopback_comm.connect()
        data = bytearray(b'\xFF' * 131072)
        cfg = {"cycles": 3, "mode": "BIN", "delay": 1, "stop_on_fail": True, "compare_bytes": True}
        w = kcf.FlashWorker(loopback_comm)
        w.setup_chaos(cfg, data)
        assert w._task == "chaos"
        assert w._chaos_cfg["cycles"] == 3
        assert w._bin_data is data


# ═══════════════════════════════════════════════════════════════════════
# MAIN WINDOW — NEW TAB WIDGETS
# ═══════════════════════════════════════════════════════════════════════

class TestMainWindowNewTabs:
    """Tests that the new tabs are present and wired in MainWindow."""

    def test_has_custom_flash_tab(self, main_window):
        assert hasattr(main_window, 'custom_flash_tab')
        assert isinstance(main_window.custom_flash_tab, kcf.CustomFlashWidget)

    def test_has_chaos_tab(self, main_window):
        assert hasattr(main_window, 'chaos_tab')
        assert isinstance(main_window.chaos_tab, kcf.ChaosTestWidget)

    def test_has_transport_tab(self, main_window):
        assert hasattr(main_window, 'transport_tab')
        assert isinstance(main_window.transport_tab, kcf.TransportSettingsWidget)

    def test_custom_flash_tab_index(self, main_window):
        assert main_window.tabs.tabText(5) == "Custom Flash"

    def test_chaos_tab_index(self, main_window):
        assert main_window.tabs.tabText(6) == "Chaos Test"

    def test_transport_tab_index(self, main_window):
        assert main_window.tabs.tabText(7) == "Transport"

    def test_has_view_action_custom_flash(self, main_window):
        assert hasattr(main_window, 'action_view_custom_flash')
        assert main_window.action_view_custom_flash.shortcut().toString() == "Ctrl+6"

    def test_has_view_action_chaos(self, main_window):
        assert hasattr(main_window, 'action_view_chaos')
        assert main_window.action_view_chaos.shortcut().toString() == "Ctrl+7"

    def test_has_view_action_transport(self, main_window):
        assert hasattr(main_window, 'action_view_transport')
        assert main_window.action_view_transport.shortcut().toString() == "Ctrl+8"

    def test_custom_flash_handler_exists(self, main_window):
        assert hasattr(main_window, '_on_custom_write')
        assert hasattr(main_window, '_on_custom_read')

    def test_chaos_handlers_exist(self, main_window):
        assert hasattr(main_window, '_on_start_chaos')
        assert hasattr(main_window, '_on_stop_chaos')

    def test_custom_flash_no_comm_warning(self, main_window):
        """Calling custom write with no connection should not crash."""
        with patch('kingai_commie_flasher.QMessageBox'):
            main_window._on_custom_write([0, 1])

    def test_chaos_no_comm_warning(self, main_window):
        """Calling chaos test with no connection should not crash."""
        with patch('kingai_commie_flasher.QMessageBox'):
            main_window._on_start_chaos({"cycles": 1, "mode": "BIN"})

    def test_flash_finished_resets_chaos_buttons(self, main_window):
        """Verify _on_flash_finished resets chaos tab buttons."""
        main_window.chaos_tab.btn_start.setEnabled(False)
        main_window.chaos_tab.btn_stop.setEnabled(True)
        main_window._on_flash_finished(True)
        assert main_window.chaos_tab.btn_start.isEnabled()
        assert not main_window.chaos_tab.btn_stop.isEnabled()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--html=gui_report.html", "--self-contained-html"])
