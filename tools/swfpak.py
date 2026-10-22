# Replace the game's asset pack (BinaryData "C_Run.ALC_FS_..._game_flash.pak") inside a SWF and recompress.
import sys, zlib, struct
src, pak, dst = sys.argv[1], sys.argv[2], sys.argv[3]
level = int(sys.argv[4]) if len(sys.argv) > 4 else 9
d = open(src, 'rb').read()
assert d[:3] in (b'CWS', b'FWS')
body = zlib.decompress(d[8:]) if d[:3] == b'CWS' else d[8:]
nbits = body[0] >> 3
p = (5 + 4 * nbits + 7) // 8 + 4
out = [body[:p]]
# find the pack's character id via SymbolClass
names = {}
q = p
while q < len(body):
    h = struct.unpack('<H', body[q:q + 2])[0]; t = h >> 6; l = h & 63; hl = 2
    if l == 63: l = struct.unpack('<I', body[q + 2:q + 6])[0]; hl = 6
    if t == 76:
        r = q + hl; n = struct.unpack('<H', body[r:r + 2])[0]; r += 2
        for _ in range(n):
            cid = struct.unpack('<H', body[r:r + 2])[0]; e = body.index(b'\0', r + 2)
            names[cid] = body[r + 2:e].decode(); r = e + 1
    q += hl + l
    if t == 0: break
pak_id = [c for c, n in names.items() if n.startswith('C_Run.ALC_FS_') and n.endswith('2E70616B')]
assert len(pak_id) == 1, pak_id
pak_id = pak_id[0]
newpak = open(pak, 'rb').read()
q = p; replaced = 0; audio = None
while q < len(body):
    h = struct.unpack('<H', body[q:q + 2])[0]; t = h >> 6; l = h & 63; hl = 2
    if l == 63: l = struct.unpack('<I', body[q + 2:q + 6])[0]; hl = 6
    tag = body[q:q + hl + l]
    if t == 87 and body[q + hl + 6:q + hl + 14] == b'MDAUDIO1':
        # sound pack for the page: moved out of the compressed body to a raw trailer (see below)
        audio = body[q + hl + 6:q + hl + l]
        q += hl + l
        continue
    if t == 87 and struct.unpack('<H', body[q + hl:q + hl + 2])[0] == pak_id:
        payload = body[q + hl:q + hl + 6] + newpak
        tag = struct.pack('<HI', (87 << 6) | 63, len(payload)) + payload
        replaced += 1
    out.append(tag)
    q += hl + l
    if t == 0: break
assert replaced == 1
nb = b''.join(out)
hdr = b'CWS' + d[3:4] + struct.pack('<I', len(nb) + 8)
trailer = b''
if audio is not None:
    # raw "MDAUDIO1..." pack, then its length and a marker, after the end of the zlib stream
    trailer = audio + struct.pack('<I', len(audio)) + b'MDAUDTRL'
open(dst, 'wb').write(hdr + zlib.compress(nb, level) + trailer)
print('written', dst, 'audio trailer', len(trailer))
