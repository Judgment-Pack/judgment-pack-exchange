# An earlier release of the example catalog

**An example, not a release.** The trees under `tests/fixtures/` stand for an example catalog, not
this repository. `v0.1.0/` here is that catalog's earlier release, of entry format version 1: its
`manifest.json`, and the `entry.json` each of its rows pins by `entryDigest`. The tests read it as
the upgrade-key check reads an earlier release from a catalog's tags (RFC 0019 §3): each row's `id`
and `entryDigest`, whatever the manifest's form, and nothing else. The example entry with authoring
metadata keys its `upgrade` note by the `entryDigest` of its row here. Nothing here is published by
the Exchange.
