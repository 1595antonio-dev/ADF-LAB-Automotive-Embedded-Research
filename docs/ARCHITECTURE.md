# Technical architecture

## Modules
1. Frontend: HTML/CSS and browser JavaScript with test-matrix editing, status tracking, filtering, exports and evidence records.
2. Local API: Python ThreadingHTTPServer bound to 127.0.0.1, JSON persistence with backups, scoped file serving and upload validation.
3. FTDI abstraction: pyserial-based port discovery; active loopback only after explicit isolated TTL fixture and disconnected-ECU confirmations.
4. Embedded reference contracts: deterministic Python state machines implementing tick accounting, mode changes, cooldown and serialized eight-byte model state.
5. Synthetic assembly validation: isolated C166 byte emission and a restricted test interpreter checked against a separate Python model.

## Boundaries and proof
Hardware traces, private serial numbers, manufacturer firmware and actual car calibration images have been excluded.
No physical ECU emulation, true interrupt scheduling, protection from indirect memory writes, calibrated timing, or memory-page ownership proof is supplied.

## Engineering next steps
Expand regression tests, verify source licensing, review generated code changes, use genuine Git commits and obtain owner approval before public publication.
