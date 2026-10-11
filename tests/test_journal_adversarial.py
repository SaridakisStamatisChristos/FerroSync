import tempfile
import unittest
from pathlib import Path

from ferrosync.engine import SyncPair
from ferrosync.errors import InjectedCrash, StateError
from ferrosync.faults import FaultInjector
from ferrosync.util import read_checked_json, write_checked_json


class JournalAdversarialTests(unittest.TestCase):
    def test_duplicate_operation_id_is_rejected_on_recovery(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td); l=base/"l"; r=base/"r"; l.mkdir(); r.mkdir(); p=SyncPair.open(l,r)
            (l/"a").write_text("a"); (l/"b").write_text("b")
            with self.assertRaises(InjectedCrash):
                p.sync(fault=FaultInjector("after_journal_creation"))
            path, journal = p.state.incomplete_journals()[0]
            plan = journal["plan"]
            plan["operations"][1]["id"] = plan["operations"][0]["id"]
            # Recompute outer plan id/checksum: semantic validation must still reject duplicates.
            logical = {k: plan[k] for k in ("version", "baseline_id", "operations", "conflicts")}
            from ferrosync.util import sha256_json
            plan["plan_id"] = sha256_json(logical)
            journal["operations"][1]["spec"] = plan["operations"][1]
            write_checked_json(path, journal)
            p.state.release_lock(force=True)
            with self.assertRaises(StateError):
                p.recover()

    def test_truncated_journal_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td); l=base/"l"; r=base/"r"; l.mkdir(); r.mkdir(); p=SyncPair.open(l,r)
            (l/"a").write_text("a")
            with self.assertRaises(InjectedCrash):
                p.sync(fault=FaultInjector("after_journal_creation"))
            path = next(p.state.journal_dir.glob("*.json"))
            path.write_bytes(path.read_bytes()[:20])
            p.state.release_lock(force=True)
            with self.assertRaises(StateError):
                p.recover()

    def test_replayed_old_journal_cannot_override_newer_baseline(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td); l=base/"l"; r=base/"r"; l.mkdir(); r.mkdir(); p=SyncPair.open(l,r)
            (l/"a").write_text("v1"); first=p.sync()
            first_path=p.state.journal_path(first["run_id"]); old=read_checked_json(first_path)
            (l/"a").write_text("v2"); p.sync()
            old["state"]="STARTED"
            for item in old["operations"]:
                item["state"]="PLANNED"
            write_checked_json(first_path, old)
            with self.assertRaises(Exception) as ctx:
                p.recover()
            self.assertIn(ctx.exception.__class__.__name__, {"RecoveryRequired", "StalePlanError"})
            self.assertEqual((l/"a").read_text(), "v2")
            self.assertEqual((r/"a").read_text(), "v2")


if __name__ == "__main__":
    unittest.main()
