// README §3: กลุ่มชิ้นที่ขยับได้ (rotate / translate / spin) และตัวควบคุมสถานะ
import * as THREE from 'three';
import { ACTUATOR_TWEEN_SECONDS } from './config.js';

const DEGREES_PER_SECOND_PER_RPM = 6; // 1 rpm = 360° / 60 s

/** วาง node ไว้ใต้ parent โดยหัก offset ของจุดกำเนิด parent ออก (พิกัดสเปก) */
export function attachAtSpecOrigin(parent, parentOrigin, node, nodeOrigin) {
  node.position.copy(nodeOrigin).sub(parentOrigin);
  parent.add(node);
}

function createCarrier(root, name, homePosition) {
  const object = new THREE.Group();
  object.name = name;
  object.position.copy(homePosition);
  root.add(object);
  return { object, home: homePosition.clone() };
}

/**
 * สร้าง pivot object ของแต่ละกลุ่มแล้วย้าย part node เข้าไป
 * กลุ่มที่ชิ้นส่วนยังสร้างไม่ครบ (โมดูลยังไม่ถึง) จะถูกข้าม
 * @returns {Map<string, object>} groupId → motion group
 */
export function createMotionGroups(groupSpecs, partNodes, root) {
  const motionGroups = new Map();

  for (const spec of groupSpecs) {
    if (!spec.parts.every((partId) => partNodes.has(partId))) continue;

    const { motion } = spec;
    const axis = new THREE.Vector3(...motion.axis).normalize();
    const carriers = [];

    if (motion.type === 'spin') {
      // แต่ละชิ้นหมุนรอบแกนของตัวเอง
      for (const partId of spec.parts) {
        const pivot = new THREE.Vector3(...motion.pivots[partId]);
        const carrier = createCarrier(root, `${spec.id}:${partId}`, pivot);
        const { node, origin } = partNodes.get(partId);
        attachAtSpecOrigin(carrier.object, pivot, node, origin);
        carriers.push(carrier);
      }
    } else if (motion.type === 'rotate' || motion.type === 'translate') {
      const pivot = new THREE.Vector3(...(motion.pivot ?? [0, 0, 0]));
      const carrier = createCarrier(root, spec.id, pivot);
      for (const partId of spec.parts) {
        const { node, origin } = partNodes.get(partId);
        attachAtSpecOrigin(carrier.object, pivot, node, origin);
      }
      carriers.push(carrier);
    } else {
      throw new Error(`${spec.id}: ไม่รู้จัก motion.type "${motion.type}"`);
    }

    motionGroups.set(spec.id, { id: spec.id, spec, motion, axis, carriers, value: 0 });
  }
  return motionGroups;
}

/**
 * ตั้งท่าของกลุ่มจากค่าตัวเลข
 * rotate = องศา, translate = มม., spin = มุมสะสมเป็นองศา (0 = ท่าอ้างอิง)
 */
export function applyMotionValue(motionGroup, value) {
  motionGroup.value = value;
  const { motion, axis, carriers } = motionGroup;
  for (const { object, home } of carriers) {
    if (motion.type === 'translate') {
      object.position.copy(home).addScaledVector(axis, value);
    } else {
      object.quaternion.setFromAxisAngle(axis, THREE.MathUtils.degToRad(value));
    }
  }
}

/**
 * ตัวควบคุมสถานะของทุกกลุ่ม
 * - setState: เปลี่ยนสถานะตามชื่อ (tween 0.2 s) กลุ่มที่ follows จะเปลี่ยนตามกลุ่มหลัก
 * - setValue: ตั้งค่าตรงๆ (ใช้โดยตัวเล่นแอนิเมชันและ verify)
 */
