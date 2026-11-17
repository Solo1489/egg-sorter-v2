// เส้นวัดระยะในฉาก (พิกัดสเปก มม. ใต้ machine.root)
//   ชุดหลัก: ยาว × ลึก × สูง ของเครื่องจาก meta.bounding_box
//   ชุดละเอียด: ช่วงตามแนว X ของแต่ละโมดูล (จากผนังของโมดูล) และความกว้างชุดราง (กลุ่ม insert.*)
// ทุกค่ามาจาก parts.json / mesh ที่สร้างจากสเปก ไม่มีขนาดชิ้นส่วนในไฟล์นี้
import * as THREE from 'three';
import { createLabel } from './labels.js';

/** ระยะห่างแต่ละแถวของเส้นวัดจากตัวเครื่อง เป็นสัดส่วนของความยาวเครื่อง */
const ROW_OFFSET_FACTOR = 0.045;
/** ขนาดขีดเฉียงที่ปลายเส้นวัด และส่วนที่เส้นต่อยื่นเลยเส้นวัด เทียบกับระยะห่างแถว */
const TICK_FACTOR = 0.22;
const OVERSHOOT_FACTOR = 0.15;
/** ยกเส้นที่วางบนพื้นโต๊ะขึ้นเล็กน้อย (มม.) ไม่ให้กระพริบกับพื้น */
const TABLE_LIFT_MM = 0.5;
const LINE_COLOR = 0x1d3557;
/** แถวของเส้นวัดด้านหน้าเครื่อง (นับจากขอบหน้าสุดออกไป) */
const ROW = { inserts: 1, modules: 2, overall: 3 };
/** ชื่อสั้นของโมดูลบนป้ายเส้นวัด (ไม่มีในรายการ ใช้ชื่อโมดูลตรงๆ) */
const MODULE_SHORT_NAMES = { input: 'ถาดป้อน', ai: 'ตู้ AI', scale: 'กล่องชั่ง' };

const lineMaterial = new THREE.LineBasicMaterial({
  color: LINE_COLOR,
  depthTest: false, // มองเห็นทะลุผนัง
  transparent: true,
  opacity: 0.9,
});

const formatMm = (value) => `${value.toFixed(1)} มม.`;

/**
 * กล่องขอบเขตในพิกัดสเปกของชิ้นส่วนที่สร้างแล้ว (ท่าปัจจุบันของกลุ่ม รวม transform.rotate)
 * @returns {THREE.Box3 | null}
 */
function specBoundsOf(machine, partIds) {
  machine.root.updateMatrixWorld(true);
  const rootInverse = machine.root.matrixWorld.clone().invert();
  const toRoot = new THREE.Matrix4();
  const partBox = new THREE.Box3();
  const bounds = new THREE.Box3();
  for (const partId of partIds) {
    const mesh = machine.partNodes.get(partId)?.mesh;
    if (!mesh) continue;
    toRoot.multiplyMatrices(rootInverse, mesh.matrixWorld);
    bounds.union(partBox.copy(mesh.geometry.boundingBox).applyMatrix4(toRoot));
  }
  return bounds.isEmpty() ? null : bounds;
}

/**
 * เส้นวัดหนึ่งเส้น: วัดจาก start ถึง end (จุดบนตัวเครื่อง) วางห่างออกไปตามเวกเตอร์ offset
 * เพิ่มจุดของเส้นต่อ เส้นวัด และขีดเฉียงปลายเส้นลงใน vertices ; คืนป้ายตัวเลขที่จุดกึ่งกลาง
 */
function addDimension(vertices, { start, end, offset, text }) {
  const along = new THREE.Vector3().subVectors(end, start).normalize();
  const outward = offset.clone().normalize();
  const rowGap = offset.length();
  const overshoot = outward.clone().multiplyScalar(rowGap * OVERSHOOT_FACTOR);
  const tick = along.clone().add(outward).normalize().multiplyScalar((rowGap * TICK_FACTOR) / 2);

  const lineStart = start.clone().add(offset);
  const lineEnd = end.clone().add(offset);
  const segments = [
    [start, lineStart.clone().add(overshoot)], // เส้นต่อ
    [end, lineEnd.clone().add(overshoot)],
    [lineStart, lineEnd], // เส้นวัด
    [lineStart.clone().sub(tick), lineStart.clone().add(tick)], // ขีดเฉียงปลายเส้น
    [lineEnd.clone().sub(tick), lineEnd.clone().add(tick)],
  ];
  for (const [from, to] of segments) vertices.push(from.x, from.y, from.z, to.x, to.y, to.z);

  const label = createLabel(text, 'scene-label--dim');
  label.position.copy(lineStart).lerp(lineEnd, 0.5);
  return label;
}

