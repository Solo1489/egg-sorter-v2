// เทียบตำแหน่ง mesh ที่สร้างจริงกับค่าที่คำนวณตรงจากสเปก
// ฝั่ง "ค่าคาดหวัง" ใช้คณิตศาสตร์ของตัวเอง (array ธรรมดา + สูตร Rodrigues + สูตรปิดของ README §1)
// ไม่ใช้ geometry, quaternion หรือ scene graph เพื่อให้เป็นการตรวจที่อิสระจากโค้ดสร้างโมเดล
import * as THREE from 'three';
import { MM_TO_M, VERIFY_TOLERANCE_MM } from './config.js';
import { specPointToWorld } from './coords.js';

const AXIS_INDEX = { x: 0, y: 1, z: 2 };

/** README §2: plane → [แกนของ u, แกนของ v, แกนที่ดัน] */
const PRISM_AXES = { xz: [0, 2, 1], yz: [1, 2, 0], xy: [0, 1, 2] };

function boxCorners(min, max) {
  const corners = [];
  for (const x of [min[0], max[0]]) {
    for (const y of [min[1], max[1]]) {
      for (const z of [min[2], max[2]]) corners.push([x, y, z]);
    }
  }
  return corners;
}

/** จุดมุมของชิ้นส่วนในท่าอ้างอิง (ก่อน transform.rotate) */
function referencePoints(part) {
  if (part.shape === 'box') return boxCorners(part.min, part.max);

  if (part.shape === 'cylinder') {
    const axisIndex = AXIS_INDEX[part.axis];
    const halfExtent = [part.radius, part.radius, part.radius];
    halfExtent[axisIndex] = part.length / 2;
    return boxCorners(
      part.center.map((value, i) => value - halfExtent[i]),
      part.center.map((value, i) => value + halfExtent[i]),
    );
  }

  if (part.shape === 'prism') {
    const [uIndex, vIndex, wIndex] = PRISM_AXES[part.plane];
    const points = [];
    for (const [u, v] of part.points) {
      for (const w of part.extrude) {
        const point = [0, 0, 0];
        point[uIndex] = u;
        point[vIndex] = v;
        point[wIndex] = w;
        points.push(point);
      }
    }
    return points;
  }
  throw new Error(`${part.id}: ไม่รู้จัก shape "${part.shape}"`);
}

const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const cross = (a, b) => [
  a[1] * b[2] - a[2] * b[1],
  a[2] * b[0] - a[0] * b[2],
  a[0] * b[1] - a[1] * b[0],
];

/** สูตร Rodrigues: หมุน point รอบแกน axis (หนึ่งหน่วย) ที่ผ่าน pivot ตามกฎมือขวา */
function rotateAboutAxis(point, pivot, axis, degrees) {
  const radians = (degrees * Math.PI) / 180;
  const cos = Math.cos(radians);
  const sin = Math.sin(radians);
  const relative = point.map((value, i) => value - pivot[i]);
  const axisCross = cross(axis, relative);
  const axisDot = dot(axis, relative);
  return relative.map(
    (value, i) => pivot[i] + value * cos + axisCross[i] * sin + axis[i] * axisDot * (1 - cos),
  );
}

/** ทรงกระบอกที่หมุนรอบแกนของตัวเอง bbox ไม่เปลี่ยน กรณีอื่นใช้มุมกล่องแทนไม่ได้ */
function isCylinderRotatedOffAxis(part, pivot, axis) {
  if (part.shape !== 'cylinder') return false;
  const axisIndex = AXIS_INDEX[part.axis];
  const isParallel = Math.abs(Math.abs(axis[axisIndex]) - 1) < 1e-9;
  const isOnAxisLine = part.center.every(
    (value, i) => i === axisIndex || Math.abs(value - pivot[i]) < 1e-9,
  );
  return !(isParallel && isOnAxisLine);
}

/**
 * จุดมุมที่คาดหวังในพิกัดสเปก เมื่อกลุ่มของชิ้นนี้อยู่ที่ค่า motionValue
 * @returns {number[][] | null} null = ตรวจด้วยวิธีนี้ไม่ได้
 */
function expectedSpecPoints(part, groupSpec, motionValue) {
  let points = referencePoints(part);

  const rotate = part.transform?.rotate;
  if (rotate) {
    if (isCylinderRotatedOffAxis(part, rotate.pivot, rotate.axis)) return null;
    if (part.shape !== 'cylinder') {
      points = points.map((point) => rotateAboutAxis(point, rotate.pivot, rotate.axis, rotate.deg));
    }
  }

  if (!groupSpec || motionValue === 0) return points;
  const { motion } = groupSpec;

  if (motion.type === 'translate') {
    return points.map((point) => point.map((value, i) => value + motion.axis[i] * motionValue));
  }

  const pivot = motion.type === 'spin' ? motion.pivots[part.id] : motion.pivot;
  if (part.shape === 'cylinder') {
    return isCylinderRotatedOffAxis(part, pivot, motion.axis) ? null : points;
  }
  return points.map((point) => rotateAboutAxis(point, pivot, motion.axis, motionValue));
}

