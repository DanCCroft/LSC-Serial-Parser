#!/usr/bin/env python3
# ==================================================
# parser.py — Canonical Tri-Carb RS-232 parser
# Handles SNC and SAMPLE protocols
# ==================================================

import sys
import os
import json
import re
import subprocess

print("=== PARSER INVOKED ===")
print("Args:", sys.argv)

# --------------------
# INPUT CHECK
# --------------------
if len(sys.argv) != 2:
    print("Usage: parser.py <binfile>")
    sys.exit(1)

bin_file = sys.argv[1]

if not os.path.exists(bin_file):
    print(f"Error: file '{bin_file}' does not exist")
    sys.exit(1)

# --------------------
# READ AND DECODE
# --------------------
try:
    with open(bin_file, "rb") as f:
        raw = f.read()
    decoded = raw.decode("ascii", errors="ignore")
except Exception as e:
    print(f"Error reading file: {e}")
    sys.exit(1)

# --------------------
# IDENTIFY FRAME TYPE
# --------------------
# Strip any leading nulls or whitespace that could survive a noisy capture.
# repr() in the print helps spot hidden characters during debugging.
cleaned = decoded.lstrip("\x00\r\n \t")
first_line = cleaned.splitlines()[0] if cleaned else ""
print(f"FIRST LINE: {first_line!r}")

# ==================================================
# SNC PATH
# ==================================================
SNC_HEADERS = (
    "C14 IPA DATA PROCESSED",
    "C14 CHI SQUARE IPA DATA PROCESSED",
    "H3 IPA DATA PROCESSED",
    "H3 CHI SQUARE IPA DATA PROCESSED",
    "BKG IPA DATA PROCESSED",
)

if any(first_line.startswith(h) for h in SNC_HEADERS):
    print(">>> SNC DETECTED")

    snc_dir = "/home/labuser/Desktop/LSC_Reports/SNC"
    os.makedirs(snc_dir, exist_ok=True)

    # Derive output filename from capture timestamp in the bin filename.
    # e.g. cap_20260317-135400.bin → snc_20260317-135400.txt
    base = os.path.basename(bin_file)
    stem, _ = os.path.splitext(base)
    txt_name = stem.replace("cap_", "snc_", 1) + ".txt"
    txt_path = os.path.join(snc_dir, txt_name)

    # --------------------------------------------------
    # PARSE SNC SECTIONS
    # Each section is a header line carrying a timestamp,
    # followed by one or more indented data lines.
    # Known sections from hex dump:
    #   C14 IPA DATA PROCESSED        → C14 Efficiency
    #   C14 CHI SQUARE IPA DATA ...   → C14 Chi Square
    #   H3 IPA DATA PROCESSED         → H3 Efficiency
    #   H3 CHI SQUARE IPA DATA ...    → H3 Chi Square
    #   BKG IPA DATA PROCESSED        → Background
    # --------------------------------------------------

    # Map the section header prefix to a human-readable label.
    # Order matters — more specific prefixes must come before shorter ones.
    SECTION_MAP = [
        ("C14 CHI SQUARE IPA DATA PROCESSED", "C14 Chi Square"),
        ("C14 IPA DATA PROCESSED",            "C14 Efficiency"),
        ("H3 CHI SQUARE IPA DATA PROCESSED",  "H3 Chi Square"),
        ("H3 IPA DATA PROCESSED",             "H3 Efficiency"),
        ("BKG IPA DATA PROCESSED",            "Background"),
    ]

    # Timestamp pattern: DD-Mon-YYYY HH:MM
    TIMESTAMP_RE = re.compile(r"\d{2}-[A-Za-z]{3}-\d{4} \d{2}:\d{2}")

    sections = []   # list of dicts: {label, datetime, data_lines[]}
    current = None

    for raw_line in cleaned.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # Check if this line is a section header
        matched_label = None
        for prefix, label in SECTION_MAP:
            if line.startswith(prefix):
                matched_label = label
                break

        if matched_label:
            # Save previous section if any
            if current is not None:
                sections.append(current)

            # Extract timestamp from header line
            ts_match = TIMESTAMP_RE.search(line)
            dt_str = ts_match.group(0) if ts_match else "unknown"

            current = {
                "label":      matched_label,
                "datetime":   dt_str,
                "data_lines": []
            }

        elif current is not None:
            # Indented data line belonging to current section
            current["data_lines"].append(line)

    # Don't forget the last section
    if current is not None:
        sections.append(current)

    print(f"SNC sections parsed: {[s['label'] for s in sections]}")

    # --------------------------------------------------
    # FORMAT REPORT
    # --------------------------------------------------
    # Extract a date for the report heading from the first section.
    report_date = "unknown date"
    if sections:
        ts = sections[0]["datetime"]
        date_match = re.match(r"(\d{2}-[A-Za-z]{3}-\d{4})", ts)
        if date_match:
            report_date = date_match.group(1)

    lines_out = []
    lines_out.append(f"SNC REPORT — {report_date}")
    lines_out.append("=" * 40)

    for section in sections:
        lines_out.append("")
        lines_out.append(section["label"])
        lines_out.append(f"  Date/Time : {section['datetime']}")
        for data_line in section["data_lines"]:
            lines_out.append(f"  {data_line}")

    lines_out.append("")  # trailing newline

    report_text = "\n".join(lines_out)

    # --------------------------------------------------
    # WRITE REPORT AND CLEAN UP
    # --------------------------------------------------
    try:
        with open(txt_path, "w") as f:
            f.write(report_text)
        print(f"SNC report saved: {txt_path}")
    except Exception as e:
        print(f"SNC write failed: {e}")
        sys.exit(1)

    try:
        os.remove(bin_file)
        print(f"Removed bin file: {bin_file}")
    except Exception as e:
        print(f"Warning: could not remove bin file: {e}")

    # --------------------------------------------------
    # UPDATE LAST SNC TIMESTAMP
    # --------------------------------------------------
    last_snc_path = "/home/labuser/lsc-capture/last_snc.txt"
    try:
        # Extract date from the first section's timestamp
        # sections[0]["datetime"] is e.g. "19-Mar-2026 15:07"
        # We only want the date portion before the space
        snc_date = sections[0]["datetime"].split()[0] if sections else "unknown"
        with open(last_snc_path, "w") as f:
            f.write(snc_date)
        print(f"Last SNC date recorded: {snc_date}")
    except Exception as e:
        print(f"Warning: could not write last_snc.txt: {e}")

        sys.exit(0)

