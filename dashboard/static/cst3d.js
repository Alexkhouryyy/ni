// Apex Constellation — the 12 expert "planets" as real 3D spheres orbiting a
// glowing Apex sun, rendered with three.js. Self-contained: mirrors the
// avatar3d.js pattern (scene/camera/renderer/loop + graceful failure).
//
// Bridges to the classic app.js via a window object app.js calls into:
//   window.Cst3D.build(planets) -> bool   (true once the scene is live)
//   .setAll(state) .setStates(keys,'thinking') .setState(key,'done')
//   .clearStates() .setConvening(bool) .select(key|null)
// A raycaster click calls window._cstOpenChat(key) (exposed by app.js).
//
// On any failure the CSS orbit in app.js stays as the fallback.

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { CSS2DRenderer, CSS2DObject } from 'three/addons/renderers/CSS2DRenderer.js';

// codename -> equirectangular texture (reusing the same assets the globe uses)
const TEX = {
  mercury: '/static/planets/mercury.jpg',
  venus:   '/static/planets/venus.jpg',
  earth:   '//unpkg.com/three-globe/example/img/earth-blue-marble.jpg',
  luna:    '/static/planets/moon.jpg',
  mars:    '/static/planets/mars.jpg',
  jupiter: '/static/planets/jupiter.jpg',
  saturn:  '/static/planets/saturn.jpg',
  neptune: '/static/planets/neptune.jpg',
  pluto:   '/static/planets/pluto.jpg',
};
// relative sphere radii (scene units)
const SIZE = {
  mercury: 0.34, venus: 0.48, earth: 0.52, luna: 0.30, mars: 0.42,
  ceres: 0.34, vesta: 0.32, pallas: 0.33,
  jupiter: 0.90, saturn: 0.80, neptune: 0.60, pluto: 0.30,
};
// pack -> orbital band (radius, inclination, color, angular speed)
const BAND = {
  mind:  { r: 3.4, incX:  0.06, incZ:  0.10, color: 0x8a7cff, spd: 0.17 },
  life:  { r: 5.1, incX:  0.18, incZ: -0.06, color: 0xffb547, spd: 0.12 },
  maker: { r: 6.9, incX: -0.12, incZ:  0.14, color: 0x3ddc97, spd: 0.085 },
};

const S = { built: false, raf: 0, tries: 0 };
let scene, camera, renderer, labelRenderer, controls, clock, raycaster, pointer;
let sunMesh, mount;
const planets = [];                 // { key, mesh, pack, color, base, angle, spd, st, cur:{}, tgt:{} }
const meshByKey = new Map();
const pickables = [];
let convening = false, hoverKey = null, selectedKey = null;

function _fail(msg) { console.warn('[Cst3D] init failed:', msg); return false; }

function _procTexture(hex) {
  const c = document.createElement('canvas'); c.width = 256; c.height = 128;
  const x = c.getContext('2d');
  const base = '#' + hex.toString(16).padStart(6, '0');
  x.fillStyle = base; x.fillRect(0, 0, 256, 128);
  for (let i = 0; i < 1400; i++) {                       // rocky speckle
    const a = Math.random() * 0.18;
    x.fillStyle = Math.random() < 0.5 ? `rgba(0,0,0,${a})` : `rgba(255,255,255,${a})`;
    x.fillRect(Math.random() * 256, Math.random() * 128, 2, 2);
  }
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}

