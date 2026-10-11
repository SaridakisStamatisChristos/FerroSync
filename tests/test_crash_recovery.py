import tempfile
import unittest
from pathlib import Path

from ferrosync.engine import SyncPair
from ferrosync.errors import InjectedCrash
from ferrosync.faults import FaultInjector


class CrashRecoveryTests(unittest.TestCase):
    def _case(self, label):
        td=tempfile.TemporaryDirectory(); base=Path(td.name)
        l=base/"l"; r=base/"r"; l.mkdir(); r.mkdir()
        (l/"a").write_text("alpha" * 100)
        p=SyncPair.open(l,r)
        with self.assertRaises(InjectedCrash):
            p.sync(fault=FaultInjector(label))
        result=p.recover()
        self.assertTrue(result["recovered"])
        self.assertEqual((l/"a").read_bytes(), (r/"a").read_bytes())
        self.assertTrue(p.verify()["ok"])
        td.cleanup()

    def test_declared_crash_boundaries(self):
        for label in [
            "after_journal_creation", "before_source_read", "during_copy", "after_temp_write",
            "after_file_fsync", "before_rename", "after_rename", "before_directory_fsync",
            "after_operation", "before_verification", "after_verification", "before_baseline_write",
            "during_baseline_write", "after_baseline_replace", "before_journal_finalize",
        ]:
            with self.subTest(label=label):
                self._case(label)

    def test_repeated_recovery_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td); l=base/"l"; r=base/"r"; l.mkdir(); r.mkdir(); (l/"a").write_text("x")
            p=SyncPair.open(l,r)
            with self.assertRaises(InjectedCrash):
                p.sync(fault=FaultInjector("after_rename"))
            first=p.recover()
            second=p.recover()
            self.assertTrue(first["recovered"])
            self.assertEqual(second["status"], "CLEAN")

    def test_exact_rename_recovery_after_destination_creation(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td); l=base/"l"; r=base/"r"; l.mkdir(); r.mkdir(); (l/"old").write_text("x")
            p=SyncPair.open(l,r); p.sync(); os = __import__("os"); os.rename(l/"old", l/"new")
            with self.assertRaises(InjectedCrash):
                p.sync(fault=FaultInjector("after_rename"))
            p.recover()
            self.assertFalse((r/"old").exists())
            self.assertEqual((r/"new").read_text(), "x")
            self.assertTrue(p.verify()["ok"])

    def test_recovery_can_itself_be_interrupted_and_retried(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td); l=base/"l"; r=base/"r"; l.mkdir(); r.mkdir(); (l/"a").write_text("x")
            p=SyncPair.open(l,r)
            with self.assertRaises(InjectedCrash):
                p.sync(fault=FaultInjector("after_rename"))
            with self.assertRaises(InjectedCrash):
                p.recover(fault=FaultInjector("before_baseline_write"))
            p.recover()
            self.assertTrue(p.verify()["ok"])
            self.assertEqual((l/"a").read_text(), (r/"a").read_text())


if __name__ == "__main__":
    unittest.main()
