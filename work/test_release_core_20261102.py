"""Execute isolated machine bytes against the independent Python contract.

Restricted sequential C166 instruction interpreter; NOT a hardware, interrupt,
diagnostic, timing or ABI-wrapper emulator. No ECU connection, no FLS writes.
"""
from pathlib import Path
import hashlib,json,random,struct,unittest
from pops_event_ticks_reference_20261102 import ReleaseBudget,MASK32

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'work/release_core_20261102'
CODE=(OUT/'isolated_core_NOT_FIRMWARE.bin').read_bytes()
LINK=0x100000
STATE=0x387f00

class CoreCPU:
    def __init__(self,serialized):
        self.memory={STATE+i:b for i,b in enumerate(serialized)}
        self.r=list(range(16));self.z=False;self.c=False;self.writes=[]
    def run(self,now,mode,pedal,eligible,cut,reset=False):
        self.r[4]=now&65535;self.r[5]=now>>16;self.r[6]=mode
        self.r[7]=int(pedal)|(int(eligible)<<1)|(int(cut)<<2)|(int(reset)<<3)
        initial=self.r.copy();self.pc=LINK;self.ext=None;self.writes=[]
        for count in range(150):
            p=self.pc-LINK;op,q=CODE[p:p+2];self.pc+=2
            if op==0xdb:break # Isolated entry return, no caller/stack emulation.
            if op==0xfa:
                self.pc=q*65536+struct.unpack_from('<H',CODE,p+2)[0]
            elif op in (0x2d,0x3d,0x8d,0x9d,0xed,0xfd):
                take={0x2d:self.z,0x3d:not self.z,0x8d:self.c,
                      0x9d:not self.c,0xed:not(self.z or self.c),0xfd:self.z or self.c}[op]
                if take:self.pc+=2*(q if q<128 else q-256)
            elif op==0xf0:
                d,s=q>>4,q&15;self.r[d]=self.r[s];self.z=self.r[d]==0
            elif op in (0x20,0x30,0x40,0x70):
                d,s=q>>4,q&15;a,b=self.r[d],self.r[s]
                if op==0x70:value=a|b;self.c=False
                else:
                    sub=b+(int(self.c) if op==0x30 else 0)
                    value=(a-sub)&65535;self.c=a<sub
                self.z=value==0
                if op!=0x40:self.r[d]=value
            elif op in (0x5c,0x7c):
                d,n=q&15,q>>4;a=self.r[d]
                value=(a<<n)&65535 if op==0x5c else a>>n
                self.r[d]=value;self.z=value==0
                self.c=bool((a>>(16-n if op==0x5c else n-1))&1)
            elif op in (0xe6,0x46,0x66,0xd7,0xf2,0xf6):
                imm=struct.unpack_from('<H',CODE,p+2)[0];self.pc+=2
                d=q-0xf0
                if op==0xd7:
                    assert q==0 and self.ext is None;self.ext=imm
                elif op in (0xf2,0xf6):
                    assert self.ext==0x38
                    addr=(self.ext<<16)+imm;self.ext=None
                    assert STATE<=addr and addr+2<=STATE+8
                    if op==0xf2:
                        value=self.memory[addr]|self.memory[addr+1]<<8;self.r[d]=value
                    else:
                        value=self.r[d];self.memory[addr]=value&255;self.memory[addr+1]=value>>8
                        self.writes.append((addr,2))
                    self.z=value==0
                elif op==0xe6:self.r[d]=imm;self.z=imm==0
                elif op==0x46:
                    self.c=self.r[d]<imm;self.z=self.r[d]==imm
                else:self.r[d]&=imm;self.z=self.r[d]==0;self.c=False
            else:raise AssertionError(('Unsupported byte',hex(LINK+p),hex(op),hex(q)))
            assert LINK<=self.pc<LINK+len(CODE)
        else:raise AssertionError('Component did not return')
        assert self.ext is None
        assert all(self.r[i]==initial[i] for i in (0,1,2,3,14,15))
        assert self.writes==[(STATE+i,2) for i in (0,2,4,6)]
        return bool(self.r[4]),bytes(self.memory[STATE+i] for i in range(8)),count+1

