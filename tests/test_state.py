import json
import tempfile
import unittest
from pathlib import Path

from ferrosync.engine import SyncPair
from ferrosync.errors import StateError


class StateTests(unittest.TestCase):
    def test_corrupt_baseline_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            l, r = Path(td)/"l", Path(td)/"r"; l.mkdir(); r.mkdir()
            p = SyncPair.open(l, r)
            (l/"a").write_text("x")
            p.sync()
            raw = bytearray(p.state.baseline_path.read_bytes())
            raw[-2] = ord("0") if raw[-2] != ord("0") else ord("1")
            p.state.baseline_path.write_bytes(raw)
            with self.assertRaises(StateError):
                p.plan()

    def test_foreign_root_identity_fails(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td); l=base/"l"; r=base/"r"; x=base/"x"
            l.mkdir(); r.mkdir(); x.mkdir()
            p=SyncPair.open(l,r); p.init()
            # Reuse LEFT state with a different RIGHT root.
            q=SyncPair.open(l,x)
            with self.assertRaises(StateError):
                q.init()


if __name__ == "__main__":
    unittest.main()
