#!/usr/bin/env python3/
import os
import sys
import json
import re
import stat
from datetime import datetime

BASE_DIR = "/home/labuser/Desktop/LSC_Reports"
INSTRUMENT_SERIAL = "TriCarb-2100TR - SN: 421879"


def fail(msg, code=1):
    print(f"[REPORTER ERROR] {msg}")
    sys.exit(code)


def load_json(path):
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        fail(f"JSON load failed: {e}", 2)


def validate_structure(data):
    if "run_header" not in data:
        fail("Missing run_header block")
    if "samples" not in data:
        fail("Missing samples array")
    if not isinstance(data["samples"], list):
        fail("samples is not a list")
    header = data["run_header"]
    required_fields = [
        "protocol",
        "roiA_low", "roiA_high",
        "roiB_low", "roiB_high",
        "roiC_low", "roiC_high"
    ]
    for field in required_fields:
        if field not in header:
            fail(f"Missing header field: {field}")
    return header, data["samples"]


def extract_timestamp_from_filename(path):
    basename = os.path.basename(path)
    # Matches new format: debug_2026-Mar-19-1520.json
    match = re.match(r"debug_(\d{4}-[A-Za-z]{3}-\d{2}-\d{4})\.json$", basename)
    if not match:
        fail(f"Filename does not match expected debug_YYYY-Mon-DD-HHMM.json pattern — got: {basename}")
    return match.group(1)


def build_directory(protocol, timestamp):
    # Parse new format: 19-Mar-2026-1520
    dt_obj = datetime.strptime(timestamp, "%Y-%b-%d-%H%M")
    date_folder = dt_obj.strftime("%Y-%m-%d")
    protocol_dir = os.path.join(BASE_DIR, f"Protocol_{protocol}")
    date_dir = os.path.join(protocol_dir, date_folder)
    os.makedirs(date_dir, exist_ok=True)
    return date_dir


def resolve_collision(directory, filename):
    base, ext = os.path.splitext(filename)
    counter = 1
    full_path = os.path.join(directory, filename)
    while os.path.exists(full_path):
        full_path = os.path.join(directory, f"{base}_{counter:02}{ext}")
        counter += 1
    return full_path


def write_sample_table(f, samples):
    col_widths = [9, 9, 12, 10, 10, 10, 11]
    headers = [
        "Cassette",
        "Position",
        "Count Time",
        "CPM A",
        "CPM B",
        "CPM C",
        "tSIE"
    ]
    header_fmt = (
        f"{headers[0]:>{col_widths[0]}} "
        f"{headers[1]:>{col_widths[1]}} "
        f"{headers[2]:>{col_widths[2]}} "
        f"{headers[3]:>{col_widths[3]}} "
        f"{headers[4]:>{col_widths[4]}} "
        f"{headers[5]:>{col_widths[5]}} "
        f"{headers[6]:>{col_widths[6]}}"
    )
    f.write(header_fmt + "\n")
    total_width = sum(col_widths) + 6
    f.write("-" * total_width + "\n")
    row_fmt = (
        f"{{cass:>{col_widths[0]}}} "
        f"{{pos:>{col_widths[1]}}} "
        f"{{ct:>{col_widths[2]}.1f}} "
        f"{{a:>{col_widths[3]}.1f}} "
        f"{{b:>{col_widths[4]}.1f}} "
        f"{{c:>{col_widths[5]}.1f}} "
        f"{{tsie:>{col_widths[6]}.2f}}"
    )
    for s in samples:
        try:
            line = row_fmt.format(
                cass=int(s.get("cassette", 0)),
                pos=int(s.get("position", 0)),
                ct=float(s.get("counttime", 0)),
                a=float(s.get("roi_a", 0)),
                b=float(s.get("roi_b", 0)),
                c=float(s.get("roi_c", 0)),
                tsie=float(s.get("tSIE", 0))
            )
        except Exception:
            continue
        f.write(line + "\n")

def get_last_snc_date(path="/home/labuser/lsc-capture/last_snc.txt"):
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return "No calibration record found"
    except Exception as e:
        return f"Unavailable ({e})"

def write_report(path, protocol, timestamp, header, samples):
    # Parse new format: 2026-Mar-19-1520
    dt_obj = datetime.strptime(timestamp, "%Y-%b-%d-%H%M")
    with open(path, "w") as f:
        last_snc = get_last_snc_date()
        f.write("Tri-Carb Liquid Scintillation Counter Report\n")
        f.write("============================================\n\n")
        f.write(f"Instrument Serial : {INSTRUMENT_SERIAL}\n")
        f.write(f"Protocol Number   : {protocol}\n")
        f.write(f"Run Date          : {dt_obj.strftime('%Y-%m-%d')}\n")
        f.write(f"Run Time          : {dt_obj.strftime('%H:%M')}\n\n")
        f.write(f"Last Calibration  : {last_snc}\n\n")
        f.write(f"Region A          : {header['roiA_low']} – {header['roiA_high']} keV\n")
        f.write(f"Region B          : {header['roiB_low']} – {header['roiB_high']} keV\n")
        f.write(f"Region C          : {header['roiC_low']} – {header['roiC_high']} keV\n")
        f.write(f"tSIE Mode         : {header.get('tsie_mode', 'UNKNOWN')}\n\n")
        write_sample_table(f, samples)


def main():
    if len(sys.argv) != 2:
        fail("Usage: reporter.py <debug_json_path>")

    json_path = sys.argv[1]
    data = load_json(json_path)
    header, samples = validate_structure(data)
    protocol = header["protocol"]
    timestamp = extract_timestamp_from_filename(json_path)
    date_dir = build_directory(protocol, timestamp)
    report_name = f"P{protocol}_{timestamp}.txt"
    full_path = resolve_collision(date_dir, report_name)
    write_report(full_path, protocol, timestamp, header, samples)
    os.chmod(full_path, 0o444)
    print(f"[REPORTER] Report written: {full_path}")


if __name__ == "__main__":
    main()
