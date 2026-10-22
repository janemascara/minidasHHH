# Building the fast MiniDash.swf

`tools/build.sh original.swf MiniDash.swf` rebuilds the game file from the original SWF.

What it changes:

- **Images.** The game decoded every PNG/JPEG with libpng/libjpeg compiled to Flash bytecode, which Ruffle
  runs very slowly (most of the menu and startup lag). `build_pak.py` decodes each image ahead of time
  (`emu.py` reproduces the game's loader byte for byte) and appends the bitmap and texture pixels after
  the image data; `spec_fast.py` makes the loaders copy those in, falling back to the original decoder
  when anything doesn't match. Every asset is stored uncompressed so the game never runs its own inflate.
- **Drawing.** `spec_gl.py` stops the GLS3D layer re-uploading unchanged shader constants and matrices
  on every draw call.
- **Sound pack.** Moved to a raw trailer after the SWF so the page reads it without inflating the file.

`Patch.java` applies the AVM2 p-code snippets (built with `asm.py`) using FFDec's library.
