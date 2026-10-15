# Example: a version-3 dialect with a research source

**This is an example, not an entry.** Its dialect is version 3 with one `research` source in the form
of RFC 0018's round 8: a question, constraints, a model, the evidence to retain, one requested field
and the `answer` capability, and none of `profile`, `profileDigest` and `webProfiles`, so it is
unbound. Its fixture carries `binding.json`, the binding document assigning the source the fixture's
own AI profile. The catalog's form checker reads the document, and the tests hold the binding
document to it. The specification's preparation verifier at the commit CI pins reads neither version
3 nor a research profile, and an entry with a research source cannot be published while the readers
refuse it (RFC 0019 §4), so the verifier test refuses this fixture. Its records are synthetic, and its
`preparation.json` is a placeholder with a matching digest.
