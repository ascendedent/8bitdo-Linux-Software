import os
APP = os.environ.get("V2_APP_DLL", "vendor/v2_app.dll")
"""Compute sequential-layout size and offsets of managed structs from field signatures."""
import sys, dnfile
pe=dnfile.dnPE(APP); md=pe.net.mdtables
PRIM={0x02:('bool',1),0x03:('char',2),0x04:('i1',1),0x05:('u1',1),0x06:('i2',2),0x07:('u2',2),0x08:('i4',4),0x09:('u4',4),0x0a:('i8',8),0x0b:('u8',8),0x0c:('r4',4),0x0d:('r8',8)}
types_by_rid={i+1:t for i,t in enumerate(md.TypeDef.rows)}
# FieldMarshal: parent field rid -> SizeConst
marsh={}
for fm in md.FieldMarshal.rows:
    p=fm.Parent
    if p.table and p.table.name=='Field':
        b=fm.NativeType.value if hasattr(fm.NativeType,'value') else fm.NativeType
        b=bytes(b)
        if b and b[0]==0x1e:  # ByValArray
            # compressed int size
            i=1; v=b[i]
            if v&0x80==0: n=v; i+=1
            elif v&0xC0==0x80: n=((v&0x3f)<<8)|b[i+1]; i+=2
            else: n=((v&0x1f)<<24)|(b[i+1]<<16)|(b[i+2]<<8)|b[i+3]; i+=4
            marsh[p.row_index]=n
def decode_tok(b,i):
    v=b[i]
    if v&0x80==0: val=v; i+=1
    elif v&0xC0==0x80: val=((v&0x3f)<<8)|b[i+1]; i+=2
    else: val=((v&0x1f)<<24)|(b[i+1]<<16)|(b[i+2]<<8)|b[i+3]; i+=4
    tag=val&3; rid=val>>2
    return (0x02,0x01,0x1b)[tag], rid, i
cache={}
def type_of_sig(b,i,frid):
    t=b[i]
    if t in PRIM: return PRIM[t][0],PRIM[t][1],PRIM[t][1]
    if t==0x1d:  # szarray
        en,es,ea=type_of_sig(b,i+1,frid); n=marsh.get(frid,0)
        return f'{en}[{n}]',es*n,ea
    if t==0x11 or t==0x12:
        tbl,rid,_=decode_tok(b,i+1)
        if tbl==0x02:
            name=types_by_rid[rid].TypeName.value
            sz,al,_=layout(types_by_rid[rid])
            return name,sz,al
        return f'ref{tbl:x}:{rid}',4,4
    if t==0x0e: return 'string',4,4
    return f'?{t:02x}',0,1
def layout(t):
    key=t.TypeName.value+'/'+str(id(t))
    if key in cache: return cache[key]
    off=0; maxal=1; fields=[]
    for fl in t.FieldList:
        sig=bytes(fl.row.Signature.value if hasattr(fl.row.Signature,'value') else fl.row.Signature)
        # sig: 0x06 then type
        if getattr(fl.row.Flags,"fdStatic",False): continue  # static
        name,sz,al=type_of_sig(sig,1,fl.row_index)
        if off%al: off+= al-off%al
        fields.append((off,fl.row.Name.value,name,sz)); off+=sz; maxal=max(maxal,al)
    if off%maxal: off+=maxal-off%maxal
    cache[key]=(off,maxal,fields); return cache[key]
want=sys.argv[1:]
seen=set()
for t in md.TypeDef.rows:
    n=t.TypeName.value
    if n in want:
        sz,al,fields=layout(t)
        print(f"\n== {t.TypeNamespace.value}.{n} size {sz:#x} ({sz}) align {al}")
        for off,fn,tn,fs in fields: print(f"   {off:#06x} {fn:22s} {tn:32s} {fs:#x}")