export function createMotionController(motionGroups, followerIdsOf) {
  const runtimeById = new Map();
  for (const groupId of motionGroups.keys()) {
    runtimeById.set(groupId, { stateName: null, tween: null, spinRpm: 0 });
  }

  function requireGroup(groupId) {
    const motionGroup = motionGroups.get(groupId);
    if (!motionGroup) throw new Error(`ไม่พบกลุ่ม "${groupId}" (อาจยังไม่ได้สร้างโมดูลของกลุ่มนี้)`);
    return motionGroup;
  }

  function setOwnState(groupId, stateName, immediate) {
    const motionGroup = requireGroup(groupId);
    const { motion } = motionGroup;
    if (!(stateName in motion.states)) {
      throw new Error(`${groupId}: ไม่มีสถานะ "${stateName}"`);
    }
    const runtime = runtimeById.get(groupId);
    runtime.stateName = stateName;
    const target = motion.states[stateName];

    if (motion.type === 'spin') {
      runtime.spinRpm = target;
      return;
    }
    if (immediate) {
      runtime.tween = null;
      applyMotionValue(motionGroup, target);
    } else {
      runtime.tween = { from: motionGroup.value, to: target, elapsed: 0 };
    }
  }

  function setState(groupId, stateName, { immediate = false } = {}) {
    setOwnState(groupId, stateName, immediate);
    for (const followerId of followerIdsOf.get(groupId) ?? []) {
      if (motionGroups.has(followerId)) setOwnState(followerId, stateName, immediate);
    }
  }

  function setValue(groupId, value) {
    runtimeById.get(groupId).tween = null;
    applyMotionValue(requireGroup(groupId), value);
  }

  function setAllToDefault({ immediate = true } = {}) {
    for (const [groupId, { motion }] of motionGroups) {
      setOwnState(groupId, motion.default, immediate);
    }
  }

  function update(deltaSeconds) {
    for (const [groupId, motionGroup] of motionGroups) {
      const runtime = runtimeById.get(groupId);
      if (motionGroup.motion.type === 'spin') {
        if (runtime.spinRpm !== 0) {
          const turned = runtime.spinRpm * DEGREES_PER_SECOND_PER_RPM * deltaSeconds;
          applyMotionValue(motionGroup, (motionGroup.value + turned) % 360);
        }
        continue;
      }
      const { tween } = runtime;
      if (!tween) continue;
      tween.elapsed += deltaSeconds;
      const progress = Math.min(tween.elapsed / ACTUATOR_TWEEN_SECONDS, 1);
      const eased = THREE.MathUtils.smoothstep(progress, 0, 1);
      applyMotionValue(motionGroup, THREE.MathUtils.lerp(tween.from, tween.to, eased));
      if (progress >= 1) runtime.tween = null;
    }
  }

  /** บันทึกชื่อสถานะโดยไม่ขยับ (ใช้เมื่อตัวเล่นแอนิเมชันตั้งค่ามุม/ระยะเองด้วย setValue) */
  function noteState(groupId, stateName) {
    const runtime = runtimeById.get(groupId);
    if (runtime) runtime.stateName = stateName;
  }

  const getStateName = (groupId) => runtimeById.get(groupId)?.stateName ?? null;
  const isFollower = (groupId) => Boolean(requireGroup(groupId).motion.follows);

  return { setState, setValue, setAllToDefault, update, getStateName, noteState, isFollower };
}

const GIZMO_COLORS = { rotate: 0xff7a00, translate: 0x00a8c6, spin: 0xc03fd6 };

/**
 * ตัวช่วยดูด้วยตา: ลูกศรชี้แกนของแต่ละกลุ่ม (หมุนตามกฎมือขวารอบลูกศร / เลื่อนตามลูกศร)
 * ลูกศรอยู่ใต้ root โดยตรง จึงไม่ขยับตามกลุ่ม
 */
export function createPivotGizmos(motionGroups, partNodes, arrowLengthMm) {
  const gizmos = new THREE.Group();
  gizmos.name = 'pivot-gizmos';

  for (const motionGroup of motionGroups.values()) {
    const { motion, axis, carriers, spec } = motionGroup;
    const color = GIZMO_COLORS[motion.type];

    let anchors;
    if (motion.type === 'translate') {
      // ไม่มี pivot ให้ใช้จุดกึ่งกลางของชิ้นส่วนในกลุ่มเป็นจุดวางลูกศร
      const centroid = new THREE.Vector3();
      for (const partId of spec.parts) centroid.add(partNodes.get(partId).origin);
      anchors = [centroid.divideScalar(spec.parts.length)];
    } else {
      anchors = carriers.map((carrier) => carrier.home);
    }

    for (const anchor of anchors) {
      const arrow = new THREE.ArrowHelper(
        axis,
        anchor,
        arrowLengthMm,
        color,
        arrowLengthMm * 0.25,
        arrowLengthMm * 0.12,
      );
      const marker = new THREE.Mesh(
        new THREE.SphereGeometry(arrowLengthMm * 0.06, 12, 8),
        new THREE.MeshBasicMaterial({ color }),
      );
      marker.position.copy(anchor);
      gizmos.add(arrow, marker);
    }
  }

  // วาดทับทุกอย่างเพื่อให้เห็นแกนแม้อยู่หลังผนัง
  gizmos.traverse((object) => {
    if (!object.material) return;
    object.material.depthTest = false;
    object.material.transparent = true;
    object.renderOrder = 10;
  });
  return gizmos;
}
