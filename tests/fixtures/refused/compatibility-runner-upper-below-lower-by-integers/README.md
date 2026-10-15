# Refused: compatibility-runner-upper-below-lower-by-integers

**An example, not an entry.** This tree is `tests/fixtures/metadata-entry/` with one change: `compatibility.runner` is `>=v0.10.0 <v0.9.0`: the upper tag sorts after the lower as text, and is below it by its integers.
`tests/test_entries.py` requires the format to refuse it, saying: compatibility: runner is not a release tag or a range. Nothing here is
published by the Exchange, and the repository root's `manifest.json` does not list it.
