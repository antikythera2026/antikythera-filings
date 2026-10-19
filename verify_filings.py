#!/usr/bin/env python3
"""verify_filings.py — standalone auditor for the ANTIKYTHERA filing chain.

Runs from a clone of the public filings repo. Python 3 standard library only.

    python3 verify_filings.py
        Recomputes every filing hash, checks every prev_hash link and seq,
        and cross-checks the canonical artefacts in filings/ byte-for-byte.

    python3 verify_filings.py --site https://example.com
        Additionally downloads every filed document from the live site and
        compares the SHA-256 of the raw bytes against the filed sha256.
        A document the site has withdrawn from public view (archived, or
        filed in error) redirects to the Research page instead of being
        served: it is listed as withheld, not checked, and not counted as
        tampering. A served document whose bytes differ is always a failure.

The hashing scheme (identical to the site's own tooling):
    canonical bytes = json.dumps(filing, sort_keys=True, separators=(",", ":"),
                                 ensure_ascii=False) + "\n", UTF-8 encoded
    filing_hash     = SHA-256 over those bytes
    chain           = each filing embeds prev_hash of the one before
                      (genesis prev_hash = 64 zeros)

Exit code 0 = chain intact (with --site: every served document matches).
          1 = evidence of tampering, every problem printed.
          2 = the check could not be completed (chain.json missing, or a
              document could not be downloaded) — not evidence either way.
"""
from __future__ import annotations
import argparse
import glob
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

VERSION = "1.1"
HERE = os.path.dirname(os.path.abspath(__file__))
GENESIS_PREV = "0" * 64

# What --site sends. An honest name: the site's host refuses urllib's default
# "Python-urllib/3.x" with Cloudflare error 1010 (Browser Integrity Check).
# "Accept: */*" fetches the bytes as stored: a request that accepts text/html,
# or names no Accept at all, gets the host's analytics <script> added to the page.
REQUEST_HEADERS = {
    "User-Agent": f"antikythera-verify_filings/{VERSION} "
                  "(+https://github.com/antikythera2026/antikythera-filings)",
    "Accept": "*/*",
    "Accept-Encoding": "identity",
}
WITHDRAWN_TO = "/research"   # where the site redirects a document it no longer shows
MAX_REDIRECTS = 5
# Cloudflare Web Analytics' beacon, as the host inserts it before </body>.
CF_BEACON = re.compile(rb'<script[^>]*static\.cloudflareinsights\.com/beacon\.min\.js[^>]*>\s*</script>\s*')


def canonical_bytes(filing: dict) -> bytes:
    return (json.dumps(filing, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False) + "\n").encode("utf-8")


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    # Hand every redirect back to fetch() (urllib before Python 3.11 cannot follow a 308).
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def _clean(path: str) -> str:
    """'/a/b.html', '/a/b' and '/a/b/' name one page: the site 308s .html to the clean URL."""
    path = path.rstrip("/")
    return path[:-5] if path.endswith(".html") else path


