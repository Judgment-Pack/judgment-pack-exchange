# Security policy

## Reporting a vulnerability

Do not open a public issue for a vulnerability. Use GitHub's private vulnerability reporting for
this repository (Security -> Report a vulnerability), or open a minimal non-sensitive issue asking
a maintainer to establish a private channel.

Report, for example:

- an entry whose dialect, fixtures or README carries a credential, token or personal data;
- a way past the tests that keep those out, or past the digests that pin an entry;
- an entry whose dialect makes a reader do unbounded work, or reach a system, when read;
- a workflow in this repository that could expose a secret or run untrusted code with privileges.

Include the affected entry or file, a minimal reproduction, the likely impact, and whether the
issue is already public. Do not put the credential or the personal data itself in the report.

## Credentials and personal data

Entries, fixtures and READMEs must hold no credentials, tokens, keys or personal data. Fixtures are
recorded or synthetic records with such content removed. A test scans every file for common
credential shapes and for local paths, and refuses the tree if it finds one. If something slips
past, report it as above; the entry is removed and the history is treated as exposed.

## Security boundary

An entry is untrusted input. A dialect document is data a reader interprets under the bounds
RFC 0018 sets; the Exchange never executes an entry. An entry establishes its author's assertion
and nothing about the truth of any record, and a passing test is not authorisation to use it.
