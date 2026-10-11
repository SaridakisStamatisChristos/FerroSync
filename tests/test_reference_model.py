import itertools
import unittest

from ferrosync.model import Entry, Snapshot
from ferrosync.planner import build_plan


def ent(path, value):
    return None if value is None else Entry(path, "file", digest=value, size=1, mode=0o644)


def expected_one_path(base, left, right):
    # Independent, deliberately tiny oracle for one logical file path.
    if base is None:
        if left is None and right is None:
            return "noop"
        if left is None or right is None:
            return "copy"
        return "noop" if left == right else "conflict"
    lc = "same" if left == base else ("deleted" if left is None else "changed")
    rc = "same" if right == base else ("deleted" if right is None else "changed")
    if left == right:
        return "noop"
    if lc == "same" and rc != "same":
        return "delete" if rc == "deleted" else "copy"
    if rc == "same" and lc != "same":
        return "delete" if lc == "deleted" else "copy"
    if lc == rc == "deleted":
        return "noop"
    return "conflict"


class ReferenceModelTests(unittest.TestCase):
    def test_exhaustive_single_path_transition_table(self):
        values = [None, "A", "B"]
        for base, left, right in itertools.product(values, values, values):
            with self.subTest(base=base, left=left, right=right):
                b = Snapshot({} if base is None else {"p": ent("p", base)})
                l = Snapshot({} if left is None else {"p": ent("p", left)})
                r = Snapshot({} if right is None else {"p": ent("p", right)})
                plan = build_plan(l, r, None if base is None else b, "id" if base is not None else None)
                observed = "conflict" if plan.has_conflicts else (plan.operations[0].action.lower() if plan.operations else "noop")
                if observed in {"copy", "symlink", "mkdir", "rename", "chmod"}:
                    observed = "copy"
                self.assertEqual(observed, expected_one_path(base, left, right))


if __name__ == "__main__":
    unittest.main()
