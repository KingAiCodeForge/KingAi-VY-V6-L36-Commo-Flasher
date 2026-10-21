"""Wire-vector tests for the standalone ALDL reader (no serial hardware).

Checksums are checked using the independent additive invariant, not the
reader's own checksum calculation, so mirrored encode/decode bugs are caught.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "tools" / "ALDL_read_RAM_commands.py"
SPEC = importlib.util.spec_from_file_location("standalone_aldl_reader", SOURCE)
reader = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(reader)


def wire(frame: bytes | bytearray) -> bytes:
    """Return exactly the ALDL bytes declared by the header."""
    return bytes(frame[:frame[1] - 82])


class ALDLStandaloneChecksumVectors(unittest.TestCase):
    def assert_valid_wire(self, frame):
        raw = wire(frame)
        self.assertEqual(len(raw), raw[1] - 82)
        self.assertEqual(sum(raw) & 0xFF, 0, raw.hex())
        self.assertTrue(reader.verify_checksum(raw))
        return raw

    def test_mode_2_standard_includes_low_address_byte(self):
        raw = self.assert_valid_wire(reader.build_mode2_read(0xF7, 0x77C0))
        self.assertEqual(raw, bytes.fromhex("F7 58 02 77 C0 78"))

    def test_mode_2_extended_includes_low_address_byte(self):
        raw = self.assert_valid_wire(reader.build_mode2_read(0xF7, 0x0177C0, extended=True))
        self.assertEqual(raw, bytes.fromhex("F7 59 02 01 77 C0 76"))

    def test_mode_8_and_9_full_wire_vectors(self):
        silence = self.assert_valid_wire(reader.build_silence_frame(0xF7))
        unsilence = self.assert_valid_wire(reader.build_unsilence_frame(0xF7))
        self.assertEqual(silence, bytes.fromhex("F7 56 08 AB"))
        self.assertEqual(sum(unsilence) & 0xFF, 0)

    def test_standalone_loopback_ack_no_index_error(self):
        loop = reader.LoopbackALDL()
        for mode, command in (
            (reader.MODE8_SILENCE, reader.build_silence_frame(0xF7)),
            (reader.MODE9_UNSILENCE, reader.build_unsilence_frame(0xF7)),
        ):
            response = loop.transact(command)
            self.assertIsNotNone(response)
            self.assertEqual(response[2], mode)
            self.assert_valid_wire(response)

    def test_last_data_byte_alters_checksum(self):
        loop = reader.LoopbackALDL()
        offset = 0x77C0
        loop.flash[offset:offset + 64] = bytes(range(1, 65))
        response = loop.transact(reader.build_mode2_read(0xF7, offset))
        self.assertIsNotNone(response)
        self.assert_valid_wire(response)
        self.assertEqual(response[-2], 64)
        corrupted = bytearray(response)
        corrupted[-2] ^= 0x01
        self.assertFalse(reader.verify_checksum(corrupted))
        self.assertEqual(reader.read_ram(loop, offset), bytes(range(1, 65)))

    def test_standalone_loopback_rejects_bad_request(self):
        loop = reader.LoopbackALDL()
        request = reader.build_mode2_read(0xF7, 0x77C0)
        request[4] ^= 0x01
        self.assertIsNone(loop.transact(request))

    def test_address_ranges_fail_closed(self):
        for invalid in (-1, 0x10000):
            with self.subTest(standard=invalid), self.assertRaises(ValueError):
                reader.build_mode2_read(0xF7, invalid)
        for invalid in (-1, 0x1000000):
            with self.subTest(extended=invalid), self.assertRaises(ValueError):
                reader.build_mode2_read(0xF7, invalid, extended=True)
        self.assert_valid_wire(reader.build_mode2_read(0xF7, 0xFFFF))
        self.assert_valid_wire(reader.build_mode2_read(0xF7, 0xFFFFFF, extended=True))

    def test_truncated_frame_is_rejected(self):
        request = wire(reader.build_mode2_read(0xF7, 0x77C0))
        self.assertFalse(reader.verify_checksum(request[:-1]))
        with self.assertRaises(ValueError):
            reader.apply_checksum(bytearray([0xF7, 0x56, 0x08]))


if __name__ == "__main__":
    unittest.main()