# ==================================================
# SAMPLE PATH
# ==================================================

print(">>> SAMPLE DETECTED")

# --------------------
# ISOLATE SAMPLE BODY
# --------------------
# Header is the first line (ends at first \r\n).
# Body is everything after, up to but not including EOP.
try:
    header, remainder = decoded.split("\r\n", 1)
except ValueError:
    print("Error: header CRLF not found")
    sys.exit(1)

if "EOP" not in remainder:
    print("Error: EOP not found in body")
    sys.exit(1)

body = remainder.split("EOP")[0]

# --------------------
# SAFE FLOAT
# --------------------
def safe_float(x):
    try:
        return float(x.strip())
    except Exception:
        return 0.0

# --------------------
# HEADER PARSING
# --------------------
header_parts = header.split(",")

run_header = {
    "protocol":  header_parts[0],
    "tsie_mode": header_parts[3],
    "roiA_low":  safe_float(header_parts[4]),
    "roiA_high": safe_float(header_parts[5]),
    "roiB_low":  safe_float(header_parts[8]),
    "roiB_high": safe_float(header_parts[9]),
    "roiC_low":  safe_float(header_parts[12]),
    "roiC_high": safe_float(header_parts[13])
}

# --------------------
# SAMPLE SEGMENTATION
# --------------------
# The entire sample run is one long comma-separated line.
# re.split() on the timestamp+protocol pattern carves it into
# per-sample field groups. The timestamps are captured separately
# with re.findall() so we can pair them back with each row.

row_pattern = r'\d{2}-[A-Za-z]{3}-\d{4} \d{2}:\d{2}\d+'

chunks    = re.split(row_pattern, body)
timestamps = re.findall(row_pattern, body)

# Keep only chunks that contain actual sample data
rows = [c.strip().rstrip(",") for c in chunks
        if c.strip().strip(",").strip()
        and c.strip().strip(",").strip()[0].isdigit()]

print(f"Chunks found:     {len(chunks)}")
print(f"Timestamps found: {len(timestamps)}")
print(f"Rows found:       {len(rows)}")

