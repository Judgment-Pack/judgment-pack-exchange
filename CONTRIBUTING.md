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
- **An entry with a `research` source publishes synthetic fixtures only**: every fixture of such an
  entry is made for the purpose, never recorded from a real person, customer or account
  (RFC 0019 §6).
- **An `upgrade` note is keyed by a released entry's bytes**: the `entryDigest` of this entry's row
  in an earlier release's manifest. The tests read the earlier releases from the repository's tags,
  so a clone that has them (`git fetch --tags`) checks what CI checks.
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
git -C .spec checkout f821757fcaf5cb9831dbcb1f8b386a5ead793e4a
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

`.spec/` is ignored and never committed. Without it the preparation-verifier test is skipped, so a
green run without it checks less than CI does. The catalog's own form checker
(`tests/dialect_form.py`) needs no checkout: it runs on every `dialect.json` with or without `.spec/`.

## Developer Certificate of Origin

Contributions must be signed off using Git's `--signoff` option. The sign-off certifies the
Developer Certificate of Origin 1.1: <https://developercertificate.org/>.

## Licence

By contributing, you agree that your contribution is licensed under Apache License 2.0, unless the
entry's `licence` names another licence that lets the Exchange publish it, in which case that
licence applies to that entry's files and you certify you have the right to grant it.

## Conduct

Participation is governed by [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).
