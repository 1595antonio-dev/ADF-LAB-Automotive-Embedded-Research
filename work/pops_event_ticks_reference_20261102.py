"""Eight-byte reference state for an independent per-release POPS budget.

No C166, no FLS patch, no RAM reservation, no injector command.
Clock counts are abstract. DEFAULT_BUDGET is an example, not a calibrated
second. An ECU clock reinitialization needs explicit notification; small
forward changes cannot distinguish a reinitialization from ordinary time.
"""
from dataclasses import dataclass
from enum import IntEnum

MASK32=(1<<32)-1
HALF32=1<<31
MAX24=(1<<24)-1
DEFAULT_BUDGET=93750

class Phase(IntEnum):
    IDLE=0
    ARMED=1
    ACTIVE=2
    SPENT=3

@dataclass
class ReleaseBudget:
    budget:int=DEFAULT_BUDGET
    last_tick:int=0
    remaining:int=0
    phase:Phase=Phase.IDLE

    def __post_init__(self):
        if not 0 < self.budget <= MAX24:
            raise ValueError('Budget must fit the 24-bit field')

    def close(self,now,phase=Phase.SPENT):
        self.last_tick=now
        self.remaining=0
        self.phase=phase
        return False

    def step(self,now,mode,pedal_positive,eligible,fuel_cut,
             *,clock_reinitialized=False,legacy_counter=0):
        if not isinstance(now,int) or not 0<=now<=MASK32:
            raise ValueError('Clock must be an unsigned 32-bit count')
        if clock_reinitialized:
            return self.close(now,Phase.IDLE)
        if mode!=165:
            return self.close(now,Phase.IDLE)
        if pedal_positive:
            return self.close(now,Phase.ARMED)
        if self.phase==Phase.ARMED:
            self.last_tick=now
            self.remaining=self.budget
            self.phase=Phase.ACTIVE
        elif self.phase==Phase.ACTIVE:
            elapsed=(now-self.last_tick)&MASK32
            self.last_tick=now
            if elapsed>=HALF32 or elapsed>=self.remaining:
                return self.close(now)
            self.remaining-=elapsed
        else:
            return self.close(now,self.phase)
        if fuel_cut:
            return self.close(now)
        # Inhibitions suppress output, but never pause or restart the budget.
        # legacy_counter intentionally has no effect on this time budget.
        return bool(eligible)

    def pack(self):
        # 0..3: last tick (two aligned words), 4..6: remaining 24-bit,
        # 7: phase. Requires an even base; no physical address reserved here.
        return (self.last_tick.to_bytes(4,'little')+
                self.remaining.to_bytes(3,'little')+bytes([int(self.phase)]))

    @classmethod
    def unpack(cls,data,budget=DEFAULT_BUDGET):
        if len(data)!=8:
            raise ValueError('Exactly eight bytes required')
        last=int.from_bytes(data[:4],'little')
        rem=int.from_bytes(data[4:7],'little')
        flag=data[7]
        if flag not in tuple(int(p) for p in Phase) or rem>budget:
            return cls(budget,last,0,Phase.SPENT)
        phase=Phase(flag)
        if phase!=Phase.ACTIVE and rem!=0:
            return cls(budget,last,0,Phase.SPENT)
        if phase==Phase.ACTIVE and rem==0:
            phase=Phase.SPENT
        return cls(budget,last,rem,phase)
