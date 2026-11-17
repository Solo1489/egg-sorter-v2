// ตรวจความถูกต้องของสเปกก่อนสร้างโมเดล (ไม่ขึ้นกับ DOM)
// คืนรายการ { section, check, ok, detail } ให้ผู้เรียกนำไปแสดงใน console / HUD

const KNOWN_SHAPES = {
  box: ['min', 'max'],
  cylinder: ['center', 'radius', 'length', 'axis'],
  prism: ['plane', 'points', 'extrude'],
};
const KNOWN_PRISM_PLANES = ['xz', 'yz', 'xy'];
const KNOWN_CYLINDER_AXES = ['x', 'y', 'z'];
const KNOWN_MOTION_TYPES = ['rotate', 'translate', 'spin'];
const UNIT_VECTOR_TOLERANCE = 1e-6;
const MAX_LISTED_PROBLEMS = 6;

const isVector3 = (value) =>
  Array.isArray(value) && value.length === 3 && value.every((n) => Number.isFinite(n));
const isUnitVector = (value) =>
  isVector3(value) && Math.abs(Math.hypot(...value) - 1) < UNIT_VECTOR_TOLERANCE;

function createRecorder(section) {
  const results = [];
  /** บันทึกผลหนึ่งข้อ: ผ่านเมื่อ problems ว่าง */
  function record(check, problems, passDetail = '') {
    const ok = problems.length === 0;
    const listed = problems.slice(0, MAX_LISTED_PROBLEMS).join(' ; ');
    const more = problems.length > MAX_LISTED_PROBLEMS ? ` … (+${problems.length - MAX_LISTED_PROBLEMS})` : '';
    results.push({ section, check, ok, detail: ok ? passDetail : listed + more });
  }
  return { results, record };
}

export function checkPartsSpec(partsSpec) {
  const { results, record } = createRecorder('parts.json');
  const { parts, groups, materials, labels, meta } = partsSpec;
  const partIds = new Set(parts.map((part) => part.id));
  const groupsById = new Map(groups.map((group) => [group.id, group]));

  const seenIds = new Set();
  const duplicateIds = [];
  for (const part of parts) {
    if (seenIds.has(part.id)) duplicateIds.push(part.id);
    seenIds.add(part.id);
  }
  record('part id ไม่ซ้ำกัน', duplicateIds, `${parts.length} ชิ้น`);

  const shapeProblems = [];
  for (const part of parts) {
    const requiredFields = KNOWN_SHAPES[part.shape];
    if (!requiredFields) {
      shapeProblems.push(`${part.id}: shape "${part.shape}"`);
      continue;
    }
    for (const field of requiredFields) {
      if (part[field] === undefined) shapeProblems.push(`${part.id}: ไม่มี ${field}`);
    }
    if (part.shape === 'prism' && !KNOWN_PRISM_PLANES.includes(part.plane)) {
      shapeProblems.push(`${part.id}: plane "${part.plane}"`);
    }
    if (part.shape === 'cylinder' && !KNOWN_CYLINDER_AXES.includes(part.axis)) {
      shapeProblems.push(`${part.id}: axis "${part.axis}"`);
    }
    for (const transformKey of Object.keys(part.transform ?? {})) {
      if (transformKey !== 'rotate') shapeProblems.push(`${part.id}: transform.${transformKey}`);
    }
  }
  record('shape และฟิลด์ที่ต้องมีครบทุกชิ้น', shapeProblems);

  record(
    'วัสดุที่อ้างถึงมีอยู่จริง',
    parts.filter((part) => !materials[part.material]).map((part) => `${part.id} → ${part.material}`),
    `${Object.keys(materials).length} วัสดุ`,
  );

  const membershipProblems = [];
  const groupIdOfPart = new Map();
  for (const group of groups) {
    for (const partId of group.parts) {
      if (!partIds.has(partId)) membershipProblems.push(`${group.id} → ไม่พบชิ้น ${partId}`);
      if (groupIdOfPart.has(partId)) {
        membershipProblems.push(`${partId} อยู่ทั้งใน ${groupIdOfPart.get(partId)} และ ${group.id}`);
      }
      groupIdOfPart.set(partId, group.id);
    }
  }
  record('ทุกชิ้นในกลุ่มมีอยู่จริง และอยู่ได้กลุ่มเดียว', membershipProblems, `${groups.length} กลุ่ม`);

  const motionProblems = [];
  for (const group of groups) {
    const { motion } = group;
    if (!KNOWN_MOTION_TYPES.includes(motion.type)) {
      motionProblems.push(`${group.id}: type "${motion.type}"`);
      continue;
    }
    if (!isUnitVector(motion.axis)) motionProblems.push(`${group.id}: axis ไม่ใช่เวกเตอร์หนึ่งหน่วย`);
    if (!(motion.default in motion.states)) {
      motionProblems.push(`${group.id}: default "${motion.default}" ไม่อยู่ใน states`);
    }
    if (motion.type === 'rotate' && !isVector3(motion.pivot)) {
      motionProblems.push(`${group.id}: ไม่มี pivot`);
    }
    if (motion.type === 'spin') {
      for (const partId of group.parts) {
        if (!isVector3(motion.pivots?.[partId])) motionProblems.push(`${group.id}: ไม่มี pivots[${partId}]`);
      }
      for (const partId of Object.keys(motion.pivots ?? {})) {
        if (!group.parts.includes(partId)) motionProblems.push(`${group.id}: pivots[${partId}] ไม่อยู่ในกลุ่ม`);
      }
    }
  }
  record('motion ของทุกกลุ่มถูกต้อง (type, axis, pivot, default)', motionProblems);

  const followProblems = [];
  for (const group of groups) {
    const leaderId = group.motion.follows;
    if (!leaderId) continue;
    const leader = groupsById.get(leaderId);
    if (!leader) {
      followProblems.push(`${group.id} follows ${leaderId} (ไม่พบ)`);
      continue;
    }
    for (const stateName of Object.keys(leader.motion.states)) {
      if (!(stateName in group.motion.states)) {
        followProblems.push(`${group.id}: ไม่มีสถานะ ${stateName} ของ ${leaderId}`);
      }
    }
  }
  record('follows ชี้ไปที่กลุ่มที่มีจริง และมีสถานะครบตามกลุ่มหลัก', followProblems);

  record(
    'labels มี text และ pos',
    labels
      .filter((label) => !label.text || !isVector3(label.pos))
      .map((label) => JSON.stringify(label)),
    `${labels.length} ป้าย`,
  );

  const metaProblems = [];
  if (!isVector3(meta?.bounding_box?.min) || !isVector3(meta?.bounding_box?.max)) {
    metaProblems.push('ไม่มี meta.bounding_box');
  }
  if (!isVector3(meta?.egg?.radii_long_axis_y)) metaProblems.push('ไม่มี meta.egg.radii_long_axis_y');
  if (!materials[meta?.egg?.material]) metaProblems.push('ไม่พบวัสดุของไข่');
  record('meta มี bounding_box และข้อมูลไข่', metaProblems);

  return results;
}

