# Fast paths for image loading: pixels pre-decoded at build time are appended to each image file
# (after the PNG IEND / JPEG EOI), see build_pak.py for the layout.
import sys
from asm import *
MAGIC = 0x5850444D   # 'MDPX' little endian (trailer)
MAGIC2 = 0x3150444D  # 'MDP1' (header)
FU = 'PackageNamespace("flash.utils")'
GL = 'PackageNamespace("GLS3D")'
TRACE = '--trace' in sys.argv
PNG = 'F__Z13ImageLoad_PNGP9CGameBasePcP10IDibBitmap'
JPG = 'F__Z13ImageLoad_JPGP9CGameBasePcP10IDibBitmap'
GLES = 'F__Z23GLES_CopyImageToTextureP18BinoteqTextureDataP9CGameBasejP10IDibBitmapiiiibb'
out = []
for v in ('MD_pb', 'MD_pbits', 'MD_palpha', 'MD_pw', 'MD_ph', 'MD_pt'):
    out.append(f'=== addvar {v}\n')

def inflate_to_ram(a, src, ln, dst, n):
    """zlib stream at ram[src..src+ln) -> ram[dst..dst+n)"""
    t = a.reg()
    a('getlex ' + Q('ByteArray', FU), 'construct 0').sl(t)
    a.gl(t).g('ram'); src(); ln(); a('callpropvoid ' + Q('writeBytes', PUB) + ', 3')
    a.gl(t)('callpropvoid ' + Q('uncompress', PUB) + ', 0')
    a.gl(t).i(0)('setproperty ' + Q('position', PUB))
    a.gl(t).g('ram'); dst(); n(); a('callpropvoid ' + Q('readBytes', PUB) + ', 3')

