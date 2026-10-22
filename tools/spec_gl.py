# GLS3D (OpenGL on Stage3D) per-draw overhead.
#  1. Upload the material/light/clip-plane constants (vc16, vc18..vc62) and the 4 matrices only after
#     something that can change them, not on every draw call; skip setProgram when it is already set.
#  2. glDrawElements fast path: the game draws triangle lists from three tightly packed client arrays
#     (float3 position, ubyte4 colour, float2 texcoord) with indices 0..n-1. Upload those arrays as-is
#     into three vertex buffers instead of copying every vertex through libGL's builder in AVM2.
# usage: spec_gl.py <dump dir with GLAPI_executeCommandList.pcode and GLAPI_glEndVertexData.pcode> out.txt
import sys
from asm import A, Q, PUB
D = sys.argv[1]
GP = 'PrivateNamespace("GLS3D:GLAPI")'
F3 = 'PackageNamespace("flash.display3D")'
CL, ML, FON = Q('MD_cclean'), Q('MD_mclean'), Q('MD_fon')
def P(n): return Q(n, PUB)

def load(name):
    dump = open(f'{D}/{name}.pcode').read().split('\n')
    c0 = next(i for i, l in enumerate(dump) if l.strip() == 'code')
    c1 = next(i for i, l in enumerate(dump) if l.strip().startswith('end ; code'))
    return dump[c0 + 1:c1]
def finder(code):
    def find(seq, start=0):
        for i in range(start, len(code) - len(seq) + 1):
            if all(code[i + k].strip() == seq[k] for k in range(len(seq))): return i
        raise SystemExit('pattern not found: %r' % (seq,))
    return find

# ---------- executeCommandList ----------
code = load('GLAPI_executeCommandList'); find = finder(code)
ctxl = 'getlex QName(PackageNamespace(""),"context")'
# vertex buffers: the fast path binds its three buffers
v0 = find([ctxl, 'pushbyte 0', 'getlocal3', 'getproperty QName(PackageNamespace(""),"vertexBuffer")', 'pushbyte 0', 'pushstring "float3"'])
v1 = next(i for i in range(v0, len(code)) if code[i].strip().endswith(':') and code[i + 1].strip() == ctxl
          and code[i + 2].strip() == 'getlocal3' and 'indexBuffer' in code[i + 3])
endlab = code[v1].strip()[:-1]
usage = ['pushbyte 0', 'getlocal3', f'getproperty {P("program")}', f'getproperty {P("vertexStreamUsageFlags")}']
fast = [f'getlex {FON}', 'iffalse md_vnorm',
        ctxl, 'pushbyte 0', f'getlex {Q("MD_fpos")}', 'pushbyte 0', 'pushstring "float3"', f'callpropvoid {P("setVertexBufferAt")}, 4',
        *usage, 'pushbyte 1', 'bitand', 'ifeq md_vc0',
        ctxl, 'pushbyte 1', f'getlex {Q("MD_fcol")}', 'pushbyte 0', 'pushstring "bytes4"', f'callpropvoid {P("setVertexBufferAt")}, 4', 'jump md_vc1',
        'md_vc0:', ctxl, 'pushbyte 1', 'pushnull', f'callpropvoid {P("setVertexBufferAt")}, 2',
        'md_vc1:', ctxl, 'pushbyte 2', 'pushnull', f'callpropvoid {P("setVertexBufferAt")}, 2',
        *usage, 'pushbyte 2', 'bitand', 'ifeq md_vt0',
        ctxl, 'pushbyte 3', f'getlex {Q("MD_ftex")}', 'pushbyte 0', 'pushstring "float2"', f'callpropvoid {P("setVertexBufferAt")}, 4', f'jump {endlab}',
        'md_vt0:', ctxl, 'pushbyte 3', 'pushnull', f'callpropvoid {P("setVertexBufferAt")}, 2', f'jump {endlab}',
        'md_vnorm:']
