# State format

State format version: **1**.

The metadata root is `LEFT/.ferrosync/`:

```text
state.json
baseline.json
journal/*.json
locks/pair.lock
conflicts/*.json
```

`state.json` records canonical LEFT/RIGHT roots, pair ID, ignore rules, and format version. `baseline.json` records the last successfully committed logical snapshot, a deterministic baseline ID, commit run ID, and timestamp.

Every authoritative JSON state file is wrapped as:

```json
{"payload": {"version": 1}, "checksum": "sha256(canonical-json(payload))"}
```

Reads are bounded to 16 MiB per state file. Unsupported versions, malformed entries, invalid paths, key/path mismatches, invalid hashes, root mismatches, and checksum mismatches fail closed. Executable code is never serialized.

### Upgrade policy

A future incompatible representation must increment the format version and ship an explicit migration. Version 1 readers do not reinterpret unknown versions.
