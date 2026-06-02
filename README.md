# RS SMP Tools

Python tools for controlling and diagnosing the Rohde & Schwarz SMP02 signal generator via GPIB.

## Overview

This repository contains a suite of GPIB-based test and diagnostic scripts for the SMP02 microwave signal generator:

- **smp_cw.py** — Set frequency, power level, and output state via command-line arguments
- **smp_diag.py** — Run comprehensive diagnostic test point measurements with variant detection
- **smp_test.py** — Functional test suite covering modules A4–A26 with optional deep testing
- **smp_ucor.py** — Manage UCOR correction lists: upload, activate, deactivate, delete, list
- **smp_common.py** — Shared utilities: connection, device queries, A9 variant detection, test point reading

## Setup

### Dependencies

- Python 3.12+
- `pyvisa>=1.14` — GPIB device control
- `quantiphy>=2.19` — Quantity parsing with unit support

Install dependencies:
```bash
pip install -r requirements.txt
```

For development (linting, type checking):
```bash
pip install -r requirements-dev.txt
```

### Configuration

Device address and retry parameters are defined in `smp_common.py`:
- `SMP_ADDRESS` — GPIB address (default: "GPIB1::28::INSTR")
- `SMP_IDN_HINT` — Expected device ID substring (default: "SMP02")
- `READS_PER_POINT` — Samples per measurement (default: 3)
- `READ_DELAY` — Inter-sample delay (default: 0.05 s)
- `POINT_DELAY` — Pre-measurement settling (default: 0.15 s)

## Quick Start

```bash
# Set frequency and power
python smp_cw.py 10GHz 0dBm on

# Run diagnostics
python smp_diag.py -m A7 A9

# Run functional tests
python smp_test.py

# Manage UCOR correction tables
python smp_ucor.py upload 0_dBm.csv --setpoint 0 --name UCOR0 --activate
python smp_ucor.py list
python smp_ucor.py delete UCOR0 --force
```

Use `--help` on any tool for full options and examples.

## Code Quality

```bash
python ci/check.py              # Check for issues
python ci/check.py --fix        # Fix issues automatically
```

Configuration: `pyproject.toml` (ruff + mypy settings)

## Related Projects

- [**rs_smp_ocr**](https://github.com/mankangustafsson/rs_smp_ocr) — OCR and PDF parsing for SMP02 documentation
- [**rs_smp_a21_repair**](https://github.com/mankangustafsson/rs_smp_a21_repair) — KiCAD files for A21 PA stage replacement board

## License

MIT License — see [LICENSE](LICENSE) file.
