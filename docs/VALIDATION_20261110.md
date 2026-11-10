# Validation record — 2026-11-10

Device used: authorized Windows 10 PC, Python 3.15.2 and Node.js v24.22.2.

## Executed on the public staging copy

- Python public package and read-only localhost API tests: **5 tests, pass**.
- Python independent reference and restricted C166 interpreter contract tests: **23 tests, pass**.
- Python isolated synthetic assembler: **completed**, generated 312 bytes (not vehicle firmware).
- Node.js syntax validation: **site/assets/app.js and site/assets/seed.js passed**.
- The original firmware and physical ECU were **not accessed or modified** by this preparation.
- All FTDI active-port tests and all physical ECU timing or ISR tests remain **not performed**.

## Important limitations

The 312-byte synthetic instruction fixture is an offline test artifact. It is not a complete ECU image and cannot be flashed. The tests do not establish effective DPP registers in actual ISR context, physical SRAM ownership, diagnostic service permissions, real interrupt timing or safe in-vehicle operation.

The public interface displays an anonymized demonstration state, not field-measured telemetry.