def fast_load(kind, cg, bmp, created, mf, frame, sp0):
    a = A()
    SP, base, size, hdr, W, H, hasA, rgbP, alP, res, tmp, data, T = [a.reg() for _ in range(13)]
    NO, END, FAIL = a.lab('no'), a.lab('end'), a.lab('fail')
    a.gl(sp0).sl(SP)
    a.g('eax')(f'iffalse {NO}')
    a.ld32(mf, 12); a.sl(size); a.ld32(mf, 4); a.sl(base)
    a.gl(size).i(64)(f'iflt {NO}')
    a.gl(base).gl(size)('add').i(4)('subtract', 'li32').i(MAGIC)(f'ifne {NO}')
    a.gl(base).gl(base).gl(size)('add').i(8)('subtract', 'li32', 'add', 'convert_i').sl(hdr)
    a.ld32(hdr, 0).i(MAGIC2)(f'ifne {NO}')
    a.ld8(cg, 7174).i(1)(f'ifne {NO}')
    a.ld8(cg, 7270)(f'iftrue {NO}')
    if kind == 'png':
        a.ld8(cg, 7175)(f'iftrue {NO}')
        a.ld8(cg, 7176).i(1)(f'ifne {NO}')
    a.ld8(bmp, 28).ld32(hdr, 4)(f'ifne {NO}')
    # same bitmap calls as the decoder makes before reading pixels
    a.vcall(bmp, 40, [], SP, tmp)
    a.vcall(bmp, 12, [], SP, tmp)
    a.g('eax').i(1)(f'ifeq {NO}')
    a.g('eax').i(2)(f'ifeq {NO}')
    a.ld32(hdr, 8); a.sl(W); a.ld32(hdr, 12); a.sl(H); a.ld32(hdr, 16); a.sl(hasA)
    a.gl(hdr).i(44)('add', 'convert_i').sl(data)
    # rgb
    a.ccall('F_malloc', [lambda: (a.gl(W), a.gl(H), a('multiply'), a.i(3), a('multiply', 'convert_i'))], SP)
    a.g('eax')('convert_i').sl(rgbP)
    a.gl(rgbP)(f'iffalse {NO}')
    inflate_to_ram(a, lambda: a.gl(data), lambda: a.ld32(hdr, 20), lambda: a.gl(rgbP), lambda: (a.gl(W), a.gl(H), a('multiply'), a.i(3), a('multiply', 'convert_i')))
    a.gl(data).ld32(hdr, 20)('add', 'convert_i').sl(data)
    a.i(0).sl(alP)
    if kind == 'png':
        skipA = a.lab('na')
        a.gl(hasA)(f'iffalse {skipA}')
        a.ccall('F_malloc', [lambda: (a.gl(W), a.gl(H), a('multiply', 'convert_i'))], SP)
        a.g('eax')('convert_i').sl(alP)
        inflate_to_ram(a, lambda: a.gl(data), lambda: a.ld32(hdr, 24), lambda: a.gl(alP), lambda: (a.gl(W), a.gl(H), a('multiply', 'convert_i')))
        a.label(skipA)
        a.i(0).gl(cg).i(7173)('add', 'si8')
    a.gl(data).ld32(hdr, 24)('add', 'convert_i').sl(data)
    # texture for the upload that follows
    a('getlex ' + Q('ByteArray', FU), 'construct 0').sl(T)
    a.gl(T).g('ram').gl(data).ld32(hdr, 36)('callpropvoid ' + Q('writeBytes', PUB) + ', 3')
    a.gl(T)('callpropvoid ' + Q('uncompress', PUB) + ', 0')
    a.gl(T).i(0)('setproperty ' + Q('position', PUB))
    if kind == 'jpg':
        # without the PNG loader's 7173 guard, SetBits uploads the texture right away
        a.gl(bmp).setg('MD_pb'); a.gl(rgbP).setg('MD_pbits'); a.i(0).setg('MD_palpha')
        a.ld32(hdr, 28); a.setg('MD_pw'); a.ld32(hdr, 32); a.setg('MD_ph'); a.gl(T).setg('MD_pt')
    # hand pixels to the bitmap exactly like the decoder does
    a.vcall(bmp, 92, [lambda: a.i(24)], SP, tmp)
    a.vcall(bmp, 20, [lambda: a.gl(rgbP), lambda: a.gl(W), lambda: a.gl(H)], SP, tmp)
    a.gl(bmp).sl(res)
    if kind == 'jpg':
        a.i(0).setg('MD_pb'); a('pushnull').setg('MD_pt')
    okBits = a.lab('ok')
    a.g('eax')(f'iftrue {okBits}')
    if kind == 'png':
        nf = a.lab('nf')
        a.gl(alP)(f'iffalse {nf}')
        a.ccall('F_free', [lambda: a.gl(alP)], SP)
        a.label(nf)
    a.ccall('F_free', [lambda: a.gl(rgbP)], SP)
    a(f'jump {FAIL}')
    a.label(okBits)
    if kind == 'png':
        a.vcall(bmp, 36, [], SP, tmp)
        noA = a.lab('noa')
        a.gl(hasA)(f'iffalse {noA}')
        a.vcall(bmp, 24, [lambda: a.gl(alP), lambda: a.gl(W), lambda: a.gl(H)], SP, tmp)
        a.g('eax')(f'iftrue {noA}')
        a.ccall('F_free', [lambda: a.gl(alP)], SP)
        a(f'jump {FAIL}')
        a.label(noA)
    if kind == 'jpg':
        a(f'jump {END}')
    # remember the texture for GLES_CopyImageToTexture
    a.gl(bmp).setg('MD_pb')
    a.ld32(bmp, 56); a.setg('MD_pbits')
    a.ld32(bmp, 60); a.setg('MD_palpha')
    a.ld32(hdr, 28); a.setg('MD_pw')
    a.ld32(hdr, 32); a.setg('MD_ph')
    a.gl(T).setg('MD_pt')
    if kind == 'png':
        a.i(1).gl(cg).i(7173)('add', 'si8')
        a.vcall(bmp, 160, [], SP, tmp)
        a.i(0).setg('MD_pb')
        a('pushnull').setg('MD_pt')
        a.g('eax')(f'iftrue {END}')
    a.label(FAIL)
    a.i(0).sl(res)
    nd = a.lab('nd')
    a.gl(created)(f'iffalse {nd}')
    a.vcall(bmp, 4, [], SP, tmp)
    a.label(nd)
    if kind == 'png':
        a.i(1).gl(cg).i(7173)('add', 'si8')
    a.label(END)
    if TRACE: a.fscommand('__v', ['fast:' + kind + ',', lambda: a.gl(res)])
    a.ccall('F__ZN11CMemoryFileD1Ev', [lambda: a.gl(mf)], SP)
    a.gl(res).setg('eax')
    a.gl(frame).setg('ESP')
    a('returnvoid')
    a.label(NO)
    if TRACE: a.fscommand('__v', ['slow:' + kind + ',', lambda: a.g('eax'), ',', lambda: a.gl(size)])
    return a

