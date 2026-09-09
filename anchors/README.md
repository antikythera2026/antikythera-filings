# Anchors

Each anchor is a **pair** sharing one filename stem, where `<head12>` is the
first 12 hex characters of the chain head hash at the time of stamping:

    chain-<head12>.ots     OpenTimestamps proof — commits to a SHA-256 digest,
                           attested in one or more Bitcoin block headers
    chain-<head12>.json    the exact bytes that digest is over — chain.json
                           as it stood at that moment, verbatim

The proof commits to a *file*, and `chain.json` is append-only, so its digest
changes with every filing. Only the newest proof matches the live `chain.json`;
every older one commits to a version of the file that no longer exists on disk.
The paired `.json` is that version, preserved so each anchor verifies on its
own — offline, from this folder alone, with no git history and no network
access to any host.

## Verify one anchor

    ots verify chain-<head12>.ots -f chain-<head12>.json

This answers *when*: it resolves to a Bitcoin block header, proving those exact
bytes existed before that block was mined. To then confirm *what* they say, run
`verify_filings.py` from the repository root against the same bytes — the chain
recomputes every filing hash and every `prev_hash` link, and each filing pins
the SHA-256 of its published documents.

## Byte-exactness

These files are evidence, not source. The digests are over the bytes exactly as
written, CRLF line endings included; `.gitattributes` sets `* -text` so git
never rewrites them on commit or checkout. Reformatting, re-indenting or
re-saving any file in this folder destroys the proof it carries. Nothing here
is ever edited — anchors are only added.

`receipts.json` is a convenience index of anchoring actions. It is not evidence:
every fact it records is independently established by the proofs themselves.
