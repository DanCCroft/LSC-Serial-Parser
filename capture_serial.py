#!/usr/bin/env python3
# capture_serial.py — content-based termination for SNC and SAMPLE runs

import serial
import os
import time
import datetime
import signal
import subprocess
import sys

INGEST_DIR = "/home/labuser/Desktop/LSC_Reports/Processing/Ingest"
SERIAL_PORT = "/dev/serial/by-id/usb-Prolific_Technology_Inc._USB-Serial_Controller_CBBFb147613-if00-port0"
BAUD_RATE = 1200

# SNC terminators
# BKG_HEADER signals the 5th and final section has begun.
# Once seen, a short completion timer is armed.
# SNC_TERMINATOR is the last line of a complete SNC transmission —
# promotion fires immediately when this is seen.
# Two spaces between H3 and E^2/B — matches raw serial format exactly.
# Verify against hex dump at offset 0x1d0 if this ever stops matching.
BKG_HEADER    = b"BKG IPA DATA PROCESSED"
SNC_TERMINATOR = b"H3  E^2/B"

# Once the BKG section header is seen, this is the maximum time we
# wait for the final line before promoting anyway.
BKG_COMPLETION_TIMEOUT = 30.0  # seconds

def make_tmp_path():
    timestamp = datetime.datetime.now().strftime("%Y-%b-%d-%H%M")
    return os.path.join(INGEST_DIR, f"tmp_{timestamp}.bin")

terminate_requested = False

def handle_shutdown(signum, frame):
    global terminate_requested
    print(">>> Shutdown signal received...")
    terminate_requested = True

signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)

os.makedirs(INGEST_DIR, exist_ok=True)

try:
    ser = serial.Serial(
        port=SERIAL_PORT,
        baudrate=BAUD_RATE,
        bytesize=serial.SEVENBITS,
        parity=serial.PARITY_EVEN,
        stopbits=serial.STOPBITS_ONE,
        timeout=1
    )
except Exception as e:
    print(f"Serial open failed: {e}")
    sys.exit(1)

ser.reset_input_buffer()
print("Serial port open. Waiting for data...")

run_active     = False
current_file   = None
tmp_path       = None
frame_mode     = None       # "SNC" or "SAMPLE"
frame_buffer   = b""        # holds bytes until mode identified
snc_buffer     = b""        # accumulates SNC content for terminator scan
bkg_seen       = False      # True once BKG section header arrives
bkg_seen_time  = None       # monotonic time when BKG header was first seen
last_byte_time = None


def finalize_capture(tmp_path, current_file, reason):
    current_file.flush()
    os.fsync(current_file.fileno())
    current_file.close()
    cap_path = tmp_path.replace("tmp_", "cap_")
    os.rename(tmp_path, cap_path)
    os.sync()
    print(f">>> Promoted to {cap_path}  (reason: {reason})")
    subprocess.Popen([
        "python3",
        "/home/labuser/lsc-capture/parser.py",
        cap_path
    ])


def reset_frame_state():
    global run_active, current_file, tmp_path, frame_mode
    global frame_buffer, snc_buffer, bkg_seen, bkg_seen_time, last_byte_time
    run_active     = False
    current_file   = None
    tmp_path       = None
    frame_mode     = None
    frame_buffer   = b""
    snc_buffer     = b""
    bkg_seen       = False
    bkg_seen_time  = None
    last_byte_time = None


try:
    while not terminate_requested:
        data = ser.read(1024)

        if data:
            # --------------------------------------------------
            # Open a new frame if we were idle
            # --------------------------------------------------
            if not run_active:
                print(">>> FRAME STARTED")
                run_active   = True
                tmp_path     = make_tmp_path()
                current_file = open(tmp_path, "wb")
                frame_buffer = b""
                snc_buffer   = b""
                bkg_seen     = False
                bkg_seen_time = None

            # --------------------------------------------------
            # Write verbatim
            # --------------------------------------------------
            current_file.write(data)
            current_file.flush()
            os.fsync(current_file.fileno())
            last_byte_time = time.monotonic()

            # --------------------------------------------------
            # Identify mode from first line if not yet known
            # --------------------------------------------------
            if frame_mode is None:
                frame_buffer += data
                if b"\r\n" in frame_buffer:
                    first_line = frame_buffer.split(b"\r\n")[0]
                    first_line_str = first_line.decode("ascii", errors="ignore").strip()
                    print(f">>> First line: {first_line_str!r}")

                    if first_line_str.startswith("C14 IPA DATA PROCESSED"):
                        frame_mode = "SNC"
                        snc_buffer = frame_buffer
                        print(">>> Mode: SNC — waiting for BKG section then H3 E^2/B terminator")
                    else:
                        frame_mode = "SAMPLE"
                        print(">>> Mode: SAMPLE — waiting for EOP")

            # --------------------------------------------------
            # SAMPLE termination: EOP in stream
            # --------------------------------------------------
            elif frame_mode == "SAMPLE":
                if b"EOP" in data:
                    print(">>> EOP detected — finalizing sample run")
                    finalize_capture(tmp_path, current_file, "EOP")
                    reset_frame_state()

            # --------------------------------------------------
            # SNC termination: content-based
            # --------------------------------------------------
            elif frame_mode == "SNC":
                snc_buffer += data

                # Step 1 — watch for BKG section header (5th burst)
                if not bkg_seen and BKG_HEADER in snc_buffer:
                    bkg_seen      = True
                    bkg_seen_time = time.monotonic()
                    print(">>> BKG section detected — short completion timer armed")

                # Step 2 — watch for final line
                if SNC_TERMINATOR in snc_buffer:
                    tail = snc_buffer[snc_buffer.index(SNC_TERMINATOR):]
                    if b"\r\n" in tail:
                        print(">>> SNC terminator received — finalizing SNC run")
                        finalize_capture(tmp_path, current_file, "SNC_TERMINATOR")
                        reset_frame_state()

        else:
            # --------------------------------------------------
            # Idle checks — only meaningful after BKG section seen
            # --------------------------------------------------
            if run_active and frame_mode == "SNC" and bkg_seen:
                idle = time.monotonic() - bkg_seen_time
                if idle >= BKG_COMPLETION_TIMEOUT:
                    print(f">>> BKG completion timeout ({idle:.1f}s) — finalizing SNC run")
                    finalize_capture(tmp_path, current_file, "BKG_TIMEOUT")
                    reset_frame_state()

except Exception as e:
    print(f"Capture error: {e}")

# --------------------------------------------------
# Clean shutdown
# --------------------------------------------------
if current_file and run_active:
    print(">>> Shutdown — finalizing partial capture")
    finalize_capture(tmp_path, current_file, "SHUTDOWN")

ser.close()
print("Serial port closed.")
