// มุมกล้องสำเร็จรูป คำนวณจากกรอบรวมของเครื่อง (meta.bounding_box)
import * as THREE from 'three';
import { PREVIEW_ISO_VIEW } from './config.js';
import { specDirectionToWorld } from './coords.js';

/** ทิศจากเครื่องไปหากล้องแบบ matplotlib (elev/azim) ในพิกัดสเปก */
function directionFromElevationAzimuth({ elevDeg, azimDeg }) {
  const elevation = THREE.MathUtils.degToRad(elevDeg);
  const azimuth = THREE.MathUtils.degToRad(azimDeg);
  return [
    Math.cos(elevation) * Math.cos(azimuth),
    Math.cos(elevation) * Math.sin(azimuth),
    Math.sin(elevation),
  ];
}

/** ทิศจากเครื่องไปหากล้อง ในพิกัดสเปก (ตรงกับ 4 มุมของ preview.png) */
const VIEW_DIRECTIONS_SPEC = {
  front: [0, -1, 0],
  side: [1, 0, 0],
  // เอียงเล็กน้อยเพื่อไม่ให้ทิศมองขนานกับแกนขึ้นของกล้อง (ด้านหน้าเครื่องอยู่ล่างจอ)
  top: [0, -0.02, 1],
  iso: directionFromElevationAzimuth(PREVIEW_ISO_VIEW),
};

/** ทรงกลมครอบเครื่องหลวมกว่าตัวเครื่องจริง จึงขยับกล้องเข้ามาเล็กน้อย */
const FRAMING_TIGHTNESS = 0.78;

export const VIEW_NAMES = Object.keys(VIEW_DIRECTIONS_SPEC);

/**
 * @param {THREE.Box3} worldBox กรอบรวมของเครื่องในพิกัด Three.js
 * @returns {(viewName: string, camera: THREE.PerspectiveCamera) => {position, target}}
 */
export function createCameraPresets(worldBox) {
  const sphere = worldBox.getBoundingSphere(new THREE.Sphere());

  return function getView(viewName, camera) {
    const direction = VIEW_DIRECTIONS_SPEC[viewName];
    if (!direction) throw new Error(`ไม่รู้จักมุมกล้อง "${viewName}"`);

    // ถอยกล้องให้ทรงกลมครอบเครื่องพอดีทั้งแนวตั้งและแนวนอน
    const verticalFov = THREE.MathUtils.degToRad(camera.fov);
    const horizontalFov = 2 * Math.atan(Math.tan(verticalFov / 2) * camera.aspect);
    const fitDistance = sphere.radius / Math.sin(Math.min(verticalFov, horizontalFov) / 2);
    const distance = fitDistance * FRAMING_TIGHTNESS;

    return {
      target: sphere.center.clone(),
      position: sphere.center.clone().addScaledVector(specDirectionToWorld(direction), distance),
    };
  };
}
