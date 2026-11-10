"""Eight-byte *theoretical* joint POPS/cluster-indicator state.

This is a behavior contract, not a firmware patch, ECU bus driver, or proof
that 0x387F00..07 is free. The indicator output is a requested cluster value;
the caller must use a verified cluster-only path, never engine-control RPM.
"""
from dataclasses import dataclass
from pops_event_ticks_reference_20261102 import ReleaseBudget, Phase, MASK32, HALF32

MODES = (90, 69, 105, 165)
RPM = (1000, 2000, 3000, 4000)
MODE_VALID = 0x20
INDICATING = 0x10


@dataclass
class JointState:
    pops_ticks: int = 93750
    indicator_ticks: int = 187506  # example: 2s only if clock ~=93753 Hz
    last_tick: int = 0
    remaining: int = 0
    phase: Phase = Phase.IDLE
    mode_index: int = 0
    mode_valid: bool = False
    indicating: bool = False

    def __post_init__(self):
        if not 0 < self.pops_ticks < 1 << 24:
            raise ValueError("POPS duration must fit 24 bits")
        if not 0 < self.indicator_ticks < 1 << 24:
            raise ValueError("indicator duration must fit 24 bits")

    def pack(self):
        control = (int(self.phase) | self.mode_index << 2 |
                   (INDICATING if self.indicating else 0) |
                   (MODE_VALID if self.mode_valid else 0))
        assert not control & 0xC0
        return (self.last_tick.to_bytes(4, "little") +
                self.remaining.to_bytes(3, "little") + bytes([control]))

    @classmethod
    def unpack(cls, data, pops_ticks=93750, indicator_ticks=187506):
        if len(data) != 8:
            raise ValueError("state must be eight bytes")
        last = int.from_bytes(data[:4], "little")
        rem = int.from_bytes(data[4:7], "little")
        ctrl = data[7]
        state = cls(pops_ticks, indicator_ticks, last)
        if ctrl & 0xC0:
            return state
        state.phase = Phase(ctrl & 3)
        state.mode_index = (ctrl >> 2) & 3
        state.mode_valid = bool(ctrl & MODE_VALID)
        state.indicating = bool(ctrl & INDICATING)
        valid = (state.mode_valid or state.phase in (Phase.IDLE, Phase.SPENT)) and (
            (state.indicating and state.phase == Phase.IDLE and 0 < rem <= indicator_ticks) or
            (not state.indicating and state.phase == Phase.ACTIVE and 0 < rem <= pops_ticks) or
            (not state.indicating and state.phase != Phase.ACTIVE and rem == 0))
        if not valid:
            return cls(pops_ticks, indicator_ticks, last, 0, Phase.SPENT)
        state.remaining = rem
        return state

    def step(self, now, mode, pedal_positive, eligible, fuel_cut, speed_zero,
             *, clock_reinitialized=False):
        """Return (POPS permission, requested cluster RPM or None)."""
        if not isinstance(now, int) or not 0 <= now <= MASK32:
            raise ValueError("unsigned 32-bit clock required")
        if clock_reinitialized:
            self.last_tick, self.remaining, self.phase = now, 0, Phase.IDLE
            self.indicating = False
            self.mode_valid = False
            return False, None
        if mode not in MODES:
            self.last_tick, self.remaining, self.phase = now, 0, Phase.IDLE
            self.indicating = False
            self.mode_valid = False
            return False, None

        index = MODES.index(mode)
        changed = self.mode_valid and index != self.mode_index
        self.mode_index, self.mode_valid = index, True
        if changed:
            self.last_tick, self.remaining, self.phase = now, 0, Phase.IDLE
            self.indicating = False
            if speed_zero is True and not pedal_positive:
                self.remaining = self.indicator_ticks
                self.indicating = True

        # The same 24-bit field is used by only one feature at a time.
        # Driver input or movement immediately yields it to POPS/normal RPM.
        if self.indicating:
            if pedal_positive or speed_zero is not True or fuel_cut:
                self.last_tick, self.remaining, self.phase = now, 0, Phase.IDLE
                self.indicating = False
            else:
                elapsed = (now - self.last_tick) & MASK32
                self.last_tick = now
                if elapsed >= HALF32 or elapsed >= self.remaining:
                    self.remaining = 0
                    self.indicating = False
                else:
                    self.remaining -= elapsed
                    return False, RPM[index]

        budget = ReleaseBudget(self.pops_ticks, self.last_tick,
                               self.remaining, self.phase)
        permission = budget.step(now, mode, pedal_positive, eligible, fuel_cut)
        self.last_tick, self.remaining, self.phase = (
            budget.last_tick, budget.remaining, budget.phase)
        return permission, None
