# Example: a version-3 dialect with an unbound source

**This is an example, not an entry.** Its dialect is the example entry's with version 3 and its
`operation` source in the unbound form of RFC 0018 §4.4: no `profile` and no `profileDigest`, and
instead the catalog `platform` and `operation`, the `shape` and the `record` an installation binds
it to. Its fixture carries `binding.json`, the binding document it was recorded under, which binds
the source to the fixture's own profile. The specification's preparation verifier does not
implement version 3 and no preparer writes it, so the fixture is held by its digests only, the
verifier test skips it naming the version, and its `preparation.json` is a placeholder with a
matching digest.
