// ฉาก: renderer, กล้อง, OrbitControls, แสง Hemisphere + Directional (มีเงา), พื้นโต๊ะ
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { createCameraPresets } from './cameraPresets.js';
import { specDirectionToWorld } from './coords.js';

const BACKGROUND_COLOR = 0xe9edf1;
const TABLE_COLOR = 0xcbb89a;
const CAMERA_FOV_DEGREES = 35;
/** พื้นโต๊ะกว้างเป็นกี่เท่าของเส้นผ่านศูนย์กลางเครื่อง */
const TABLE_SIZE_FACTOR = 2.5;
/** ทิศจากเครื่องไปหาดวงไฟหลัก ในพิกัดสเปก (หน้า-ซ้าย-บน) */
const KEY_LIGHT_DIRECTION_SPEC = [-0.45, -0.6, 1];
const SHADOW_MAP_SIZE = 2048;

function createTable(machineSphere) {
  const size = machineSphere.radius * 2 * TABLE_SIZE_FACTOR;
  const table = new THREE.Mesh(
    new THREE.PlaneGeometry(size, size),
    new THREE.MeshStandardMaterial({
      color: TABLE_COLOR,
      roughness: 0.9,
      // กันกระพริบกับผิวล่างของแผ่นฐานที่อยู่ระนาบเดียวกัน (Z = 0)
      polygonOffset: true,
      polygonOffsetFactor: 1,
      polygonOffsetUnits: 1,
    }),
  );
  table.name = 'table';
  table.rotation.x = -Math.PI / 2;
  table.position.set(machineSphere.center.x, 0, machineSphere.center.z);
  table.receiveShadow = true;
  return table;
}

function createLights(machineSphere) {
  const hemisphere = new THREE.HemisphereLight(0xffffff, 0x8d939c, 1.3);

  const keyLight = new THREE.DirectionalLight(0xffffff, 2.2);
  const lightDistance = machineSphere.radius * 3;
  keyLight.position
    .copy(machineSphere.center)
    .addScaledVector(specDirectionToWorld(KEY_LIGHT_DIRECTION_SPEC), lightDistance);
  keyLight.target.position.copy(machineSphere.center);
  keyLight.castShadow = true;
  keyLight.shadow.mapSize.set(SHADOW_MAP_SIZE, SHADOW_MAP_SIZE);
  keyLight.shadow.bias = -0.0005;

  // กล้องเงาครอบทรงกลมของเครื่องพอดี
  const shadowExtent = machineSphere.radius * 1.3;
  const shadowCamera = keyLight.shadow.camera;
  shadowCamera.left = -shadowExtent;
  shadowCamera.right = shadowExtent;
  shadowCamera.top = shadowExtent;
  shadowCamera.bottom = -shadowExtent;
  shadowCamera.near = lightDistance - shadowExtent * 1.5;
  shadowCamera.far = lightDistance + shadowExtent * 1.5;
  shadowCamera.updateProjectionMatrix();

  return [hemisphere, keyLight, keyLight.target];
}

/**
 * @param {HTMLElement} container
 * @param {THREE.Box3} machineWorldBox กรอบรวมของเครื่องในพิกัด Three.js
 */
export function createSceneContext(container, machineWorldBox) {
  const machineSphere = machineWorldBox.getBoundingSphere(new THREE.Sphere());

  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFShadowMap;
  container.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(BACKGROUND_COLOR);
  scene.add(createTable(machineSphere), ...createLights(machineSphere));

  const camera = new THREE.PerspectiveCamera(
    CAMERA_FOV_DEGREES,
    1,
    machineSphere.radius / 100,
    machineSphere.radius * 100,
  );
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  // ล้อเมาส์ซูมเข้าหาจุดที่เมาส์ชี้ แทนที่จะซูมเข้าหากึ่งกลางเครื่อง
  controls.zoomToCursor = true;
  controls.minDistance = machineSphere.radius / 50;
  controls.maxDistance = machineSphere.radius * 20;

  const getView = createCameraPresets(machineWorldBox);
  function setView(viewName) {
    const { position, target } = getView(viewName, camera);
    camera.position.copy(position);
    controls.target.copy(target);
    controls.update();
  }

  /** เลื่อนจุดมองไปที่ worldPoint แล้วขยับกล้องเข้าใกล้ zoomFactor เท่า โดยคงทิศมองเดิม */
  function focusOn(worldPoint, zoomFactor = 1) {
    const offset = camera.position.clone().sub(controls.target).divideScalar(zoomFactor);
    controls.target.copy(worldPoint);
    camera.position.copy(worldPoint).add(offset);
    controls.update();
  }

  /**
   * ดับเบิลคลิกที่ชิ้นส่วนเพื่อย้ายจุดหมุนของกล้องไปที่จุดนั้น (ระยะกล้องเท่าเดิม)
   * @param {THREE.Object3D} pickRoot ต้นไม้ของชิ้นส่วนที่คลิกเลือกได้
   */
  function enableDoubleClickFocus(pickRoot) {
    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    renderer.domElement.addEventListener('dblclick', (event) => {
      const bounds = renderer.domElement.getBoundingClientRect();
      pointer.set(
        ((event.clientX - bounds.left) / bounds.width) * 2 - 1,
        -((event.clientY - bounds.top) / bounds.height) * 2 + 1,
      );
      raycaster.setFromCamera(pointer, camera);
      // นับเฉพาะชิ้นส่วนที่มองเห็นอยู่ (ไม่รวมเส้นขอบและลูกศรแกน)
      const hit = raycaster
        .intersectObject(pickRoot, true)
        .find(({ object }) => object.isMesh && object.visible && object.userData.partId);
      if (hit) focusOn(hit.point);
    });
  }

  function resize() {
    const { clientWidth, clientHeight } = container;
    renderer.setSize(clientWidth, clientHeight);
    camera.aspect = clientWidth / clientHeight;
    camera.updateProjectionMatrix();
  }
  window.addEventListener('resize', resize);
  resize();

  function render() {
    controls.update();
    renderer.render(scene, camera);
  }

  return {
    scene,
    camera,
    controls,
    renderer,
    setView,
    focusOn,
    enableDoubleClickFocus,
    render,
    machineSphere,
  };
}
