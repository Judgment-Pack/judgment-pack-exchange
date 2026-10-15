# Refused: manifest-path-trailing-slash

**An example, not an entry.** This tree is `tests/fixtures/metadata-entry/` with one change: the row's `path` ends in `/`.
`tests/test_entries.py` requires the format to refuse it, saying: manifest[0]: path is not entries/example/fx-metadata, the path its id names. Nothing here is
published by the Exchange, and the repository root's `manifest.json` does not list it.