code[v0:v0] = fast
# material/light/clip-plane constants
a = find([ctxl, 'pushstring "vertex"', 'pushbyte 18'])
b = find(['getlocal 11', 'pushbyte 8'], a)
assert code[b + 2].strip().startswith('iflt ')
b += 3
code[b:b] = ['pushtrue', f'findproperty {CL}', 'swap', f'setproperty {CL}', 'md_cdone:']
code[a:a] = [f'getlex {CL}', 'iftrue md_cdone']
c16 = find([ctxl, 'pushstring "vertex"', 'pushbyte 16'])
code[c16 + 5:c16 + 5] = ['md_c16:']
code[c16:c16] = [f'getlex {CL}', 'iftrue md_c16']
# setProgram only when it changes
sp = find([ctxl, 'getlocal3', f'getproperty {P("program")}', f'getproperty {P("program")}', f'callpropvoid {P("setProgram")}, 1'])
code[sp:sp + 5] = ['getlocal3', f'getproperty {P("program")}', f'getproperty {P("program")}', 'dup',
                   f'getlex {Q("MD_lprog")}', 'ifstrictne md_sp1', 'pop', 'jump md_sp2',
                   'md_sp1:', 'dup', f'findproperty {Q("MD_lprog")}', 'swap', f'setproperty {Q("MD_lprog")}',
                   ctxl, 'swap', f'callpropvoid {P("setProgram")}, 1', 'md_sp2:']
# matrices
ISG = Q('isGLState', GP)
m0 = find(['getlex QName(PrivateNamespace("GLS3D:GLAPI"),"modelViewStack")'])
code[m0:m0] = [f'getlex {ML}', 'iffalse md_mdo', f'findpropstrict {ISG}', 'pushbyte 18', f'callproperty {ISG}, 1',
               'iftrue md_mdo', 'pushtrue', 'setlocal {R0}', 'jump md_mskip0', 'md_mdo:', 'pushfalse', 'setlocal {R0}']
