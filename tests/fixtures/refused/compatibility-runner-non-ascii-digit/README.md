# Refused: compatibility-runner-non-ascii-digit

**An example, not an entry.** This tree is `tests/fixtures/metadata-entry/` with one change: `compatibility.runner` is `v١.0.0`, whose major version is the Arabic-Indic digit one.
`tests/test_entries.py` requires the format to refuse it, saying: compatibility: runner is not a release tag or a range. Nothing here is
published by the Exchange, and the repository root's `manifest.json` does not list it.
