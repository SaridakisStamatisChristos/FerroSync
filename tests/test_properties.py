import random
import tempfile
import unittest
from pathlib import Path

from ferrosync.engine import SyncPair
from ferrosync.errors import ConflictError


class PropertyCampaignTests(unittest.TestCase):
    def test_seeded_random_nonconflicting_sequences(self):
        # 40 reproducible seeds x 12 mutation/sync rounds.
        for seed in range(40):
            rng = random.Random(seed)
            with self.subTest(seed=seed), tempfile.TemporaryDirectory() as td:
                base=Path(td); l=base/"l"; r=base/"r"; l.mkdir(); r.mkdir()
                p=SyncPair.open(l,r)
                p.sync()  # establish empty baseline
                for step in range(12):
                    side = l if rng.randrange(2) == 0 else r
                    peer = r if side == l else l
                    name = f"f{rng.randrange(6)}.txt"
                    target = side/name
                    action = rng.randrange(3)
                    if action == 0 or not target.exists():
                        target.write_text(f"seed={seed};step={step};v={rng.randrange(1_000_000)}")
                    elif action == 1:
                        target.write_text(target.read_text() + "!")
                    else:
                        target.unlink()
                    # We sync after one-sided mutation, so no conflict is expected.
                    p.sync()
                    self.assertTrue(p.verify()["ok"])
                    # A repeated plan must be byte-for-byte deterministic and empty.
                    a, b = p.plan().to_dict(), p.plan().to_dict()
                    self.assertEqual(a, b)
                    self.assertEqual(a["operations"], [])
                    self.assertEqual(a["conflicts"], [])

    def test_conflict_never_erases_versions(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td); l=base/"l"; r=base/"r"; l.mkdir(); r.mkdir(); p=SyncPair.open(l,r)
            (l/"x").write_text("base"); p.sync()
            (l/"x").write_text("L"); (r/"x").write_text("R")
            with self.assertRaises(ConflictError): p.sync()
            self.assertEqual((l/"x").read_text(), "L")
            self.assertEqual((r/"x").read_text(), "R")

    def test_ignored_paths_never_enter_baseline(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td); l=base/"l"; r=base/"r"; l.mkdir(); r.mkdir(); p=SyncPair.open(l,r)
            (l/"scratch.tmp").write_text("ignore")
            (l/"build").mkdir(); (l/"build"/"x").write_text("ignore")
            p.sync()
            baseline = p.state.load_baseline()[1]
            self.assertNotIn("scratch.tmp", baseline.entries)
            self.assertNotIn("build", baseline.entries)
            self.assertFalse((r/"scratch.tmp").exists())


if __name__ == "__main__":
    unittest.main()
