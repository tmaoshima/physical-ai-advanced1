"""ROS 2を使わずに色領域の抽出処理を検証する。"""
from pathlib import Path
import ast
from types import SimpleNamespace

CODE = (Path(__file__).resolve().parents[1]/'camera_ai.py').read_text()
TREE = ast.parse(CODE)
F = next(n for n in TREE.body if isinstance(n,ast.FunctionDef) and n.name=='measure_color')
ns={}
exec(compile(ast.Module(body=[F],type_ignores=[]),'<test>','exec'),ns)
measure=ns['measure_color']

def test_color(color,encoding):
    w,h=320,240
    bg=(145,145,145)
    channel=3
    raw=bytearray()
    for y in range(h):
        for x in range(w):
            rgb=color if 100<x<220 and 65<y<175 else bg
            raw.extend(rgb[::-1] if encoding=='bgr8' else rgb)
    msg=SimpleNamespace(encoding=encoding,width=w,height=h,step=3*w,data=bytes(raw))
    return measure(msg)

assert test_color((230,12,15),'rgb8')[0]=='red'
assert test_color((12,15,230),'rgb8')[0]=='blue'
assert test_color((230,12,15),'bgr8')[0]=='red'
assert test_color((12,15,230),'bgr8')[0]=='blue'
print('Pure image processing tests: passed')
