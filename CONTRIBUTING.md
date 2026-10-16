# Contributing

Thank you for helping test whether dialects can be shared between people who do not share a
system. Critical feedback and counterexamples are as valuable as new entries.

## Adding an entry

- **One entry per pull request.** The entry's directory, its line in `manifest.json`, and nothing
  else.
- **Open an entry proposal first** (the issue template) when the dialect is for a system or a pack
  nobody has written one for, so the source kinds and the fixtures' origin can be settled before the
  work is done.
- **Fixtures are required** for an entry of kind `dialect` and direction `input` or `both`, at least
  one: the recorded source records as the Runner retains them, and `preparation.json`, the exact
  canonical bytes the dialect must produce. The tests run the specification's preparation verifier
  over each. Two kinds of entry carry none. An entry of kind `dialect` and direction `output` holds
  `fixtures: []` until the gateway publishes policy vectors. An entry of kind `preset` has no pack
  and no fixtures: its directory holds exactly `entry.json`, `dialect.json` (version 3, every
  bindable source unbound) and `README.md`, and it is checked by its document's form, its digests
  and the scans only. Every `dialect.json`, of either kind, is held to its document form by the
  catalog's own form checker.
- **Every entry is of entry format version 3**: `entryVersion` is `3`, and the tests refuse an entry
  of version 1 or 2 as `entry-version-unread`, so a release never mixes versions.
- **A named document carries its identity, read from the document.** For a document in a named
  format of RFC 0021 (`formatVersion` `"2.0.0"` or `"3.0.0"`, with `id` and `version`), an entry of
  kind `dialect` references it as `{path, formatVersion, digest}` and carries `artifact`, exactly
  the document's `id` and `version`. Copy both from the document; never edit them on their own. The
  tests refuse a reference or pair that does not hold against the document by name
  (`dialect-reference-form`, `dialect-format-mismatch`, `artifact-required`, `artifact-forbidden`,
  `artifact-malformed`, `artifact-mismatch`, `dialect-digest-mismatch`), the first that applies. An
  integer-format document keeps `{path, dialectVersion, digest}` and no `artifact`, and a preset
  stays integer-only, with neither `formatVersion` nor `artifact`.
- **A published pair is never reused for other content.** `(artifact.id, artifact.version)` is
  immutable across this catalog's history, an entry since withdrawn included: other canonical
  content under a pair any release published, or under a pair another entry of the release
  declares, is `artifact-content-changed`, so new content needs a new artifact version. The same
  content under the pair is admitted in another entry. The entry holds the published document,
  never an installation's bound derivative, which keeps the pair and carries no marker: a reviewer
  refuses one.
- **An entry with a `research` source publishes synthetic fixtures only**: every fixture of such an
  entry is made for the purpose, never recorded from a real person, customer or account
  (RFC 0019 §6).
- **An `upgrade` note is keyed by a released entry's bytes**: the `entryDigest` of this entry's row
  in an earlier release's manifest, never an artifact pair. The tests read the earlier releases, and
  the entries their rows pin, from the repository's tags, so a full clone that has them
  (`git fetch --tags`) checks what CI checks; a shallow clone, which may omit release history and
  tags, is refused as `artifact-history-invalid`.
- **Say only what the format lets you say.** The entry's `assertion` is the format's sentence,
  unchanged; the README states what the dialect is for and nothing about the truth of any record.
- **No credentials, tokens or personal data** in any file. Record fixtures from synthetic or
  consenting sources and remove the rest; for an entry with a `research` source, synthetic only. CI refuses recognised credential shapes and local paths;
  a maintainer must refuse credentials and personal data in every file before merge; the scan's
  silence proves nothing, so the check is yours first.

The format is in [`docs/entry-format.md`](docs/entry-format.md); worked examples, which are not
entries, are in [`tests/fixtures/example-entry/`](tests/fixtures/example-entry/) (kind `dialect`) and
[`tests/fixtures/preset-entry/`](tests/fixtures/preset-entry/) (kind `preset`).

## Review

A material entry (a new dialect, or a change to a dialect's rules) gets the review the
specification's
[GOVERNANCE](https://github.com/Judgment-Pack/judgment-pack-spec/blob/main/GOVERNANCE.md) sets for
material changes. A change that touches only a README or a title is reviewed as a small change. A
maintainer merges; an author does not merge their own entry.

## Working on an issue

You're welcome to comment that you'd like to take an issue, and a maintainer may assign it to you.
Only that assignment reserves it. Without one, the first pull request that meets the issue's
acceptance criteria is the one that gets merged. Work on one issue at a time.

## Local checks

CI runs the checks on Python 3.12, with the specification checked out at the commit `ci.yml` pins:

```bash
git clone https://github.com/Judgment-Pack/judgment-pack-spec.git .spec
git -C .spec checkout c51c81de244a0da279f8b926507e3fe2142348d1
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

`.spec/` is ignored and never committed. Without it the preparation-verifier test is skipped, so a
green run without it checks less than CI does. The tests read the catalog's earlier releases from
its tags, so run them in a full clone with its tags (`git fetch --tags`): in a shallow clone, or
outside a git checkout, the artifact-history check refuses the release rather than check by form
alone. The catalog's own form checker (`tests/dialect_form.py`) needs no checkout: it runs on every
`dialect.json` with or without `.spec/`.

## Developer Certificate of Origin

Contributions must be signed off using Git's `--signoff` option. The sign-off certifies the
Developer Certificate of Origin 1.1: <https://developercertificate.org/>.

## Licence

By contributing, you agree that your contribution is licensed under Apache License 2.0, unless the
entry's `licence` names another licence that lets the Exchange publish it, in which case that
licence applies to that entry's files and you certify you have the right to grant it.

## Conduct

Participation is governed by [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).
