# Example: a version-3 dialect with an unbound source

**This is an example, not an entry.** Its dialect is the example entry's with version 3, written the
one way version 3 is (without version 2's `provider`, `facts` and `evidence`), and its `operation`
source in the unbound form of RFC 0018 §4.4: no `profile` and no `profileDigest`, and instead the
catalog `platform` and `operation`, the `shape` and the `record` an installation binds it to. Its
fixture carries `binding.json`, the binding document it was recorded under, which binds the source
to the fixture's own profile. The specification's preparation verifier at the commit CI pins reads
version 3 and takes that binding document, so the verifier test replays the fixture: its
`preparation.json` is the preparation the verifier computes, and its digest is the entry's
`preparationDigest`. The catalog's form checker reads its dialect all the same.
