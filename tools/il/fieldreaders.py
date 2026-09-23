import sys,dnfile
from ildump import Reader, build_owners, _mowner
from dncil.cil.body import CilMethodBody
import os
APP = os.environ.get("V2_APP_DLL", "vendor/v2_app.dll")
pe=dnfile.dnPE(APP); build_owners(pe); md=pe.net.mdtables
typ=sys.argv[1]; names=set(sys.argv[2:])
toks={}
for t in md.TypeDef.rows:
    if t.TypeName.value==typ:
        for fl in t.FieldList:
            if fl.row.Name.value in names: toks[0x04000000|fl.row_index]=fl.row.Name.value
print('tokens',{hex(k):v for k,v in toks.items()})
for i,r in enumerate(md.MethodDef.rows):
    if not r.Rva: continue
    try: b=CilMethodBody(Reader(pe,r.Rva))
    except Exception: continue
    hit=set()
    for ins in b.instructions:
        op=ins.operand
        if ins.mnemonic in ('ldsfld','ldfld','ldsflda') and hasattr(op,'value') and op.value in toks: hit.add(toks[op.value])
    if hit: print(f"  {_mowner.get(i+1)}::{r.Name.value} rva {hex(r.Rva)}  {sorted(hit)}")
