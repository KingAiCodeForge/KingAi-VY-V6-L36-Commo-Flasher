# KingAI Commie Flasher — Architecture & Wiring Map

> Auto-generated from code analysis — 2026-02-18
> Single-file monolith: `kingai_commie_flasher.py` (~6700 lines, 15 sections)

---

## Code Sections (top to bottom)

| Section | Lines | Contents |
|---------|-------|----------|
| 0 — Imports & Globals | 176–326 | stdlib, PySide6 (optional), logging, paths |
| 1 — Constants & Protocol Defs | 327–471 | `DeviceID`, `ALDLMode`, `FlashBank`, `FlashSector`, erase maps, timing constants |
| 2 — Data Stream Definitions | 472–544 | `DataStreamParam`, `MODE1_MSG0_PARAMS` (57 params) |
| 3 — Calibration Table Defs | 545–626 | `CalibrationTable`, `CALIBRATION_TABLES` (spark, fuel, TCC, etc.) |
| 4 — HC11 Flash Kernel | 627–812 | `FlashKernel` — 3 byte arrays of 68HC11 machine code for RAM upload |
| 5 — ALDL Frame Protocol | 813–1010 | `ALDLProtocol` — frame building, checksums, seed/key, Mode 1 parsing |
| 6 — Transport Layer | 1011–1509 | `BaseTransport`, `PySerialTransport`, `D2XXTransport`, `LoopbackTransport` |
| 7 — ECU Communication | 1510–2379 | `ECUComm` — framing, retries, silence, echo, security, kernel upload, erase, write, verify |
| 8 — Bin File Utilities | 2380–2529 | `BinFile` — load/save/checksum/diff/table read-write |
| 9 — Flash Operations | 2530–3031 | `FlashOp` — high-level `full_read()`, `full_write()`, `custom_read()`, `custom_write()` |
| 10 — DataLogger | 3032–3130 | `DataLogger` — Mode 1 polling to CSV in background thread |
| 11 — Live Tuner | 3131–3280 | `LiveTuner` — RAM shadow table editing with safety checks |
| 12 — GUI | 3281–6396 | All PySide6 widgets, `FlashWorker`, `MainWindow` |
| 13 — CLI Interface | 6397–6585 | `argparse` subcommands: gui, read, write, datalog, info, checksum, ports |
| 14 — Entry Point | 6586–end | `if __name__ == "__main__"` |

---

## Class Dependency Chain

```
ALDLProtocol (static — frame building, no state)
     │
BaseTransport ←── PySerialTransport / D2XXTransport / LoopbackTransport
     │
ECUComm (owns transport, handles framing/retries/state machine)
     │
     ├── FlashOp (owns ECUComm — orchestrates full read/write sequences)
     ├── DataLogger (owns ECUComm — polls Mode 1 in background thread)
     └── LiveTuner (owns ECUComm + BinFile data — RAM shadow writes)

BinFile (static utility — load/save/checksum, no ECU dependency)

FlashWorker (QObject — wraps FlashOp, runs in QThread, emits Qt signals)
     │
MainWindow (owns FlashWorker + ECUComm + all tab widgets)
```

---

## GUI Tab Index Map

| Index | Tab Name | Widget Class | Signals Emitted | Connected To |
|-------|----------|--------------|-----------------|--------------|
| 0 | Dashboard | `DashboardWidget` | — | `dash_timer.timeout` → `_update_dashboard()` |
| 1 | Table Editor | `TableEditorWidget` | `cell_changed(row, col, value)` | (internal table update) |
| 2 | Disassembler | `DisassemblerWidget` | `disassembly_done(list, int)` | (internal display) |
| 3 | Log | `LogWidget` | — | Flash ops switch here and lock all other tabs |
| 4 | Options | `OptionsWidget` | `config_changed()` | `_on_options_changed()` |
| 5 | Custom Flash | `CustomFlashWidget` | `start_custom_write(list)`, `start_custom_read(int, int)` | `_on_custom_write()`, `_on_custom_read()` |
| 6 | Chaos Test | `ChaosTestWidget` | `start_chaos(dict)`, `stop_chaos()` | `_on_start_chaos()`, `_on_stop_chaos()` |
| 7 | Transport | `TransportSettingsWidget` | `config_changed()` | `_on_options_changed()` |

