# Refused: upgrade-empty

**An example, not an entry.** This tree is `tests/fixtures/metadata-entry/` with one change: `upgrade` is the empty object.
`tests/test_entries.py` requires the format to refuse it, saying: upgrade: not an object of 1 to 32 members. Nothing here is
published by the Exchange, and the repository root's `manifest.json` does not list it.