pend = find(['pushbyte 0', 'setlocal 11', 'jump ofs015e'], m0)
code[pend:pend] = ['md_mskip0:']
u0 = find(['getlocal3', 'getproperty QName(PackageNamespace(""),"polygonOffset")'])
u1 = find(['pushbyte 12', 'getlocal 12', 'pushtrue', 'callpropvoid QName(PackageNamespace(""),"setProgramConstantsFromMatrix"), 4'], u0) + 4
code[u1:u1] = ['pushtrue', f'findproperty {ML}', 'swap', f'setproperty {ML}', 'md_mskip1:']
code[u0:u0] = ['getlocal {R0}', 'iftrue md_mskip1']
out = [f'=== addvar {v}\n' for v in ('MD_cclean', 'MD_mclean', 'MD_lprog', 'MD_fon', 'MD_fpos', 'MD_fcol', 'MD_ftex', 'MD_rpos', 'MD_rcol', 'MD_rtex', 'MD_ri')]
out.append('=== body GLAPI/executeCommandList\n#regs 1\n#stack 4\n' + '\n'.join(code) + '\n')
out.append(f'''=== func GLAPI/executeCommandList entry
#regs 0
getlocal1
getproperty {P("commands")}
getproperty {P("length")}
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
# ---------- glEndVertexData: the fast path supplies its own position buffer ----------
code = load('GLAPI_glEndVertexData'); find = finder(code)
k = find(['ofs005b:']) + 1
code[k:k] = [f'getlex {FON}', 'iffalse md_e1', f'getlex {Q("MD_fpos")}', f'coerce {Q("VertexBuffer3D", F3)}', 'setlocal 8', 'jump ofs0070', 'md_e1:']
out.append('=== body GLAPI/glEndVertexData\n#regs 0\n#stack 2\n' + '\n'.join(code) + '\n')

ML_ = 'MultinameL([PackageNamespace("")])'
# ---------- dirty flags ----------
def setflag(var, val): return f'push{val}\nfindproperty {var}\nswap\nsetproperty {var}\n'
for f in ('GLAPI/glEnable', 'GLAPI/glDisable'):   # only GL_LIGHTING, GL_CLIP_PLANEi, GL_LIGHTi
    out.append(f'=== func {f} entry\n#regs 0\ngetlocal1\npushint 2896\nifeq md_dirty\ngetlocal1\npushint 12288\nsubtract\nconvert_u\npushbyte 6\niflt md_dirty\n'
               f'getlocal1\npushint 16384\nsubtract\nconvert_u\npushbyte 8\niflt md_dirty\njump md_keep\nmd_dirty:\n{setflag(CL, "false")}md_keep:\n')
for f in ('GLAPI/glClipPlane', 'GLAPI/glMaterial', 'GLAPI/glLight', 'GLAPI/glLightModeli', 'GLAPI/glPopAttrib', 'GLAPI/glPushAttrib'):
    out.append(f'=== func {f} entry\n#regs 0\n{setflag(CL, "false")}')
for f in ('GLAPI/glPopMatrix', 'GLAPI/glLoadIdentity', 'GLAPI/glOrtho', 'GLAPI/glTranslate', 'GLAPI/glRotate',
          'GLAPI/glScale', 'GLAPI/glMultMatrix', 'GLAPI/multMatrix', 'GLAPI/glLoadMatrix'):
    out.append(f'=== func {f} entry\n#regs 0\n{setflag(ML, "false")}')
# new context: everything must be uploaded again, and the fast path's buffers belong to the old one
out.append(f'=== func GLAPI$/init entry\n#regs 0\n{setflag(CL, "false")}{setflag(ML, "false")}'
           f'pushnull\nfindproperty {Q("MD_lprog")}\nswap\nsetproperty {Q("MD_lprog")}\n'
           f'pushnull\nfindproperty {Q("MD_rpos")}\nswap\nsetproperty {Q("MD_rpos")}\n')

# ---------- glDrawElements fast path ----------
RING, CAP = 256, 2048
GLA = Q('GLAPI', 'PackageNamespace("GLS3D")')
VBB = 'QName(PackageNamespace("C_Run_C_3A__5C_FlasCC_5C_cygwin_5C_tmp_5C_ccDfHDRY_2E_lto_2E_bc_3A_f9955b5d_2D_a307_2D_4a63_2D_88da_2D_dc2ca410c86c"),"__ZL3vbb")'
ML_ = 'MultinameL([PackageNamespace("")])'
a = A()
Fr, cnt, ip, T, colEn, texEn, i, g, k, pos, col, tex, p, flags = [a.reg() for _ in range(14)]
NO = a.lab('dno')
def st(o, w=32): a.g('_AState'); a.i(o)('add', f'li{w}')
a.esp()('convert_i').sl(Fr)
a.gl(Fr)('li32').i(4)(f'ifne {NO}')
a.ld32(Fr, 8).i(5125)(f'ifne {NO}')
a.ld32(Fr, 4); a.sl(cnt)
a.gl(cnt).i(1)(f'iflt {NO}')
a.gl(cnt).i(CAP)(f'ifgt {NO}')
a.ld32(Fr, 12); a.sl(ip)
st(0, 8); a(f'iffalse {NO}')
st(4); a.i(3)(f'ifne {NO}')
st(8); a.i(5126)(f'ifne {NO}')
st(12); a(f'iftrue {NO}')
st(20, 8); a.sl(colEn)
sk = a.lab('c')
a.gl(colEn)(f'iffalse {sk}')
st(24); a.i(4)(f'ifne {NO}')
st(28); a.i(5121)(f'ifne {NO}')
st(32); a(f'iftrue {NO}')
a.label(sk)
a.g('_AState').g('_activeTextureUnit')('li32').i(33984)('subtract').i(20)('multiply', 'add', 'convert_i').sl(T)
a.ld8(T, 40); a.sl(texEn)
sk = a.lab('t')
a.gl(texEn)(f'iffalse {sk}')
a.ld32(T, 44).i(2)(f'ifne {NO}')
a.ld32(T, 48).i(5126)(f'ifne {NO}')
a.ld32(T, 52)(f'iftrue {NO}')
a.label(sk)
# indices must be 0,1,2,...
l1, l2 = a.lab('ix'), a.lab('ixd')
a.i(0).sl(i)
a.label(l1).gl(i).gl(cnt)(f'ifge {l2}')
a.gl(ip).gl(i).i(4)('multiply', 'add', 'li32').gl(i)(f'ifne {NO}')
a(f'inclocal_i {i}')(f'jump {l1}')
a.label(l2)
a(f'getlex {GLA}', f'getproperty {P("instance")}').sl(g)
a.gl(g)(f'getproperty {Q("activeCommandList", GP)}')(f'iftrue {NO}')
# --- from here on the draw is ours ---
ok = a.lab('r')
a.g('MD_rpos')(f'iftrue {ok}')
for v in ('MD_rpos', 'MD_rcol', 'MD_rtex'):
    a(f'getlex {Q("Array", PUB)}', 'construct 0'); a.setg(v)
a.i(0).setg('MD_ri')
a.label(ok)
a.g('MD_ri')('convert_i').sl(k)
a.gl(k)('increment_i').i(RING)('modulo', 'convert_i'); a.setg('MD_ri')
def buf(var, reg, d32, src):
    have = a.lab('h')
    a.g(var).gl(k)(f'getproperty {ML_}', 'dup').sl(reg)(f'iftrue {have}')
    a.gl(g)(f'getproperty {P("context")}').i(CAP).i(d32)(f'callproperty {P("createVertexBuffer")}, 2', 'dup').sl(reg)
    a.g(var)('swap').gl(k)('swap')(f'setproperty {ML_}')
    a.label(have)
    a.gl(reg).g('ram'); src(); a.i(0).gl(cnt)(f'callpropvoid {P("uploadFromByteArray")}, 4')
buf('MD_rpos', pos, 3, lambda: st(16))
a('pushnull').sl(col)('pushnull').sl(tex).i(0).sl(flags)
sk = a.lab('cb')
a.gl(colEn)(f'iffalse {sk}')
buf('MD_rcol', col, 1, lambda: st(36))
a.i(1).sl(flags)
# libGL leaves the last vertex colour as the current colour
st(36); a.gl(cnt)('decrement_i').i(4)('multiply', 'add', 'convert_i').sl(p)
for o in range(4):
    a.ld8(p, o)('convert_d').i(255)('divide')(f'getlex {VBB}').i(24 + 4 * o)('add', 'sf32')
a.gl(g)
for o in range(4): a.ld8(p, o)('convert_d').i(255)('divide')
a(f'callpropvoid {P("glColor")}, 4')
a.label(sk)
sk = a.lab('tb')
a.gl(texEn)(f'iffalse {sk}')
buf('MD_rtex', tex, 2, lambda: a.ld32(T, 56))
a.gl(flags).i(2)('bitor', 'convert_i').sl(flags)
a.ld32(T, 56); a.gl(cnt)('decrement_i').i(8)('multiply', 'add', 'convert_i').sl(p)
a.gl(p)('lf32')(f'getlex {VBB}').i(52)('add', 'sf32')
a.gl(p).i(4)('add', 'lf32')(f'getlex {VBB}').i(56)('add', 'sf32')
a.label(sk)
a.i(-2128831035)(f'getlex {VBB}')('si32')
a.i(4)(f'getlex {VBB}').i(4)('add', 'si32')
a.gl(flags)(f'getlex {VBB}').i(8)('add', 'si32')
a.gl(cnt)(f'getlex {VBB}').i(68)('add', 'si32')
a.gl(pos).setg('MD_fpos'); a.gl(col).setg('MD_fcol'); a.gl(tex).setg('MD_ftex')
a('pushtrue').setg('MD_fon')
a.gl(Fr)(f'pushint -16', 'bitand').setg('ESP')
a.gl(g).gl(cnt).i(4).g('ram').i(0).i(0).gl(flags)(f'callpropvoid {P("glEndVertexData")}, 6')
a('pushfalse').setg('MD_fon')
a.gl(Fr).setg('ESP')
a('returnvoid')
a.label(NO)
out.append(a.text('=== func F_glDrawElements entry'))
open(sys.argv[2], 'w').write(''.join(out))
