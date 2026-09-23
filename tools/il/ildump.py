import os
APP = os.environ.get("V2_APP_DLL", "vendor/v2_app.dll")
"""Dump IL for methods of a type. usage: ildump.py TypeName [method ...]"""
import sys
import dnfile
from dncil.cil.body import CilMethodBody
from dncil.cil.body.reader import CilMethodBodyReaderBase
from dncil.cil.error import MethodBodyFormatError
from dncil.clr.token import Token, StringToken, InvalidToken

class Reader(CilMethodBodyReaderBase):
    def __init__(self, pe, rva):
        self.pe=pe; self.off=pe.get_offset_from_rva(rva)
    def read(self, n):
        d=self.pe.get_data(self.pe.get_rva_from_offset(self.off), n); self.off+=n; return d
    def tell(self): return self.off
    def seek(self, o): self.off=o; return o

def name_of(pe, tok):
    if isinstance(tok, StringToken):
        return repr(pe.net.user_strings.get(tok.rid).value)
    tbl = pe.net.mdtables.tables_by_index.get(tok.table) if hasattr(pe.net.mdtables,'tables_by_index') else None
    try:
        row = pe.net.mdtables.tables_by_index[tok.table].rows[tok.rid-1] if False else None
    except Exception:
        row=None
    md=pe.net.mdtables
    t=tok.table
    try:
        if t==0x06: r=md.MethodDef.rows[tok.rid-1]; return f"{owner_of_method(pe,tok.rid)}::{r.Name.value}"
        if t==0x04: r=md.Field.rows[tok.rid-1]; return f"{owner_of_field(pe,tok.rid)}::{r.Name.value}"
        if t==0x0a: r=md.MemberRef.rows[tok.rid-1]; cls=r.Class.row; cn=getattr(cls,'TypeName',None); cn=cn.value if cn else type(cls).__name__; return f"{cn}::{r.Name.value}"
        if t==0x02: r=md.TypeDef.rows[tok.rid-1]; return r.TypeName.value
        if t==0x01: r=md.TypeRef.rows[tok.rid-1]; return r.TypeName.value
        if t==0x1b: return f"TypeSpec#{tok.rid}"
        if t==0x2b: return f"MethodSpec#{tok.rid}"
    except Exception as e:
        return f"?{e}"
    return f"tok{tok.table:02x}{tok.rid:06x}"

_fowner={}; _mowner={}
def build_owners(pe):
    md=pe.net.mdtables
    for i,t in enumerate(md.TypeDef.rows):
        for m in t.MethodList: 
            try: _mowner[m.row_index]=t.TypeName.value
            except Exception: pass
        for fl in t.FieldList:
            try: _fowner[fl.row_index]=t.TypeName.value
            except Exception: pass
def owner_of_method(pe,rid): return _mowner.get(rid,'?')
def owner_of_field(pe,rid): return _fowner.get(rid,'?')

def dump(pe, typename, methods):
    md=pe.net.mdtables
    for t in md.TypeDef.rows:
        if t.TypeName.value!=typename: continue
        for m in t.MethodList:
            n=m.row.Name.value
            if methods and n not in methods: continue
            if not m.row.Rva: continue
            print(f"\n=== {typename}::{n} rva {hex(m.row.Rva)}")
            try:
                body=CilMethodBody(Reader(pe,m.row.Rva))
            except MethodBodyFormatError as e:
                print('bad body',e); continue
            print(f"  maxstack {body.max_stack} size {body.code_size} locals {body.local_var_sig_tok}")
            for ins in body.instructions:
                op=ins.operand
                s=''
                if isinstance(op,(Token,)):
                    s=name_of(pe,op)+f"  [{op.value:08x}]"
                elif op is not None:
                    s=str(op) if not isinstance(op,int) else (f"{op} (0x{op:x})" if op>9 or op<-9 else str(op))
                print(f"  {ins.offset:04x}: {ins.mnemonic:<12} {s}")

if __name__=='__main__':
    pe=dnfile.dnPE(APP); build_owners(pe)
    dump(pe, sys.argv[1], set(sys.argv[2:]))