---

## Toolbar Buttons → Handlers

These are the `QPushButton` widgets in the main toolbar strip (top of window):

| Button | Label | `.clicked.connect(...)` | What It Does |
|--------|-------|------------------------|--------------|
| `refresh_btn` | ↻ | `_refresh_ports()` | Rescan serial ports, update combo box |
| `connect_btn` | Connect | `_toggle_connect()` | Connect/disconnect to ECU via selected transport |
| `load_btn` | Load .bin | `_load_bin()` | Open file dialog, load 128KB or 16KB .bin |
| `save_btn` | Save .bin | `_save_bin()` | Save current `_bin_data` to file |
| `read_btn` | Read ECU | `_read_ecu()` | Start full 128KB read (→ `FlashWorker` thread) |
| `write_btn` | Write ECU | `_write_ecu()` | Start write (uses write mode combo: BIN/CAL) |
| `cancel_btn` | Cancel | `_cancel_op()` | Set `_comm.cancel()` — aborts current flash op |

---

## Menu Bar → Actions → Handlers

### File Menu (5 actions)

| Action | Label | Shortcut | `.triggered.connect(...)` | Same As Button? |
|--------|-------|----------|--------------------------|----------------|
| `action_load` | Load .bin | Ctrl+O | `_load_bin()` | Yes → `load_btn` |
| `action_save` | Save .bin | Ctrl+S | `_save_bin()` | Yes → `save_btn` |
| `action_save_as` | Save .bin As... | Ctrl+Shift+S | `_save_bin()` | Yes → `save_btn` (⚠ same handler — no "save as" dialog yet) |
| `action_save_cal` | Save .cal... | — | `_save_cal()` | No — separate handler, exports 16KB cal region |
| `action_exit` | Exit | Alt+F4 | `self.close()` | No |

### Connection Menu (2 actions + vEEPROM submenu)

| Action | Label | Shortcut | `.triggered.connect(...)` | Same As Button? |
|--------|-------|----------|--------------------------|----------------|
| `action_connect` | Connect | Ctrl+K | `_toggle_connect()` | Yes → `connect_btn` |
| `action_refresh_ports` | Refresh Ports | F5 | `_refresh_ports()` | Yes → `refresh_btn` |

#### vEEPROM Submenu (5 actions — Loopback transport only)

| Action | Label | Shortcut | `.triggered.connect(...)` |
|--------|-------|----------|--------------------------|
| `action_veeprom_load` | Load .bin to vEEPROM... | Ctrl+Shift+L | `_veeprom_load()` |
| `action_veeprom_unload` | Unload vEEPROM | Ctrl+Shift+U | `_veeprom_unload()` |
| `action_veeprom_erase` | Erase vEEPROM | Ctrl+Shift+E | `_veeprom_erase()` |
| `action_veeprom_export` | Export vEEPROM to .bin... | Ctrl+Shift+X | `_veeprom_export()` |
| `action_veeprom_info` | vEEPROM Info | — | `_veeprom_info()` |

### Flash Menu (4 actions + 4 toggles)

| Action | Label | Shortcut | `.triggered.connect(...)` | Same As Button? |
|--------|-------|----------|--------------------------|----------------|
| `action_read_ecu` | Read ECU | Ctrl+R | `_read_ecu()` | Yes → `read_btn` |
| `action_write_bin` | Write BIN (Full) | Ctrl+W | `_write_ecu_mode("BIN")` | Partial → `write_btn` calls `_write_ecu()` which reads combo box |
| `action_write_cal` | Write CAL (Partial) | Ctrl+Shift+W | `_write_ecu_mode("CAL")` | Partial → `write_btn` calls `_write_ecu()` which reads combo box |
| `action_cancel` | Cancel Operation | Escape | `_cancel_op()` | Yes → `cancel_btn` |

