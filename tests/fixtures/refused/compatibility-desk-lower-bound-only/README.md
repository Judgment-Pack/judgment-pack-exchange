# Refused: compatibility-desk-lower-bound-only

**An example, not an entry.** This tree is `tests/fixtures/metadata-entry/` with one change: `compatibility.desk` is `>=v0.14.0`, a lower bound with no upper.
`tests/test_entries.py` requires the format to refuse it, saying: compatibility: desk is not a release tag or a range. Nothing here is
published by the Exchange, and the repository root's `manifest.json` does not list it.
