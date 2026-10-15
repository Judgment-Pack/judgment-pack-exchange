# Releasing the Exchange

Only maintainers release this repository. A release is a tag a person pushes on a commit already on
`main`. [`release.yml`](../.github/workflows/release.yml) writes the release's files from that
commit and publishes no release until a maintainer approves it.

What a release is to a consumer is [the release contract](release-contract.md): the tagged commit,
from which a consumer reads `manifest.json` and every entry file as blobs and holds each to the
manifest's digests. The files this workflow publishes are a copy of that commit's manifest, with its
checksums and an attestation, for checking what the workflow saw.

## What a release is

- `manifest.json`: the manifest of the tagged commit, the blob byte for byte. While the Exchange
  holds no entries it is the empty manifest, `[]`.
- `checksums.txt`: the SHA-256 of `manifest.json`, in the form `sha256sum` writes.
- A build-provenance attestation whose subjects are both files, `manifest.json` and `checksums.txt`,
  each by its own digest, signed by GitHub for this workflow at the tagged commit.
- The notes a person wrote, from `docs/releases/<tag>.md`.

Entry files are not release assets: a consumer fetches them from the tagged commit, using the
manifest's fixture file lists. Nothing is signed by the catalog itself (RFC 0019, Unresolved
question 1).

## Once, before the first release

1. Create the `release` environment with a required reviewer. The workflow reads the rule before it
   writes anything and refuses a repository without it, because GitHub creates a missing
   environment on first use with no protection.

   ```sh
   gh api -X PUT repos/Judgment-Pack/judgment-pack-exchange/environments/release \
     -F 'reviewers[][type]=User' -F "reviewers[][id]=$(gh api user --jq .id)"
   ```

   The workflow reads that a reviewer rule exists. It does not read who the reviewers are, and it
   cannot stop an administrator from changing the rule later. With one maintainer, the person who
   pushed the tag is the person who approves: the gate is a pause to read the draft, not a second
   person.

2. Turn on release immutability for the repository (Settings → General → Releases). It locks the
   tag and the assets once a release is published, not before. Until then the workflow compares the
   tag with the commit the run was started for. The workflow does not read this setting.

## Prepare the release

1. Open a pull request that adds `docs/releases/<tag>.md`: the entries added, changed and withdrawn
   since the last release, as the release contract counts them; the specification commit CI pins;
   and anything a consumer must review. It is the text the release page will carry.
2. Run the checks locally, with the specification checked out at the commit `ci.yml` pins
   ([`CONTRIBUTING.md`](../CONTRIBUTING.md), "Local checks"):

   ```sh
   python -m unittest discover -s tests -v
   ```

3. Merge the pull request.

## Tag

Tag the merge commit on `main`, signed, and push only that tag:

```sh
git fetch origin
git tag -s <tag> -m "exchange <tag>" "$(git rev-parse origin/main)"
git push origin <tag>
```

If no signing key is configured, stop and settle the signing policy. Do not replace a signed tag
with an unsigned one. Signing is the maintainer's practice; the workflow does not check it.

