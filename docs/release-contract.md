# The release contract

This page states what a release of a catalog in the entry format is, and what a consumer — a desk,
or anything else that imports an entry — fetches, verifies and refuses before it offers an entry for
import. [RFC 0019](https://github.com/Judgment-Pack/judgment-pack-spec/blob/main/rfcs/0019-exchange.md)
§7, "A catalog's release contract", as revised on 2026-10-15 (judgment-pack-spec#163), is the
authority: this page restates it in this repository's words, and where the two differ, the RFC is
right and this page is a bug. The contract is that of any catalog in the [entry format](entry-format.md),
this repository included, so a desk can consume this catalog or another one in the same format.

## A catalog and a release

- A **catalog location** is a git repository URL, or a local directory containing the catalog's git
  repository.
- A **release** is a tag resolved to the commit it names, an annotated tag peeled to its commit. A
  tag that does not resolve to a commit is refused. The tag has the
  [release-tag grammar](entry-format.md#release-tags-and-compatibility-ranges), `vMAJOR.MINOR.PATCH`.
- No branch ancestry is checked. This repository tags only commits on `main`
  ([releasing](releasing.md)), and a consumer does not rely on it.
- The consumer reads `manifest.json` and every entry file as the blob in that commit's tree, byte for
  byte, with no conversion, including no checkout line-ending conversion. Every file it fetches
  therefore belongs to that same commit.
- The consumer retains the catalog location, the tag, the resolved commit and the manifest for the
  import. A later state of the repository does not replace what the installation imported. A tag
  that now resolves to a commit other than the one retained for that tag is refused.
- A catalog with no entries may release the empty manifest, `[]`.

## What a release pins

The manifest pins each entry by digests over the bytes as stored, and the entry pins its documents
and fixtures in turn ([the entry format](entry-format.md)):

- the manifest's `entryDigest`, over `entry.json`; `dialectDigest`, over `dialect.json`, for an entry
  with an input dialect; and `outputDigest`, over `output.json`, for an entry with an output dialect;
- the manifest's `fixtures`, each fixture's complete file set, by basename, in `entry.json`'s order;
- in `entry.json`, `dialect.digest` and `output.digest`, over the documents' canonical bytes
  (RFC 0018 §1, §2, §10), and each fixture's `preparationDigest`, over its `preparation.json` as
  stored.

The manifest gives no separate digest for `README.md` or for each fixture input. Those files are
fetched as blobs from the same commit, and the commit pins them.

## Before import: what a consumer verifies

The consumer performs these checks itself, independently of a catalog's CI. It fetches the release's
manifest within the bounds of 1 MiB (1,048,576 bytes) and 1,024 rows, checks its form
([the manifest](entry-format.md#the-manifest)), and checks one row per entry directory in the
commit's tree and one entry per row, distinct ids in byte order, closed rows and the exact
`id`-to-`path` match. For each entry it would offer for import, it fetches the entry's files from that
release, using the manifest's fixture file lists, and verifies:

- `entry.json` against the manifest's `entryDigest`, and its members against
  [the members' table](entry-format.md#the-members), its `id`, direction and authoring metadata
  included, with the row's path matching its `id`;
- `dialect.json` against the manifest's `dialectDigest` over the stored bytes, and against
  `dialect.digest` over the document's canonical bytes (RFC 0018 §1, §2), when the entry has an input
  dialect;
- `output.json` against `outputDigest` over the stored bytes, and against `output.digest` over the
  document's canonical bytes (RFC 0018 §10), when the entry has an output dialect;
- each fixture's `preparation.json` against its `preparationDigest`, and the fixture's closed file
  set against the manifest's list and the format, with every listed file fetched successfully;
- every pinned digest against the fetched bytes it names, the profiles and acquisitions the reader
  checks included, using canonical bytes only where that digest's definition requires them;
- each file's bounds (the entry format, and RFC 0018 §12), and every file against the credential and
  local-path scan: a recognised credential or local path refuses the entry, and the scan's silence
  establishes no absence of credentials or personal data; and
- each recomputable fixture, by replay with the consumer's own preparation reader, using the entry's
  own dialect, the fixture's own `profiles.json` and remaining inputs, and, for an unbound version-3
  dialect, that fixture's `binding.json` (RFC 0018 §4.4). The reader must return a reading with no
  finding and a digest equal to `preparationDigest`. No record is supplied, so the reading's binding
  is `not-checked`. A fixture outside the reader's supported versions or kinds is reported as not
  recomputable, with the reason, and never as a successful replay.

File digests and canonical digests are distinct checks, even when they happen to be equal. For a
fixture that is not recomputed, the checks establish only the pinned bytes, not the derivation.

## What a consumer refuses

- **The catalog's import**, when the manifest is malformed.
- **An entry**, before it is offered for import, on a failed digest, form, file-set, bound or scan
  check, and on a replay disagreement, a finding or a verifier refusal.
- **A tag** that does not resolve to a commit, and a tag that now resolves to a commit other than the
  one retained for it.
- **An update to a lower tag**, ordered by its three integer components.

## What a consumer must not do

- Run code an entry supplies. Verification runs none, and re-executes no research recipe.
- Treat an entry's requirements or suggested limits as allowances. They are data for review.
- Bind a connection, call a source, schedule a run or authorise a write because an entry was
  imported.
- Replay a fixture under the installation's own bindings or profiles. Replay uses the fixture's own
  binding document and profiles.
- Substitute profiles in a version-2 entry. Using one against the installation's sources is
  re-authoring, an open question (RFC 0019, Unresolved question 7).
- Let a newer tag, or an author's compatibility statement, replace the installation's review.
- Remove or replace an imported entry silently.
- Rely on the catalog's CI in place of its own checks.

## Updates, changes and withdrawal

An **update** is an explicit, reviewed upgrade from one release to another. A lower tag is refused,
as is a moved tag, and the consumer verifies the new release as above.

An entry is **changed** if any file under its path is added, removed or differs in bytes between the
two commits, its README, fixture inputs and binding documents included, even when no pinned digest
changes. A change of direction is a change to the entry, and is shown for review with the changed
files.

An entry absent from the new release is **withdrawn**: it stays imported at its previous commit and is
shown as withdrawn. It is not silently removed or replaced.

## Compatibility is advice

For a changed entry, the consumer shows the entry, its `compatibility` statement, and the `upgrade`
note keyed by the previously imported entry's digest, if one exists. A compatibility range that
excludes the consumer's own release informs the review and does not block the upgrade. An absent
`compatibility` makes no compatibility statement, and an absent `upgrade`, or no note for the
previous digest, supplies no upgrade guidance; none of these absences approves an import or an
upgrade. These members are the author's statements, not verification records or permissions.

## Review records

The review of an update records who approved it (the reviewer's identifier), when, and both the
previously imported commit and the new one. Only that explicit approval replaces the imported entry.

## Importing enables no execution and grants no permission

Local binding means the binding document of RFC 0018 §4.4, for a version-3 dialect with unbound
sources, mapping those sources to the installation's input profiles; a fixture's replay still uses
the fixture's own binding document and profiles. A version-2 entry is imported as published and
re-verified under its own dialect with its fixtures' own profiles; import does not substitute
profiles in it. The installation chooses its local bindings and parameters separately, and may export
its own dialect as an entry in any catalog.

## This repository's releases

This catalog is released by [`release.yml`](../.github/workflows/release.yml), as
[releasing](releasing.md) describes: a tag in the grammar, on a commit on `main`, after the `entries`
checks pass at that commit. The release carries that commit's `manifest.json`, the blob byte for
byte, and `checksums.txt`, both the subjects of a build-provenance attestation, and is published
only after a maintainer approves it. These assets are a copy for checking: a consumer following this
contract reads the manifest and the entries from the tagged commit, and can compare the copy, its
checksums and its attestation with that blob. The attestation says which workflow made the files
from which commit; it says nothing about any entry's review, and nothing here is signed by the
catalog (RFC 0019, Unresolved question 1).

This repository's tests hold the manifest and the entries a release carries to the form and bounds
above (the CI job `entries`). The consumer's own fetch, replay and update checks are the consumer's:
a desk's importer is tracked by judgment-pack-desk#400.
