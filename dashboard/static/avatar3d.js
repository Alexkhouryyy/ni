// Apex 3D avatar — a Ready Player Me human head rendered with three.js that
// lip-syncs to Apex's real voice. Fully local & free: the GLB is loaded from
// Ready Player Me's CDN, all rendering + lip-sync runs in the browser.
//
// Bridges to the classic app.js via window globals it writes each frame:
//   window.__apexState       'idle' | 'thinking' | 'speaking'
//   window.__apexMouth       0..1 target mouth openness (from audio RMS)
//   window.__apexAudioActive bool — true while real TTS audio is analysed
//
// app.js calls window.ApexAvatar.start() when the Vision tab opens. On any
// failure it sets ApexAvatar.failed = true so app.js can fall back to the 2D
// canvas face.

import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

// A few public Ready Player Me avatars (requested with ARKit + Oculus viseme
// morph targets so we can drive the mouth and blinks). Tried in order.
const AVATARS = [
  'https://models.readyplayer.me/64bfa15f0e72c63d7c3934a6.glb?morphTargets=ARKit,Oculus%20Visemes&textureAtlas=1024&lod=1',
  'https://models.readyplayer.me/6460b7b0b9b6f3f0b6b0f0a0.glb?morphTargets=ARKit,Oculus%20Visemes&textureAtlas=1024&lod=1',
];

const State = { renderer: null, started: false };

window.ApexAvatar = {
  ready: false,
  failed: false,
  start() { _start(); },
};

function _fail(msg) {
  console.warn('[ApexAvatar] 3D init failed:', msg);
  window.ApexAvatar.failed = true;
}

function _start() {
  if (State.started) return;
  const mount = document.getElementById('apex-avatar-3d');
  if (!mount) return;
  // Container must have a layout size (tab visible) before we build the renderer.
  const size = Math.min(mount.clientWidth || 320, 360) || 320;
  if (size < 40) { setTimeout(_start, 150); return; }
  State.started = true;

  let scene, camera, renderer, clock, headBone, root;
  const morphTargets = {};       // name -> [{ mesh, idx }]
  const cur = { mouth: 0, blink: 0 };
  let nextBlink = 1.5 + Math.random() * 3;

  try {
    scene = new THREE.Scene();

    camera = new THREE.PerspectiveCamera(26, 1, 0.1, 100);
    camera.position.set(0, 1.62, 0.62);

    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(size, size);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    State.renderer = renderer;
    mount.appendChild(renderer.domElement);

    // Lighting — soft key + cyan/violet rim to match the dashboard theme.
    scene.add(new THREE.HemisphereLight(0xffffff, 0x303048, 1.1));
    const key = new THREE.DirectionalLight(0xffffff, 1.6);
    key.position.set(0.5, 2.2, 1.4);
    scene.add(key);
    const rimC = new THREE.DirectionalLight(0x5fd8ff, 1.3);
    rimC.position.set(-1.6, 1.6, 0.4);
    scene.add(rimC);
    const rimV = new THREE.DirectionalLight(0xa078ff, 0.7);
    rimV.position.set(1.6, 1.2, -0.6);
    scene.add(rimV);

    clock = new THREE.Clock();
  } catch (e) { return _fail(e.message); }

  const loader = new GLTFLoader();

  function tryLoad(i) {
    if (i >= AVATARS.length) return _fail('all avatar URLs failed');
    loader.load(
      AVATARS[i],
      (gltf) => {
        try {
          root = gltf.scene;
          scene.add(root);

          // Collect morph-target handles and locate the head bone.
          root.traverse((o) => {
            if (o.isMesh && o.morphTargetDictionary) {
              o.frustumCulled = false;
              for (const name in o.morphTargetDictionary) {
                (morphTargets[name] ||= []).push({ mesh: o, idx: o.morphTargetDictionary[name] });
              }
            }
            if (o.isBone && /head/i.test(o.name) && !/topend|end/i.test(o.name)) {
              headBone = o;
            }
          });

          // Frame the camera on the head.
          const target = new THREE.Vector3(0, 1.62, 0);
          if (headBone) headBone.getWorldPosition(target);
          camera.position.set(target.x, target.y + 0.03, target.z + 0.6);
          camera.lookAt(target.x, target.y - 0.02, target.z);

          const loadingEl = document.getElementById('apex-avatar-loading');
          if (loadingEl) loadingEl.style.display = 'none';

          window.ApexAvatar.ready = true;
          animate();
        } catch (e) { _fail(e.message); }
      },
      undefined,
      () => tryLoad(i + 1),   // network/parse error → next URL
    );
  }
  tryLoad(0);

  function setMorph(name, value) {
    const list = morphTargets[name];
    if (!list) return;
    for (const { mesh, idx } of list) mesh.morphTargetInfluences[idx] = value;
  }

  function animate() {
    requestAnimationFrame(animate);
    const dt = Math.min(0.05, clock.getDelta());
    const t = clock.elapsedTime;
    const st = window.__apexState || 'idle';

    // ----- mouth target -----
    let mouthTarget;
    if (st === 'speaking') {
      mouthTarget = window.__apexAudioActive
        ? (window.__apexMouth || 0)
        : 0.25 + 0.4 * Math.abs(Math.sin(t * 9)) * (0.5 + 0.5 * Math.sin(t * 3.3));
    } else {
      mouthTarget = 0.02; // closed / faint breathing
    }
    cur.mouth += (mouthTarget - cur.mouth) * Math.min(1, dt * 20);

    // ----- blink -----
    if (t > nextBlink && cur.blink === 0) cur.blink = 0.0001;
    if (cur.blink > 0) {
      cur.blink += dt * 9;
      if (cur.blink >= 2) { cur.blink = 0; nextBlink = t + 2 + Math.random() * 4; }
    }
    const blinkV = cur.blink === 0 ? 0 : (cur.blink > 1 ? 2 - cur.blink : cur.blink);

    // ----- apply morphs -----
    const m = cur.mouth;
    setMorph('jawOpen', Math.min(0.75, m * 0.85));
    setMorph('mouthOpen', Math.min(0.6, m * 0.7));
    setMorph('viseme_aa', Math.min(0.9, m));
    setMorph('viseme_O', Math.min(0.5, m * 0.5));
    setMorph('mouthSmile', st === 'speaking' ? 0.12 : 0.18);
    setMorph('eyeBlinkLeft', blinkV);
    setMorph('eyeBlinkRight', blinkV);
    // subtle brow lift while speaking
    setMorph('browInnerUp', st === 'speaking' ? 0.15 * m : st === 'thinking' ? 0.05 : 0);

    // ----- head motion -----
    if (headBone) {
      const baseY = headBone.userData._baseRotY ??= headBone.rotation.y;
      const baseX = headBone.userData._baseRotX ??= headBone.rotation.x;
      if (st === 'thinking') {
        headBone.rotation.y = baseY + 0.18 * Math.sin(t * 1.3);
        headBone.rotation.x = baseX + 0.06 * Math.cos(t * 0.9) - 0.04;
      } else {
        headBone.rotation.y = baseY + 0.05 * Math.sin(t * 0.6);
        headBone.rotation.x = baseX + 0.025 * Math.sin(t * 0.45);
      }
    }
    // gentle breathing sway of the whole avatar
    if (root) root.position.y = 0.004 * Math.sin(t * 1.1);

    renderer.render(scene, camera);
  }
}
