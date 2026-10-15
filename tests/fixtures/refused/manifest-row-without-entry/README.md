# Refused: manifest-row-without-entry

**An example, not an entry.** This tree is `tests/fixtures/metadata-entry/` with one change: a second row, for `example.fx-missing`, which no directory holds.
`tests/test_entries.py` requires the format to refuse it, saying: entries/example/fx-missing: listed in the manifest, no such entry. Nothing here is
published by the Exchange, and the repository root's `manifest.json` does not list it.
