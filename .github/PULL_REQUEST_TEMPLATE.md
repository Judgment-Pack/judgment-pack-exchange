## Summary

Which entry (`entries/<publisher>/<name>/`) is added or changed, and what is the dialect for?
One entry per pull request.

## System and pack

The entry's kind (`dialect` or `preset`), the system the dialect speaks to, the pack (id and
versions or digests) it was written against (none for a preset), and the direction (`input`,
`output` or `both`; `input` for a preset).

## Fixtures

Where each fixture's recorded records come from, and what was removed from them. Fixtures are
required for kind `dialect` and direction `input` or `both`: at least one for every such entry. An
entry of direction `output` holds `fixtures: []`, and a preset has none. Every fixture of an entry
with a `research` source is synthetic.

## Personal data and credentials

- [ ] No credentials, tokens or personal data are in any file (CI refuses recognised shapes and local
      paths only, and its silence proves nothing; a maintainer refuses the rest before merge).
- [ ] Records in the fixtures are recorded or synthetic, and say which; for an entry with a
      `research` source, every fixture is synthetic.

## Checklist

- [ ] `manifest.json` lists the entry, in `id` order, with its `kind`, its `entryDigest`, the
      digest of each document it holds (`dialectDigest`, `outputDigest`) and its fixtures' files.
- [ ] `python -m unittest discover -s tests -v` passes with `.spec/` checked out.
- [ ] The entry's `assertion` is the format's sentence, unchanged, and the README does not claim
      more: nothing about any record's truth.
- [ ] The entry's licence is stated and lets the Exchange publish it.
- [ ] I signed off my commits under the DCO.
