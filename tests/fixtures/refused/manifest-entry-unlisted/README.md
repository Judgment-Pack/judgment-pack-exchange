# Refused: manifest-entry-unlisted

**An example, not an entry.** This tree is `tests/fixtures/metadata-entry/` with one change: a second entry, `example.fx-unlisted`, that no row lists.
`tests/test_entries.py` requires the format to refuse it, saying: entries/example/fx-unlisted: an entry the manifest does not list. Nothing here is
published by the Exchange, and the repository root's `manifest.json` does not list it.