A tag has the [release-tag grammar](entry-format.md#release-tags-and-compatibility-ranges):
`vMAJOR.MINOR.PATCH`, in ASCII digits with no leading zeroes, and nothing after; the grammar has no
prerelease and no build metadata. Choose a tag above every earlier release's, by the three
integers: a consumer refuses an update to a lower tag. A tag is never moved or reused: a consumer
refuses a tag that resolves to a commit other than the one it retained for it. A fix is a new
release.

## What the workflow does

Every job works on the commit the run was started for, by its digest, not on the tag's name.

1. **Admits the tag.** It is in the grammar, checked in the shell and again by `release_tag_ok` in
   [`tests/test_entries.py`](../tests/test_entries.py); it names the commit the run was started for;
   that commit is on `main`; its notes exist; and the `release` environment has a reviewer rule.
2. **Runs CI at that commit.** The release calls the commit's own
   [`ci.yml`](../.github/workflows/ci.yml): the `entries` checks, with the specification at the
   commit it pins. A check `main` has gained since that commit is not run.
3. **Writes the release's files.** `manifest.json` is read as the blob of the tagged commit
   (`git cat-file blob <commit>:manifest.json`) and compared with the checkout; `checksums.txt` is
   written over it and checked.
4. **Attests and drafts.** Only if the tag still names the commit and no release exists under the
   tag, both files are attested, each by its own path, and a draft release is created with the
   notes from the commit. The job records the draft's release id for the publish job.
5. **Waits at the `release` gate.** Review the draft on the Releases page: the notes and the two
   assets. Approve the pending deployment on the run.
6. **Compares the draft with the run, and publishes it by its id.** A draft can be changed while it
   waits, by anyone who can write to the repository. After the gate, the tag is compared with the
   commit once more, and the run's own files are held to their checksums. The release the run
   drafted is then read through the releases API by its id, without downloading anything: it must
   still be a draft under the tag, with the title the workflow gave it and the notes the commit
   holds (compared without the newlines either ends in), and the digest the API reports for each of
   its assets must be the digest of the run's file of that name, no asset more or fewer. Any
   difference refuses. The publish call follows that last read at once, addressed to the same
   release id, not to the tag, and marks the release latest.
7. **Reads the published release again.** Immediately after publication the job reads the
   published release's asset digests through the API once more, and fails the step `Require the
   published release to hold what this run wrote`, printing both digest sets, if they differ from
   the run's files.

An approval given more than thirty days after the run finds the run's files gone, and the job
fails: release a new version.

### The window that remains

The API cannot publish a release on condition that its assets are the ones just read, so one
window remains: between the last read of the draft's asset digests and the publish call, a few
moments of the same step. Whoever can write to the repository's releases can act in it: a
repository writer, which in this organisation is a maintainer, the same people the `release` gate
asks to approve. Nothing in the workflow closes that window. A file replaced in it is published,
and the read after publication then fails the run by name; with release immutability on, the
published release can no longer be changed, so the replacement stays visible as a failed release
and is not quietly corrected.

No maintainer token and no repository secret is used.

### What exists before the approval

The gate is on the release. Three things exist before it and are not secret:

- the files, as an artifact of the workflow run, downloadable for thirty days by anyone who can read
  the repository's runs;
- the attestation of `manifest.json` and `checksums.txt`, recorded in a public transparency log when
  it is made. It says which workflow wrote the files, from which commit. It does not say a
  maintainer approved them, or that any entry was reviewed;
- the draft, visible to those who can write to the repository.

### If a run fails

Fix the cause on `main` and release a new version. Re-running is for a failure that was the hosted
runner's: re-run the failed jobs, not all jobs.

What to do with a draft depends on which job failed:

| The job that failed | The draft | What to do |
| --- | --- | --- |
| Any job before `Attest and draft release` | none was made | re-run the failed jobs |
| `Attest and draft release` | may exist, and may lack assets | read it, delete it by hand, then re-run the failed jobs. The job refuses to run while a release under the tag exists, draft or published, and refuses when it cannot find out |
| `Publish release`, before publication | needs looking at: it may be as it was made, changed, incomplete or gone | read why the job failed, and look at the Releases page. **Keep** a draft that is as it was made, and re-run the failed jobs: that job only publishes the release id the run drafted. Do not publish a draft that was changed or is incomplete. Where the draft cannot be published, release a new version |
| `Publish release`, at `Require the published release to hold what this run wrote` | published, holding files this run did not write, or not published after the call | someone who can write to the repository changed the release in the window above. Treat it as an incident: tell the maintainers, point no one at the release, and release a new version from a new tag. Do not re-run |

Delete a draft with `gh release delete <tag> --repo Judgment-Pack/judgment-pack-exchange`, which
leaves the tag. A published release is never deleted to make room for another.

## Verifying a release by hand

Both files are attestation subjects, and `checksums.txt` also names `manifest.json`'s digest. From a
clone of the repository, with the release's files downloaded into a directory of their own:

```sh
git clone https://github.com/Judgment-Pack/judgment-pack-exchange.git exchange
commit="$(git -C exchange rev-parse '<tag>^{commit}')"
gh release download <tag> --repo Judgment-Pack/judgment-pack-exchange --dir release-<tag>
cd release-<tag>
for file in manifest.json checksums.txt; do
  gh attestation verify "${file}" \
    --repo Judgment-Pack/judgment-pack-exchange \
    --signer-workflow Judgment-Pack/judgment-pack-exchange/.github/workflows/release.yml \
    --source-ref refs/tags/<tag> \
    --source-digest "${commit}"
done
sha256sum --check --strict checksums.txt
git -C ../exchange cat-file blob "${commit}:manifest.json" | cmp - manifest.json
```

The loop checks each file against the attestation made in this repository, by this workflow, in a
run started for that tag, from that commit; with `--repo` alone it would check the repository and
nothing more. The checksum command checks `manifest.json` against `checksums.txt`, itself an
attested file. The last command checks that the published `manifest.json` is the blob a consumer
reads under the release contract. `commit` is the full digest of the commit the tag names, an
annotated tag peeled to its commit. None of these says a maintainer approved the release, which its
being published says, and none verifies an entry: that is the consumer's own check under the
release contract.

On macOS use `shasum -a 256 --check checksums.txt`. `gh attestation verify` prints nothing when its
output is not a terminal; add `--format json` in a script.
