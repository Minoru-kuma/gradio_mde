# Three.js r180 / npm 0.180.0 (MIT)

Vendored from the official [r180 source](https://github.com/mrdoob/three.js/tree/r180).
No package manager or CDN is used at runtime. Keep LICENSE with these files.

- `build/three.module.min.js` and `build/three.core.min.js`: unchanged.
- `examples/jsm/controls/OrbitControls.js`: only `from 'three'` is replaced with
  `from './three.module.min.js'` for relative local module resolution.
- SHA-256 below describes the committed files, including that import patch.

- `three.module.min.js`: `e2b5ee6bccd38fd6d8a2428546b83c5f2426d84b152ef82be8055556e3b40eb6`
- `three.core.min.js`: `61ba0df005b05991361d040d8ff670e1aadfd0ce7aeebd1fdb0725957a8957de`
- `OrbitControls.js`: `6c860c6b342200f8aef65493319c12bfb2d652107355b1d25eb2154371128391`
- `LICENSE`: `bfe119ea4fd413f5f7ca3fcd63adb0c4a073ed39daa2fe7d3e6b769e21272601`