/**
 * ตรวจ animation.json เทียบกับ parts.json
 * รูปแบบที่คาดหวัง: actuators = { groupId: [สถานะ] }, lights = { lightId: … },
 * egg.spin_axis เป็นเวกเตอร์, demo_playlist[].end_pos
 */
export function checkAnimationSpec(partsSpec, animationSpec) {
  const { results, record } = createRecorder('animation.json');
  const groupsById = new Map(partsSpec.groups.map((group) => [group.id, group]));
  const actuators = animationSpec.actuators ?? {};
  const lights = animationSpec.lights;
  const hasLights = lights !== null && typeof lights === 'object';
  const lightIds = hasLights ? Object.keys(lights) : [];

  record('มี lights', hasLights ? [] : ['ไม่พบ animation.json → lights'], `${lightIds.length} ดวง`);

  const actuatorProblems = [];
  for (const [actuatorId, stateNames] of Object.entries(actuators)) {
    const group = groupsById.get(actuatorId);
    if (!group) {
      actuatorProblems.push(`"${actuatorId}" ไม่ใช่ group id`);
      continue;
    }
    const groupStateNames = Object.keys(group.motion.states);
    const isSameStates =
      stateNames.length === groupStateNames.length &&
      stateNames.every((stateName) => groupStateNames.includes(stateName));
    if (!isSameStates) actuatorProblems.push(`${actuatorId}: สถานะไม่ตรงกับ groups`);
  }
  record(
    'ทุกคีย์ใน actuators เป็น group ที่มีจริง และสถานะตรงกัน',
    actuatorProblems,
    `${Object.keys(actuators).length} คีย์`,
  );

  const sequenceIds = new Set();
  const setProblems = [];
  const keyframeProblems = [];
  const spinAxisProblems = [];
  for (const sequence of animationSpec.sequences ?? []) {
    sequenceIds.add(sequence.id);
    let previousTime = -Infinity;
    if (!isVector3(sequence.keyframes[0]?.egg?.pos)) {
      keyframeProblems.push(`${sequence.id}: keyframe แรกไม่มี egg.pos`);
    }
    for (const keyframe of sequence.keyframes) {
      if (!(keyframe.t >= previousTime)) keyframeProblems.push(`${sequence.id}: t=${keyframe.t} ไม่เรียงลำดับ`);
      previousTime = keyframe.t;

      for (const [targetId, stateName] of Object.entries(keyframe.set ?? {})) {
        const isActuator = targetId in actuators;
        if (!isActuator && !lightIds.includes(targetId)) {
          setProblems.push(`${sequence.id} t=${keyframe.t}: "${targetId}" ไม่อยู่ใน actuators/lights`);
        } else if (isActuator && !actuators[targetId].includes(stateName)) {
          setProblems.push(`${sequence.id} t=${keyframe.t}: ${targetId}=${stateName}`);
        }
      }

      const spinAxis = keyframe.egg?.spin_axis;
      if (spinAxis !== undefined && !isUnitVector(spinAxis)) {
        spinAxisProblems.push(`${sequence.id} t=${keyframe.t}: spin_axis=${JSON.stringify(spinAxis)}`);
      }
    }
  }
  record('ทุก set อ้างถึง actuators หรือ lights และสถานะมีจริง', setProblems);
  record('keyframe เรียงตามเวลา และเริ่มด้วย egg.pos', keyframeProblems, `${sequenceIds.size} sequence`);
  record('egg.spin_axis เป็นเวกเตอร์หนึ่งหน่วย', spinAxisProblems);

  const playlistProblems = [];
  for (const entry of animationSpec.demo_playlist ?? []) {
    if (!sequenceIds.has(entry.seq)) playlistProblems.push(`ไม่พบ sequence "${entry.seq}"`);
    if (!isVector3(entry.end_pos)) playlistProblems.push(`${entry.seq}: ไม่มี end_pos`);
  }
  record('demo_playlist อ้างถึง sequence ที่มีจริง และมี end_pos', playlistProblems);

  return results;
}

export function runSelfCheck(partsSpec, animationSpec) {
  const results = [...checkPartsSpec(partsSpec), ...checkAnimationSpec(partsSpec, animationSpec)];
  return { ok: results.every((result) => result.ok), results };
}
