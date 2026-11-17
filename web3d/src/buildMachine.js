// สร้างโมเดลเครื่องจาก parts.json ทีละโมดูล (ไม่ขึ้นกับ DOM ใช้ได้ทั้งเบราว์เซอร์และ Node)
import * as THREE from 'three';
import { WALL_ID_PATTERN } from './config.js';
import { createSpecRoot } from './coords.js';
import { attachAtSpecOrigin, createMotionController, createMotionGroups } from './groups.js';
import { createMaterialLibrary } from './materials.js';
import { createPartGeometry } from './shapes.js';
import { createSpecIndex } from './specIndex.js';

const EDGE_THRESHOLD_DEGREES = 30;
const SPEC_ORIGIN = new THREE.Vector3(0, 0, 0);

const edgeMaterial = new THREE.LineBasicMaterial({
  color: 0x2b3440,
  transparent: true,
  opacity: 0.35,
});

/**
 * สร้าง node ของชิ้นส่วนหนึ่งชิ้น
 * geometry ถูกย้ายให้จุดกึ่งกลางอยู่ที่ origin ของ mesh เพื่อให้การเรียงชิ้นโปร่งใสถูกต้อง
 * origin คือจุดในพิกัดสเปกที่ node นี้ต้องไปวาง
 */
function createPartNode(part, materials) {
  const geometry = createPartGeometry(part);
  geometry.computeBoundingBox();
  const center = geometry.boundingBox.getCenter(new THREE.Vector3());
  geometry.translate(-center.x, -center.y, -center.z);

  const mesh = new THREE.Mesh(geometry, materials.get(part.material));
  mesh.name = part.id;
  mesh.castShadow = materials.castsShadow(part.material);
  mesh.receiveShadow = true;
  mesh.userData = {
    partId: part.id,
    module: part.module,
    isWall: WALL_ID_PATTERN.test(part.id),
  };

  const edges = new THREE.LineSegments(
    new THREE.EdgesGeometry(geometry, EDGE_THRESHOLD_DEGREES),
    edgeMaterial,
  );
  edges.name = `${part.id}:edges`;
  edges.userData.isEdgeOutline = true;
  mesh.add(edges);

  const rotate = part.transform?.rotate;
  if (!rotate) return { part, mesh, node: mesh, origin: center };

  // README §2: ชิ้นที่มี transform.rotate หมุนรอบ pivot ของตัวเองตามกฎมือขวา
  const pivot = new THREE.Vector3(...rotate.pivot);
  const wrapper = new THREE.Group();
  wrapper.name = `${part.id}:transform`;
  wrapper.quaternion.setFromAxisAngle(
    new THREE.Vector3(...rotate.axis).normalize(),
    THREE.MathUtils.degToRad(rotate.deg),
  );
  attachAtSpecOrigin(wrapper, pivot, mesh, center);
  return { part, mesh, node: wrapper, origin: pivot };
}

/**
 * @param {object} partsSpec เนื้อหา parts.json
 * @param {{modules: string[]}} options โมดูลที่จะสร้าง
 */
export function buildMachine(partsSpec, { modules }) {
  const index = createSpecIndex(partsSpec);
  const builtModules = new Set(modules);
  const root = createSpecRoot();
  const materials = createMaterialLibrary(partsSpec.materials);

  const partNodes = new Map();
  for (const part of partsSpec.parts) {
    if (builtModules.has(part.module)) partNodes.set(part.id, createPartNode(part, materials));
  }

  const motionGroups = createMotionGroups(partsSpec.groups, partNodes, root);

  // ชิ้นที่ไม่ได้อยู่ในกลุ่มที่สร้างแล้ว วางใต้ root ตรงๆ
  for (const [partId, { node, origin }] of partNodes) {
    const groupId = index.groupIdOfPart.get(partId);
    if (groupId && motionGroups.has(groupId)) continue;
    attachAtSpecOrigin(root, SPEC_ORIGIN, node, origin);
  }

  const controller = createMotionController(motionGroups, index.followerIdsOf);
  controller.setAllToDefault({ immediate: true });

  return { root, index, materials, partNodes, motionGroups, controller, modules: [...modules] };
}
