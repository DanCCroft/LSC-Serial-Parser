# LSC Serial Data Parser

## Overview
This project provides a complete pipeline for capturing and processing RS-232 output from a Packard Tri-Carb Liquid Scintillation Counter (LSC).

The system handles both:
- Sample runs (EOP-terminated)
- SNC calibration runs (no explicit terminator)

## Architecture

Capture → Parse → Report → Organize

1. capture_serial.py
   - Reads continuous RS-232 stream
   - Detects run type (SAMPLE or SNC)
   - Writes raw data to file

2. parser.py
   - Reconstructs records from continuous stream
   - Outputs structured JSON
   - Handles SNC section parsing

3. reporter.py
   - Generates human-readable reports
   - Organizes output by protocol and date

4. structured_organizer.py
   - Runs periodically via cron
   - Moves processed files into protocol and date subfolders

## Key Technical Challenge

The instrument outputs a continuous comma-delimited stream with no explicit record boundaries.  
Records must be reconstructed using deterministic segmentation and timestamp extraction.

Sample runs terminate on EOP detection. SNC runs present a more complex challenge — five 
sections are minutes or hours apart with no explicit terminator. The pipeline uses
content-based detection to identify the final section and a short completion timer as a 
safety net.

## Software Requirements

- Python 3
- pyserial

## Equipment Requirements

### Computing
- Raspberry Pi 4 (4GB) or Raspberry Pi 5 (developer used 8GB Pi 5)
- Official power supply
- MicroSD card (32GB Class 10 or better)
- Case with cooling
- Anker 4-port USB hub (necessary — serial adapter, keyboard, 
  mouse, and USB transfer drive consume all available ports)

### Display and Input
- Monitor with appropriate cable
- Wireless keyboard and mouse combo

### Serial Interface
- USB-A to DB9 RS-232 adapter (Prolific PL2303 chipset)
- RS-232 DB9 extension cable with pigtail ends, Female
- DB25 breakout connector, Female

Note: Total hardware investment in the $200–350 range depending 
on component choices and availability. Current Raspberry Pi pricing 
fluctuates — check official resellers for current rates.

## Serial Configuration
Baud rate   : 1200
Data bits   : 7
Parity      : Even
Stop bits   : 1
Flow control: None

A sample systemd service file is provided for running the capture script as a background service.

Features:
- Automatic restart on failure
- Boot-time startup
- System-level logging via journalctl

To use:
1. Copy capture_serial.service to /etc/systemd/system/
2. Adjust paths and user as needed
3. Run:
   sudo systemctl daemon-reload
   sudo systemctl enable capture_serial
   sudo systemctl start capture_serial

## File Structure Overview
...
/home/User/
+--capture_serial.py  # Serial capture and frame detection

/home/labuser/lsc-capture/
+--parser.py               # Protocol parsing and JSON output
+-- reporter.py             # Human-readable report generation
+-- structured_organizer.py # Periodic file organization
+-- last_snc.txt            # Auto-updated calibration timestamp
`-- capture_serial.service  # Copy to /etc/systemd/system/

Output Structure
Reports are organized automatically under a configurable base directory:
LSC_Reports/
+--Protocol_8/
│   `--2026-03-19/
│       `--P8_2026-Mar-19-1520.txt
+-- SNC/
│   `--snc_2026-Mar-19-1354.txt
`--Processing/
    +--Ingest/        # Active capture landing zone
    `--Structured/    # Parsed files awaiting organization
...

## Notes

- RS-232 pinout may be non-standard; breakout-based wiring may be required
- Designed for Raspberry Pi but portable to other systems

## Troubleshooting
- No data received: Check serial port path with `ls /dev/serial/by-id/`
- SNC run not captured: Confirm BKG_HEADER and SNC_TERMINATOR 
  match your instrument's exact output using xxd on a captured file
- Wrong user permissions: Ensure service runs as the same user 
  that owns the output directories

## License

MIT
