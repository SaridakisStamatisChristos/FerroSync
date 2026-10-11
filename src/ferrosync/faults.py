from __future__ import annotations

import os

from .errors import InjectedCrash


class FaultInjector:
    """Deterministic crash injection.

    Spec syntax: LABEL or LABEL:N, where N is the 1-based hit count for LABEL.
    """

    def __init__(self, spec: str | None = None):
        self.spec = spec if spec is not None else os.environ.get("FERROSYNC_CRASH_AT", "")
        self.counts: dict[str, int] = {}
        self.target_label = ""
        self.target_count = 1
        if self.spec:
            label, sep, count = self.spec.partition(":")
            self.target_label = label
            self.target_count = int(count) if sep else 1

    def hit(self, label: str) -> None:
        self.counts[label] = self.counts.get(label, 0) + 1
        if label == self.target_label and self.counts[label] == self.target_count:
            raise InjectedCrash(f"injected crash at {label}:{self.target_count}")
