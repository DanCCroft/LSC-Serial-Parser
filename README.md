# LSC Serial Data Parser

A low-cost, non-invasive system for capturing and digitizing output from legacy liquid
scintillation counters.

This project captures RS-232 serial output from a Packard Tri-Carb instrument and
converts it into structured digital data and readable reports without modifying the
instrument or disrupting normal operation.

## Overview

LSC → RS-232 → Raspberry Pi → Digital Text Report

The system handles both:
- Sample runs (EOP-terminated)
- SNC calibration runs (no explicit terminator)

## Data Types and Parsing Strategy

The system handles two fundamentally different data formats:

### SAMPLE Runs (Reconstructed)
- Continuous CSV-like stream
- Header + variable-length data line
- No explicit record boundaries
- Requires pattern-based reconstruction

### SNC Runs (Pass-Through)
- Multi-section human-readable report
- Transmitted in several serial bursts
- Already structured for interpretation

### Design Approach

- SAMPLE data is parsed and reconstructed into structured JSON
- SNC data is identified and preserved as a text report

This minimizes complexity while maintaining fidelity to instrument output.

## Why This Matters

Many legacy laboratory instruments still rely on paper-based output.

This system:
- Eliminates manual transcription
- Reduces data loss risk
- Enables automated analysis
- Extends the useful life of legacy equipment

## Quick Start

1. Connect Raspberry Pi to RS-232 output
2. Run capture_serial.py
3. Parser processes captured BIN file automatically
4. Output appears as:
   - JSON (sample runs)
   - BIN (raw data)
   - TXT report (SNC runs)
5. Reporter processes the JSON file automatically
6. Output appears as:
   - TXT report (organized sample data)

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

## Serial Wiring (RS-232 Interface)

### Important

The RS-232 output on the Packard Tri-Carb does not follow a standard PC serial wiring configuration.

A custom cable and breakout wiring were required to establish reliable communication.

---

### Signal Mapping

Instrument (DB25) → USB Serial Adapter (DB9)

| Function                  | DB9 Pin | DB25 Pin | Notes |
|--------------------------|--------|---------|------|
| TXD (Instrument → Pi)    | 2      | 2       | Data transmitted from instrument |
| RXD (Pi → Instrument)    | 3      | 3       | Required for handshake logic     |
| CTS                      | 8      | 5       | Clear to Send                    |
| DCD                      | 1      | 8       | Data Carrier Detect              |
| RI                       | 9      | 22      | Ring Indicator                   |

---

### Hardware Handshake (Critical)

The instrument requires certain hardware handshake signals to be present before it will transmit data.

Because no modem is used, these signals are satisfied locally using jumpers inside the DB25 breakout connector.

---

### Breakout Jumper Configuration

Inside the DB25 breakout:

- Pin 4   ↔ Pin 5   (RTS ↔ CTS)
- Pin 20  ↔ Pin 6   (DTR ↔ DSR)

These jumpers emulate the expected modem control signals and allow the instrument to transmit data normally.

---

### Notes

- A direct-cable or standard adapter will likely NOT work without these modifications.
- If no data is received, incorrect handshake wiring is a common cause.
- Wiring must be verified against the instrument manual and may vary by model.
Instrument (DB25)
      |
      |  custom breakout wiring
      |
     DB9 USB Adapter → Raspberry Pi

TX → RX 
RX ← TX 
GND ↔ GND

RTS ─┐
      ├────────── CTS
DTR ─┘


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

## File Structure

```
/home/labuser/
└── capture_serial.py       # Serial capture and frame detection

/home/labuser/lsc-capture/
├── parser.py               # Protocol parsing and JSON output
├── reporter.py             # Human-readable report generation
├── structured_organizer.py # Periodic file organization
├── last_snc.txt            # Auto-updated calibration timestamp
└── capture_serial.service  # Copy to /etc/systemd/system/
```

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
