# ANTIKYTHERA — public filing record

This repository is the **public anchor** for the ANTIKYTHERA filing chain.
Every research publication and investment call on the ANTIKYTHERA site is a
*filing*: a fixed-field JSON object, serialised deterministically, hashed with
SHA-256 and chained to the filing before it. This repo receives the evidence
after every filing, so its commit history is an independent, timestamped,
publicly browsable record of each chain head.

## What's here

| Path | Contents |
|---|---|
| `chain.json` | The full hash chain — the single source of truth |
| `filings/` | The exact canonical bytes of every filing, one file each |
| `anchors/` | OpenTimestamps proofs (`.ots`) + anchor receipts |
| `verify_filings.py` | Standalone verifier — Python 3, no dependencies |

## The two anchors

1. **OpenTimestamps (trustless).** After each filing, the SHA-256 of
   `chain.json` is stamped into the Bitcoin blockchain. Verify a proof with the
   open-source client, trusting no one — not us, not GitHub:

   ```
   pip install opentimestamps-client
   ots verify anchors/chain-<head12>.ots -f chain.json
   ```

2. **This repository (convenient).** Every push timestamps the chain bytes on
   GitHub's servers. The commit history shows exactly when each head existed
   and cannot be silently rewritten without the divergence being visible.

## Verify the chain yourself

```
python3 verify_filings.py
```

recomputes every filing hash from `chain.json`, checks every `prev_hash` link
and sequence number, and cross-checks the canonical artefacts in `filings/`
byte-for-byte. To also confirm the *published documents* match what was filed,
point it at the live site — it downloads every filed document (a post may file
several: e.g. fundamental, technical and screening outputs for one stock) and
compares the SHA-256 of the raw bytes against the hash recorded in the chain:

```
python3 verify_filings.py --site https://<the-antikythera-domain>
```

A document the site has withdrawn from public view (archived, or filed in
error) is not served: its address redirects to the Research page. The
verifier lists it as *withheld* rather than checking it; its hash stays in the
chain. A served document whose bytes differ from the filing is always a
failure.

Exit code 0 = intact. 1 = evidence of tampering, with every problem printed.
2 = the check could not be completed (for example, a document could not be
downloaded) — not evidence either way.

## What this proves — and what it doesn't

The chain proves *integrity* (nothing filed was altered afterwards) and the
anchors prove *existence at a time* (the head existed no later than the Bitcoin
block / commit timestamp). None of it proves a call was *good* — that judgement
is yours; the record just makes it honest.

Nothing here is financial advice. Filings are evidence of what was said and
when — not recommendations.

<!-- portfolio-ledger -->
## The portfolio ledger (`portfolio/`)

The ANTIKYTHERA Portfolio keeps a hash chain of its own, separate from the
filing chain above: every deposit, trade, dividend and interest credit,
correction, corporate action and monthly report is one record, written as
canonical JSON, hashed with SHA-256 and chained to the record before it.
Trades, deposits, corrections, corporate actions and reports carry their own
OpenTimestamps proof (`records/*.json.ots`); dividend and interest credits are
covered by the next stamped record. The folder is mirrored here from the site
every week, append-only, so this repository's history timestamps every trade
publicly as well.

| Path | Contents |
|---|---|
| `portfolio/chain.json` | Every record in order, with its SHA-256 |
| `portfolio/records/` | One canonical record per file, and its `.ots` proof |
| `portfolio/reports/` | The saved monthly reports each report record pins by SHA-256 |
| `portfolio/anchors.json` | The portfolio app's notes on each proof (informational) |
| `portfolio/verify.py` | Standalone checker, Python 3 standard library only |

```
python3 portfolio/verify.py            # every hash, link, proof digest and report file
python3 portfolio/verify.py --online   # also confirms each proof's Bitcoin block (pip install opentimestamps)
```

The same ledger, and a check that runs in your browser, is on the site's
Verify page.
