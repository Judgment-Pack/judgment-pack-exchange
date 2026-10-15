# Refused: upgrade-33-members

**An example, not an entry.** This tree is `tests/fixtures/metadata-entry/` with one change: `upgrade` has 33 members.
`tests/test_entries.py` requires the format to refuse it, saying: upgrade: not an object of 1 to 32 members. Nothing here is
published by the Exchange, and the repository root's `manifest.json` does not list it.
