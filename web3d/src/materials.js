// วัสดุจาก parts.json → materials (สี, opacity, roughness, metalness, emissive)
import * as THREE from 'three';
import { GHOST_OPACITY } from './config.js';

const DEFAULT_ROUGHNESS = 0.6;
const DEFAULT_METALNESS = 0;
/** ชิ้นที่โปร่งกว่านี้ไม่ทอดเงา */
const SHADOW_CASTER_MIN_OPACITY = 0.5;

function applyOpacity(material, opacity) {
  material.opacity = opacity;
  material.transparent = opacity < 1;
  // ชิ้นโปร่งใสไม่เขียน depth เพื่อให้เห็นชิ้นที่อยู่ข้างหลังเสมอ
  material.depthWrite = !material.transparent;
  material.needsUpdate = true;
}

export function createMaterialLibrary(materialSpecs) {
  const materialsByKey = new Map();

  function get(materialKey) {
    if (materialsByKey.has(materialKey)) return materialsByKey.get(materialKey);
    const spec = materialSpecs[materialKey];
    if (!spec) throw new Error(`ไม่พบวัสดุ "${materialKey}" ใน parts.json → materials`);

    const material = new THREE.MeshStandardMaterial({
      name: materialKey,
      color: spec.color,
      roughness: spec.roughness ?? DEFAULT_ROUGHNESS,
      metalness: spec.metalness ?? DEFAULT_METALNESS,
    });
    if (spec.emissive) {
      material.emissive.set(spec.emissive);
      material.emissiveIntensity = spec.emissiveIntensity ?? 1;
    }
    applyOpacity(material, spec.opacity ?? 1);
    materialsByKey.set(materialKey, material);
    return material;
  }

  function castsShadow(materialKey) {
    return (materialSpecs[materialKey]?.opacity ?? 1) >= SHADOW_CASTER_MIN_OPACITY;
  }

  /** โหมดโปร่งใส: ลด opacity ของวัสดุอะคริลิกทุกชนิดให้มองทะลุตัวตู้ได้ */
  function setGhostMode(isGhost) {
    for (const [materialKey, material] of materialsByKey) {
      if (!materialKey.startsWith('acrylic')) continue;
      const specOpacity = materialSpecs[materialKey].opacity ?? 1;
      applyOpacity(material, isGhost ? Math.min(specOpacity, GHOST_OPACITY) : specOpacity);
    }
  }

  return { get, castsShadow, setGhostMode };
}
