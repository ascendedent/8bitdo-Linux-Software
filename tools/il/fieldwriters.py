import os
APP = os.environ.get("V2_APP_DLL", "vendor/v2_app.dll")
"""List every stfld/stsfld to fields of a type whose name matches a prefix, with the constant pushed before it."""
import sys,dnfile
from ildump import Reader, build_owners, _mowner
from dncil.cil.body import CilMethodBody
pe=dnfile.dnPE(APP); build_owners(pe); md=pe.net.mdtables
owner_type=sys.argv[1]; prefixes=tuple(sys.argv[2:])
targets={}
for t in md.TypeDef.rows:
    if t.TypeName.value==owner_type:
        for fl in t.FieldList:
            n=fl.row.Name.value
            if n.startswith(prefixes): targets[0x04000000|fl.row_index]=n
for i,r in enumerate(md.MethodDef.rows):
    if not r.Rva: continue
    try: b=CilMethodBody(Reader(pe,r.Rva))
    except Exception: continue
    ins=b.instructions
    for k,x in enumerate(ins):
        op=x.operand
        if x.mnemonic in ('stfld','stsfld') and hasattr(op,'value') and op.value in targets:
            prev=ins[k-1]
            pv=prev.operand if prev.operand is not None else prev.mnemonic
            print(f"{_mowner.get(i+1)}::{r.Name.value}  {targets[op.value]} <- {pv if not isinstance(pv,int) else hex(pv)}")
