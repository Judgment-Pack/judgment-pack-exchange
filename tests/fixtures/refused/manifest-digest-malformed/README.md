# Refused: manifest-digest-malformed

**An example, not an entry.** This tree is `tests/fixtures/metadata-entry/` with one change: the row's `entryDigest` is written in upper-case hexadecimal.
`tests/test_entries.py` requires the format to refuse it, saying: manifest[0]: entryDigest is not a sha256 digest. Nothing here is
published by the Exchange, and the repository root's `manifest.json` does not list it.