function worldBoxOfMesh(mesh) {
  const box = new THREE.Box3();
  const vertex = new THREE.Vector3();
  const positions = mesh.geometry.attributes.position;
  for (let i = 0; i < positions.count; i += 1) {
    box.expandByPoint(vertex.fromBufferAttribute(positions, i).applyMatrix4(mesh.matrixWorld));
  }
  return box;
}

function boxErrorMm(actual, expected) {
  let maxDifference = 0;
  for (const corner of ['min', 'max']) {
    for (const component of ['x', 'y', 'z']) {
      maxDifference = Math.max(
        maxDifference,
        Math.abs(actual[corner][component] - expected[corner][component]),
      );
    }
  }
  return maxDifference / MM_TO_M;
}

/**
 * ตรวจทุกชิ้นในท่าอ้างอิง (ทุกกลุ่ม = 0) และตรวจทุกกลุ่มในทุกสถานะ
 * หมายเหตุ: จบแล้วทุกกลุ่มจะกลับไปที่ motion.default
 */
export function verifyMachine(machine, { toleranceMm = VERIFY_TOLERANCE_MM } = {}) {
  const { root, index, partNodes, motionGroups, controller } = machine;
  const rows = [];

  function checkPart(partId, pose, groupSpec, motionValue) {
    const { part, mesh } = partNodes.get(partId);
    const expectedPoints = expectedSpecPoints(part, groupSpec, motionValue);
    if (!expectedPoints) {
      rows.push({ partId, module: part.module, pose, errorMm: null, ok: true, skipped: true });
      return;
    }
    const expectedBox = new THREE.Box3().setFromPoints(expectedPoints.map(specPointToWorld));
    const errorMm = boxErrorMm(worldBoxOfMesh(mesh), expectedBox);
    rows.push({
      partId,
      module: part.module,
      pose,
      errorMm,
      ok: errorMm <= toleranceMm,
      skipped: false,
    });
  }

  // 1) ท่าอ้างอิง: ทุกกลุ่มอยู่ที่ค่า 0
  for (const groupId of motionGroups.keys()) controller.setValue(groupId, 0);
  root.updateMatrixWorld(true);
  for (const partId of partNodes.keys()) {
    const groupId = index.groupIdOfPart.get(partId);
    const groupSpec = motionGroups.has(groupId) ? index.groupsById.get(groupId) : null;
    checkPart(partId, 'reference', groupSpec, 0);
  }

  // 2) ทุกสถานะของทุกกลุ่ม (spin ใช้ 90° เป็นตัวแทน เพราะสถานะของมันคือความเร็ว ไม่ใช่ท่า)
  for (const [groupId, { spec, motion }] of motionGroups) {
    const poses =
      motion.type === 'spin'
        ? [['angle 90°', 90]]
        : Object.entries(motion.states).map(([stateName, value]) => [stateName, value]);
    for (const [poseName, value] of poses) {
      controller.setValue(groupId, value);
      root.updateMatrixWorld(true);
      for (const partId of spec.parts) checkPart(partId, `${groupId}=${poseName}`, spec, value);
    }
    controller.setValue(groupId, 0);
  }

  controller.setAllToDefault({ immediate: true });
  root.updateMatrixWorld(true);

  const failures = rows.filter((row) => !row.ok);
  const skipped = rows.filter((row) => row.skipped);
  const maxErrorMm = rows.reduce((max, row) => Math.max(max, row.errorMm ?? 0), 0);
  return { ok: failures.length === 0, rows, failures, skipped, maxErrorMm, toleranceMm };
}

/** สรุปผลรายโมดูล สำหรับ console.table */
export function summarizeByModule(report, moduleOrder) {
  return moduleOrder
    .map((module) => {
      const rows = report.rows.filter((row) => row.module === module);
      if (rows.length === 0) return null;
      return {
        module,
        checks: rows.length,
        failed: rows.filter((row) => !row.ok).length,
        skipped: rows.filter((row) => row.skipped).length,
        maxErrorMm: Number(rows.reduce((max, row) => Math.max(max, row.errorMm ?? 0), 0).toFixed(5)),
      };
    })
    .filter(Boolean);
}
