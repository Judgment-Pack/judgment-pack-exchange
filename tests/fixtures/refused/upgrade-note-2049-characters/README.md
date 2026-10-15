# Refused: upgrade-note-2049-characters

**An example, not an entry.** This tree is `tests/fixtures/metadata-entry/` with one change: the upgrade note is 2049 characters.
`tests/test_entries.py` requires the format to refuse it, saying: upgrade: the note for 'sha256:52895deee7e135c99f48553cfcd01586aafcfea29232c03698aac6bec1ca6c31' is not a string of 1 to 2048 characters. Nothing here is
published by the Exchange, and the repository root's `manifest.json` does not list it.