#### Flash Toggles (checkable — `.toggled.connect(...)`)

| Action | Label | Default | `.toggled.connect(...)` | What It Sets |
|--------|-------|---------|------------------------|--------------|
| `action_auto_checksum` | Auto-fix Checksum Before Write | ON | `_on_toggle_auto_checksum()` | `_config.auto_checksum_fix` |
| `action_verify_after_write` | Verify After Write | ON | `_on_toggle_verify_write()` | `_verify_after_write` |
| `action_high_speed_read` | High-Speed Read | OFF | `_on_toggle_high_speed()` | `_config.high_speed_read` |
| `action_ignore_echo` | Ignore Echo | OFF | `_on_toggle_ignore_echo()` | `_config.ignore_echo` |

### Tools Menu (3 actions)

| Action | Label | `.triggered.connect(...)` |
|--------|-------|--------------------------|
| `action_checksum` | Verify/Fix Checksum | `_verify_checksum()` |
| `action_ecu_info` | ECU Info | `_show_ecu_info()` — calls `request_mode1()`, shows QMessageBox |
| `action_options` | Options... | `_show_options()` — switches to Tab 4 |

### View Menu (8 actions — tab shortcuts)

| Action | Label | Shortcut | Target |
|--------|-------|----------|--------|
| `action_view_dash` | Dashboard | Ctrl+1 | `tabs.setCurrentIndex(0)` |
| `action_view_tables` | Table Editor | Ctrl+2 | `tabs.setCurrentIndex(1)` |
| `action_view_disasm` | Disassembler | Ctrl+3 | `tabs.setCurrentIndex(2)` |
| `action_view_log` | Log | Ctrl+4 | `tabs.setCurrentIndex(3)` |
| `action_view_options` | Options | Ctrl+5 | `tabs.setCurrentIndex(4)` |
| `action_view_custom_flash` | Custom Flash | Ctrl+6 | `tabs.setCurrentIndex(5)` |
| `action_view_chaos` | Chaos Test | Ctrl+7 | `tabs.setCurrentIndex(6)` |
| `action_view_transport` | Transport | Ctrl+8 | `tabs.setCurrentIndex(7)` |

### Help Menu (1 action)

| Action | Label | `.triggered.connect(...)` |
|--------|-------|--------------------------|
| `action_about` | About | `_show_about()` |

**Total: 32 actions** (5 File + 7 Connection + 8 Flash + 3 Tools + 8 View + 1 Help)

---

## Button ↔ Action Duplicate Map

Every major action has BOTH a toolbar button AND a menu action, connected to the same handler:

| Handler | Toolbar Button | Menu Action(s) | Shortcut |
|---------|---------------|----------------|----------|
| `_load_bin()` | `load_btn` | `action_load` | Ctrl+O |
| `_save_bin()` | `save_btn` | `action_save`, `action_save_as` | Ctrl+S, Ctrl+Shift+S |
| `_read_ecu()` | `read_btn` | `action_read_ecu` | Ctrl+R |
| `_write_ecu()` | `write_btn` | — | — |
| `_write_ecu_mode("BIN")` | — | `action_write_bin` | Ctrl+W |
| `_write_ecu_mode("CAL")` | — | `action_write_cal` | Ctrl+Shift+W |
| `_cancel_op()` | `cancel_btn` | `action_cancel` | Escape |
| `_toggle_connect()` | `connect_btn` | `action_connect` | Ctrl+K |
| `_refresh_ports()` | `refresh_btn` | `action_refresh_ports` | F5 |

