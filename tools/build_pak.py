# Rebuild the game's asset pack: every PNG/JPEG gets its decoded pixels appended after the image data
# (bitmap RGB, alpha and the ready-to-upload texture, each zlib-compressed), and every entry is stored
# uncompressed so the game never runs its own (slow) inflate on it.
#
# trailer layout (little endian):
#   header @H: 'MDP1', half, W, H, hasAlpha, rgbZ, alphaZ, TW, TH, texZ, reserved   (44 bytes)
#   rgb zlib (rgbZ bytes), alpha zlib (alphaZ), texture zlib (texZ)
#   u32 H (offset of header from file start), 'MDPX'
import io, struct, sys, zipfile, zlib, time
from multiprocessing import Pool
import numpy as np
from PIL import Image
from emu import png_bitmap, texture

def pot(n):
    p = 32
    while p < n: p *= 2
    return p

def jpg_bitmap(data):
    im = Image.open(io.BytesIO(data)); im = im.convert('RGB')
    return im.size[0], im.size[1], np.asarray(im), None

def augment(item):
    name, data = item
    low = name.lower()
    if not low.endswith(('.png', '.jpg')): return name, data, None
    try:
        W, H, rgb, alpha = png_bitmap(data, 0) if low.endswith('.png') else jpg_bitmap(data)
    except Exception as e:
        return name, data, 'skip %s: %s' % (name, e)
    TW, TH = pot(W), pot(H)
    T = texture(W, H, rgb, alpha, TW, TH)
    rz = zlib.compress(np.ascontiguousarray(rgb).tobytes(), 9)
    az = zlib.compress(alpha.tobytes(), 9) if alpha is not None else b''
    tz = zlib.compress(T.tobytes(), 9)
    hdr = struct.pack('<4s10i', b'MDP1', 0, W, H, 1 if alpha is not None else 0, len(rz), len(az), TW, TH, len(tz), 0)
    off = len(data)
    return name, data + hdr + rz + az + tz + struct.pack('<I4s', off, b'MDPX'), None

if __name__ == '__main__':
    src, dst = sys.argv[1], sys.argv[2]
    zin = zipfile.ZipFile(src)
    items = [(i.filename, zin.read(i.filename)) for i in zin.infolist()]
    t0 = time.time()
    with Pool() as p:
        res = p.map(augment, items, chunksize=1)
    zout = zipfile.ZipFile(dst, 'w', zipfile.ZIP_STORED)
    for (name, data, msg), info in zip(res, zin.infolist()):
        if msg: print(msg)
        zi = zipfile.ZipInfo(name, date_time=info.date_time)
        zi.compress_type = zipfile.ZIP_STORED
        zi.external_attr = info.external_attr
        zout.writestr(zi, data)
    zout.close()
    import os
    print('pak', os.path.getsize(src), '->', os.path.getsize(dst), 'in %.0fs' % (time.time() - t0))
