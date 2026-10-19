#!/usr/bin/env python3
"""Check an ANTIKYTHERA ledger bundle without the app that wrote it.

    python verify.py            standard library only: every record's hash, link and chain entry;
                                that every .ots proof is for its own record; every report file against
                                the SHA-256 its report record names; which records each proof covers
    python verify.py --online   also confirm each Bitcoin attestation's merkle root with a public block
                                explorer (needs: pip install opentimestamps)

Exit code 0 = the chain is intact (records not yet timestamped are listed, not failed); 1 = a check failed."""
import hashlib, json, re, sys, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
GENESIS = "0" * 64
FIELDS = sorted(["schema", "seq", "kind", "recorded_utc", "effective", "body", "salt", "prev_hash"])
MAGIC = b"\x00OpenTimestamps\x00\x00Proof\x00\xbf\x89\xe2\xe8\x84\xe8\x92\x94"


def canonical(rec):
    return (json.dumps(rec, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def proof_digest(path):
    raw = path.read_bytes()[:65]
    if len(raw) < 65 or raw[:31] != MAGIC or raw[31] != 1 or raw[32] != 0x08:
        return None
    return raw[33:65].hex()


def attestations(path):
    try:
        from opentimestamps.core.serialize import StreamDeserializationContext
        from opentimestamps.core.timestamp import DetachedTimestampFile
        from opentimestamps.core.notary import BitcoinBlockHeaderAttestation, PendingAttestation
    except ImportError:
        return None
    with open(path, "rb") as fh:
        dtf = DetachedTimestampFile.deserialize(StreamDeserializationContext(fh))
    blocks, pending = [], []

    def walk(t):
        yield t
        for s in t.ops.values():
            yield from walk(s)
    for t in walk(dtf.timestamp):
        for a in t.attestations:
            if isinstance(a, BitcoinBlockHeaderAttestation):
                blocks.append((a.height, t.msg))
            elif isinstance(a, PendingAttestation):
                pending.append(a)
    return sorted(blocks), pending


def main():
    online = "--online" in sys.argv
    try:
        chain = json.loads((HERE / "chain.json").read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"FAIL chain.json cannot be read: {exc}")
        return 1
    bad, prev, lines = 0, GENESIS, []
    proofs = {}
    for i, e in enumerate(chain):
        if not isinstance(e, dict):
            lines.append((i + 1, f"FAIL {i + 1:04d} chain.json entry is not a record entry", None))
            bad += 1
            prev = ""
            continue
        name = f"{i + 1:04d} {str(e.get('kind')):<16}"
        f = HERE / "records" / str(e.get("file"))
        problems, note = [], ""
        if not f.exists():
            lines.append((i + 1, "FAIL " + name + " record file missing", None))
            bad += 1
            prev = e.get("hash", "")
            continue
        data = f.read_bytes()
        h = hashlib.sha256(data).hexdigest()
        try:
            rec = json.loads(data.decode("utf-8"))
            assert isinstance(rec, dict)
        except Exception:
            lines.append((i + 1, "FAIL " + name + " not a readable JSON record", None))
            bad += 1
            prev = e.get("hash", "")
            continue
        if h != e.get("hash"): problems.append("hash differs from chain.json")
        if canonical(rec) != data: problems.append("not canonical")
        if sorted(rec) != FIELDS: problems.append("wrong field set")
        if rec.get("prev_hash") != prev: problems.append("broken link to previous record")
        seq = rec.get("seq")
        if not isinstance(seq, int) or isinstance(seq, bool):
            problems.append("seq is not a whole number")
            seq = i + 1
        if seq != i + 1 or e.get("seq") != i + 1: problems.append("out of order")
        want = f"{seq:04d}-{rec.get('kind')}-{h[:12]}.json"
        if (e.get("kind"), e.get("effective"), e.get("recorded_utc"), e.get("file")) != (rec.get("kind"), rec.get("effective"), rec.get("recorded_utc"), want):
            problems.append("chain.json entry does not match the record")
        if rec.get("kind") == "report":
            b = rec.get("body") or {}
            rp = HERE / "reports" / str(b.get("file", ""))
            if rp.exists():
                rd = rp.read_bytes()
                if hashlib.sha256(rd).hexdigest() != b.get("sha256") or len(rd) != b.get("bytes"):
                    problems.append("report file differs from its recorded SHA-256")
                else:
                    note += " report file matches"
            else:
                note += " (report file not in this bundle)"
        proof = f.with_name(f.name + ".ots")
        if proof.exists():
            d = proof_digest(proof)
            if d is None: problems.append("proof file cannot be read")
            elif d != h: problems.append("proof is for a different file")
            else:
                proofs[i + 1] = proof
                att = attestations(proof)
                if att is None:
                    note += " own proof (digest checked; install opentimestamps to read its attestations)"
                else:
                    blocks, pending = att
                    if blocks:
                        height, msg = blocks[0]
                        note += f" own proof: names Bitcoin block {height}"
                        if online:
                            try:
                                bh = urllib.request.urlopen(f"https://blockstream.info/api/block-height/{height}", timeout=20).read().decode().strip()
                                b = json.loads(urllib.request.urlopen(f"https://blockstream.info/api/block/{bh}", timeout=20).read())
                                if msg[::-1].hex() != b["merkle_root"]: problems.append("merkle root does not match the block")
                                else: note += " (merkle root confirmed)"
                            except Exception as exc:
                                note += f" (explorer not reached: {type(exc).__name__})"
                        else:
                            note += " (not checked against Bitcoin: use --online)"
                    else:
                        note += " own proof: waiting for its Bitcoin block"
        lines.append((i + 1, ("FAIL " if problems else "ok   ") + name + " " + h[:16] + "  " + "; ".join(problems), note))
        bad += bool(problems)
        prev = e.get("hash", "")
    # which records each proof covers (a proof on a record proves every record before it)
    cover, nxt = {}, None
    for seq in range(len(chain), 0, -1):
        if seq in proofs: nxt = seq
        cover[seq] = nxt
    untimed = 0
    for seq, line, note in lines:
        c = cover.get(seq)
        extra = "" if seq in proofs else (f"  covered by {c:04d}" if c else "  NOT YET TIMESTAMPED")
        untimed += (c is None)
        print(line + (note or "") + extra)
    known = [r.name for r in (HERE / "records").glob("*.json")]
    listed = {e.get("file") for e in chain if isinstance(e, dict)}
    for s in sorted(set(known) - listed):
        print(f"note stray file {s} is not in chain.json (not part of the record)")
    print(f"\n{len(chain)} records, head {prev}")
    if bad:
        print(f"{bad} RECORD(S) FAILED")
        return 1
    print("ALL CHECKS PASSED" if not untimed else f"CHAIN OK; {untimed} RECORD(S) NOT YET COVERED BY A TIMESTAMP")
    return 0


if __name__ == "__main__":
    sys.exit(main())
