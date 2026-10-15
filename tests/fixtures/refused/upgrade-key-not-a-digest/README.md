# Refused: upgrade-key-not-a-digest

**An example, not an entry.** This tree is `tests/fixtures/metadata-entry/` with one change: `upgrade` is keyed by a release tag, not an entry digest.
`tests/test_entries.py` requires the format to refuse it, saying: upgrade: the key 'v0.1.0' is not a sha256 digest. Nothing here is
published by the Exchange, and the repository root's `manifest.json` does not list it.