def fetch(url: str, withdrawn: str) -> tuple[str, object]:
    """('served', bytes), ('withheld', redirect) or ('unreachable', reason).

    Follows redirects that keep the document's own address (http -> https,
    .html -> clean URL); a redirect to the withdrawal page means withheld."""
    own = _clean(urllib.parse.urlsplit(url).path)
    for _ in range(MAX_REDIRECTS + 1):
        try:
            with _OPENER.open(urllib.request.Request(url, headers=REQUEST_HEADERS), timeout=30) as r:
                enc = (r.headers.get("Content-Encoding") or "identity").lower()
                if enc != "identity":
                    return "unreachable", f"the server sent {enc}-encoded bytes, not the document as stored"
                return "served", r.read()
        except urllib.error.HTTPError as e:
            loc = e.headers.get("Location")
            try:   # the host's own refusals carry a short "error code: NNNN" body
                note = e.read(64).decode("utf-8", "replace").strip()
            except Exception:
                note = ""
            e.close()
            if not (300 <= e.code < 400 and loc):
                return "unreachable", f"HTTP {e.code} {e.reason}" + (f" ({note})" if note.startswith("error code") else "")
            nxt = urllib.parse.urljoin(url, loc)
            path = _clean(urllib.parse.urlsplit(nxt).path)
            if path == withdrawn:
                return "withheld", f"{e.code} to {urllib.parse.urlsplit(nxt).path}"
            if path != own:
                return "unreachable", f"redirected ({e.code}) to {nxt}"
            url = nxt
        except Exception as e:
            return "unreachable", str(getattr(e, "reason", e))
    return "unreachable", f"more than {MAX_REDIRECTS} redirects"


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
    rows, unreachable = [], []
    if a.site:
        base = a.site.rstrip("/")
        site = urllib.parse.urlsplit(base)
        if site.scheme not in ("http", "https") or not site.netloc:
            print("FAIL: --site needs a full URL, e.g. --site https://example.com")
            return 2
        withdrawn = _clean(site.path + WITHDRAWN_TO)
        for rec in chain:
            f = rec["filing"]
            if f.get("kind") != "post":
                continue
            # 1.0 posts pin one document (content_file/content_sha256);
            # 1.1 posts pin a documents list — every one must match.
            docs = f.get("documents") or [{"file": f["content_file"],
                                           "sha256": f["content_sha256"]}]
            for d in docs:
                url = f"{base}/{urllib.parse.quote(d['file'])}"
                state, got = fetch(url, withdrawn)
                note = ""
                if state == "served" and sha256(got) == d.get("sha256"):
                    state = "match"
                elif state == "served":
                    state = "ALTERED"
                    stripped = CF_BEACON.sub(b"", got, count=1)
                    why = (" (the only difference is a Cloudflare Web Analytics <script> the host"
                           " inserted; the bytes served are still not the bytes filed)"
                           if stripped != got and sha256(stripped) == d.get("sha256") else "")
                    problems.append(f"[seq {f['seq']}] PUBLISHED DOCUMENT ALTERED: {url} does not match filed SHA-256{why}")
                elif state == "withheld":
                    note = f"  ({got})"
                else:
                    state = "not fetched"
                    unreachable.append(f"[seq {f['seq']}] could not fetch {url}: {got}")
                rows.append((state, f["seq"], d["file"], note))

    head = chain[-1]["filing_hash"] if chain else GENESIS_PREV
    print(f"filings checked : {len(chain)}")
    print(f"chain head      : {head}")
    withheld = sum(1 for r in rows if r[0] == "withheld")
    if a.site:
        count = {s: sum(1 for r in rows if r[0] == s) for s in ("match", "ALTERED", "not fetched")}
        print(f"documents       : {len(rows)} filed — {count['match']} match, {withheld} withheld, "
              f"{count['ALTERED']} altered, {count['not fetched']} not fetched")
        for state, seq, file, note in rows:
            tag = f"[seq {seq}]"
            print(f"  {state:<11} {tag:<9} {file}{note}")
        if withheld:
            print("\nWithheld = withdrawn from public view (archived, or filed in error): the site")
            print(f"redirects the document to {WITHDRAWN_TO} instead of serving it, so it cannot be")
            print("checked here. Its hash stays in the chain; it is not counted as tampering.")
    if problems:
        issues = problems + unreachable
        print(f"\nRESULT: FAIL — {len(issues)} problem(s):")
        for pr in issues:
            print(f"  - {pr}")
        return 1
    if unreachable:
        print(f"\nRESULT: INCOMPLETE — the chain is intact, but {len(unreachable)} document(s) could not")
        print("be fetched, so were not checked (not evidence either way):")
        for pr in unreachable:
            print(f"  - {pr}")
        return 2
    print("\nRESULT: PASS — every hash recomputes, every link holds, every")
    if a.site:
        print("artefact matches byte-for-byte, every served document matches its")
        print("filed SHA-256" + (f" ({withheld} withheld from public view, listed above)." if withheld else "."))
    else:
        print("artefact matches byte-for-byte. (Add --site <url> to also check the published documents.)")
    print("\nConfirm WHEN the head existed: `ots verify anchors/chain-<head12>.ots -f chain.json`")
    print("and this repository's own commit history.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
