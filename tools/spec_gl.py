# GLS3D (OpenGL on Stage3D) per-draw overhead: upload the material/light/clip-plane constants
# (vc18..vc62) only after something that can change them, instead of on every draw call.
import sys, re
from asm import Q
dump = open(sys.argv[1]).read().split('\n')     # Patch PATCH_DUMP of GLAPI/executeCommandList
c0 = next(i for i, l in enumerate(dump) if l.strip() == 'code')
c1 = next(i for i, l in enumerate(dump) if l.strip().startswith('end ; code'))
code = dump[c0 + 1:c1]
CL = Q('MD_cclean')
def find(seq, start=0):
    for i in range(start, len(code) - len(seq) + 1):
        if all(code[i + k].strip() == seq[k] for k in range(len(seq))): return i
    raise SystemExit('pattern not found: %r' % (seq,))
a = find(['getlex QName(PackageNamespace(""),"context")', 'pushstring "vertex"', 'pushbyte 18'])
b = find(['getlocal 11', 'pushbyte 8'], a)
assert code[b + 2].strip().startswith('iflt ')
b += 3
code[b:b] = ['pushtrue', f'findproperty {CL}', 'swap', f'setproperty {CL}', 'md_cdone:']
code[a:a] = [f'getlex {CL}', 'iftrue md_cdone']
# matrices: skip the clone/invert/upload of the 4 matrices while the matrix stacks are unchanged
ML = Q('MD_mclean')
ISG = Q('isGLState', 'PrivateNamespace("GLS3D:GLAPI")')
m0 = find(['getlex QName(PrivateNamespace("GLS3D:GLAPI"),"modelViewStack")'])
pend = find(['pushbyte 0', 'setlocal 11', 'jump ofs015e'], m0)   # first statement after the polygon-offset block
assert code[pend - 1].strip().endswith(':')
code[m0:m0] = [f'getlex {ML}', 'iffalse md_mdo', f'findpropstrict {ISG}', 'pushbyte 18', f'callproperty {ISG}, 1',
               'iftrue md_mdo', 'pushtrue', 'setlocal {R0}', 'jump md_mskip0', 'md_mdo:', 'pushfalse', 'setlocal {R0}']
pend = find(['pushbyte 0', 'setlocal 11', 'jump ofs015e'], m0)
code[pend:pend] = ['md_mskip0:']
u0 = find(['getlocal3', 'getproperty QName(PackageNamespace(""),"polygonOffset")'])
u1 = find(['pushbyte 12', 'getlocal 12', 'pushtrue', 'callpropvoid QName(PackageNamespace(""),"setProgramConstantsFromMatrix"), 4'], u0) + 4
code[u1:u1] = ['pushtrue', f'findproperty {ML}', 'swap', f'setproperty {ML}', 'md_mskip1:']
code[u0:u0] = ['getlocal {R0}', 'iftrue md_mskip1']
out = ['=== addvar MD_cclean\n', '=== addvar MD_mclean\n']
out.append('=== body GLAPI/executeCommandList\n#regs 1\n#stack 2\n' + '\n'.join(code) + '\n')
# display lists can carry material state: re-upload after replaying one
out.append(f'''=== func GLAPI/executeCommandList entry
#regs 0
getlocal1
getproperty {Q("commands", 'PackageNamespace("")')}
getproperty {Q("length", 'PackageNamespace("")')}
pushbyte 1
ifeq md_one
pushfalse
findproperty {CL}
swap
setproperty {CL}
pushfalse
findproperty {ML}
swap
setproperty {ML}
md_one:
''')
# glEnable/glDisable: only GL_LIGHTING (0x0B50), GL_CLIP_PLANE0..5 (0x3000..) and GL_LIGHT0..7 (0x4000..)
for f in ('GLAPI/glEnable', 'GLAPI/glDisable'):
    out.append(f'''=== func {f} entry
#regs 0
getlocal1
pushint 2896
ifeq md_dirty
getlocal1
pushint 12288
subtract
convert_u
pushbyte 6
iflt md_dirty
getlocal1
pushint 16384
subtract
convert_u
pushbyte 8
iflt md_dirty
jump md_keep
md_dirty:
pushfalse
findproperty {CL}
swap
setproperty {CL}
md_keep:
''')
for f in ('GLAPI/glClipPlane', 'GLAPI/glMaterial', 'GLAPI/glLight',
          'GLAPI/glLightModeli', 'GLAPI/glPopAttrib', 'GLAPI/glPushAttrib', 'GLAPI$/init'):
    out.append(f'=== func {f} entry\n#regs 0\npushfalse\nfindproperty {CL}\nswap\nsetproperty {CL}\n')
for f in ('GLAPI/glPopMatrix', 'GLAPI/glLoadIdentity', 'GLAPI/glOrtho', 'GLAPI/glTranslate', 'GLAPI/glRotate',
          'GLAPI/glScale', 'GLAPI/glMultMatrix', 'GLAPI/multMatrix', 'GLAPI/glLoadMatrix', 'GLAPI$/init'):
    out.append(f'=== func {f} entry\n#regs 0\npushfalse\nfindproperty {ML}\nswap\nsetproperty {ML}\n')
open(sys.argv[2], 'w').write(''.join(out))
