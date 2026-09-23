import sys,dnfile
from ildump import Reader, build_owners, _mowner
from dncil.cil.body import CilMethodBody
import os
APP = os.environ.get("V2_APP_DLL", "vendor/v2_app.dll")
pe=dnfile.dnPE(APP); build_owners(pe); md=pe.net.mdtables
target=set()
for t in md.TypeDef.rows:
    if t.TypeName.value==sys.argv[1]:
        for m in t.MethodList:
            if m.row.Name.value==sys.argv[2]: target.add(0x06000000|m.row_index)
print('tokens',[hex(x) for x in target])
for i,r in enumerate(md.MethodDef.rows):
    if not r.Rva: continue
    try: b=CilMethodBody(Reader(pe,r.Rva))
    except Exception: continue
    for ins in b.instructions:
        op=ins.operand
        if hasattr(op,'value') and op.value in target:
            print(f"  {_mowner.get(i+1)}::{r.Name.value} rva {hex(r.Rva)}"); break
