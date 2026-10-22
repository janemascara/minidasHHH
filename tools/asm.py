# Tiny helper for writing AVM2 p-code snippets for Patch.java
CR = 'PackageNamespace("C_Run")'
FS = 'PackageNamespace("flash.system")'
PUB = 'PackageNamespace("")'
def Q(name, ns=CR): return f'QName({ns},"{name}")'
class A:
    _lab = [0]
    def __init__(self, nregs=0):
        self.lines = []
        self.nregs = nregs
    def reg(self):
        r = '{R%d}' % self.nregs; self.nregs += 1; return r
    def lab(self, hint='L'):
        A._lab[0] += 1; return f'md_{hint}{A._lab[0]}'
    def __call__(self, *ops):
        for o in ops:
            for l in str(o).split('\n'):
                if l.strip(): self.lines.append(l)
        return self
    def label(self, l): self.lines.append(l + ':'); self.lines.append('label'); return self
    # values
    def gl(self, r): return self(f'getlocal {r}')
    def sl(self, r): return self(f'setlocal {r}')
    def i(self, v): return self(f'pushint {int(v)}')
    def s(self, v): return self('pushstring "%s"' % v.replace('\\', '\\\\').replace('"', '\\"'))
    def g(self, name): return self(f'getlex {Q(name)}')
    def setg(self, name):   # value on stack -> global
        return self(f'findproperty {Q(name)}', 'swap', f'setproperty {Q(name)}')
    def esp(self): return self.g('ESP')
    def set_esp_from(self, r): return self.gl(r).setg('ESP')
    # memory: address must be on stack
    def li32(self): return self('li32')
    def li8(self): return self('li8')
    def ld32(self, base_r, off):
        self.gl(base_r)
        if off: self.i(off)('add')
        return self('li32')
    def ld8(self, base_r, off):
        self.gl(base_r)
        if off: self.i(off)('add')
        return self('li8')
    # call a C function F_xxx with int args (list of callables that push a value), result -> eax
    def ccall(self, fname, args, sp):
        n = len(args); fr = ((4 * n + 15) // 16) * 16 or 16
        self.gl(sp).i(fr)('subtract', 'convert_i').sl(sp)
        for k, a in enumerate(args):
            a(); self.gl(sp)
            if k: self.i(4 * k)('add')
            self('si32')
        self.set_esp_from(sp)
        self(f'findpropstrict {Q(fname)}', f'callpropvoid {Q(fname)}, 0')
        self.gl(sp).i(fr)('add', 'convert_i').sl(sp)
        return self
    # call through vtable: obj in register objr, slot offset
    def vcall(self, objr, off, args, sp, tmp):
        self.gl(objr)('li32').i(off)('add', 'li32').sl(tmp)
        n = len(args) + 1; fr = ((4 * n + 15) // 16) * 16
        self.gl(sp).i(fr)('subtract', 'convert_i').sl(sp)
        self.gl(objr).gl(sp)('si32')
        for k, a in enumerate(args):
            a(); self.gl(sp).i(4 * (k + 1))('add', 'si32')
        self.set_esp_from(sp)
        self.g('ptr2fun')('dup').gl(tmp)('getproperty MultinameL([PackageNamespace("")])', 'swap', 'call 0', 'pop')
        self.gl(sp).i(fr)('add', 'convert_i').sl(sp)
        return self
    def fscommand(self, cmd, parts):
        """parts: list of str (literal) or callable (pushes value)"""
        self('findpropstrict ' + Q('fscommand', FS))
        self.s(cmd).s('')
        for p in parts:
            if callable(p): p()
            else: self.s(p)
            self('add')
        self('callpropvoid ' + Q('fscommand', FS) + ', 2')
        return self
    def checksum(self, ptr, n, out):
        """ptr, n: callables; result int -> register out"""
        P, N, I = self.reg(), self.reg(), self.reg()
        ptr(); self.sl(P); n(); self.sl(N)
        self.i(0).sl(out).i(0).sl(I)
        l1, l2, l3, l4 = self.lab(), self.lab(), self.lab(), self.lab()
        self.label(l1).gl(I).i(4)('add').gl(N)(f'ifgt {l2}')
        self.gl(out).i(31)('multiply').gl(P).gl(I)('add', 'li32', 'add', 'convert_i').sl(out)
        self.gl(I).i(4)('add', 'convert_i').sl(I)(f'jump {l1}')
        self.label(l2).gl(I).gl(N)(f'ifge {l3}')
        self.gl(out).i(31)('multiply').gl(P).gl(I)('add', 'li8', 'add', 'convert_i').sl(out)
        self(f'inclocal_i {I}')(f'jump {l2}')
        self.label(l3)
        return self
    def cstring(self, ptr, out):
        P, C = self.reg(), self.reg()
        ptr(); self.sl(P); self.s('').sl(out)
        l1, l2 = self.lab(), self.lab()
        self.label(l1).gl(P)('li8', 'dup').sl(C)(f'iffalse {l2}')
        self.gl(out)('getlex ' + Q('String', PUB)).gl(C)('callproperty ' + Q('fromCharCode', PUB) + ', 1', 'add').sl(out)
        self(f'inclocal_i {P}')(f'jump {l1}')
        self.label(l2)
        return self
    def text(self, header):
        return f'{header}\n#regs {self.nregs}\n' + '\n'.join(self.lines) + '\n'
