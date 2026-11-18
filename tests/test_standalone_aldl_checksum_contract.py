"""Independent ALDL wire checks for the standalone VY RAM reader.

Synthetic/offline protocol tests only. They do not authorize a live PCM read
or flash and do not establish transport timing, pin-level BCM behavior or
ECU hardware compatibility.

The standalone checksum routine's argument is the complete byte prefix
*before* its checksum; callers already slice to that position.
"""
from __future__ import annotations

from tools import ALDL_read_RAM_commands as standalone
from kingai_commie_flasher import ALDLProtocol


def require(test: bool, reason: str) -> None:
    """Explicit failure so these tests also work with python -O."""
    if not test:
        raise AssertionError(reason)


def wire(frame: bytes | bytearray) -> bytes:
    length = frame[1] - 82
    require(length >= 4 and length <= len(frame), "invalid ALDL wire length")
    return bytes(frame[:length])


def test_known_mode8_mode9_checksum_includes_mode_byte() -> None:
    mode8 = wire(standalone.build_silence_frame(0xF7))
    mode9 = wire(standalone.build_unsilence_frame(0xF7))
    require(mode8 == bytes((0xF7, 0x56, 0x08, 0xAB)), "Mode 8 checksum mismatch")
    require(mode9 == bytes((0xF7, 0x56, 0x09, 0xAA)), "Mode 9 checksum mismatch")
    for frame in (mode8, mode9):
        require((sum(frame) & 0xFF) == 0, "on-wire checksum not zero-sum")
        require(standalone.verify_checksum(frame), "standalone rejects valid frame")
        require(ALDLProtocol.verify_checksum(bytearray(frame)),
                "main flasher rejects standalone frame")


def test_standard_and_extended_read_checksums_use_last_address_byte() -> None:
    cases = (
        (0x77C1, False, bytes((0xF7, 0x58, 0x02, 0x77, 0xC1, 0x77))),
        (0x18027, True, bytes((0xF7, 0x59, 0x02, 0x01, 0x80, 0x27, 0x06))),
    )
    for address, extended, expected in cases:
        result = wire(standalone.build_mode2_read(0xF7, address, extended=extended))
        require(result == expected, f"Mode 2 address {address:#x} checksum mismatch")
        require((sum(result) & 0xFF) == 0, "nonzero on-wire checksum")
        require(standalone.verify_checksum(result), "standalone rejects valid request")


def test_standalone_frames_match_independent_main_protocol_builder() -> None:
    cases = (
        (standalone.build_silence_frame(0xF7),
         ALDLProtocol.build_simple_frame(0xF7, 0x08)),
        (standalone.build_unsilence_frame(0xF7),
         ALDLProtocol.build_simple_frame(0xF7, 0x09)),
        (standalone.build_mode2_read(0xF7, 0x77C1),
         ALDLProtocol.build_mode2_read(0xF7, 0x77C1)),
        (standalone.build_mode2_read(0xF7, 0x18027, extended=True),
         ALDLProtocol.build_mode2_read(0xF7, 0x18027, extended=True)),
    )
    for standalone_frame, main_frame in cases:
        require(wire(standalone_frame) == wire(main_frame),
                "main ALDL protocol and standalone reader generate different wire bytes")


def test_verify_checksum_rejects_corrupted_mode_and_final_address_byte() -> None:
    original = wire(standalone.build_mode2_read(0xF7, 0x77C1))
    for index in (2, 3, 4, len(original)-1):
        tampered = bytearray(original)
        tampered[index] ^= 1
        require(not standalone.verify_checksum(tampered),
                f"corruption at byte {index} not rejected by standalone")
        require(not ALDLProtocol.verify_checksum(tampered),
                f"corruption at byte {index} not rejected by main flasher")


def test_loopback_nonzero_final_payload_byte_matches_wire_checksum() -> None:
    emu = standalone.LoopbackALDL()
    address = 0x77C1
    payload = bytes(range(1, 65))
    emu.flash[address:address+len(payload)] = payload
    response = emu.transact(standalone.build_mode2_read(0xF7, address))
    require(response is not None, "synthetic Mode 2 loopback no response")
    require(bytes(response[3:3+64]) == payload, "loopback source payload mismatch")
    require((sum(response) & 0xFF) == 0, "loopback wire checksum not zero-sum")
    require(standalone.verify_checksum(response), "standalone rejects valid loopback response")
    require(ALDLProtocol.verify_checksum(bytearray(response)),
            "main flasher rejects valid loopback response")
    wrong = bytearray(response)
    wrong[3+63] ^= 1  # Final data byte before checksum, exactly the prior bug.
    require(not standalone.verify_checksum(wrong),
            "corrupt final data byte incorrectly accepted")


def test_compute_checksum_prefix_contract_and_truncated_frame() -> None:
    prefix = bytearray((0xF7, 0x56, 0x08))
    require(standalone.compute_checksum(prefix) == 0xAB,
            "compute_checksum must include all supplied pre-checksum bytes")
    for malformed in (b"", b"\xf7", b"\xf7\x56", b"\xf7\x56\x08"):
        require(not standalone.verify_checksum(malformed),
                "short frame should never verify")
