"""Build an isolated C166 component, NOT an ECU firmware image.

ABI: R4/R5 coherent tick low/high, R6 mode, R7 flags:
bit0 pedal positive, bit1 eligible, bit2 fuel cut, bit3 clock reinitialized.
Returns R4=0/1. Clobbers R4..R13 and flags. No interrupt exclusion.
R0..R3/R14/R15, DPP and CP are not changed. No nested calls.
State has the reference model's eight-byte layout. 387F00 is a provisional
development address: this builder does NOT establish RAM ownership.
The synthetic link address 100000 is NOT an approved flash destination.
"""
from pathlib import Path
import hashlib,json,struct

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'work/release_core_20261102'
LINK=0x100000
STATE=0x7f00
BUDGET=93750 # Abstract example counts, not a calibrated duration.

class Assembler:
    def __init__(self):self.b=bytearray();self.labels={};self.fix=[];self.source=[]
    def emit(self,h,note):
        data=bytes.fromhex(h);self.source.append((len(self.b),data.hex(' '),note));self.b+=data
    def word(self,op,q,n,note):self.emit(bytes([op,q]).hex()+struct.pack('<H',n).hex(),note)
    def label(self,name):assert name not in self.labels;self.labels[name]=len(self.b)
    def mov(self,d,s):self.emit(f'f0{d*16+s:02x}',f'mov r{d},r{s}')
    def imm(self,d,n):self.word(0xe6,0xf0+d,n,f'mov r{d},#{n:04x}')
    def alu(self,op,d,s,name):self.emit(f'{op:02x}{d*16+s:02x}',f'{name} r{d},r{s}')
    def cmp(self,d,n):self.word(0x46,0xf0+d,n,f'cmp r{d},#{n:04x}')
    def mask(self,d,n):self.word(0x66,0xf0+d,n,f'and r{d},#{n:04x}')
    def shift(self,d,n,left=False):self.emit(f'{0x5c if left else 0x7c:02x}{n*16+d:02x}',f'{"shl" if left else "shr"} r{d},#{n}')
    def mem(self,d,relative,write=False):
        self.word(0xd7,0,0x38,'exts #38,#1')
        self.word(0xf6 if write else 0xf2,0xf0+d,STATE+relative,
                  f'{"store" if write else "load"} word state+{relative},r{d}')
    def jump(self,target,cc=None):
        if cc is not None:
            inverse={0x2d:0x3d,0x3d:0x2d,0x8d:0x9d,0x9d:0x8d,0xed:0xfd,0xfd:0xed}[cc]
            self.emit(f'{inverse:02x}02','inverted condition: skip JMPS')
        self.fix.append((len(self.b),target));self.emit('fa100000','jmps '+target)
    def bit(self,bit,target):
        self.mov(4,7);self.mask(4,bit);self.jump(target,0x3d)
    def finish(self):
        for p,target in self.fix:
            address=LINK+self.labels[target];assert address>>16==LINK>>16
            self.b[p+2:p+4]=struct.pack('<H',address&65535)
        return bytes(self.b)

def build():
    a=Assembler();a.mov(12,4);a.mov(13,5)
    a.bit(8,'idle');a.cmp(6,165);a.jump('idle',0x3d);a.bit(1,'armed')
    a.mem(8,4);a.mem(6,6);a.mov(9,6);a.mask(9,255);a.shift(6,8)
    a.cmp(6,3);a.jump('spent',0xed);a.cmp(6,2);a.jump('active',0x2d)
    # Nonactive serialized states must have zero remaining, like unpack().
    a.mov(4,8);a.alu(0x70,4,9,'or');a.jump('spent',0x3d)
    a.cmp(6,1);a.jump('save_closed',0x3d)
    a.imm(8,BUDGET&65535);a.imm(9,BUDGET>>16);a.imm(6,2);a.jump('permit')
    a.label('active')
    a.cmp(9,BUDGET>>16);a.jump('spent',0xed);a.jump('valid_remaining',0x8d)
    a.cmp(8,BUDGET&65535);a.jump('spent',0xed)
    a.label('valid_remaining');a.mov(4,8);a.alu(0x70,4,9,'or');a.jump('spent',0x2d)
    a.mem(10,0);a.mem(11,2);a.mov(4,12);a.mov(5,13)
    a.alu(0x20,4,10,'sub');a.alu(0x30,5,11,'subc')
    a.alu(0x40,5,9,'cmp');a.jump('spent',0xed);a.jump('subtract',0x8d)
    a.alu(0x40,4,8,'cmp');a.jump('spent',0x9d)
    a.label('subtract');a.alu(0x20,8,4,'sub');a.alu(0x30,9,5,'subc')
    a.label('permit');a.bit(4,'spent');a.imm(11,0)
    a.mov(4,7);a.mask(4,2);a.jump('save',0x2d);a.imm(11,1);a.jump('save')
    a.label('idle');a.imm(6,0);a.jump('close')
    a.label('armed');a.imm(6,1);a.jump('close')
    a.label('spent');a.imm(6,3)
    a.label('close');a.imm(8,0);a.imm(9,0)
    a.label('save_closed');a.imm(11,0)
    a.label('save');a.shift(6,8,True);a.alu(0x70,9,6,'or')
    for r,o in ((12,0),(13,2),(8,4),(9,6)):a.mem(r,o,True)
    a.mov(4,11);a.emit('db00','rets')
    code=a.finish();OUT.mkdir(exist_ok=True)
    (OUT/'isolated_core_NOT_FIRMWARE.bin').write_bytes(code)
    lines=[f'{LINK+offset:06X} {code[offset:offset+len(bytes.fromhex(h))].hex(" "):20s} {note}'
           for offset,h,note in a.source]
    (OUT/'assembly_source.txt').write_text('\n'.join(lines)+'\n')
    manifest={'status':'ISOLATED_COMPONENT_NOT_FIRMWARE','bytes':len(code),
       'sha256':hashlib.sha256(code).hexdigest(),'synthetic_link':hex(LINK),
       'development_state_start':'0x387F00','RAM_reserved':False,'RAM_ownership_proven':False,
       'budget_abstract_ticks':BUDGET,'calibrated_seconds':False,
       'input_ABI':'R4=tick low; R5=tick high; R6=mode; R7=pedal|eligible<<1|fuel_cut<<2|clock_reset<<3',
       'output_ABI':'R4=permission 0/1; R4..R13 and PSW flags clobbered',
       'labels':{k:hex(LINK+v) for k,v in a.labels.items()},
       'clock_reader_integrated':False,'concurrency_proven':False,
       'firmware_modified':False,'flashable':False}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps(manifest,indent=2))

if __name__=='__main__':build()