class MachineContractTests(unittest.TestCase):
    comparisons=0
    max_instructions=0
    def check_sequence(self,events,initial=bytes(8)):
        cpu=CoreCPU(initial);model=ReleaseBudget.unpack(initial)
        for now,mode,pedal,eligible,cut,reset in events:
            expected=model.step(now,mode,pedal,eligible,cut,clock_reinitialized=reset)
            actual,state,n=cpu.run(now,mode,pedal,eligible,cut,reset)
            self.assertEqual((actual,state),(expected,model.pack()))
            type(self).comparisons+=1;type(self).max_instructions=max(type(self).max_instructions,n)

    def test_boot_and_mode_contract(self):
        for mode in range(256):
            self.check_sequence([(0,mode,False,True,False,False),(1,mode,True,True,False,False),
                                 (2,mode,False,True,False,False)])

    def test_lift_deadline_and_five_callers(self):
        events=[(0,165,True,True,False,False)]
        for tick in (1,2,65535,65536,93750,93751,93752):
            events.extend([(tick,165,False,True,False,False)]*5)
        self.check_sequence(events)

    def test_inhibition_does_not_pause_the_deadline(self):
        # Same core contract is intended for both speed contexts; map selection
        # and execution in motion/at standstill are outside this component.
        self.check_sequence([(99,165,True,True,False,False),(100,165,False,True,False,False),
            (300,165,False,False,False,False),(500,165,False,True,False,False),
            (93850,165,False,True,False,False)])

    def test_wrap_and_clock_discontinuity(self):
        for start in (0,65530,0xffff0000,MASK32-1):
            for delta in (0,1,65535,65536,93749,93750,93751,0x80000000,0xffffffff):
                self.check_sequence([((start-1)&MASK32,165,True,True,False,False),
                    (start,165,False,True,False,False),
                    ((start+delta)&MASK32,165,False,True,False,False)])

    def test_cancel_requires_rearm_and_other_mode_pedal_does_not_arm(self):
        self.check_sequence([(0,90,True,True,False,False),(1,165,False,True,False,False),
           (2,165,True,True,False,False),(3,165,False,True,False,False),
           (4,165,False,True,True,False),(5,165,False,True,False,False),
           (6,165,True,True,False,False),(7,165,False,True,False,False),
           (8,165,False,True,False,True),(9,165,False,True,False,False),
           (10,165,True,True,False,False),(11,165,False,True,False,False),
           (12,105,False,True,False,False),(13,165,False,True,False,False)])

    def test_serialized_states_and_flags(self):
        for phase in (0,1,2,3,4,255):
            for remaining in (0,1,65535,65536,93749,93750,93751,0xffffff):
                initial=(100).to_bytes(4,'little')+remaining.to_bytes(3,'little')+bytes([phase])
                for flags in range(16):
                    self.check_sequence([(101,165,bool(flags&1),bool(flags&2),bool(flags&4),bool(flags&8))],initial)

    def test_random_event_sequences(self):
        rng=random.Random(20261102)
        for sequence in range(100):
            now=rng.randrange(1<<32);events=[]
            for i in range(200):
                now=(now+rng.choice([0,1,2,100,2000,30000,65536,93750,0xffffffff]))&MASK32
                events.append((now,rng.choice([165]*12+[90,69,105]),rng.randrange(9)==0,
                               rng.randrange(4)!=0,rng.randrange(40)==0,rng.randrange(80)==0))
            self.check_sequence(events)

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(MachineContractTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    record={'status':'ISOLATED_SEQUENTIAL_MACHINE_BYTES_ONLY','tests':result.testsRun,
       'success':result.wasSuccessful(),'failures':len(result.failures),'errors':len(result.errors),
       'machine_reference_step_comparisons':MachineContractTests.comparisons,
       'max_observed_instructions_per_call':MachineContractTests.max_instructions,
       'machine_sha256':hashlib.sha256(CODE).hexdigest(),
       'hardware_emulated':False,'interrupts_emulated':False,'integration_verified':False,
       'firmware_modified':False,'flashable':False}
    (OUT/'machine_test_result.json').write_text(json.dumps(record,indent=2))
    print(json.dumps(record,indent=2))
    raise SystemExit(0 if result.wasSuccessful() else 1)
