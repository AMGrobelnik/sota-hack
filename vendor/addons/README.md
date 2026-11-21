# three.js addons (version 0.187.0)

Copied from `examples/jsm` of the npm package three@0.187.0, the same
version as `vendor/three.module.min.js`. Only the `from 'three'`
imports were rewritten, to `../../three.module.min.js`; the imports
between addons are unchanged. No CDN, no import map needed. Proven in
headless Chromium: all addons imported, one frame rendered with an
environment map and bloom, no console error, every request on the
local server.

Import lines, from a page in `variants/`:

```js
import * as THREE from '../vendor/three.module.min.js';
import { RoomEnvironment } from '../vendor/addons/environments/RoomEnvironment.js';
import { RoundedBoxGeometry } from '../vendor/addons/geometries/RoundedBoxGeometry.js';
import { EffectComposer } from '../vendor/addons/postprocessing/EffectComposer.js';
import { RenderPass } from '../vendor/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from '../vendor/addons/postprocessing/UnrealBloomPass.js';
import { BokehPass } from '../vendor/addons/postprocessing/BokehPass.js';
import { OutputPass } from '../vendor/addons/postprocessing/OutputPass.js';
import { ShaderPass } from '../vendor/addons/postprocessing/ShaderPass.js';
```

Supporting files they pull in, no import needed from a page:
`postprocessing/Pass.js` (also exports `FullScreenQuad`),
`postprocessing/MaskPass.js`, `shaders/CopyShader.js`,
`shaders/LuminosityHighPassShader.js`, `shaders/OutputShader.js`,
`shaders/BokehShader.js`. `ShaderPass` takes a shader object, for
example `new ShaderPass(CopyShader)` after importing `CopyShader` from
`../vendor/addons/shaders/CopyShader.js`.

| Addon | Use |
|---|---|
| RoomEnvironment | Studio-like scene for reflections |
| RoundedBoxGeometry | Boxes with real bevelled edges |
| EffectComposer | Runs the post-processing passes in order |
| RenderPass | First pass, renders the scene |
| UnrealBloomPass | Glow on bright parts |
| BokehPass | Depth-of-field blur |
| OutputPass | Last pass, tone mapping and colour space |
| ShaderPass | Wraps any custom shader as a pass |

Environment map plus output pass:

```js
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
const composer = new EffectComposer(renderer);
composer.addPass(new RenderPass(scene, camera));
composer.addPass(new OutputPass()); // last; call composer.render() each frame
```

With a composer, leave `renderer.toneMapping` at its default for the
render pass and let OutputPass apply tone mapping and sRGB. Put
UnrealBloomPass between RenderPass and OutputPass.