function _texFor(codename, packColor) {
  const url = TEX[(codename || '').toLowerCase()];
  if (!url) return _procTexture(packColor);
  const t = new THREE.TextureLoader().load(url);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

function _glowSprite(color, size) {
  const c = document.createElement('canvas'); c.width = c.height = 128;
  const x = c.getContext('2d');
  const g = x.createRadialGradient(64, 64, 0, 64, 64, 64);
  const col = new THREE.Color(color);
  g.addColorStop(0, `rgba(${col.r*255|0},${col.g*255|0},${col.b*255|0},0.9)`);
  g.addColorStop(0.4, `rgba(${col.r*255|0},${col.g*255|0},${col.b*255|0},0.25)`);
  g.addColorStop(1, 'rgba(0,0,0,0)');
  x.fillStyle = g; x.fillRect(0, 0, 128, 128);
  const tex = new THREE.CanvasTexture(c);
  const spr = new THREE.Sprite(new THREE.SpriteMaterial({
    map: tex, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true }));
  spr.scale.set(size, size, 1);
  return spr;
}

function _label(p, base) {
  const el = document.createElement('div');
  el.className = `cst3d-label pack-${p.pack}`;
  el.innerHTML = `<span class="cst3d-glyph">${p.glyph || '✦'}</span>${p.display}`;
  const obj = new CSS2DObject(el);
  obj.position.set(0, base + 0.55, 0);
  obj.el = el;
  return obj;
}

function build(roster) {
  if (S.built) return true;
  mount = document.getElementById('cst-3d');
  if (!mount) return false;
  // The mount is display:none until `.has-3d` flips on (added on success below),
  // so it reports zero width. Measure the visible parent stage instead, otherwise
  // we deadlock: hidden mount -> width 0 -> bail -> never add has-3d -> stays hidden.
  const stage = mount.parentElement;
  const w = mount.clientWidth || (stage && stage.clientWidth) || 0;
  const h = mount.clientHeight || w;
  if (w < 60) {                       // Constellation tab not laid out yet
    if (S.tries++ < 60) setTimeout(() => build(roster), 200);
    return false;
  }

  try {
    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(42, w / h, 0.1, 100);
    camera.position.set(0, 5.4, 12);

    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(w, h);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    mount.appendChild(renderer.domElement);

    labelRenderer = new CSS2DRenderer();
    labelRenderer.setSize(w, h);
    Object.assign(labelRenderer.domElement.style, { position: 'absolute', top: '0', left: '0', pointerEvents: 'none' });
    mount.appendChild(labelRenderer.domElement);

    controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true; controls.dampingFactor = 0.06;
    controls.autoRotate = true; controls.autoRotateSpeed = 0.45;
    controls.enablePan = false;
    controls.minDistance = 7; controls.maxDistance = 20;
    controls.target.set(0, 0, 0);

    scene.add(new THREE.HemisphereLight(0xbfd4ff, 0x101018, 0.8));
    const sunLight = new THREE.PointLight(0xfff0d0, 3.4, 120, 1.1);
    scene.add(sunLight);  // at origin
    const fill = new THREE.DirectionalLight(0xffffff, 0.5);
    fill.position.set(3, 6, 8); scene.add(fill);

    // ---- Apex sun ----
    const sunTex = new THREE.TextureLoader().load('/static/planets/sun.jpg');
    sunTex.colorSpace = THREE.SRGBColorSpace;
    sunMesh = new THREE.Mesh(
      new THREE.SphereGeometry(1.5, 48, 48),
      new THREE.MeshBasicMaterial({ map: sunTex })
    );
    scene.add(sunMesh);
    scene.add(_glowSprite(0xffc56b, 7.5));
    const sunLabel = new CSS2DObject(Object.assign(document.createElement('div'), {
      className: 'cst3d-label cst3d-sun', textContent: 'APEX' }));
    sunLabel.position.set(0, 2.1, 0);
    sunMesh.add(sunLabel);

    raycaster = new THREE.Raycaster();
    pointer = new THREE.Vector2();

    // ---- orbital bands + planets ----
    const byPack = {};
    roster.forEach(p => (byPack[p.pack] = byPack[p.pack] || []).push(p));

    Object.entries(byPack).forEach(([pack, list]) => {
      const band = BAND[pack] || BAND.life;
      const grp = new THREE.Group();
      grp.rotation.x = band.incX; grp.rotation.z = band.incZ;
      scene.add(grp);

      // faint orbit ring lying in the band's local plane
      const ring = new THREE.Mesh(
        new THREE.RingGeometry(band.r - 0.015, band.r + 0.015, 96),
        new THREE.MeshBasicMaterial({ color: band.color, transparent: true, opacity: 0.28,
          side: THREE.DoubleSide, depthWrite: false })
      );
      ring.rotation.x = -Math.PI / 2;
      grp.add(ring);

      const m = list.length;
      list.forEach((p, k) => {
        const base = SIZE[(p.codename || '').toLowerCase()] || 0.4;
        const mesh = new THREE.Mesh(
          new THREE.SphereGeometry(base, 36, 36),
          new THREE.MeshStandardMaterial({
            map: _texFor(p.codename, band.color), roughness: 1, metalness: 0,
            emissive: new THREE.Color(band.color), emissiveIntensity: 0, transparent: true, opacity: 1,
          })
        );
        mesh.userData.key = p.key;
        if ((p.codename || '').toLowerCase() === 'saturn') {        // Saturn's ring
          const sr = new THREE.Mesh(
            new THREE.RingGeometry(base * 1.4, base * 2.1, 48),
            new THREE.MeshBasicMaterial({ color: 0xd9c98a, transparent: true, opacity: 0.55, side: THREE.DoubleSide })
          );
          sr.rotation.x = -Math.PI / 2.3; mesh.add(sr);
        }
        const pObj = {
          key: p.key, mesh, pack, color: band.color, base, label: null,
          angle: (k / m) * Math.PI * 2, spd: band.spd,
          st: 'idle', cur: { glow: 0, op: 1, sc: 1 }, tgt: { glow: 0, op: 1, sc: 1 },
        };
        const lab = _label(p, base); mesh.add(lab); pObj.label = lab;
        grp.add(mesh);
        planets.push(pObj); meshByKey.set(p.key, pObj); pickables.push(mesh);
        _place(pObj, band, 0);
      });
    });

    renderer.domElement.addEventListener('pointermove', _onMove);
    renderer.domElement.addEventListener('click', _onClick);
    window.addEventListener('resize', _resize);
    if (window.ResizeObserver) new ResizeObserver(_resize).observe(mount);

    S.built = true;
    document.querySelector('.cst-stage')?.classList.add('has-3d');
    _animate();
    console.log('[Cst3D] solar system live');
    return true;
  } catch (e) { return _fail(e.message); }
}

function _place(p, band, dt) {
  if (!convening) p.angle += p.spd * dt;
  p.mesh.position.set(band.r * Math.cos(p.angle), 0, band.r * Math.sin(p.angle));
}

function _ndc(ev) {
  const r = renderer.domElement.getBoundingClientRect();
  pointer.x = ((ev.clientX - r.left) / r.width) * 2 - 1;
  pointer.y = -((ev.clientY - r.top) / r.height) * 2 + 1;
}
function _hit(ev) {
  _ndc(ev); raycaster.setFromCamera(pointer, camera);
  const h = raycaster.intersectObjects(pickables, false);
  return h.length ? h[0].object.userData.key : null;
}
function _onMove(ev) {
  const key = _hit(ev);
  if (key !== hoverKey) {
    hoverKey = key;
    renderer.domElement.style.cursor = key ? 'pointer' : 'grab';
  }
}
function _onClick(ev) {
  const key = _hit(ev);
  if (key && window._cstOpenChat) window._cstOpenChat(key);
}

function _animate() {
  S.raf = requestAnimationFrame(_animate);
  const dt = Math.min(0.05, clock ? clock.getDelta() : 0.016);
  const t = (clock ||= new THREE.Clock()).elapsedTime;

  planets.forEach(p => {
    const band = BAND[p.pack] || BAND.life;
    _place(p, band, dt);
    p.mesh.rotation.y += dt * 0.25;

    // targets from state
    const hovered = p.key === hoverKey, selected = p.key === selectedKey;
    let glow = p.tgt.glow, sc = p.tgt.sc, op = p.tgt.op;
    if (p.st === 'thinking') glow = 0.5 + 0.4 * Math.abs(Math.sin(t * 3));   // pulse
    if (hovered || selected) { sc = Math.max(sc, 1.28); glow = Math.max(glow, 0.4); }
    p.cur.glow += (glow - p.cur.glow) * Math.min(1, dt * 8);
    p.cur.sc   += (sc   - p.cur.sc)   * Math.min(1, dt * 10);
    p.cur.op   += (op   - p.cur.op)   * Math.min(1, dt * 8);
    p.mesh.material.emissiveIntensity = p.cur.glow;
    p.mesh.material.opacity = p.cur.op;
    p.mesh.scale.setScalar(p.cur.sc);
    if (p.label?.el) p.label.el.classList.toggle('hot', hovered || selected || p.st !== 'idle');
  });

  if (sunMesh) sunMesh.rotation.y += dt * 0.04;
  controls?.update();
  renderer.render(scene, camera);
  labelRenderer.render(scene, camera);
}

function _resize() {
  if (!renderer || !mount) return;
  const w = mount.clientWidth, h = mount.clientHeight || w;
  if (w < 60) return;
  camera.aspect = w / h; camera.updateProjectionMatrix();
  renderer.setSize(w, h); labelRenderer.setSize(w, h);
}

// ---- state API mirrored from app.js ----
function setAll(state) {
  planets.forEach(p => {
    p.st = 'idle';
    p.tgt = { glow: 0, op: state === 'dim' ? 0.22 : 1, sc: 1 };
  });
}
function setStates(keys, state) {
  const set = new Set(keys || []);
  planets.forEach(p => {
    if (set.has(p.key)) { p.st = state; p.tgt = { glow: 0.6, op: 1, sc: 1.12 }; }
    else { p.st = 'idle'; p.tgt = { glow: 0, op: 0.18, sc: 1 }; }
  });
}
function setState(key, state) {
  const p = meshByKey.get(key); if (!p) return;
  p.st = state;
  if (state === 'done') p.tgt = { glow: 0.5, op: 1, sc: 1.1 };
}
function clearStates() {
  planets.forEach(p => { p.st = 'idle'; p.tgt = { glow: 0, op: 1, sc: 1 }; });
}
function setConvening(b) { convening = !!b; if (controls) controls.autoRotate = !b; }
function select(key) { selectedKey = key || null; }

window.Cst3D = { build, setAll, setStates, setState, clearStates, setConvening, select };
