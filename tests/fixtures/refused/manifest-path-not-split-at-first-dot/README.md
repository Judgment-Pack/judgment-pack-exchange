# Refused: manifest-path-not-split-at-first-dot

**An example, not an entry.** This tree is `tests/fixtures/metadata-entry/` with one change: the entry `example.fx.metadata` lies at `entries/example.fx/metadata`, and its row names that path.
`tests/test_entries.py` requires the format to refuse it, saying: manifest[0]: path is not entries/example/fx.metadata, the path its id names. Nothing here is
published by the Exchange, and the repository root's `manifest.json` does not list it.
