"""Offline portability and evidence-preservation regressions."""
import os
from pathlib import Path
import subprocess
import sys

import pytest
from tools import ALDL_read_RAM_commands as reader

ROOT = Path(__file__).resolve().parents[1]


def invoke(tmp_path, script, *args, without_site=False):
    cwd = tmp_path / "arbitrary working directory"
    cwd.mkdir(exist_ok=True)
    env = dict(os.environ, KINGAI_FLASHER_DATA_DIR=str(tmp_path / "runtime data"),
               PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, *(["-S"] if without_site else []),
                           str(ROOT / script), *map(str, args)], cwd=cwd,
                          env=env, capture_output=True, text=True, timeout=30)


def test_cli_help_without_optional_dependencies_from_other_directory(tmp_path):
    result = invoke(tmp_path, "kingai_commie_flasher.py", "--help", without_site=True)
    assert result.returncode == 0, result.stderr
    assert "checksum" in result.stdout
    assert not (tmp_path / "arbitrary working directory" / "logs").exists()
    assert (tmp_path / "runtime data" / "logs").is_dir()


def test_missing_gui_dependency_is_clear(tmp_path):
    result = invoke(tmp_path, "kingai_commie_flasher.py", "gui", without_site=True)
    assert result.returncode == 1
    assert "PySide6 failed to load" in result.stdout


def test_checksum_requires_separate_output_and_preserves_source(tmp_path):
    source = tmp_path / "original image.bin"
    source.write_bytes(bytes(131072))
    result = invoke(tmp_path, "kingai_commie_flasher.py", "checksum", "--input", source,
                    "--fix", without_site=True)
    assert result.returncode == 2
    assert "--fix requires --output" in result.stderr
    output = tmp_path / "corrected copy.bin"
    result = invoke(tmp_path, "kingai_commie_flasher.py", "checksum", "--input", source,
                    "--fix", "--output", output, without_site=True)
    assert result.returncode == 0, result.stderr
    assert output.stat().st_size == 131072
    assert source.read_bytes() == bytes(131072)
    result = invoke(tmp_path, "kingai_commie_flasher.py", "checksum", "--input", source,
                    "--fix", "--output", output, without_site=True)
    assert result.returncode == 2
    assert "output already exists" in result.stderr


def test_invalid_cli_arguments_are_rejected_before_transport(tmp_path):
    for args in (("read", "--retries", "-1"), ("read", "--device-id", "nonsense"),
                 ("read", "--timeout", "0"), ("read", "--cal", "--cal-padded")):
        result = invoke(tmp_path, "kingai_commie_flasher.py", *args, without_site=True)
        assert result.returncode == 2, result.stderr
        assert "Connecting" not in result.stdout


def test_standalone_reader_exact_count_and_output_collision(tmp_path):
    output = tmp_path / "read evidence.bin"
    result = invoke(tmp_path, "tools/ALDL_read_RAM_commands.py", "--loopback", "--address",
                    "0x4000", "--count", "7", "--output", output, "--no-hexdump")
    assert result.returncode == 0, result.stderr
    assert output.read_bytes() == bytes(7)
    result = invoke(tmp_path, "tools/ALDL_read_RAM_commands.py", "--loopback", "--address",
                    "0x4000", "--output", output)
    assert result.returncode == 2
    assert output.read_bytes() == bytes(7)


@pytest.mark.parametrize("count", ["0", "-1", "131073"])
def test_standalone_reader_invalid_ranges(tmp_path, count):
    result = invoke(tmp_path, "tools/ALDL_read_RAM_commands.py", "--loopback", "--address",
                    "0", "--count", count)
    assert result.returncode == 2


def test_standalone_reader_rejects_missing_or_partial_virtual_input(tmp_path):
    with pytest.raises(FileNotFoundError):
        reader.LoopbackALDL(str(tmp_path / "missing.bin"))
    partial = tmp_path / "partial.bin"
    partial.write_bytes(b"evidence")
    with pytest.raises(ValueError, match="exactly"):
        reader.LoopbackALDL(str(partial))
    assert partial.read_bytes() == b"evidence"


def test_standalone_cli_image_errors_are_clear(tmp_path):
    partial = tmp_path / "partial evidence.bin"
    partial.write_bytes(b"evidence")
    for path in (tmp_path / "missing image.bin", partial):
        result = invoke(tmp_path, "tools/ALDL_read_RAM_commands.py", "--loopback",
                        "--bin-file", path, "--address", "0x4000")
        assert result.returncode == 1
        assert "ERROR:" in result.stderr
        assert "Traceback" not in result.stderr
    assert partial.read_bytes() == b"evidence"


