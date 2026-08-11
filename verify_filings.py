#!/usr/bin/env python3
"""verify_filings.py — standalone auditor for the ANTIKYTHERA filing chain.

Runs from a clone of the public filings repo. Python 3 standard library only.

    python3 verify_filings.py
        Recomputes every filing hash, checks every prev_hash link and seq,
        and cross-checks the canonical artefacts in filings/ byte-for-byte.

    python3 verify_filings.py --site https://example.com
        Additionally downloads every published post from the live site and
        compares the SHA-256 of the raw bytes against the filed content_sha256.

The hashing scheme (identical to the site's own tooling):
    canonical bytes = json.dumps(filing, sort_keys=True, separators=(",", ":"),
                                 ensure_ascii=False) + "\n", UTF-8 encoded
    filing_hash     = SHA-256 over those bytes
    chain           = each filing embeds prev_hash of the one before
                      (genesis prev_hash = 64 zeros)

Exit code 0 = chain intact. Non-zero = problems, all printed.
"""
from __future__ import annotations
import argparse
import glob
import hashlib
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
GENESIS_PREV = "0" * 64


def canonical_bytes(filing: dict) -> bytes:
    return (json.dumps(filing, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode("utf-8")


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--site", help="base URL of the live site, to also verify published documents")
    a = p.parse_args()

    chain_path = os.path.join(HERE, "chain.json")
    if not os.path.exists(chain_path):
        print("FAIL: chain.json not found — run from a clone of the filings repo.")
        return 2
    chain = json.load(open(chain_path, encoding="utf-8"))
    problems = []

    # 1. hashes, links, sequence
    prev = GENESIS_PREV
    for i, rec in enumerate(chain):
        f, claimed = rec.get("filing", {}), rec.get("filing_hash", "")
        recomputed = sha256(canonical_bytes(f))
        if recomputed != claimed:
            problems.append(f"[seq {f.get('seq')}] filing_hash mismatch: chain says {claimed[:12]}…, recomputed {recomputed[:12]}…")
        if f.get("prev_hash") != prev:
            problems.append(f"[seq {f.get('seq')}] prev_hash broken")
        if f.get("seq") != i + 1:
            problems.append(f"[index {i}] seq out of order: {f.get('seq')}")
        prev = claimed

    # 2. canonical artefacts byte-for-byte
    artefacts = {os.path.basename(p): p for p in glob.glob(os.path.join(HERE, "filings", "*.json"))}
    for rec in chain:
        f, fh = rec["filing"], rec["filing_hash"]
        name = f"{f['seq']:04d}-{f['kind']}-{fh[:12]}.json"
        path = artefacts.pop(name, None)
        if path is None:
            problems.append(f"[seq {f['seq']}] canonical artefact missing: filings/{name}")
        elif open(path, "rb").read() != canonical_bytes(f):
            problems.append(f"[seq {f['seq']}] canonical artefact bytes differ: filings/{name}")
    for name in artefacts:
        problems.append(f"orphan artefact not in chain: filings/{name}")

    # 3. published documents against the live site
    if a.site:
        base = a.site.rstrip("/")
        for rec in chain:
            f = rec["filing"]
            if f.get("kind") != "post":
                continue
            # 1.0 posts pin one document (content_file/content_sha256);
            # 1.1 posts pin a documents list — every one must match.
            docs = f.get("documents") or [{"file": f["content_file"],
                                           "sha256": f["content_sha256"]}]
            for d in docs:
                url = f"{base}/{d['file']}"
                try:
                    body = urllib.request.urlopen(url, timeout=30).read()
                except Exception as e:
                    problems.append(f"[seq {f['seq']}] could not fetch {url}: {e}")
                    continue
                if sha256(body) != d.get("sha256"):
                    problems.append(f"[seq {f['seq']}] PUBLISHED DOCUMENT ALTERED: {url} does not match filed SHA-256")

    head = chain[-1]["filing_hash"] if chain else GENESIS_PREV
    print(f"filings checked : {len(chain)}")
    print(f"chain head      : {head}")
    if problems:
        print(f"\nRESULT: FAIL — {len(problems)} problem(s):")
        for pr in problems:
            print(f"  - {pr}")
        return 1
    print("\nRESULT: PASS — every hash recomputes, every link holds, every")
    print("artefact matches byte-for-byte" +
          (", every published document matches its filed SHA-256." if a.site
           else ". (Add --site <url> to also check the published documents.)"))
    print("\nConfirm WHEN the head existed: `ots verify anchors/chain-<head12>.ots -f chain.json`")
    print("and this repository's own commit history.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
