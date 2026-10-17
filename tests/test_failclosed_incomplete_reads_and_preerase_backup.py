"""Offline-only regression tests for partial-read and pre-erase backup refusal.

Mock ECU. No serial adapter, PCM, security key or erase operation is performed.
"""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import Mock, patch
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import kingai_commie_flasher as flasher


def fake_comm(read_return=None):
    comm = Mock()
    comm.cancelled = False
    comm.disable_chatter.return_value = True
    comm.unlock_security.return_value = True
    comm.enter_programming.return_value = True
    comm.upload_kernel.return_value = True
    comm.read_flash_info.return_value = {"synthetic": True}
    comm.read_ram.return_value = read_return
    comm.erase_sectors.return_value = False
    comm.write_flash_data.return_value = False
    comm.config.baud = 8192
    comm.config.high_speed_read = False
    comm.config.write_chunk_size = 32
    comm.config.auto_checksum_fix = False
    return comm


class FailClosedReadTests(unittest.TestCase):
    def test_full_read_all_retries_exhausted_does_not_return_zero_filled_bin(self):
        comm = fake_comm(read_return=None)
        with patch.object(flasher.time, "sleep", return_value=None):
            result = flasher.FlashOp(comm).full_read()
        self.assertIsNone(result)
        comm.cleanup_and_reset.assert_called_once()
        comm.enable_chatter.assert_called()
        self.assertEqual(comm.read_ram.call_count, flasher.READ_BLOCK_MAX_RETRIES)

    def test_full_read_truncated_nonempty_chunks_are_not_success(self):
        comm = fake_comm(read_return=b"A" * 16)
        with patch.object(flasher.time, "sleep", return_value=None):
            result = flasher.FlashOp(comm).full_read()
        self.assertIsNone(result)
        self.assertEqual(comm.read_ram.call_count, flasher.READ_BLOCK_MAX_RETRIES)

    def test_full_read_complete_mock_blocks_can_return_full_bin(self):
        comm = fake_comm(read_return=b"R" * 64)
        with patch.object(flasher.time, "sleep", return_value=None):
            result = flasher.FlashOp(comm).full_read()
        self.assertIsNotNone(result)
        self.assertEqual(len(result), flasher.BinFile.BIN_SIZE)
        self.assertEqual(bytes(result), b"R" * flasher.BinFile.BIN_SIZE)
        self.assertEqual(comm.read_ram.call_count, flasher.BinFile.BIN_SIZE // 64)

    def test_custom_read_retry_exhaustion_returns_none_not_partial_zeros(self):
        comm = fake_comm(read_return=None)
        with patch.object(flasher.time, "sleep", return_value=None):
            result = flasher.FlashOp(comm).custom_read(0x2000,0x203F)
        self.assertIsNone(result)
        comm.cleanup_and_reset.assert_called_once()
        self.assertEqual(comm.read_ram.call_count, flasher.READ_BLOCK_MAX_RETRIES)

    def test_custom_read_short_nonempty_chunk_exhaustion_returns_none(self):
        comm = fake_comm(read_return=b"A" * 8)
        with patch.object(flasher.time, "sleep", return_value=None):
            result = flasher.FlashOp(comm).custom_read(0x2000,0x203F)
        self.assertIsNone(result)

    def test_custom_read_retry_count_resets_after_successful_block(self):
        comm = fake_comm()
        # First block 1 failure -> success, next block 1 failure -> success.
        comm.read_ram.side_effect = [None,b"A"*64,None,b"B"*64]
        with patch.object(flasher.time, "sleep", return_value=None):
            result = flasher.FlashOp(comm).custom_read(0x2000,0x207F)
        self.assertEqual(result,bytearray(b"A"*64 + b"B"*64))
        self.assertEqual(comm.read_ram.call_count,4)


class PreEraseBackupTests(unittest.TestCase):
    def _write(self,read_return):
        comm=fake_comm(read_return=read_return)
        op=flasher.FlashOp(comm)
        payload=bytearray(b"\xFF" * flasher.BinFile.BIN_SIZE)
        with patch.object(flasher.BinFile,"verify_checksum",return_value=True):
            with patch.object(flasher.time,"sleep",return_value=None):
                result=op.full_write(payload,mode="CAL")
        return op,comm,result

    def test_missing_prewrite_backup_aborts_before_erase(self):
        op,comm,result=self._write(None)
        self.assertFalse(result)
        self.assertIsNone(op._backup_bin)
        comm.erase_sectors.assert_not_called()
        comm.write_flash_data.assert_not_called()
        comm.cleanup_and_reset.assert_called_once()

    def test_truncated_prewrite_backup_aborts_before_erase(self):
        op,comm,result=self._write(b"B"*8)
        self.assertFalse(result)
        self.assertIsNone(op._backup_bin)
        comm.erase_sectors.assert_not_called()
        comm.write_flash_data.assert_not_called()

    def test_complete_mock_prewrite_backup_can_reach_erase_gate(self):
        op,comm,result=self._write(b"B"*64)
        self.assertFalse(result)  # erase mock deliberately refuses
        self.assertIsNotNone(op._backup_bin)
        comm.erase_sectors.assert_called_once()
        comm.write_flash_data.assert_not_called()


if __name__=="__main__":
    unittest.main()
