#!/bin/sh
# Rebuild the fast MiniDash.swf from the original game file.
#   tools/build.sh original.swf out.swf
# Needs: java 17+, python3 with numpy + Pillow, and FFDec's library jars
# (`npm pack jpexs-ts` contains bin/lib/ffdec_lib.jar); set FFDEC_LIB to that lib folder.
set -e
IN=$1; OUT=$2; T=$(cd "$(dirname "$0")" && pwd); W=${TMPDIR:-/tmp}/minidash-build
: "${FFDEC_LIB:?set FFDEC_LIB to the folder containing ffdec_lib.jar}"
rm -rf "$W"; mkdir -p "$W/classes" "$W/dump"
javac -cp "$FFDEC_LIB/ffdec_lib.jar" -d "$W/classes" "$T/Patch.java"
P="java -Xmx6g -cp $W/classes:$FFDEC_LIB/*"
# 1. asset pack: pre-decoded pixels appended to every image, all entries stored
python3 "$T/extract_pak.py" "$IN" "$W/pak_orig.zip"
python3 "$T/build_pak.py" "$W/pak_orig.zip" "$W/pak_fast.zip"
# 2. code: image fast paths, direct vertex upload + GLS3D per-draw caching, no back buffer MSAA
printf '=== func GLAPI/executeCommandList entry\n#regs 0\nnop\n=== func GLAPI/glEndVertexData entry\n#regs 0\nnop\n' > "$W/nop.txt"
PATCH_DUMP="$W/dump" $P Patch "$IN" "$W/nop.swf" "$W/nop.txt"
(cd "$T" && python3 spec_fast.py "$W/spec_fast.txt" && python3 spec_gl.py "$W/dump" "$W/spec_gl.txt")
$P Patch "$IN" "$W/abc.swf" "$W/spec_fast.txt" "$W/spec_gl.txt" "$T/spec_misc.txt"
# 3. swap in the new pack, move the page's sound pack to a raw trailer, recompress
python3 "$T/swfpak.py" "$W/abc.swf" "$W/pak_fast.zip" "$OUT" 9
