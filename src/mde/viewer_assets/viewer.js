// Three.js is loaded from the pinned local assets. No CDN or remote loaders.
(async () => {
const THREE = await import('__ASSET_URL__/three.module.min.js');
const { OrbitControls } = await import('__ASSET_URL__/OrbitControls.js');
const q = s => element.querySelector(s);
let renderer, camera, controls, scene, object, texture, bounds, resizeObserver;
let selectedRun = '', currentMode = 'Depth', data, requestSerial = 0;
let pointColor = 'RGB color', meshStyle = 'RGB textured';
const floats = b => new Float32Array(bytes(b));
const ints = b => new Uint32Array(bytes(b));
function bytes(b) {
  const s = atob(b), a = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i++) a[i] = s.charCodeAt(i);
  return a.buffer;
}
function disposeObject() {
  if (object) { scene.remove(object); object.geometry.dispose(); object.material.dispose(); object = null; }
  if (texture) { texture.dispose(); texture = null; }
}
function render() {
  if (!renderer) return;
  renderer.render(scene, camera);
  const stage = q('[data-stage]');
  stage.dataset.camera = JSON.stringify([...camera.position.toArray(), ...controls.target.toArray()]);
  stage.dataset.renderCount = String(Number(stage.dataset.renderCount || 0) + 1);
}
function size() {
  const stage = q('[data-stage]');
  if (!renderer || !stage.clientWidth) return;
  renderer.setSize(stage.clientWidth, 420);
  camera.aspect = stage.clientWidth / 420;
  camera.updateProjectionMatrix(); render();
}
function init3D() {
  if (renderer) { q('[data-stage]').appendChild(renderer.domElement); size(); return; }
  renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.setClearColor(0x18202c);
  renderer.domElement.setAttribute('aria-label', 'Interactive 3D geometry');
  scene = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(45, 1, 0.001, 1000);
  // Saved OpenCV axes, no artifact/renderer axis conversion. Camera up is -Y.
  camera.up.set(0, -1, 0);
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = false;
  controls.addEventListener('change', render);
  q('[data-stage]').appendChild(renderer.domElement);
  resizeObserver = new ResizeObserver(size); resizeObserver.observe(element);
  size();
}
function resetCamera() {
  if (!bounds) return;
  const center = bounds.getCenter(new THREE.Vector3());
  const radius = Math.max(bounds.getSize(new THREE.Vector3()).length()/2, 1e-6);
  camera.near = radius / 10000; camera.far = radius * 100;
  camera.updateProjectionMatrix();
  controls.target.copy(center); camera.position.copy(center).add(new THREE.Vector3(0, 0, -radius*3));
  controls.update(); render();
}
function setOptions() {
  const color = q('[data-color]'), mesh = q('[data-mesh]');
  color.disabled = currentMode !== 'Point Cloud'; mesh.disabled = currentMode !== 'Mesh';
  color.options[0].disabled = !data?.rgb_colors;
  color.options[0].title = data?.rgb_reason || '';
  color.options[2].disabled = !data?.normal_colors;
  color.options[2].title = data?.normal_reason || '';
  mesh.options[0].disabled = !data?.texture; mesh.options[0].title = data?.rgb_reason || '';
  if (!data?.rgb_colors && pointColor === 'RGB color') pointColor = 'Depth color';
  if (!data?.normal_colors && pointColor === 'Normal color') pointColor = 'Depth color';
  if (!data?.texture && meshStyle === 'RGB textured') meshStyle = 'Geometry';
  color.value = pointColor; mesh.value = meshStyle;
}
function draw3D(newRun) {
  init3D(); disposeObject();
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(floats(data.positions), 3));
  geometry.computeBoundingBox(); bounds = geometry.boundingBox;
  if (currentMode === 'Point Cloud') {
    const color = pointColor === 'RGB color' ? data.rgb_colors : pointColor === 'Normal color' ? data.normal_colors : data.depth_colors;
    const linear = floats(color);
    for (let i = 0; i < linear.length; i++) {
      const c = linear[i]; linear[i] = c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
    }
    geometry.setAttribute('color', new THREE.BufferAttribute(linear, 3));
    object = new THREE.Points(geometry, new THREE.PointsMaterial({ vertexColors: true,
      size: Math.max(bounds.getSize(new THREE.Vector3()).length()*0.003, 1e-6) }));
  } else {
    geometry.setIndex(new THREE.BufferAttribute(ints(data.faces), 1));
    const material = new THREE.MeshBasicMaterial({ color: 0xc8d8e8, side: THREE.DoubleSide,
      wireframe: meshStyle === 'Wireframe' });
    if (meshStyle === 'RGB textured' && data.texture) {
      geometry.setAttribute('uv', new THREE.BufferAttribute(floats(data.uv), 2));
      texture = new THREE.TextureLoader().load(data.texture, render);
      texture.colorSpace = THREE.SRGBColorSpace;
      texture.minFilter = THREE.LinearFilter; texture.magFilter = THREE.LinearFilter;
      material.color.set(0xffffff); material.map = texture;
    }
    object = new THREE.Mesh(geometry, material);
  }
  scene.add(object);
  if (newRun) resetCamera();
  q('[data-reset]').disabled = false;
  const stage = q('[data-stage]');
  stage.dataset.count = data.count; stage.dataset.faces = data.face_count || 0;
  stage.dataset.renderMode = currentMode; stage.dataset.style = currentMode === 'Mesh' ? meshStyle : pointColor;
  stage.dataset.cacheReused = String(data.cache_reused ?? '');
  stage.dataset.library = THREE.REVISION;
  render();
}
function bind() {
  q('[data-mode]').value = currentMode;
  q('[data-mode]').onchange = e => { currentMode = e.target.value; refresh(); };
  q('[data-color]').onchange = e => { pointColor = e.target.value; draw3D(false); };
  q('[data-mesh]').onchange = e => { meshStyle = e.target.value; draw3D(false); };
  q('[data-reset]').onclick = resetCamera;
}
async function refresh() {
  const serial = ++requestSerial;
  q('section').dataset.loadedMode = '';
  q('[data-stage]').style.display = 'none'; q('[data-depth]').style.display = 'none';
  q('[data-download]').style.display = 'none'; q('[data-reset]').disabled = true;
  q('[data-stats]').textContent = ''; q('[data-provenance]').textContent = '';
  if (!selectedRun) { q('[data-message]').textContent = 'Select a completed Run to view its saved artifacts.'; return; }
  q('[data-message]').textContent = currentMode === 'Mesh' ? 'Loading mesh; first request generates and saves derived geometry…' : 'Loading saved artifacts…';
  try {
    const result = await server.render_view({ run_id: selectedRun, mode: currentMode });
    if (serial !== requestSerial) return;
    if (result.error) throw new Error(result.error);
    data = result; setOptions();
    q('[data-stats]').textContent = JSON.stringify(data.stats, null, 2);
    q('[data-provenance]').textContent = JSON.stringify({ origin: data.origin, frame: data.frame, unit: data.unit,
      scale: data.scale, normal_orientation: data.normal_orientation, rgb: data.rgb_reason || 'recorded identity grid',
      normal: data.normal_reason, derived: data.derived, display: 'No LOD or coordinate transform; camera up = -Y' }, null, 2);
    if (currentMode === 'Depth') { q('[data-depth]').src = data.image; q('[data-depth]').style.display = 'block'; }
    else if (currentMode === 'RawDepth') {
      const a = q('[data-download]'); a.href = 'data:application/octet-stream;base64,' + data.download;
      a.download = selectedRun + '-depth.npy'; a.style.display = 'block';
    } else {
      q('[data-stage]').style.display = 'block'; draw3D(!camera || !camera.userData.run || camera.userData.run !== selectedRun);
      camera.userData.run = selectedRun;
    }
    q('[data-message]').textContent = 'Loaded ' + currentMode + ' · ' + data.origin +
      (currentMode === 'Mesh' ? ' · ' + data.face_count + ' faces · cache ' + (data.cache_reused ? 'reused' : 'created') : '') +
      (data.rgb_reason ? '\n' + data.rgb_reason : '') + (data.normal_reason ? '\n' + data.normal_reason : '');
    q('section').dataset.runId = data.run_id; q('section').dataset.loadedMode = currentMode;
  } catch (e) {
    if (serial === requestSerial) {
      q('[data-message]').textContent = e.message;
      q('[data-color]').disabled = true; q('[data-mesh]').disabled = true;
    }
  }
}
function update() {
  selectedRun = props.value || ''; currentMode = 'Depth'; data = null;
  bind(); refresh();
}
watch('value', update);
bind(); update();
// Release WebGL resources and event listeners when the component is removed.
const removal = new MutationObserver(() => {
  if (!element.isConnected) {
    requestSerial++; disposeObject(); controls?.dispose(); renderer?.dispose();
    resizeObserver?.disconnect(); removal.disconnect();
  }
});
removal.observe(document.body, { childList: true, subtree: true });
})().catch(error => {
  element.querySelector('[data-message]').textContent = 'Viewer initialization failed: ' + error.message;
  console.error(error);
});
