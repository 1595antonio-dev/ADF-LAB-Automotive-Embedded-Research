# ADF LAB — Automotive Embedded Research Bench

**Working software portfolio | Python, JavaScript, HTML/CSS and offline embedded-state models**

ADF LAB is a locally hosted engineering application for organizing experiments in automotive embedded systems. It combines a stateful test matrix, a local Python HTTP API, FTDI adapter safety checks and independent reference-model tests.

The application and model code come from a real, continuing research project. **The public demonstration state is anonymized.** Manufacturer firmware, calibration data, original device serials, ECU logs, real measurements and vehicle identifiers are excluded. No vehicle-level safety or functional claim is implied by the portfolio.

## Code structure

- site: editable nine-section engineering dashboard, Python localhost server, JSON state persistence, backups and optional FTDI discovery.
- work: reference controllers, isolated assembly builder and a restricted sequential C166 test interpreter.
- tests: public package and local read-only API regression tests.
- docs: architecture, application description, technical limits and publication checklist.

## Run dashboard

On Windows with Python 3 installed:

~~~powershell
cd site
python servidor_local.py --sin-navegador
~~~

Open http://127.0.0.1:8765. Server binds only to localhost. It is not suitable for internet exposure without authentication and security hardening.

Alternatively open site/index.html directly. Browser-only mode works without hardware access; persistent disk API requires the local Python backend.

## Run offline tests

~~~powershell
python work/build_release_core_20261102.py
python -m unittest discover -s work -p "test_*.py" -v
python -m unittest discover -s tests -p "test_*.py" -v
node --check site/assets/app.js
node --check site/assets/seed.js
~~~

Node.js validation is optional. Python uses standard library except optional pyserial for a separately validated isolated fixture.

The assembler creates an **isolated synthetic instruction fixture** for a restricted sequential interpreter. It is **not manufacturer firmware and is never flashable**. Its tests do not emulate physical memory access, ISR/PEC behavior, effective DPP, timing, complete ECU execution, or diagnostic writes. No automated test opens a serial COM port.

## How AI-assisted coding is reviewed

I evaluate AI-generated or AI-assisted changes through explicit behavior contracts, deterministic regression tests, comparisons against reference models, careful distinction between measured evidence and assumptions, and rejection of unproven hardware conclusions. Work remains ongoing.

## Publication and ownership

This public repository is the selected, anonymized portfolio snapshot. Its Git history starts with an authentic initial commit; no earlier history is fabricated. Proprietary firmware and private diagnostic evidence remain outside the repository. Copyright remains with the project owner; no open-source license is granted in this snapshot. Review distribution rights before adding new third-party code.
