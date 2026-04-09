#!/usr/bin/env python3
# PIPELINE STAGE: INGESTION

"""
Continuously reads RS-232 output from a Tri-Carb LSC and writes raw data to disk.

Responsibilities:
    - Detect start of a data frame
    - Identify run type (SAMPLE vs SNC)
    - Apply termination logic:
          - Sample → "EOP"
          - SNC → content-based detection
    - Promote completed files for downstream parsing

Key Constraints:
The instrument output is a continuous byte stream with no guaranteed
record or frame boundaries.  This script relies on content-based detection
rather than transport-level structure.

Designed to run as a long-lived system service.
"""

# ==================================================
# IMPORTS
# ==================================================

import serial
import os
import time
import datetime
import signal
import subprocess
import sys

# ==================================================
# CONFIGURATION (PATHS, SERIAL SETTINGS)
# ==================================================

INGEST_DIR = "/home/labuser/Desktop/LSC_Reports/Processing/Ingest"
SERIAL_PORT = "/dev/serial/by-id/usb-Prolific_Technology_Inc._USB-Serial_Controller_CBBFb147613-if00-port0"
BAUD_RATE = 1200

# ==================================================
# PROTOCOL CONSTANTS (SNC TERMINATION MARKERS)
# ==================================================

# Exact match required for final SNC line.
# Note: spacing is significant due to raw instrument output format.

BKG_HEADER    = b"BKG IPA DATA PROCESSED"
SNC_TERMINATOR = b"H3  E^2/B"

BKG_COMPLETION_TIMEOUT = 30.0  # seconds

# ==================================================
# SIGNAL HANDLING
# ==================================================

terminate_requested = False

def handle_shutdown(signum, frame):
    global terminate_requested
    print(">>> Shutdown signal received...")
    terminate_requested = True

signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)

# ==================================================
# SERIAL INITIALIZATION
# ==================================================

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
frame_mode     = None
frame_buffer   = b"" 
snc_buffer     = b"" 
bkg_seen       = False
bkg_seen_time  = None       
last_byte_time = None

# ==================================================
# HELPER FUNCTIONS
# ==================================================

# Promote completed capture:
# - Flush and close file
# - Rename tmp → cap to signal completeness
# - Trigger downstream parser
#
# The rename acts as a synchronization point to prevent
# downstream processes from reading partial files.

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

# Reset all state variables to prepare for the next frame.
# Ensures no residual data contaminates subsequent runs.

def make_tmp_path():
    timestamp = datetime.datetime.now().strftime("%Y-%b-%d-%H%M")
    return os.path.join(INGEST_DIR, f"tmp_{timestamp}.bin")

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

# ==================================================
# MAIN CAPTURE LOOP
# ==================================================

try:
    while not terminate_requested:
        data = ser.read(1024)

        if data:
            # --------------------------------------------------
            # FRAME START
            # --------------------------------------------------
            # The instrument does not emit an explicit start-of-run marker
            # A new frame is assumed when data arrives after and idle period.

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
            # WRITE
            # --------------------------------------------------
            # Write raw bytes immediately to disk.
            # fsync ensures data is physically written, reducing risk of loss
            # in long-running unattended operation

            current_file.write(data)
            current_file.flush()
            os.fsync(current_file.fileno())
            last_byte_time = time.monotonic()

            # --------------------------------------------------
            # MODE DETECTION
            # --------------------------------------------------
            # Detmine run mode from the first line of output.
            # SNC runs include human-readable headers; samples runs do not.
            # Mode detection is required before applying termination logic.

            if frame_mode is None:
                frame_buffer += data
                if b"\r\n" in frame_buffer:
                    first_line = frame_buffer.split(b"\r\n")[0]
                    first_line_str = first_line.decode("ascii", errors="ignore").strip()
                    
                    if first_line_str.startswith("C14 IPA DATA PROCESSED"):
                        frame_mode = "SNC"
                        snc_buffer = frame_buffer
                        
                    else:
                        frame_mode = "SAMPLE"
                        
            # --------------------------------------------------
            # SAMPLE TERMINATION
            # --------------------------------------------------
            # Sample runs include an explicit "EOP" terminator.
            # Detection is straightforward compared to SNC.

            elif frame_mode == "SAMPLE":
                if b"EOP" in data:
                    finalize_capture(tmp_path, current_file, "EOP")
                    reset_frame_state()

            # --------------------------------------------------
            # SNC TERMINATION
            # --------------------------------------------------
            # SNC runs do NOT include an explicit end-of-process marker.
            # Completion is inferred using a combination of:
            #     1. Detection of final section header (BKG)
            #     2. Detection of the final statistics line
            #     3. A fallback timeout after the final section begins

            elif frame_mode == "SNC":
                snc_buffer += data

                # Step 1 — detect start of final SNC section (Background data)
                if not bkg_seen and BKG_HEADER in snc_buffer:
                    bkg_seen      = True
                    bkg_seen_time = time.monotonic()
                    
                # Step 2 — watch for final line
                if SNC_TERMINATOR in snc_buffer:
                    tail = snc_buffer[snc_buffer.index(SNC_TERMINATOR):]
                    if b"\r\n" in tail:
                        finalize_capture(tmp_path, current_file, "SNC_TERMINATOR")
                        reset_frame_state()

        else:
            # --------------------------------------------------
            # IDLE CHECK
            # --------------------------------------------------
            # After the final SNC section begins, the instrument may pause
            # before sending the final line. A timeout ensures the run is
            # finalized even if the last line is delayed or missing.

            if run_active and frame_mode == "SNC" and bkg_seen:
                idle = time.monotonic() - bkg_seen_time
                if idle >= BKG_COMPLETION_TIMEOUT:
                    finalize_capture(tmp_path, current_file, "BKG_TIMEOUT")
                    reset_frame_state()

except Exception as e:
    print(f"Capture error: {e}")

# ==================================================
# CLEAN SHUTDOWN
# ==================================================
# If a run is in progress, finalize partial capture to avoid data loss.

if current_file and run_active:
    print(">>> Shutdown — finalizing partial capture")
    finalize_capture(tmp_path, current_file, "SHUTDOWN")

ser.close()
print("Serial port closed.")
