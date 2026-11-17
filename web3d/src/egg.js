// ไข่ทรงรี (README §4): รัศมีจาก parts.json → meta.egg แกนยาวของตัวไข่คือแกน Y ของ mesh
import * as THREE from 'three';

const WIDTH_SEGMENTS = 40;
const HEIGHT_SEGMENTS = 24;
const Z_AXIS = new THREE.Vector3(0, 0, 1);
const BODY_LONG_AXIS = new THREE.Vector3(0, 1, 0);

/** ท่าพื้นฐานตาม long_axis: y = แกนยาวขนาน Y (ไม่หมุน), x = หมุน 90° รอบ Z ให้แกนยาวขนาน X */
const BASE_ORIENTATION = {
  y: new THREE.Quaternion(),
  x: new THREE.Quaternion().setFromAxisAngle(Z_AXIS, Math.PI / 2),
};

/**
 * ชั้นของไข่ทั้งหมดในฉาก (อยู่ใต้ root จึงใช้พิกัดสเปก มม.)
 * @param {THREE.Object3D} root
 * @param {object} materials ไลบรารีวัสดุจาก materials.js
 * @param {object} eggSpec parts.json → meta.egg
 */
export function createEggLayer(root, materials, eggSpec) {
  const [radiusShort, radiusLong] = eggSpec.radii_long_axis_y;
  const geometry = new THREE.SphereGeometry(1, WIDTH_SEGMENTS, HEIGHT_SEGMENTS);
  geometry.scale(radiusShort, radiusLong, radiusShort);
  const material = materials.get(eggSpec.material);

  const layer = new THREE.Group();
  layer.name = 'eggs';
  root.add(layer);
  const meshes = [];

  const baseQuaternion = new THREE.Quaternion();
  const rollQuaternion = new THREE.Quaternion();
  const spinQuaternion = new THREE.Quaternion();
  const spinAxis = new THREE.Vector3();

  function setCount(count) {
    while (meshes.length < count) {
      const mesh = new THREE.Mesh(geometry, material);
      mesh.name = `egg.${meshes.length}`;
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      mesh.visible = false;
      layer.add(mesh);
      meshes.push(mesh);
    }
    meshes.forEach((mesh, index) => {
      if (index >= count) mesh.visible = false;
    });
  }

  /** @param {Array<null | object>} samples ผลจาก sampleEgg() ต่อไข่หนึ่งฟอง (null = ซ่อน) */
  function update(samples) {
    samples.forEach((sample, index) => {
      const mesh = meshes[index];
      if (!mesh) return;
      mesh.visible = sample !== null;
      if (!sample) return;

      mesh.position.set(...sample.pos);
      baseQuaternion
        .copy(BASE_ORIENTATION[sample.longAxisFrom])
        .slerp(BASE_ORIENTATION[sample.longAxisTo], sample.longAxisFraction);
      rollQuaternion.setFromAxisAngle(BODY_LONG_AXIS, sample.roll);
      if (sample.spinAxis && sample.spinDegrees) {
        spinAxis.set(...sample.spinAxis).normalize();
        spinQuaternion.setFromAxisAngle(spinAxis, THREE.MathUtils.degToRad(sample.spinDegrees));
      } else {
        spinQuaternion.identity();
      }
      // ท่าตาม long_axis × หมุนบนลูกกลิ้ง × กลิ้งรอบแกนยาวของตัวไข่
      // การหมุนบนลูกกลิ้งเกิดตอน long_axis = y (ท่าพื้นฐานไม่หมุน) แกนโลกจึงตรงกับแกนตัวไข่ ;
      // คิดในกรอบตัวไข่เพื่อให้มุมที่สะสมไว้ติดไปกับไข่ ไม่ทำให้ไข่ตั้งขึ้นเมื่อบิดตัวไปนอนตามแกน X
      mesh.quaternion.copy(baseQuaternion).multiply(spinQuaternion).multiply(rollQuaternion);
    });
  }

  return { object: layer, setCount, update };
}
