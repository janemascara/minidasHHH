# Building the fast MiniDash.swf

`tools/build.sh original.swf MiniDash.swf` rebuilds the game file from the original SWF.

What it changes:

- **Images.** The game decoded every PNG/JPEG with libpng/libjpeg compiled to Flash bytecode, which Ruffle
  runs very slowly (most of the menu and startup lag). `build_pak.py` decodes each image ahead of time
  (`emu.py` reproduces the game's loader byte for byte) and appends the bitmap and texture pixels after
  the image data; `spec_fast.py` makes the loaders copy those in, falling back to the original decoder
  when anything doesn't match. Every asset is stored uncompressed so the game never runs its own inflate.
- **Drawing.** The game's libGL copied every vertex one by one in AVM2 before each draw; `spec_gl.py`
  uploads its three vertex arrays (position, colour, texcoord) straight into Stage3D buffers instead,
  and stops GLS3D re-uploading unchanged shader constants, matrices and programs on every draw call.
- **No anti-aliasing.** `spec_misc.txt` makes the game ask for a back buffer without MSAA
  (`configureBackBuffer(w, h, 0, true)` instead of `2`). Ruffle draws each Stage3D draw call in its own
  render pass, so with MSAA every draw resolved the whole screen again; the game's sprites look the same.
- **Sound pack.** Moved to a raw trailer after the SWF so the page reads it without inflating the file.

`Patch.java` applies the AVM2 p-code snippets (built with `asm.py`) using FFDec's library.

# The Flash player (ruffle/)

`ruffle/` is Ruffle 0.7.1 (commit 89a7049) built from source with `ruffle-stage3d-batching.patch`:
Stage3D draw calls are recorded and replayed in one render pass per target instead of one render pass
and queue submission each, program constants go into a ring buffer with dynamic offsets, and render
pipelines and bind groups are cached instead of rebuilt after every `setTextureAt`/`setVertexBufferAt`.
`build_ruffle.sh` rebuilds it.
