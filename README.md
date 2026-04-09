# LSC Serial Data Parser

## Overview
This project provides a complete pipeline for capturing and processing RS-232 output from a Packard Tri-Carb Liquid Scintillation Counter (LSC).

The system handles both:
- Sample runs (EOP-terminated)
- SNC calibration runs (no explicit terminator)

## Architecture

Capture → Parse → Report

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

## Key Technical Challenge

The instrument outputs a continuous comma-delimited stream with no explicit record boundaries.  
Records must be reconstructed using deterministic segmentation and timestamp extraction.

## Requirements

- Python 3
- pyserial

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

## Notes

- RS-232 pinout may be non-standard; breakout-based wiring may be required
- Designed for Raspberry Pi but portable to other systems

## License

MIT
