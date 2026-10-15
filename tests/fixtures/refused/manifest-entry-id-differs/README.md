# Refused: manifest-entry-id-differs

**An example, not an entry.** This tree is `tests/fixtures/metadata-entry/` with one change: `entry.json` says `example.fx-other` at the path of `example.fx-metadata`.
`tests/test_entries.py` requires the format to refuse it, saying: entry: id example.fx-other is not its path's example.fx-metadata. Nothing here is
published by the Exchange, and the repository root's `manifest.json` does not list it.