def test_standalone_reader_refuses_malformed_responses():
    transport = reader.LoopbackALDL()
    valid = transport.transact(reader.build_mode2_read(0xF7, 0x4000))
    assert reader.read_ram(transport, 0x4000) == bytes(64)
    class Response:
        def __init__(self, frame):
            self.frame = frame
        def transact(self, request):
            return self.frame
    for malformed in (b"", b"\xf7", valid[:-1], valid + b"\x00",
                      bytes([0xF5]) + valid[1:], valid[:-1] + bytes([valid[-1] ^ 1])):
        assert reader.read_ram(Response(malformed), 0x4000) is None


def test_comparison_and_checksum_helpers_use_explicit_files(tmp_path):
    reference = tmp_path / "reference image.bin"
    short = tmp_path / "truncated evidence.bin"
    reference.write_bytes(bytes(32768))
    short.write_bytes(bytes(32767))
    result = invoke(tmp_path, "tests/_compare_bins.py", reference, short)
    assert result.returncode == 0, result.stderr
    assert "differences=1" in result.stdout
    result = invoke(tmp_path, "tests/_checksum_investigate.py", reference, short)
    assert result.returncode == 2
    assert "complete calibration area" in result.stderr


def test_unwritable_runtime_directory_keeps_help_available(tmp_path):
    blocked = tmp_path / "runtime data"
    blocked.write_bytes(b"existing evidence")
    result = invoke(tmp_path, "kingai_commie_flasher.py", "--help", without_site=True)
    assert result.returncode == 0
    assert "cannot write logs" in result.stderr
    assert blocked.read_bytes() == b"existing evidence"


def test_virtual_server_invalid_cli_inputs_fail_before_starting(tmp_path):
    partial = tmp_path / "partial image.bin"
    partial.write_bytes(b"partial")
    for args in (("--port", "0"), ("--bin", "absent.bin"),
                 ("--bin", str(partial)),
                 ("--mode", "send", "--frame", "wrong"),
                 ("--mode", "send", "--frame", "F7 01 02")):
        result = invoke(tmp_path, "tools/virtual_aldl_frame_sender_and_vecu.py", *args,
                        without_site=True)
        assert result.returncode == 2, result.stderr


def test_virtual_server_refuses_malformed_frames_and_invalid_inputs(tmp_path):
    from tools import virtual_aldl_frame_sender_and_vecu as server
    with pytest.raises(FileNotFoundError):
        server.VirtualECU(str(tmp_path / "missing.bin"))
    partial = tmp_path / "partial.bin"
    partial.write_bytes(b"actual evidence")
    with pytest.raises(ValueError):
        server.VirtualECU(str(partial))
    ecu = server.VirtualECU()
    original = bytes(ecu.flash)
    for frame in (b"", b"\xf7\x56\x02\xb1", b"\xf7\x56\x10\xa3"):
        assert ecu.process_frame(frame) is None
        assert bytes(ecu.flash) == original
    assert not ecu.erase_sector(-1)
    assert not ecu.erase_sector(8)


def test_standalone_incomplete_read_preserves_exact_prefix_and_bad_frame():
    class Partial:
        def __init__(self):
            self.calls = 0
        def transact(self, frame):
            self.calls += 1
            if self.calls == 1:
                response = bytearray(reader.LoopbackALDL().transact(frame))
                response[3:67] = bytes(range(64))
                reader.apply_checksum(response)
                return bytes(response)
            return b"partial raw response"
    transport = Partial()
    assert reader.read_range(transport, 0x4000, 128) is None
    assert transport.partial_read == bytes(range(64))
    assert transport.failed_read_address == 0x4040
    assert transport.last_read_response == b"partial raw response"


def test_standalone_cli_failure_saves_incomplete_evidence_only(tmp_path, monkeypatch):
    import json
    actual = reader.LoopbackALDL()
    class Partial:
        def __init__(self):
            self.calls = 0
        def open(self):
            pass
        def close(self):
            pass
        def transact(self, frame):
            self.calls += 1
            return actual.transact(frame) if self.calls == 1 else b"bad last frame"
    monkeypatch.setattr(reader, "LoopbackALDL", lambda **kwargs: Partial())
    output = tmp_path / "capture.bin"
    monkeypatch.setattr(sys, "argv", ["reader", "--loopback", "--address", "0x4000",
                                     "--count", "128", "--output", str(output)])
    assert reader.main() == 1
    assert not output.exists()
    assert Path(str(output) + ".partial").read_bytes() == bytes(64)
    metadata = json.loads(Path(str(output) + ".partial.json").read_text())
    assert metadata["status"] == "incomplete"
    assert metadata["complete_bytes"] == 64
    assert metadata["failed_response_hex"] == b"bad last frame".hex()
