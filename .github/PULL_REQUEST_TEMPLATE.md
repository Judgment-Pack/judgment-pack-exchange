## Summary

Which entry (`entries/<publisher>/<name>/`) is added or changed, and what is the dialect for?
One entry per pull request.

## System and pack

The system the dialect speaks to, the pack (id and versions or digests) it was written against,
and the direction (`input`, `output` or `both`).

## Fixtures

Where each fixture's recorded records come from, and what was removed from them. Fixtures are
required: at least one for every entry.

## Personal data and credentials

- [ ] No credentials, tokens or personal data are in any file (the tests refuse the common shapes;
      this is the author's check too).
- [ ] Records in the fixtures are recorded or synthetic, and say which.

## Checklist

- [ ] `manifest.json` lists the entry, in `id` order, with both digests.
- [ ] `python -m unittest discover -s tests -v` passes with `.spec/` checked out.
- [ ] The entry's `assertion` is the format's sentence, unchanged, and the README does not claim
      more: nothing about any record's truth.
- [ ] The entry's licence is stated and lets the Exchange publish it.
- [ ] I signed off my commits under the DCO.
