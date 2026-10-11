import os
import tempfile
import unittest
from pathlib import Path

from ferrosync.engine import SyncPair
from ferrosync.errors import PathSafetyError
from ferrosync.util import confined_path, validate_relpath


class SecurityTests(unittest.TestCase):
    def test_path_traversal_rejected(self):
        for p in ("../x", "/tmp/x", "C:/x", "a/../../x"):
            with self.assertRaises(PathSafetyError):
                validate_relpath(p)

    @unittest.skipIf(os.name == "nt", "symlink creation may require Windows developer mode")
    def test_symlink_parent_escape_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"root"; out=Path(td)/"outside"; root.mkdir(); out.mkdir()
            os.symlink(out, root/"escape")
            with self.assertRaises(PathSafetyError):
                confined_path(root, "escape/pwn")

    @unittest.skipIf(os.name == "nt", "symlink creation may require Windows developer mode")
    def test_symlink_loop_scan_is_safe(self):
        with tempfile.TemporaryDirectory() as td:
            l=Path(td)/"l"; r=Path(td)/"r"; l.mkdir(); r.mkdir()
            os.symlink("loop", l/"loop")
            p=SyncPair.open(l,r)
            plan=p.plan()
            self.assertFalse(plan.has_conflicts)
            self.assertEqual(plan.operations[0].action, "SYMLINK")


if __name__ == "__main__":
    unittest.main()
