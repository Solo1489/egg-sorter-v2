import * as THREE from 'three';
import { MM_TO_M } from './config.js';

/**
 * README §1: root ที่แปลงพิกัดสเปก (มม., Z ขึ้น) เป็น Three.js (เมตร, Y ขึ้น)
 * ทุกชิ้นส่วนอยู่ใต้ root นี้และใช้พิกัดสเปกตรงๆ
 */
export function createSpecRoot() {
  const root = new THREE.Group();
  root.name = 'spec-root';
  root.rotation.x = -Math.PI / 2;
  root.scale.setScalar(MM_TO_M);
  return root;
}

/** สูตรปิดของ README §1: (x, y, z) ในสเปก → (x, z, −y) × 0.001 ใน Three.js */
export function specPointToWorld([x, y, z]) {
  return new THREE.Vector3(x * MM_TO_M, z * MM_TO_M, -y * MM_TO_M);
}

/** ทิศทางในสเปก → ทิศทางใน Three.js (ไม่คูณสเกล) */
export function specDirectionToWorld([x, y, z]) {
  return new THREE.Vector3(x, z, -y).normalize();
}

/** กล่องขอบเขตในสเปก {min, max} → Box3 ในพิกัด Three.js */
export function specBoundsToWorldBox({ min, max }) {
  return new THREE.Box3().setFromPoints([specPointToWorld(min), specPointToWorld(max)]);
}
