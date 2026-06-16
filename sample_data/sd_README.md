Example data captured from the instrument.

Includes:
- Raw .bin files (captured serial data)
- Processed outputs (JSON and TXT)

These files demonstrate expected input and output formats.

Both SAMPLE and SNC data types are represented, illustrating the system’s different handling approaches.

These files allow users to verify parser behavior and understand the expected data flow through the system.  Included are both minimal and representative sample runs for demonstration and validation.

Note: Additional SAMPLE run data will be added to further illustrate record reconstruction and structured output.

### File Naming

Example files use the same naming conventions as the live system:

- tmp_*  → active capture (incomplete)
- cap_*  → completed capture (ready for parsing)
- par_*  → completed parsing (kept for recovery)
- debug_* → structured JSON output from parser
- report (.txt) → final human-readable report

In the full system, files are organized by protocol and date.  
In this folder, files are shown together for clarity and demonstration.