if len(timestamps) != len(rows):
    print("WARNING: timestamp and row count mismatch — check raw body")
    for i, c in enumerate(chunks):
        print(f"  CHUNK {i}: {c.strip()[:80]!r}")

# --------------------
# STRIP LEADING PROTOCOL FROM SAMPLE 1
# --------------------
# Sample 1 begins with the protocol number (e.g. "8," or "12,").
# Samples 2+ begin directly with cassette number.
# We know the protocol from the run header, so we strip it explicitly
# rather than inferring from field counts, which would be ambiguous
# when protocol numbers and cassette numbers share the same value.

protocol_num = run_header["protocol"]

if rows and rows[0].startswith(protocol_num + ","):
    rows[0] = rows[0][len(protocol_num) + 1:]
    print(f"Stripped leading protocol '{protocol_num}' from sample 1")
else:
    print(f"Note: sample 1 did not start with protocol '{protocol_num}' — check header parsing")

# --------------------
# SAMPLE RECORD PARSING
# --------------------
# After stripping the leading protocol from sample 1, every row
# has the same 8-field structure:
#   cassette, position, counttime, roiA, roiB, roiC, tSIE, [EOP or empty]
# The timestamp for each record comes from the parallel timestamps list.
# The protocol is the same for all records and comes from run_header.

run_records = []

for i, (row, ts) in enumerate(zip(rows, timestamps)):
    parts = [p.strip() for p in row.split(",")]

    # Filter out any trailing EOP or empty fields
    parts = [p for p in parts if p and p != "EOP"]

    if len(parts) < 7:
        print(f"  Skipping row {i+1} — too few fields ({len(parts)}): {row[:60]!r}")
        continue

    if len(parts) > 7:
        print(f"  Warning: row {i+1} has extra fields ({len(parts)}) — using first 7: {row[:60]!r}")

    # Timestamp has protocol digit appended — strip the last character
    # e.g. "17-Mar-2026 15:208" → "17-Mar-2026 15:20", protocol "8"
    # For double-digit protocols the last TWO characters would be the
    # protocol — but we already know the protocol from the header,
    # so we strip exactly len(protocol_num) characters from the tail.
    datetime_str = ts[:-(len(protocol_num))].strip()

    record = {
        "protocol":  protocol_num,
        "datetime":  datetime_str,
        "cassette":  parts[0],
        "position":  parts[1],
        "counttime": safe_float(parts[2]),
        "roi_a":     safe_float(parts[3]),
        "roi_b":     safe_float(parts[4]),
        "roi_c":     safe_float(parts[5]),
        "tSIE":      safe_float(parts[6])
    }

    run_records.append(record)
    print(f"  Record {i+1}: cassette={parts[0]} pos={parts[1]} dt={datetime_str}")

print(f"Records parsed: {len(run_records)}")

# --------------------
# FILE PATHS
# --------------------
structured_dir = "/home/labuser/Desktop/LSC_Reports/Processing/Structured"
os.makedirs(structured_dir, exist_ok=True)

base = os.path.basename(bin_file)
stem, _ = os.path.splitext(base)
json_name = stem.replace("cap_", "debug_", 1) + ".json"
json_path = os.path.join(structured_dir, json_name)

# --------------------
# SAVE JSON
# --------------------
try:
    with open(json_path, "w") as jf:
        json.dump({
            "run_header": run_header,
            "samples":    run_records
        }, jf, indent=2)
    print(f"JSON saved: {json_path} ({len(run_records)} records)")
except Exception as e:
    print(f"JSON write failed: {e}")
    sys.exit(1)

# --------------------
# PROMOTE CAP → PAR
# --------------------
if base.startswith("cap_"):
    promoted_name = base.replace("cap_", "par_", 1)
else:
    promoted_name = f"par_{base}"

promoted_path = os.path.join(structured_dir, promoted_name)

try:
    os.rename(bin_file, promoted_path)
    print(f"Promoted CAP → PAR: {promoted_path}")
except Exception as e:
    print(f"Rename failed: {e}")

# --------------------
# CALL REPORTER
# --------------------
subprocess.Popen([
    "python3",
    "/home/labuser/lsc-capture/reporter.py",
    json_path
])
