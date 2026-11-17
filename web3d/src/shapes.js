// README §2: สร้าง geometry ของชิ้นส่วนในพิกัดสเปก (มม.) จาก box / cylinder / prism
import * as THREE from 'three';
import { CYLINDER_RADIAL_SEGMENTS } from './config.js';

function createBoxGeometry(part) {
  const [minX, minY, minZ] = part.min;
  const [maxX, maxY, maxZ] = part.max;
  const geometry = new THREE.BoxGeometry(maxX - minX, maxY - minY, maxZ - minZ);
  geometry.translate((minX + maxX) / 2, (minY + maxY) / 2, (minZ + maxZ) / 2);
  return geometry;
}

function createCylinderGeometry(part) {
  // CylinderGeometry ตั้งตามแกน Y อยู่แล้ว จึงหมุนเฉพาะเมื่อแกนเป็น x หรือ z
  const geometry = new THREE.CylinderGeometry(
    part.radius,
    part.radius,
    part.length,
    CYLINDER_RADIAL_SEGMENTS,
  );
  if (part.axis === 'x') geometry.rotateZ(Math.PI / 2);
  else if (part.axis === 'z') geometry.rotateX(Math.PI / 2);
  else if (part.axis !== 'y') throw new Error(`${part.id}: ไม่รู้จักแกนทรงกระบอก "${part.axis}"`);
  geometry.translate(...part.center);
  return geometry;
}

/**
 * ExtrudeGeometry ให้รูปใน (u, v) แล้วดันตาม +w ช่วง [0, depth]
 * ตารางนี้พาแกน (u, v, w) ไปยังแกนสเปกตาม README §2 โดยใช้การหมุนล้วน (det = +1)
 * เพื่อไม่ให้ face กลับด้าน:
 *   xz: u→X, v→Z, w→−Y  แล้วเลื่อนไปเริ่มที่ Y = to  (ถ้าใช้ w→+Y จะเป็นภาพสะท้อน det = −1)
 *   yz: u→Y, v→Z, w→+X  แล้วเลื่อนไปเริ่มที่ X = from
 *   xy: u→X, v→Y, w→+Z  แล้วเลื่อนไปเริ่มที่ Z = from
 */
const PRISM_PLANE_FRAMES = {
  xz: {
    uAxis: [1, 0, 0],
    vAxis: [0, 0, 1],
    wAxis: [0, -1, 0],
    origin: ([, to]) => [0, to, 0],
  },
  yz: {
    uAxis: [0, 1, 0],
    vAxis: [0, 0, 1],
    wAxis: [1, 0, 0],
    origin: ([from]) => [from, 0, 0],
  },
  xy: {
    uAxis: [1, 0, 0],
    vAxis: [0, 1, 0],
    wAxis: [0, 0, 1],
    origin: ([from]) => [0, 0, from],
  },
};

function createPrismGeometry(part) {
  const frame = PRISM_PLANE_FRAMES[part.plane];
  if (!frame) throw new Error(`${part.id}: ไม่รู้จักระนาบ prism "${part.plane}"`);

  const outline = new THREE.Shape(part.points.map(([u, v]) => new THREE.Vector2(u, v)));
  const [from, to] = part.extrude;
  const geometry = new THREE.ExtrudeGeometry(outline, { depth: to - from, bevelEnabled: false });

  const toSpecAxes = new THREE.Matrix4().makeBasis(
    new THREE.Vector3(...frame.uAxis),
    new THREE.Vector3(...frame.vAxis),
    new THREE.Vector3(...frame.wAxis),
  );
  toSpecAxes.setPosition(...frame.origin(part.extrude));
  geometry.applyMatrix4(toSpecAxes);
  return geometry;
}

const GEOMETRY_BUILDERS = {
  box: createBoxGeometry,
  cylinder: createCylinderGeometry,
  prism: createPrismGeometry,
};

/** geometry ของชิ้นส่วนในพิกัดสเปกสัมบูรณ์ (ท่าอ้างอิง ยังไม่รวม transform.rotate) */
export function createPartGeometry(part) {
  const build = GEOMETRY_BUILDERS[part.shape];
  if (!build) throw new Error(`${part.id}: ไม่รู้จัก shape "${part.shape}"`);
  return build(part);
}
