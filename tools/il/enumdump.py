import sys, struct, dnfile
import os
APP = os.environ.get("V2_APP_DLL", "vendor/v2_app.dll")
pe=dnfile.dnPE(APP); md=pe.net.mdtables
want=set(sys.argv[1:])
# map field rid -> constant
consts={}
for c in md.Constant.rows:
    p=c.Parent
    if p.table and p.table.name=='Field':
        consts[p.row_index]=(c.Type, c.Value.value if hasattr(c.Value,'value') else c.Value)
for t in md.TypeDef.rows:
    if t.TypeName.value in want:
        print(f"\n== {t.TypeNamespace.value}.{t.TypeName.value}")
        for fl in t.FieldList:
            rid=fl.row_index; n=fl.row.Name.value
            if rid in consts:
                ty,v=consts[rid]
                if isinstance(v,(bytes,bytearray)):
                    if len(v)==4: v=struct.unpack('<i',v)[0]
                    elif len(v)==1: v=v[0]
                    elif len(v)==2: v=struct.unpack('<h',v)[0]
                    elif len(v)==8: v=struct.unpack('<q',v)[0]
                print(f"  {n} = {v} (0x{v & 0xffffffff:x})" if isinstance(v,int) else f"  {n} = {v!r}")
            else:
                print(f"  {n} (no const)")
