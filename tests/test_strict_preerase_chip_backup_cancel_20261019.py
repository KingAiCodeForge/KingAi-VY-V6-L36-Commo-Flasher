"""Offline mock-only fail-closed pre-erase regression cases.

No ALDL transport, connected ECU, sector erase, or hardware interaction.
The erase method is a mocked sentinel returning False even for a valid backup.
"""
import unittest
from unittest.mock import Mock, patch
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kingai_commie_flasher as f

def comm():
    c = Mock()
    c.cancelled = False
    c.disable_chatter.return_value = True
    c.unlock_security.return_value = True
    c.enter_programming.return_value = True
    c.upload_kernel.return_value = True
    c.read_flash_info.return_value = f.FLASH_AMD_29F010
    c.read_ram.return_value = b"Y"*64
    c.erase_sectors.return_value = False
    c.config.auto_checksum_fix = False
    c.config.baud = 8192
    c.config.high_speed_read = False
    return c

def attempted_cal_write(c):
    p = f.FlashOp(c)
    with patch.object(f.BinFile, "verify_checksum", return_value=True):
        with patch.object(f.time, "sleep", return_value=None):
            result = p.full_write(bytearray(f.BinFile.BIN_SIZE), mode="CAL")
    return p, result

class StrictPreErase(unittest.TestCase):
    def test_wrong_chip_variants_never_read_or_erase(self):
        for chip in [None, (), {"synthetic": True}, (0x01,0xA4), (0x31,0xB4), (0xFF,0xFF)]:
            with self.subTest(chip=chip):
                c=comm();c.read_flash_info.return_value=chip
                p,ok=attempted_cal_write(c)
                self.assertFalse(ok);self.assertIsNone(p._backup_bin)
                c.read_ram.assert_not_called();c.erase_sectors.assert_not_called()
                c.cleanup_and_reset.assert_called_once()

    def test_short_and_oversized_backup_frames_never_erase(self):
        for n in (0,1,63,65,128):
            with self.subTest(n=n):
                c=comm();c.read_ram.return_value=b"Y"*n
                p,ok=attempted_cal_write(c)
                self.assertFalse(ok);self.assertIsNone(p._backup_bin)
                c.erase_sectors.assert_not_called()

    def test_cancel_before_first_backup_read(self):
        c=comm();c.cancelled=True
        p,ok=attempted_cal_write(c)
        self.assertFalse(ok);self.assertIsNone(p._backup_bin)
        c.read_ram.assert_not_called();c.erase_sectors.assert_not_called()

    def test_cancel_after_second_read(self):
        c=comm()
        def read(address,extended=True):
            if c.read_ram.call_count==2:c.cancelled=True
            return b"Y"*64
        c.read_ram.side_effect=read
        p,ok=attempted_cal_write(c)
        self.assertFalse(ok);self.assertIsNone(p._backup_bin)
        self.assertEqual(c.read_ram.call_count,2)
        c.erase_sectors.assert_not_called()

    def test_cancel_on_final_calibration_read(self):
        c=comm()
        def read(address,extended=True):
            if address==0x7FC0:c.cancelled=True
            return b"Y"*64
        c.read_ram.side_effect=read
        p,ok=attempted_cal_write(c)
        self.assertFalse(ok);self.assertIsNone(p._backup_bin)
        c.erase_sectors.assert_not_called()

    def test_cancel_in_backup_status_callback(self):
        c=comm()
        def emit(event,**kwargs):
            if kwargs.get("msg","").startswith("Backup complete"):
                c.cancelled=True
        c.emit.side_effect=emit
        p,ok=attempted_cal_write(c)
        self.assertFalse(ok);self.assertIsNone(p._backup_bin)
        c.erase_sectors.assert_not_called()

    def test_exact_chip_and_exact_complete_frames_reach_only_mock_erase(self):
        c=comm()
        p,ok=attempted_cal_write(c)
        self.assertFalse(ok) # mock erase denies progression
        self.assertIsNotNone(p._backup_bin)
        c.erase_sectors.assert_called_once()
        c.write_flash_data.assert_not_called()

if __name__=="__main__":
    unittest.main()
