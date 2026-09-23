# IL readers for the V2 1.35 managed assembly

Static only. Nothing here opens a HID device.

```
python3 -m pip install --target .pydeps dnfile dncil
python3 tools/il/extract_app.py            # writes vendor/v2_app.dll (ignored by git)
PYTHONPATH=.pydeps python3 tools/il/ildump.py BasicAdvanceUIData getKey
PYTHONPATH=.pydeps python3 tools/il/enumdump.py S_ButtonKeyType KeyMap
PYTHONPATH=.pydeps python3 tools/il/callers.py BasicAdvanceUIData getKey
PYTHONPATH=.pydeps python3 tools/il/fieldreaders.py VIDPID PID_QINGCHUN2
PYTHONPATH=.pydeps python3 tools/il/fieldwriters.py BasicAdvanceUIData KEY_ DIR_
PYTHONPATH=.pydeps python3 tools/il/structsize.py custom_config_record_t_u2
PYTHONPATH=.pydeps python3 tools/il/constfind.py 0x8000004
```

Set `V2_APP_DLL` to point at the extracted assembly if it is not at `vendor/v2_app.dll`. Run from the repo root so `ildump` can be imported by the others.
