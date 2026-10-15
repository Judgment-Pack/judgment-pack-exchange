# Refused: dialect-refused-though-every-fixture-is-skipped

**An example, not an entry.** This tree is `tests/fixtures/unbound-entry/` with one change: the version-3 dialect carries `provider`, a member of version 2 alone; the verifier skips its one fixture, and the form checker still refuses it.
`tests/test_entries.py` requires the format to refuse it with exactly the problems it lists for this
tree, and requires the tree to pass once that change is reverted. Nothing here is published by the
Exchange, and the repository root's `manifest.json` does not list it.
