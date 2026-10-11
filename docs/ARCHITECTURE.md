# Architecture

## Components

FerroSync is deliberately small. `scanner.py` produces immutable logical snapshots; `planner.py` compares LEFT, RIGHT, and the last committed baseline; `engine.py` applies a plan under a pair lock and durable journal; `state.py` owns checksummed persistence; `util.py` owns confinement and atomic state writes; `cli.py` is a thin adapter over the library API.

```text
LEFT tree ----> scanner ----\
                           planner ---> Plan ---> engine ---> RIGHT tree
RIGHT tree ---> scanner ----/   ^          |         |
                               baseline    |       journal
                                  ^        |         |
                                  +--------+---- verified commit
```

The planner does not mutate. The engine never invents an operation outside the plan. State is anchored at `LEFT/.ferrosync/` and records the ordered pair's canonical root identities.

## Trust and authority

LEFT and RIGHT have symmetric data authority. The only asymmetry is metadata placement. User filenames, tree contents, and persisted state are treated as malformed until parsed/validated. FerroSync does not defend against a hostile process with arbitrary concurrent write access to both roots.

## Dependency graph

`model/util` are foundational; `scanner` depends on them; `planner` depends only on snapshots/models; `state` depends on models/util; `engine` integrates scanner/planner/state; `cli` depends on the public engine. Tests exercise the production paths rather than shadow implementations.
