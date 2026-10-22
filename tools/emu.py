import io, struct, zlib
import numpy as np
from PIL import Image

def s32(x):
    x &= 0xffffffff
    return x - (1 << 32) if x >= 1 << 31 else x

def checksum(buf):
    b = bytes(buf); n = len(b); h = 0
    n4 = n // 4
    if n4:
        words = np.frombuffer(b[:n4 * 4], dtype='<i4').astype(np.int64)
        # h = h*31 + w  (mod 2^32) over sequence -> Horner; do in chunks with python ints for exactness
        M = 1 << 32
        for w in words.tolist():
            h = (h * 31 + w) % M
    for i in range(n4 * 4, n):
        h = (h * 31 + b[i]) % (1 << 32)
    return s32(h)

def checksum_fast(buf):
    """same as checksum but vectorised: h = sum w_i * 31^(n-1-i) mod 2^32"""
    b = bytes(buf); n = len(b); n4 = n // 4
    M = 1 << 32
    h = 0
    if n4:
        w = np.frombuffer(b[:n4 * 4], dtype='<u4').astype(np.uint64)
        # powers of 31 mod 2^32
        p = np.empty(n4, dtype=np.uint64)
        p[-1] = 1
        # compute powers backwards with uint64 wraparound then mask
        pw = np.uint64(1)
        # vectorised via cumulative product in blocks
        powers = np.ones(n4, dtype=np.uint64)
        if n4 > 1:
            r = np.full(n4 - 1, 31, dtype=np.uint64)
            # cumprod with mask to keep in 32 bits (uint64 multiply of two <2^32 values fits? 31*2^32 < 2^64 yes)
            acc = 1
            out = np.empty(n4 - 1, dtype=np.uint64)
            # chunked loop for exactness
            cur = np.uint64(1)
            blk = 4096
            base = np.ones(blk, dtype=np.uint64)
            for k in range(1, blk): base[k] = (base[k - 1] * np.uint64(31)) & np.uint64(0xffffffff)
            step = (base[-1] * np.uint64(31)) & np.uint64(0xffffffff)
            vals = []
            m = n4
            k = 0
            while k < m:
                c = min(blk, m - k)
                vals.append((base[:c] * cur) & np.uint64(0xffffffff))
                cur = (cur * step) & np.uint64(0xffffffff)
                k += c
            powers = np.concatenate(vals)[::-1]
        prod = (w * powers) & np.uint64(0xffffffff)
        h = int(prod.sum(dtype=np.uint64)) % M  # sum of up to 2^20 values < 2^32 fits in 2^52
    for i in range(n4 * 4, n):
        h = (h * 31 + b[i]) % M
    return s32(h)

def decode_bgra(data):
    """libpng with expand, filler(0xff, after), palette->rgb, gray->rgb, bgr, tRNS->alpha: returns HxWx4 uint8 BGRA"""
    im = Image.open(io.BytesIO(data))
    im.load()
    a = np.asarray(im.convert('RGBA'))
    return a[:, :, [2, 1, 0, 3]].copy()

def png_bitmap(data, half):
    """emulates ImageLoad_PNG (24-bit mode, no bleed, normal orientation) + ImagePremultiplyAlpha
    returns (w, h, rgb bytes, alpha bytes or None)"""
    src = decode_bgra(data).astype(np.uint32)
    H, W = src.shape[:2]
    if half:
        h2, w2 = H >> 1, W >> 1
        s = src[:h2 * 2, :w2 * 2]
        s = s[0::2, 0::2] + s[0::2, 1::2] + s[1::2, 0::2] + s[1::2, 1::2]
        src = s >> 2
        H, W = h2, w2
    bgra = src.astype(np.uint8)
    rgb = bgra[:, :, [2, 1, 0]].copy()
    alpha = bgra[:, :, 3].copy()
    if int(np.bitwise_and.reduce(alpha.ravel())) == 255 if alpha.size else True:
        return W, H, rgb, None
    rgb = ((rgb.astype(np.uint32) * alpha[:, :, None].astype(np.uint32)) >> 8).astype(np.uint8)
    return W, H, rgb, alpha

def texture(W, H, rgb, alpha, TW, TH):
    """emulates GLES_CopyImageToTexture for format 32993 (BGRA, 4 bpp) from a 24-bit bitmap"""
    T = np.zeros((TH, TW, 4), np.uint8)
    rows = min(TH, H + 2)
    yi = np.minimum(np.arange(rows), H - 1)
    xi = np.minimum(np.arange(TW), W - 1)
    T[:rows, :, :3] = rgb[yi][:, xi][:, :, ::-1]
    T[:rows, :, 3] = 255 if alpha is None else alpha[yi][:, xi]
    return T
