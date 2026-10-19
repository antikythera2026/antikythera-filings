ANTIKYTHERA LEDGER

Each file in records/ is one event in the portfolio's life: the opening deposit, a trade, a dividend
or interest credit, a corporate action, a correction, a saved monthly report. A record is a fixed set
of eight fields written as canonical JSON (UTF-8, keys sorted, no spaces, one line feed). Its SHA-256
is the record hash; the first 12 characters of that hash are in the file name. chain.json lists the
records in order.

Every record carries prev_hash, the hash of the record before it, so the set is a chain: changing,
inserting or removing any record changes every hash after it.

A .ots file beside a record is its OpenTimestamps proof. It shows the record existed, byte for byte,
no later than the Bitcoin block it names. Because each record names the hash of the one before it,
a proof on one record also proves every earlier record existed by then.

A report record names the SHA-256 of the saved report file (reports/<period>/...html), so a report
cannot be changed after it was recorded without the change showing.

To check without the app:
  1. Hash each record file with any SHA-256 tool; it must equal the hash in chain.json, and each
     record's prev_hash must equal the hash of the record before it (the first one: 64 zeros).
  2. Check a proof against Bitcoin with the open-source OpenTimestamps client:
         ots verify 0001-deposit-xxxxxxxxxxxx.json.ots
     or drop the .json and the .ots on https://opentimestamps.org.
  verify.py in a public bundle does step 1, checks every proof is for its own file and every report
  file against its recorded hash (standard library only), and says which records each proof covers.
  With --online and the opentimestamps package it also confirms each Bitcoin attestation.

Do not edit anything in this folder: a changed byte breaks the hash, and the proof with it.
