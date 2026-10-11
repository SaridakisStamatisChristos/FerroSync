import errno
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from ferrosync.engine import SyncPair
from ferrosync.errors import PathSafetyError, RecoveryRequired, StalePlanError
from ferrosync.model import Entry, Snapshot
from ferrosync.planner import build_plan


class AdversarialTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        base = Path(self.td.name)
        self.l, self.r = base/"left", base/"right"
        self.l.mkdir(); self.r.mkdir()
        self.p = SyncPair.open(self.l, self.r)

    def tearDown(self):
        self.td.cleanup()

    def test_stale_plan_refuses_newer_destination(self):
        (self.l/"a").write_text("base")
        self.p.sync()
        (self.l/"a").write_text("left-v2")
        plan = self.p.plan()
        (self.r/"a").write_text("right-raced")
        with self.assertRaises(StalePlanError):
            self.p.apply(plan)
        self.assertEqual((self.l/"a").read_text(), "left-v2")
        self.assertEqual((self.r/"a").read_text(), "right-raced")

    def test_casefold_collision_fails_safe(self):
        # Exercise the portable logical namespace directly. Some CI filesystems
        # are case-insensitive and cannot physically represent both spellings.
        left = Snapshot({
            "A.txt": Entry("A.txt", "file", digest="0" * 64, size=3),
            "a.txt": Entry("a.txt", "file", digest="1" * 64, size=3),
        })
        plan = build_plan(left, Snapshot({}), None)
        self.assertTrue(any(c.kind == "case-collision" for c in plan.conflicts))
        self.assertFalse(plan.operations)

    def test_file_directory_collision_is_conflict(self):
        (self.l/"x").write_text("file")
        (self.r/"x").mkdir()
        self.assertTrue(self.p.plan().has_conflicts)

    def test_zero_byte_unicode_and_empty_directory(self):
        (self.l/"κενό.txt").write_bytes(b"")
        (self.l/"empty-dir").mkdir()
        self.p.sync()
        self.assertEqual((self.r/"κενό.txt").read_bytes(), b"")
        self.assertTrue((self.r/"empty-dir").is_dir())

    def test_large_file(self):
        data = (b"0123456789abcdef" * (512 * 1024))  # 8 MiB
        (self.l/"large.bin").write_bytes(data)
        self.p.sync()
        self.assertEqual((self.r/"large.bin").read_bytes(), data)

    def test_source_disappearing_during_scan_is_rejected(self):
        f = self.l/"volatile"
        f.write_text("x")
        import ferrosync.scanner as scanner
        original = scanner.file_sha256
        def disappearing(path):
            result = original(path)
            Path(path).unlink()
            return result
        with mock.patch("ferrosync.scanner.file_sha256", side_effect=disappearing):
            with self.assertRaises(PathSafetyError):
                self.p.plan()

    def test_permission_error_during_scan_is_rejected(self):
        import ferrosync.scanner as scanner
        original = scanner.os.scandir
        def denied(path):
            # SyncPair canonicalizes roots. Compare against that canonical root
            # so macOS /var -> /private/var and Windows path normalization do
            # not bypass the injected permission failure.
            if Path(path).resolve() == self.p.left:
                raise PermissionError(errno.EACCES, "denied")
            return original(path)
        with mock.patch("ferrosync.scanner.os.scandir", side_effect=denied):
            with self.assertRaises(PathSafetyError):
                self.p.plan()

    def test_disk_full_leaves_baseline_unadvanced_and_recoverable_journal(self):
        (self.l/"a").write_bytes(b"x" * 1024)
        with mock.patch("ferrosync.engine.os.write", side_effect=OSError(errno.ENOSPC, "disk full")):
            with self.assertRaises(OSError):
                self.p.sync()
        self.assertFalse(self.p.state.baseline_path.exists())
        self.assertEqual(len(self.p.state.incomplete_journals()), 1)
        self.p.recover()
        self.assertEqual((self.r/"a").read_bytes(), b"x" * 1024)

    def test_unexpected_temp_artifact_detected(self):
        (self.l/"a").write_text("x")
        self.p.sync()
        (self.l/".x.ferrosync-tmp-deadbeef-op").write_text("orphan")
        result = self.p.verify()
        self.assertFalse(result["ok"])
        self.assertTrue(any("temporary" in x for x in result["issues"]))

    def test_directory_rename_with_peer_child_edit_preserves_both(self):
        (self.l/"d").mkdir(); (self.l/"d"/"a").write_text("base")
        self.p.sync()
        os.rename(self.l/"d", self.l/"renamed")
        (self.r/"d"/"a").write_text("peer edit")
        plan = self.p.plan()
        self.assertTrue(plan.has_conflicts)
        self.assertEqual((self.l/"renamed"/"a").read_text(), "base")
        self.assertEqual((self.r/"d"/"a").read_text(), "peer edit")

    def test_destination_appearing_at_commit_is_not_overwritten(self):
        (self.l/"a").write_text("source")
        class RaceInjector:
            def __init__(self, dest): self.dest=dest; self.done=False
            def hit(self, label):
                if label == "before_rename" and not self.done:
                    self.dest.write_text("raced")
                    self.done=True
        with self.assertRaises(StalePlanError):
            self.p.sync(fault=RaceInjector(self.r/"a"))
        self.assertEqual((self.l/"a").read_text(), "source")
        self.assertEqual((self.r/"a").read_text(), "raced")
        self.assertFalse(self.p.state.baseline_path.exists())

    def test_source_change_in_final_window_prevents_commit_baseline(self):
        (self.l/"a").write_text("source-v1")
        class SourceRaceInjector:
            def __init__(self, src): self.src=src; self.done=False
            def hit(self, label):
                if label == "before_rename" and not self.done:
                    self.src.write_text("source-v2")
                    self.done=True
        with self.assertRaises(RecoveryRequired):
            self.p.sync(fault=SourceRaceInjector(self.l/"a"))
        self.assertEqual((self.l/"a").read_text(), "source-v2")
        self.assertEqual((self.r/"a").read_text(), "source-v1")
        self.assertFalse(self.p.state.baseline_path.exists())

    def test_strange_legal_and_long_filename(self):
        name = "space [x];#-" + ("n" * 120) + ".txt"
        (self.l/name).write_text("ok")
        self.p.sync()
        self.assertEqual((self.r/name).read_text(), "ok")


if __name__ == "__main__":
    unittest.main()
