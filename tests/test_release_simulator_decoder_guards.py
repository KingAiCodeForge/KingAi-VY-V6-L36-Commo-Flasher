"""Synthetic regressions for simulator and decoder software contracts only."""
import pytest
import virtual_128kb_eeprom as v
from tools.hc11_disassembler import HC11Disassembler


def test_program_f0_is_data_after_program_command():
    flash = v.AMD29F010()
    assert flash.program_byte_at(0x1234, 0xF0) is True
    assert flash.read(0x1234) == 0xF0
    assert flash.stats['programs'] == 1


@pytest.mark.parametrize('address', [-1, v.FLASH_SIZE, v.FLASH_SIZE + 10, True, '4'])
def test_invalid_program_address_fails_before_state_or_data_changes(address):
    flash = v.AMD29F010()
    before = bytes(flash.data)
    with pytest.raises(ValueError, match='address'):
        flash.program_byte_at(address, 0x42)
    assert bytes(flash.data) == before
    assert flash.state == v.FlashState.READ
    assert flash.stats['programs'] == 0


@pytest.mark.parametrize('value', [-1, 256, True, '42'])
def test_invalid_program_value_fails_before_unlock_sequence(value):
    flash = v.AMD29F010()
    with pytest.raises(ValueError, match='byte'):
        flash.program_byte_at(0x1234, value)
    assert flash.state == v.FlashState.READ
    assert flash.read(0x1234) == 0xFF


@pytest.mark.parametrize('operation', ['read', 'write'])
def test_low_level_invalid_address_does_not_alias_flash(operation):
    flash = v.AMD29F010()
    with pytest.raises(ValueError):
        if operation == 'read':
            flash.read(-1)
        else:
            flash.write(v.FLASH_SIZE, v.CMD_RESET)
    assert flash.stats['resets'] == 0
    assert flash.state == v.FlashState.READ


def test_protected_sector_erase_reports_failure_without_modifying_bytes():
    flash = v.AMD29F010()
    flash.data[0x4000] = 0
    flash._sector_protect[1] = v.SECTOR_PROTECT_PROTECTED
    assert flash.erase_sector_by_index(1) is False
    assert flash.read(0x4000) == 0
    assert flash.stats['sector_erases'] == 0


def test_protected_byte_program_reports_failure():
    flash = v.AMD29F010()
    flash._sector_protect[1] = v.SECTOR_PROTECT_PROTECTED
    assert flash.program_byte_at(0x4000, 0x42) is False
    assert flash.read(0x4000) == 0xFF


def test_chip_erase_refuses_protected_contents_in_the_functional_model():
    flash = v.AMD29F010()
    flash.data[0x4000] = 0
    flash._sector_protect[1] = v.SECTOR_PROTECT_PROTECTED
    for address, value in [(v.CMD_ADDR_1, v.CMD_UNLOCK_1), (v.CMD_ADDR_2, v.CMD_UNLOCK_2),
                           (v.CMD_ADDR_1, v.CMD_ERASE_SETUP), (v.CMD_ADDR_1, v.CMD_UNLOCK_1),
                           (v.CMD_ADDR_2, v.CMD_UNLOCK_2), (v.CMD_ADDR_1, v.CMD_CHIP_ERASE)]:
        flash.write(address, value)
    assert flash.poll(0x4000) == (True, True)
    assert flash.read(0x4000) == 0
    assert flash.stats['chip_erases'] == 0


@pytest.mark.parametrize('bank,address', [(0x58, 0), (0x58, 0x7FFF), (0x50, 0x10000),
                                         (0x48, -1), (0, 0x8000), (0x48, True)])
def test_invalid_bank_window_is_rejected(bank, address):
    banked = v.BankedFlash()
    with pytest.raises(ValueError):
        banked.cpu_to_flash_addr(address, bank)


@pytest.mark.parametrize('bank,cpu,expected', [(0x48, 0, 0), (0x48, 0xFFFF, 0xFFFF),
    (0x58, 0x8000, 0x10000), (0x58, 0xFFFF, 0x17FFF),
    (0x50, 0x8000, 0x18000), (0x50, 0xFFFF, 0x1FFFF)])
def test_valid_bank_boundaries_map_exactly(bank, cpu, expected):
    assert v.BankedFlash().cpu_to_flash_addr(cpu, bank) == expected


@pytest.mark.parametrize('offset', [-1, True, '0'])
def test_decoder_rejects_invalid_offset_instead_of_empty_instruction(offset):
    with pytest.raises(ValueError, match='offset'):
        HC11Disassembler().decode_one(b'\x86\x42', offset=offset)


def test_decoder_preserves_all_bytes_of_unknown_or_truncated_instructions():
    decoder = HC11Disassembler()
    for source in (b'\x18', b'\x18\x00', b'\xB6\x77', bytes(range(256))):
        decoded = decoder.disassemble(source)
        assert all(inst.length > 0 for inst in decoded)
        assert b''.join(inst.raw_bytes for inst in decoded) == source


@pytest.mark.parametrize('data', [0, 8, True, False])
def test_decoder_rejects_integer_input_instead_of_fabricating_zero_bytes(data):
    with pytest.raises(TypeError, match='byte data'):
        HC11Disassembler().disassemble(data)
