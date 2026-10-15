# Refused: compatibility-desk-65-characters

**An example, not an entry.** This tree is `tests/fixtures/metadata-entry/` with one change: `compatibility.desk` is a range in the grammar, 65 characters long.
`tests/test_entries.py` requires the format to refuse it, saying: compatibility: desk is not a release tag or a range. Nothing here is
published by the Exchange, and the repository root's `manifest.json` does not list it.
