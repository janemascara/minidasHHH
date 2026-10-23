#!/bin/sh
# Rebuild ruffle/ (Ruffle 0.7.1 + Stage3D batching and AVM2 fused-op patches) into the given folder.
#   tools/build_ruffle.sh ../ruffle-checkout out-dir
# Needs: rust (wasm32-unknown-unknown target + rust-src), wasm-bindgen-cli 0.2.127, wasm-opt, node 22.
set -e
SRC=$1; OUT=$2; T=$(cd "$(dirname "$0")" && pwd)
[ -d "$SRC/.git" ] || git clone https://github.com/ruffle-rs/ruffle.git "$SRC"
cd "$SRC"
git checkout 89a7049965f3090e706265670df309a5128233ac
git apply "$T/ruffle-stage3d-batching.patch" "$T/ruffle-avm2-fused-ops.patch"
cd web && npm ci
(cd packages/core && BUILD_WASM_MVP=true npm run build)
(cd packages/selfhosted && npm run build)
mkdir -p "$OUT" && cp packages/selfhosted/dist/*.wasm packages/selfhosted/dist/*.js packages/selfhosted/dist/LICENSE_* "$OUT"/