/** กลุ่มของเส้นวัดหลายเส้น: LineSegments ชุดเดียว + ป้ายตัวเลข */
function createDimensionSet(name, dimensions) {
  const set = new THREE.Group();
  set.name = name;
  const vertices = [];
  for (const dimension of dimensions) set.add(addDimension(vertices, dimension));
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
  const lines = new THREE.LineSegments(geometry, lineMaterial);
  lines.renderOrder = 999;
  set.add(lines);
  return set;
}

/** ขนาดรวมของเครื่อง: ยาว (หน้า แถวนอกสุด) ลึก (ขวา บนโต๊ะ) สูง (มุมหน้าขวา) */
function overallDimensions({ min, max }, rowGap) {
  const z0 = min[2] + TABLE_LIFT_MM;
  const frontRight = new THREE.Vector3(max[0], min[1], z0);
  return [
    {
      start: new THREE.Vector3(min[0], min[1], z0),
      end: frontRight,
      offset: new THREE.Vector3(0, -rowGap * ROW.overall, 0),
      text: `ยาว ${formatMm(max[0] - min[0])}`,
    },
    {
      start: frontRight,
      end: new THREE.Vector3(max[0], max[1], z0),
      offset: new THREE.Vector3(rowGap, 0, 0),
      text: `ลึก ${formatMm(max[1] - min[1])}`,
    },
    {
      start: new THREE.Vector3(max[0], min[1], min[2]),
      end: new THREE.Vector3(max[0], min[1], max[2]),
      offset: new THREE.Vector3(rowGap, 0, 0),
      text: `สูง ${formatMm(max[2] - min[2])}`,
    },
  ];
}

/** ช่วงตามแนว X ด้านหน้าเครื่อง (บนโต๊ะ) */
function spanAlongX(name, x0, x1, frontY, z0, rowGap, row) {
  return {
    start: new THREE.Vector3(x0, frontY, z0),
    end: new THREE.Vector3(x1, frontY, z0),
    offset: new THREE.Vector3(0, -rowGap * row, 0),
    text: `${name} ${formatMm(x1 - x0)}`,
  };
}

/** ช่วง X ของแต่ละโมดูลที่มีผนัง (ถาดป้อน / ตู้ AI / กล่องชั่ง) และความกว้างของชุดรางแต่ละชุด */
function detailDimensions(machine, partsSpec, { min }, rowGap) {
  const z0 = min[2] + TABLE_LIFT_MM;
  const frontY = min[1];
  const dimensions = [];

  for (const module of machine.modules) {
    const wallIds = [...machine.partNodes.values()]
      .filter(({ mesh }) => mesh.userData.module === module && mesh.userData.isWall)
      .map(({ part }) => part.id);
    const bounds = specBoundsOf(machine, wallIds);
    if (!bounds) continue;
    const name = MODULE_SHORT_NAMES[module] ?? module;
    dimensions.push(spanAlongX(name, bounds.min.x, bounds.max.x, frontY, z0, rowGap, ROW.modules));
  }

  for (const group of partsSpec.groups.filter(({ id }) => id.startsWith('insert.'))) {
    const bounds = specBoundsOf(machine, group.parts);
    if (!bounds) continue;
    dimensions.push(spanAlongX(group.name, bounds.min.x, bounds.max.x, frontY, z0, rowGap, ROW.inserts));
  }
  return dimensions;
}

/**
 * สร้างเส้นวัดใต้ machine.root ; เรียกหลัง buildMachine (กลุ่มอยู่ท่า default) ก่อนตั้งสถานะจาก URL
 * @returns {{ setOverallVisible(boolean): void, setDetailVisible(boolean): void }}
 */
export function createDimensionLayer(machine, partsSpec) {
  const box = partsSpec.meta.bounding_box;
  const rowGap = (box.max[0] - box.min[0]) * ROW_OFFSET_FACTOR;

  const overall = createDimensionSet('dimensions:overall', overallDimensions(box, rowGap));
  const detail = createDimensionSet('dimensions:detail', detailDimensions(machine, partsSpec, box, rowGap));
  machine.root.add(overall, detail);

  return {
    setOverallVisible: (isVisible) => {
      overall.visible = isVisible;
    },
    setDetailVisible: (isVisible) => {
      detail.visible = isVisible;
    },
  };
}
