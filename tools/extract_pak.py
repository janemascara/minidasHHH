# Extract the game's asset pack (the zip embedded as "C_Run.ALC_FS_..._game_flash.pak") from a SWF.
import sys, zlib, struct
d = open(sys.argv[1], 'rb').read()
body = zlib.decompressobj().decompress(d[8:]) if d[:3] == b'CWS' else d[8:]
p = (5 + 4 * (body[0] >> 3) + 7) // 8 + 4
tags, names = [], {}
while p < len(body):
    h = struct.unpack('<H', body[p:p + 2])[0]; t = h >> 6; l = h & 63; hl = 2
    if l == 63: l = struct.unpack('<I', body[p + 2:p + 6])[0]; hl = 6
    tags.append((t, p + hl, l))
    if t == 76:
        r = p + hl; n = struct.unpack('<H', body[r:r + 2])[0]; r += 2
        for _ in range(n):
            cid = struct.unpack('<H', body[r:r + 2])[0]; e = body.index(b'\0', r + 2)
            names[cid] = body[r + 2:e].decode(); r = e + 1
    p += hl + l
    if t == 0: break
pak = [c for c, n in names.items() if n.startswith('C_Run.ALC_FS_') and n.endswith('2E70616B')][0]
for t, o, l in tags:
    if t == 87 and struct.unpack('<H', body[o:o + 2])[0] == pak:
        open(sys.argv[2], 'wb').write(body[o + 6:o + l])
        print('pak', l - 6, 'bytes')