out.append(fast_load('png', cg=33, bmp=32, created=31, mf=28, frame=12, sp0=11).text(f'=== func {PNG} after:callpropvoid/DidLoadOpenImageFile1x_2x'))
out.append(fast_load('jpg', cg=32, bmp=30, created=28, mf=22, frame=2, sp0=1).text(f'=== func {JPG} after:callpropvoid/DidLoadOpenImageFile1x_2x'))

# GLES_CopyImageToTexture: upload the texture built at load time
a = A()
F, SP, bmp, w, h, tex = [a.reg() for _ in range(6)]
NO = a.lab('gno')
def arg(k): return lambda: (a.gl(F), a.i(4 * k), a('add', 'li32'))
a.esp()('convert_i').sl(F); a.gl(F).sl(SP)
arg(3)(); a.sl(bmp)
a.gl(bmp)(f'iffalse {NO}')
a.g('MD_pb').gl(bmp)(f'ifne {NO}')
a.ld32(bmp, 56).g('MD_pbits')(f'ifne {NO}')
a.ld32(bmp, 60).g('MD_palpha')(f'ifne {NO}')
arg(0)(); a(f'iffalse {NO}')
arg(2)(); a.sl(tex); a.gl(tex)(f'iffalse {NO}')
for k in (4, 5, 8, 9):
    arg(k)(); a(f'iftrue {NO}')
arg(6)(); a.sl(w); arg(7)(); a.sl(h)
a.gl(w).g('MD_pw')(f'ifne {NO}')
a.gl(h).g('MD_ph')(f'ifne {NO}')
for gname in ('_g_bRestoringLostContext', '_g_bPlayCreekLoadTextureHalfSize', '_g_bPlayCreekMakeMipMapsForTexture'):
    a.g(gname)('li8')(f'iftrue {NO}')
a.g('_g_nTextureDataBufferSize')('li32').gl(w).gl(h)('multiply').i(4)('multiply')(f'iflt {NO}')
a.i(32993); arg(0)(); a.i(100)('add', 'si32')
a.ccall('F_glBindTexture', [lambda: a.i(3553), lambda: a.gl(tex)], SP)
a.gl(tex).g('_g_Current_texName')('si32')
a.ccall('F_glPixelStorei', [lambda: a.i(3317), lambda: a.i(1)], SP)
a('getlex ' + Q('GLAPI', GL), 'getproperty ' + Q('instance', PUB))
a.i(3553).i(0).i(32993).gl(w).gl(h).i(0).i(32993).i(5121).i(0).g('MD_pt')
a('callpropvoid ' + Q('glTexImage2D', PUB) + ', 10')
a.i(0).setg('MD_pb')
a('pushnull').setg('MD_pt')
if TRACE: a.fscommand('__v', ['gfast:', lambda: a.gl(w), ',', lambda: a.gl(h)])
a.i(1).setg('eax')
a.gl(F).setg('ESP')
a('returnvoid')
a.label(NO)
out.append(a.text(f'=== func {GLES} entry'))
open(sys.argv[1], 'w').write(''.join(out))
