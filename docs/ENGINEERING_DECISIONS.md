# Engineering decisions and code-review criteria

1. **Strict separation of software and hardware evidence.** A host-side UART echo check can validate transport through an isolated fixture, but cannot emulate an automotive C166 ECU or prove interrupt scheduling.
2. **Fail-closed state machine.** The independent eight-byte controller handles invalid serialized states, deadline expiry, clock rollover, deactivation and reset without silently extending the time budget.
3. **Deterministic tests over visual success.** Reference-model invariants are asserted using repeatable regression cases and pseudo-random event sequences. A passing model test is not represented as physical ECU validation.
4. **Local-first application.** The Python server listens on the loopback address only. State persistence is explicit and retains backups; raw customer and ECU evidence is not part of the public repository.
5. **Git history must be genuine.** The export is a project snapshot. Future commits should accurately reflect actual modifications; synthetic backdated histories are inappropriate.
6. **No firmware publication.** Manufacturer binaries, modified flash images, calibration datasets and private ECU logs are excluded from the portfolio.