**Note:** `write_btn` reads the write-mode combo box ("BIN" or "CAL") and calls `_write_ecu()`, while the menu actions `action_write_bin` / `action_write_cal` call `_write_ecu_mode()` with a hardcoded mode. Both paths converge at `_start_flash_op("write", mode)`.

---

## Tab-Internal Buttons (not in toolbar)

### Tab 2 — Disassembler

| Button | `.clicked.connect(...)` |
|--------|------------------------|
| `btn_disasm` (Disassemble) | `_on_disassemble()` — runs HC11 disassembler on pasted hex or loaded bin |
| `btn_clear` (Clear) | `_on_clear()` — clears output |

### Tab 5 — Custom Flash

| Button | `.clicked.connect(...)` |
|--------|------------------------|
| `btn_apply_input` (Apply) | `_apply_sector_input()` — parse hex input for sector selection |
| `btn_custom_write` (Start Custom Sector Write) | `_on_custom_write()` → emits `start_custom_write(sectors)` signal |
| `btn_custom_read` (Start Custom Address Read) | `_on_custom_read()` → emits `start_custom_read(start, end)` signal |
| `btn_range_write` (Start Address Range Write) | `_on_range_write()` → (no menu action — tab-only) |

### Tab 6 — Chaos Test

| Button | `.clicked.connect(...)` |
|--------|------------------------|
| `btn_start` (Start Chaos Test) | `_on_start()` → emits `start_chaos(config)` signal |
| `btn_stop` (Stop) | `_on_stop()` → emits `stop_chaos()` signal |

### Tab 7 — Transport Settings

| Button | `.clicked.connect(...)` |
|--------|------------------------|
| `apply_btn` (Apply Transport Settings) | `_on_apply()` → emits `config_changed()` signal |
| `reset_btn` (Reset to Defaults) | `_on_reset()` → emits `config_changed()` signal |

### Tab 4 — Options

| Button | `.clicked.connect(...)` |
|--------|------------------------|
| `apply_btn` (Apply) | `_on_apply()` → emits `config_changed()` signal |
| `reset_btn` (Reset to Defaults) | `_on_reset()` → emits `config_changed()` signal |

---

## Flash Operation Flow (Read)

```
User clicks [Read ECU] button OR Flash menu → Read ECU (Ctrl+R)
  │
  ├── _read_ecu()
  │     └── _start_flash_op("read")
  │           ├── _lock_ui_for_flash("read")     — disables all buttons/tabs/menus except Cancel + Log
  │           ├── FlashWorker(comm).setup_read()
  │           └── _start_flash_thread(worker)    — creates QThread, wires signals, starts
  │
  │   [Worker thread]
  │     └── FlashWorker.run()
  │           ├── comm.reset_cancel()            — clear stale cancel flag
  │           ├── FlashOp.full_read()
  │           │     ├── comm.disable_chatter()   — Mode 8 (silence bus)
  │           │     ├── comm.unlock_security()   — Mode 13 (seed/key)
  │           │     ├── comm.enter_programming() — Mode 5
  │           │     ├── comm.upload_kernel()      — Mode 6 (3 kernel blocks → RAM)
  │           │     ├── comm.read_flash_info()    — Mode 6 (AMD chip ID)
  │           │     ├── comm.read_ram() × 2048    — Mode 2 (64 bytes × 2048 = 128KB)
  │           │     ├── comm.cleanup_and_reset()
  │           │     └── comm.enable_chatter()    — Mode 9
  │           ├── emit read_data(bytearray)      — sends 128KB to MainWindow
  │           └── emit finished(True)
  │
  │   [Main thread — signal handlers]
  │     ├── _on_read_data(data)                  — stores in _bin_data, updates file_label
  │     ├── _on_flash_finished(True)
  │     │     ├── _unlock_ui_after_flash()       — re-enables everything
  │     │     └── "Operation completed!" log
  │     └── worker.deleteLater() + thread.deleteLater()  — cleanup
```

## Flash Operation Flow (Write)

