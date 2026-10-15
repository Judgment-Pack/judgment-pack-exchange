# Refused: compatibility-not-an-object

**An example, not an entry.** This tree is `tests/fixtures/metadata-entry/` with one change: `compatibility` is a release tag, not an object.
`tests/test_entries.py` requires the format to refuse it, saying: compatibility: not an object. Nothing here is
published by the Exchange, and the repository root's `manifest.json` does not list it.
