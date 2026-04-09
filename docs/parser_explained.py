#!/usr/bin/env python3
# PIPELINE STAGE: TRANSFORMATION

"""
Parses captured binary data from a Packard Tri-Carb LSC (Liquid Scintillation Counter) instrument
and converts it into structured output.

This script handles 2 distinct data modes:

1.  Sample runs
    - Continuous comma-delimited stream
    - No explicit row delimiters
    - Ends with "EOP"

2.  SNC (calibration) runs
    - Human-readable multi-section report
    - No explicit terminator
    - Organized into labeled sections

Key Design Challenge:
The SAMPLE data stream is not truly structured.  Record boundaries must be
reconstructed using timestamp patterns rather than relying on delimiters.

Pipeline Role:
Cap (.bin) → Parser → JSON → Reporter
"""

# ==================================================
# IMPORTS
# ==================================================

import sys
import os
import json
import re
import subprocess

print("=== PARSER INVOKED ===")
print("Args:", sys.argv)

# ==================================================
# INPUT VALIDATION
# ==================================================

if len(sys.argv) != 2:
    print("Usage: parser.py <binfile>")
    sys.exit(1)

bin_file = sys.argv[1]

if not os.path.exists(bin_file):
    print(f"Error: file '{bin_file}' does not exist")
    sys.exit(1)

# ==================================================
# FILE READ / DECODE
# ==================================================
try:
    with open(bin_file, "rb") as f:
        raw = f.read()
    decoded = raw.decode("ascii", errors="ignore")
except Exception as e:
    print(f"Error reading file: {e}")
    sys.exit(1)

# ==================================================
# FRAME TYPE DETECTION
# ==================================================
# The first line determines whether this is:
# -SAMPLE run
# -SNC calibration report
#
# We strip leading noise (nulls/shitespace) to ensure accurate detection.

cleaned = decoded.lstrip("\x00\r\n \t")
first_line = cleaned.splitlines()[0] if cleaned else ""

print(f"FIRST LINE: {first_line!r}")

# ==================================================
# SNC PROCESSING PATH (Calibration Reports)
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

    # Derive output filename from capture timestamp
    # e.g. cap_20260317-135400.bin → snc_20260317-135400.txt
    base = os.path.basename(bin_file)
    stem, _ = os.path.splitext(base)
    txt_name = stem.replace("cap_", "snc_", 1) + ".txt"
    txt_path = os.path.join(snc_dir, txt_name)

    # --------------------------------------------------
    # SNC Section Parsing
    # --------------------------------------------------
    # Each section consists of:
    #    Header line (Contains timestamp)
    #    Followed by one or more data lines
    
    SECTION_MAP = [
        ("C14 CHI SQUARE IPA DATA PROCESSED", "C14 Chi Square"),
        ("C14 IPA DATA PROCESSED",            "C14 Efficiency"),
        ("H3 CHI SQUARE IPA DATA PROCESSED",  "H3 Chi Square"),
        ("H3 IPA DATA PROCESSED",             "H3 Efficiency"),
        ("BKG IPA DATA PROCESSED",            "Background"),
    ]

    TIMESTAMP_RE = re.compile(r"\d{2}-[A-Za-z]{3}-\d{4} \d{2}:\d{2}")

    sections = []   # list of dicts: {label, datetime, data_lines[]}
    current = None

    for raw_line in cleaned.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        matched_label = None
        for prefix, label in SECTION_MAP:
            if line.startswith(prefix):
                matched_label = label
                break

        if matched_label:
            if current is not None:
                sections.append(current)

             ts_match = TIMESTAMP_RE.search(line)
            dt_str = ts_match.group(0) if ts_match else "unknown"

            current = {
                "label":      matched_label,
                "datetime":   dt_str,
                "data_lines": []
            }

        elif current is not None:

    if current is not None:
        sections.append(current)

    print(f"SNC sections parsed: {[s['label'] for s in sections]}")

    # --------------------------------------------------
    # FORMAT REPORT
    # --------------------------------------------------
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
    # WRITE OUTPUT
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
        # Record the most recent SNC Calibration date.
        # This is used by downstream reporting to contextualize sample runs.

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

# --------------------------------------------------
# ISOLATE HEADER AND BODY
# --------------------------------------------------

try:
    header, remainder = decoded.split("\r\n", 1)
except ValueError:
    print("Error: header CRLF not found")
    sys.exit(1)

if "EOP" not in remainder:
    print("Error: EOP not found in body")
    sys.exit(1)

body = remainder.split("EOP")[0]

# --------------------------------------------------
# HEADER PARSING
# --------------------------------------------------
def safe_float(x):
    try:
        return float(x.strip())
    except Exception:
        return 0.0

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

# --------------------------------------------------
# SAMPLE SEGMENTATION
# --------------------------------------------------
# CRITICAL:
# The data stream has no row delimiters.
# Each record ends with a timestamp that includes the protocol digit at the end.
# 
# Strategy:
#     - Split rows using timestamp pattern (boundary marker)
#     - Extract timestamps separately
#     - Reassociate them with each row

row_pattern = r'\d{2}-[A-Za-z]{3}-\d{4} \d{2}:\d{2}\d+'

chunks    = re.split(row_pattern, body)
timestamps = re.findall(row_pattern, body)

rows = [c.strip().rstrip(",") for c in chunks
        if c.strip().strip(",").strip()
        and c.strip().strip(",").strip()[0].isdigit()]

if len(timestamps) != len(rows):
    print("WARNING: row/timestamp mismatch - possible boundary error")

# --------------------------------------------------
# NORMALIZE FIRST ROW
# --------------------------------------------------
# First row contains protocol prefix -remove it explicitly

protocol_num = run_header["protocol"]

if rows and rows[0].startswith(protocol_num + ","):
    rows[0] = rows[0][len(protocol_num) + 1:]
    print(f"Stripped leading protocol '{protocol_num}' from sample 1")
else:
    print(f"Note: sample 1 did not start with protocol '{protocol_num}' — check header parsing")

# --------------------------------------------------
# RECORD RECONSTRUCTION
# --------------------------------------------------
# Each row contains 7 fields:
# cassette, position, counttime, roiA, roiB, roiC, tSIE
#
# Timestamp is NOT a true field:
#    - It includes protocol digits
#    - It exists at record boundaries
#    - It must be cleaned and reattached

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

    # Remove protocol digits from timestamp
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
    
print(f"Records parsed: {len(run_records)}")

# ==================================================
# OUTPUT (JSON + FILE PROMOTION)
# ==================================================

structured_dir = "/home/labuser/Desktop/LSC_Reports/Processing/Structured"
os.makedirs(structured_dir, exist_ok=True)

base = os.path.basename(bin_file)
stem, _ = os.path.splitext(base)
json_name = stem.replace("cap_", "debug_", 1) + ".json"

json_path = os.path.join(structured_dir, json_name)

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

# ==================================================
# HANDOFF TO REPORTER
# ==================================================
subprocess.Popen([
    "python3",
    "/home/labuser/lsc-capture/reporter.py",
    json_path
])