```
User clicks [Write ECU] button → _write_ecu() reads combo box (BIN/CAL)
  OR Flash menu → Write BIN (Ctrl+W) / Write CAL (Ctrl+Shift+W)
  │
  ├── _write_ecu() / _write_ecu_mode(mode)
  │     ├── Safety confirmation QMessageBox (Yes/No, default No)
  │     └── _start_flash_op("write", mode)
  │           ├── _lock_ui_for_flash("write")
  │           ├── FlashWorker(comm).setup_write(bin_data, mode)
  │           └── _start_flash_thread(worker)
  │
  │   [Worker thread]
  │     └── FlashOp.full_write(bin_data, mode)
  │           ├── BinFile.verify_checksum() → auto-fix if enabled
  │           ├── comm.disable_chatter()
  │           ├── comm.unlock_security()
  │           ├── comm.enter_programming()
  │           ├── comm.upload_kernel()
  │           ├── comm.read_flash_info()
  │           ├── ** Pre-write backup read ** → _backup_bin (in-memory)
  │           ├── comm.erase_sectors(erase_map)  — AMD 29F010 sector erase
  │           ├── comm.write_flash_data()         — bank-switched write with 3× retry
  │           ├── comm.verify_checksum()          — on-PCM checksum compare
  │           ├── comm.cleanup_and_reset()
  │           └── comm.enable_chatter()
  │
  │   [Main thread]
  │     └── _on_flash_finished() → _unlock_ui_after_flash()
```

## Custom Flash Flow (Tab 5)

```
User selects sectors [0-7] → clicks [Start Custom Sector Write]
  │
  └── CustomFlashWidget._on_custom_write()
        └── emits start_custom_write(sector_list)
              └── MainWindow._on_custom_write(sectors)
                    └── _start_custom_flash_op("custom_write", sectors=sectors)
                          ├── _lock_ui_for_flash(...)
                          ├── FlashWorker.setup_custom_write(bin_data, sectors)
                          └── _start_flash_thread(worker)

User enters hex range → clicks [Start Custom Address Read]
  │
  └── CustomFlashWidget._on_custom_read()
        └── emits start_custom_read(start_addr, end_addr)
              └── MainWindow._on_custom_read(start, end)
                    └── _start_custom_flash_op("custom_read", start_addr=..., end_addr=...)
```

## Chaos Test Flow (Tab 6)

```
User sets config → clicks [Start Chaos Test]
  │
  └── ChaosTestWidget._on_start()
        └── emits start_chaos(config_dict)
              └── MainWindow._on_start_chaos(config)
                    └── _start_custom_flash_op("chaos", chaos_cfg=config)

User clicks [Stop]
  │
  └── ChaosTestWidget._on_stop()
        └── emits stop_chaos()
              └── MainWindow._on_stop_chaos()
                    └── comm.cancel()  — sets threading.Event
```

---

## UI Lock/Unlock During Flash Operations

Both `_start_flash_op()` and `_start_custom_flash_op()` call the same helpers:

### _lock_ui_for_flash(task) — disables:

- **Toolbar buttons:** `read_btn`, `write_btn`, `load_btn`, `save_btn` (but enables `cancel_btn`)
- **Menu actions:** `action_read_ecu`, `action_write_bin`, `action_write_cal`, `action_load`, `action_save`, `action_save_as`, `action_save_cal`, `action_checksum`, `action_ecu_info`
- **Flash toggles:** `action_auto_checksum`, `action_verify_after_write`, `action_high_speed_read`, `action_ignore_echo`
- **View actions:** all 8 `action_view_*` actions
- **Options:** `apply_btn`, `reset_btn`
- **All tabs except Tab 3 (Log)** — forced switch to Log tab

### _unlock_ui_after_flash() — re-enables everything above

### _start_flash_thread(worker) — wires signals + cleanup:

