import unittest

from ferrosync.model import Entry, Snapshot
from ferrosync.planner import build_plan


def f(path, digest):
    return Entry(path, "file", digest=digest, size=1, mode=0o644)


class PlannerTests(unittest.TestCase):
    def test_initial_collision_is_conflict(self):
        p = build_plan(Snapshot({"a": f("a", "L")}), Snapshot({"a": f("a", "R")}), None)
        self.assertTrue(p.has_conflicts)
        self.assertEqual(p.conflicts[0].kind, "initial-collision")
        self.assertFalse(p.operations)

    def test_initial_one_sided_copy(self):
        p = build_plan(Snapshot({"a": f("a", "X")}), Snapshot({}), None)
        self.assertEqual([(o.action, o.side, o.path) for o in p.operations], [("COPY", "RIGHT", "a")])

    def test_delete_requires_baseline_evidence(self):
        base = Snapshot({"a": f("a", "X")})
        p = build_plan(Snapshot({}), Snapshot({"a": f("a", "X")}), base, "b")
        self.assertEqual([(o.action, o.side) for o in p.operations], [("DELETE", "RIGHT")])
        p2 = build_plan(Snapshot({}), Snapshot({"a": f("a", "Y")}), base, "b")
        self.assertTrue(p2.has_conflicts)

    def test_deterministic_plan(self):
        base = Snapshot({"b": f("b", "B"), "a": f("a", "A")})
        left = Snapshot({"b": f("b", "B2"), "a": f("a", "A")})
        right = Snapshot({"a": f("a", "A"), "b": f("b", "B")})
        p1 = build_plan(left, right, base, "id")
        p2 = build_plan(Snapshot(dict(reversed(list(left.entries.items())))), Snapshot(dict(reversed(list(right.entries.items())))), base, "id")
        self.assertEqual(p1.to_dict(), p2.to_dict())

    def test_exact_content_rename(self):
        base = Snapshot({"old": f("old", "A")})
        left = Snapshot({"new": f("new", "A")})
        right = Snapshot({"old": f("old", "A")})
        p = build_plan(left, right, base, "id")
        self.assertFalse(p.has_conflicts)
        self.assertEqual((p.operations[0].action, p.operations[0].side, p.operations[0].source_path, p.operations[0].path), ("RENAME", "RIGHT", "old", "new"))

    def test_rename_modify_conflict(self):
        base = Snapshot({"old": f("old", "A")})
        left = Snapshot({"new": f("new", "A")})
        right = Snapshot({"old": f("old", "B")})
        p = build_plan(left, right, base, "id")
        self.assertTrue(any(c.kind == "rename/modify" for c in p.conflicts))

    def test_incremental_add_add_different_content_conflicts(self):
        base = Snapshot({})
        p = build_plan(Snapshot({"a": f("a", "L")}), Snapshot({"a": f("a", "R")}), base, "id")
        self.assertTrue(p.has_conflicts)
        self.assertEqual(p.conflicts[0].kind, "add/add")

    def test_divergent_rename_conflicts(self):
        base = Snapshot({"old": f("old", "A")})
        left = Snapshot({"left-name": f("left-name", "A")})
        right = Snapshot({"right-name": f("right-name", "A")})
        p = build_plan(left, right, base, "id")
        self.assertTrue(any(c.kind == "rename/rename-divergence" for c in p.conflicts))

    def test_modify_delete_and_delete_modify_conflicts(self):
        base = Snapshot({"a": f("a", "A")})
        p1 = build_plan(Snapshot({"a": f("a", "B")}), Snapshot({}), base, "id")
        p2 = build_plan(Snapshot({}), Snapshot({"a": f("a", "B")}), base, "id")
        self.assertEqual(p1.conflicts[0].kind, "modify/delete")
        self.assertEqual(p2.conflicts[0].kind, "delete/modify")

    def test_symlink_target_divergence_conflicts(self):
        def s(path, target, digest):
            return Entry(path, "symlink", digest=digest, size=len(target), mode=0o777, link_target=target)
        base = Snapshot({"link": s("link", "a", "a"*64)})
        left = Snapshot({"link": s("link", "b", "b"*64)})
        right = Snapshot({"link": s("link", "c", "c"*64)})
        plan = build_plan(left, right, base, "id")
        self.assertTrue(plan.has_conflicts)

    def test_case_only_rename_fails_portable_namespace_policy(self):
        base = Snapshot({"Name.txt": f("Name.txt", "A")})
        left = Snapshot({"name.txt": f("name.txt", "A")})
        right = Snapshot({"Name.txt": f("Name.txt", "A")})
        plan = build_plan(left, right, base, "id")
        self.assertTrue(any(c.kind == "case-collision" for c in plan.conflicts))


if __name__ == "__main__":
    unittest.main()
