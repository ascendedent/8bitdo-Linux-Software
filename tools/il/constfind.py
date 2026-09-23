import sys,struct,dnfile
import os
APP = os.environ.get("V2_APP_DLL", "vendor/v2_app.dll")
pe=dnfile.dnPE(APP); md=pe.net.mdtables
want={int(x,0) for x in sys.argv[1:]}
owner={}
for t in md.TypeDef.rows:
    for fl in t.FieldList: owner[fl.row_index]=t.TypeName.value
for c in md.Constant.rows:
    p=c.Parent
    if p.table and p.table.name=='Field':
        v=c.Value.value if hasattr(c.Value,'value') else c.Value
        if isinstance(v,(bytes,bytearray)) and len(v)==4:
            iv=struct.unpack('<I',v)[0]
            if iv in want: print(hex(iv), owner.get(p.row_index), md.Field.rows[p.row_index-1].Name.value)
