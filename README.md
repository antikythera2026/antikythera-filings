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

Exit code 0 = intact. Non-zero = evidence of tampering, with every problem
printed.

## What this proves — and what it doesn't

The chain proves *integrity* (nothing filed was altered afterwards) and the
anchors prove *existence at a time* (the head existed no later than the Bitcoin
block / commit timestamp). None of it proves a call was *good* — that judgement
is yours; the record just makes it honest.

Nothing here is financial advice. Filings are evidence of what was said and
when — not recommendations.