- `worker.finished` → `_on_flash_finished()`
- `worker.read_data` → `_on_read_data()`
- `worker.progress` → `_on_flash_progress()`
- `worker.log_message` → `log_widget.append_log()`
- `worker.state_changed` → `_update_state()`
- `worker.finished` → `thread.quit()`
- `thread.finished` → `worker.deleteLater()` + `thread.deleteLater()`

---

## Safety Gates

| Gate | Location | What It Prevents |
|------|----------|-----------------|
| `closeEvent()` override | `MainWindow` | Blocks window close during write (event.ignore). Allows close during read with confirmation. |
| Disconnect during write | `_toggle_connect()` | Shows danger QMessageBox: "ECU may be bricked" |
| Disconnect during read | `_toggle_connect()` | Shows warning but allows disconnect |
| Write confirmation | `_write_ecu_mode()` | QMessageBox Yes/No (default No) before any write |
| Cancel flag | `ECUComm._cancel` | `threading.Event` — checked in `_transact()`, `full_read()` loop, and chaos loop |
| `reset_cancel()` | `FlashWorker.run()` | Clears stale cancel flag at start of every new operation |
| Thread lock | `ECUComm._lock` | `_transact()` acquires lock — prevents DataLogger and FlashWorker from colliding on serial port |

---

## ECUComm State Machine

```
DISCONNECTED ──connect()──→ CONNECTED
CONNECTED ──disable_chatter()──→ SILENCED
SILENCED ──unlock_security()──→ UNLOCKED
UNLOCKED ──enter_programming()──→ PROGRAMMING
PROGRAMMING ──upload_kernel()──→ KERNEL_LOADED
KERNEL_LOADED ──(read/write/erase)──→ FLASHING
FLASHING ──cleanup_and_reset()──→ CONNECTED
CONNECTED ──disconnect()──→ DISCONNECTED
```

Any state can transition to `DISCONNECTED` via `disconnect()` or transport error.

---

## Event System (ECUComm callbacks)

`ECUComm.on(event, callback)` — lightweight pub/sub, no Qt dependency:

| Event | Payload | Where Consumed |
|-------|---------|----------------|
| `"log"` | `msg: str, level: str` | FlashWorker → `log_message` signal → LogWidget |
| `"progress"` | `current: int, total: int, label: str` | FlashWorker → `progress` signal → progress bar |
| `"state"` | `state: CommState` | FlashWorker → `state_changed` signal → state label |
| `"frame_tx"` | `frame_hex: str, length: int` | LogWidget (if `log_tx_frames` enabled) |
| `"frame_rx"` | `frame_hex: str, length: int, checksum_ok: bool` | LogWidget (if `log_rx_frames` enabled) |
| `"retry"` | `attempt: int, max_retries: int, reason: str` | LogWidget (if `log_retries` enabled) |

---

## CLI Commands (Section 13)

```
kingai_commie_flasher.py <command> [options]
```

| Command | Handler | Requires Connection? |
|---------|---------|---------------------|
| `gui` | Launches `MainWindow` | No |
| `read` | `ECUComm` → `FlashOp.full_read()` → file | Yes |
| `write` | `ECUComm` → `FlashOp.full_write()` | Yes |
| `datalog` | `ECUComm` → `DataLogger.start()` | Yes |
| `info` | `ECUComm` → `request_mode1()` | Yes |
| `checksum` | `BinFile.verify_checksum()` / `fix_checksum()` | No |
| `ports` | Lists serial ports | No |

CLI commands create their own `PySerialTransport` + `ECUComm` — completely independent of the GUI.

---

## Known Wiring Issues

| Issue | Status |
|-------|--------|
| `action_save_as` connects to `_save_bin()` — same as `action_save`, no "save as" dialog | ⚠ Open |
| `_show_ecu_info()` runs Mode 1 on GUI thread (blocks if PCM slow) | ⚠ Open |
| `btn_range_write` has no menu action — only reachable from Tab 5 button | By design — advanced feature |
| `_backup_bin` stored in memory only — lost on crash | ⚠ Open |
