import os
import tempfile
import unittest
from pathlib import Path

from ferrosync.engine import SyncPair
from ferrosync.errors import ConflictError, StalePlanError


class SyncIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.left, self.right = base / "left", base / "right"
        self.left.mkdir(); self.right.mkdir()
        self.pair = SyncPair.open(self.left, self.right)

    def tearDown(self):
        self.tmp.cleanup()

    def test_initial_and_incremental_bidirectional_sync(self):
        (self.left / "left.txt").write_text("L")
        (self.right / "right.txt").write_text("R")
        result = self.pair.sync()
        self.assertEqual(result["status"], "COMMITTED")
        self.assertEqual((self.right / "left.txt").read_text(), "L")
        self.assertEqual((self.left / "right.txt").read_text(), "R")
        (self.left / "left.txt").write_text("L2")
        (self.right / "right.txt").write_text("R2")
        self.pair.sync()
        self.assertEqual((self.right / "left.txt").read_text(), "L2")
        self.assertEqual((self.left / "right.txt").read_text(), "R2")
        self.assertTrue(self.pair.verify()["ok"])

    def test_conflict_preserves_both_versions(self):
        (self.left / "a").write_text("base")
        self.pair.sync()
        (self.left / "a").write_text("left")
        (self.right / "a").write_text("right")
        with self.assertRaises(ConflictError):
            self.pair.sync()
        self.assertEqual((self.left / "a").read_text(), "left")
        self.assertEqual((self.right / "a").read_text(), "right")

    def test_delete_propagation_is_baseline_gated(self):
        (self.left / "a").write_text("x")
        self.pair.sync()
        (self.left / "a").unlink()
        self.pair.sync()
        self.assertFalse((self.right / "a").exists())

    def test_noop_sync_does_not_change_baseline_bytes(self):
        (self.left / "a").write_text("x")
        self.pair.sync()
        before = self.pair.state.baseline_path.read_bytes()
        result = self.pair.sync()
        after = self.pair.state.baseline_path.read_bytes()
        self.assertEqual(result["status"], "NOOP")
        self.assertEqual(before, after)

    @unittest.skipIf(os.name == "nt", "symlink creation may require Windows developer mode")
    def test_symlink_copied_not_followed(self):
        target = self.left / "target"
        target.write_text("secret")
        os.symlink("target", self.left / "link")
        self.pair.sync()
        self.assertTrue((self.right / "link").is_symlink())
        self.assertEqual(os.readlink(self.right / "link"), "target")

    def test_exact_content_rename_applies_bidirectionally(self):
        (self.left / "old.txt").write_text("payload")
        self.pair.sync()
        os.rename(self.left / "old.txt", self.left / "new.txt")
        result = self.pair.sync()
        self.assertEqual(result["status"], "COMMITTED")
        self.assertFalse((self.right / "old.txt").exists())
        self.assertEqual((self.right / "new.txt").read_text(), "payload")

    def test_status_reports_committed_baseline_and_no_pending_changes(self):
        (self.left / "a").write_text("x")
        self.pair.sync()
        status = self.pair.status()
        self.assertIsNotNone(status["baseline_id"])
        self.assertIsNotNone(status["last_successful_sync_ns"])
        self.assertEqual(status["pending_operations"], 0)
        self.assertEqual(status["detected_conflicts"], 0)
        self.assertFalse(status["incomplete_prior_run"])


if __name__ == "__main__":
    unittest.main()
