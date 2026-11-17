// README §4: แปลง animation.json เป็น timeline ที่ประเมินค่าได้จากเวลา t อย่างเดียว
// (ไม่สะสมค่าทีละเฟรม จึงลากสไลเดอร์ไปหน้า/ถอยหลังได้ตรงเสมอ) ไฟล์นี้ไม่ใช้ DOM หรือ THREE
import { ACTUATOR_TWEEN_SECONDS } from '../config.js';

const DEGREES_PER_SECOND_PER_RPM = 6; // 1 rpm = 360° / 60 s
/** เวลาที่ค้างภาพสุดท้ายไว้ก่อนวนรอบใหม่ */
export const END_HOLD_SECONDS = 1.5;
export const PLAYLIST_ID = 'demo_playlist';

const smoothstep = (x) => {
  const clamped = Math.min(Math.max(x, 0), 1);
  return clamped * clamped * (3 - 2 * clamped);
};
const lerp = (a, b, f) => a + (b - a) * f;

/** รายการโปรแกรมที่เล่นได้: playlist + ทุก sequence */
export function listPrograms(animationSpec) {
  return [
    { id: PLAYLIST_ID, label: 'demo_playlist (2 เลนพร้อมกัน)' },
    ...animationSpec.sequences.map((sequence) => ({
      id: sequence.id,
      label: `${sequence.id} (เลน ${sequence.lane} → ${sequence.outcome})`,
    })),
  ];
}

/**
 * เส้นทางไข่หนึ่งฟอง: จุดที่มี pos (เชิงเส้นระหว่างจุด) + มุมกลิ้งสะสม + ช่วงหมุนบนลูกกลิ้ง
 * มุมกลิ้งหมุนรอบแกนยาวของไข่: long_axis y → กลิ้งตาม X (Δx / a), long_axis x → กลิ้งตาม Y (Δy / a)
 */
function buildEggTrack(sequence, start, endPos, rollRadius, queue) {
  const points = [];
  // demo_playlist[].queue: ไข่รอในถาดป้อน (เวลาของ playlist) ก่อนถึงคิวของตัวเอง
  for (const point of queue ?? []) points.push({ t: point.t, pos: [...point.pos], longAxis: 'y', roll: 0 });
  let longAxis = 'y';
  for (const keyframe of sequence.keyframes) {
    if (keyframe.egg?.long_axis) longAxis = keyframe.egg.long_axis;
    if (!keyframe.egg?.pos) continue;
    points.push({ t: start + keyframe.t, pos: [...keyframe.egg.pos], longAxis, roll: 0 });
  }
  // README §6 ของ playlist: ใช้ end_pos แทนตำแหน่ง keyframe สุดท้าย (ไข่ต่อคิวในถาด)
  if (endPos) points[points.length - 1].pos = [...endPos];

  for (let i = 1; i < points.length; i += 1) {
    const [dx, dy] = [0, 1].map((k) => points[i].pos[k] - points[i - 1].pos[k]);
    const travel = points[i].longAxis === 'y' ? dx : dy;
    points[i].roll = points[i - 1].roll + travel / rollRadius;
  }

  const spins = [];
  let spinAxis = null;
  for (const keyframe of sequence.keyframes) {
    if (!keyframe.egg || !('spin_rpm' in keyframe.egg)) continue;
    if (keyframe.egg.spin_axis) spinAxis = keyframe.egg.spin_axis;
    spins.push({ t: start + keyframe.t, rpm: keyframe.egg.spin_rpm, axis: spinAxis });
  }

  const visibleFrom = queue?.length ? Math.min(queue[0].t, start) : start;
  return { seqId: sequence.id, lane: sequence.lane, start: visibleFrom, end: points[points.length - 1].t, points, spins };
}

/** มุมหมุนสะสม (องศา) ของ rpm ที่เปลี่ยนเป็นขั้น ณ เวลา t */
function integrateRpm(steps, t) {
  let degrees = 0;
  for (let i = 0; i < steps.length; i += 1) {
    const { t: t0, rpm } = steps[i];
    if (t <= t0) break;
    const t1 = i + 1 < steps.length ? Math.min(steps[i + 1].t, t) : t;
    degrees += rpm * DEGREES_PER_SECOND_PER_RPM * (t1 - t0);
  }
  return degrees;
}

/**
 * ตัวอย่างของไข่ ณ เวลา t
 * @returns {null | {pos, roll, longAxisFrom, longAxisTo, longAxisFraction, spinDegrees, spinAxis}}
 *          null = ยังไม่ถึงเวลาเริ่มของไข่ฟองนี้ (ซ่อน)
 */
export function sampleEgg(track, t) {
  const { points } = track;
  if (t < track.start) return null;

  let i = points.length - 1;
  while (i > 0 && points[i].t > t) i -= 1;
  const from = points[i];
  const to = points[Math.min(i + 1, points.length - 1)];
  const span = to.t - from.t;
  const fraction = to === from || span <= 0 ? 1 : Math.min((t - from.t) / span, 1);
  const spinAxis = track.spins.find((spin) => spin.axis)?.axis ?? null;

  return {
    pos: from.pos.map((value, k) => lerp(value, to.pos[k], fraction)),
    roll: lerp(from.roll, to.roll, fraction),
    longAxisFrom: from.longAxis,
    longAxisTo: to.longAxis,
    longAxisFraction: fraction,
    spinDegrees: integrateRpm(track.spins, t),
    spinAxis,
  };
}

/** เหตุการณ์ของตัวหนึ่ง (actuator หรือไฟ) เรียงตามเวลา ณ เวลา t: สถานะปัจจุบัน สถานะก่อนหน้า และเวลาที่เปลี่ยน */
function stateAt(events, t, defaultState) {
  let state = defaultState;
  let previous = defaultState;
  let since = Infinity;
  for (const event of events) {
    if (event.t > t) break;
    previous = state;
    state = event.state;
    since = t - event.t;
  }
  return { state, previous, since };
}

/**
 * @param {object} animationSpec animation.json
 * @param {object} partsSpec parts.json (ใช้ groups และ meta.egg)
 * @param {string} programId PLAYLIST_ID หรือ sequence id
 */
export function compileProgram(animationSpec, partsSpec, programId) {
  const sequencesById = new Map(animationSpec.sequences.map((sequence) => [sequence.id, sequence]));
  const groupsById = new Map(partsSpec.groups.map((group) => [group.id, group]));
  const lights = animationSpec.lights ?? {};

  const entries =
    programId === PLAYLIST_ID
      ? animationSpec.demo_playlist.map((entry) => ({ seqId: entry.seq, start: entry.start, endPos: entry.end_pos, queue: entry.queue }))
      : [{ seqId: programId, start: 0, endPos: null }];
  for (const { seqId } of entries) {
    if (!sequencesById.has(seqId)) throw new Error(`ไม่พบ sequence "${seqId}"`);
  }

  const rollRadius = partsSpec.meta.egg.radii_long_axis_y[0];
  const eggTracks = entries.map(({ seqId, start, endPos, queue }) =>
    buildEggTrack(sequencesById.get(seqId), start, endPos, rollRadius, queue),
  );

  const groupEvents = new Map();
  const lightEvents = new Map(Object.keys(lights).map((lightId) => [lightId, []]));
  const messages = [];
  let order = 0;
  for (const { seqId, start } of entries) {
    const sequence = sequencesById.get(seqId);
    for (const keyframe of sequence.keyframes) {
      const t = start + keyframe.t;
      for (const [targetId, state] of Object.entries(keyframe.set ?? {})) {
        const target = lightEvents.has(targetId) ? lightEvents : groupEvents;
        if (!target.has(targetId)) target.set(targetId, []);
        target.get(targetId).push({ t, state, order: (order += 1) });
      }
      for (const kind of ['event', 'note']) {
        if (keyframe[kind]) messages.push({ t, kind, text: keyframe[kind], seqId, lane: sequence.lane });
      }
    }
  }
  const byTime = (a, b) => a.t - b.t || (a.order ?? 0) - (b.order ?? 0);
  for (const events of [...groupEvents.values(), ...lightEvents.values()]) events.sort(byTime);
  messages.sort(byTime);

  // กลุ่มที่ follows ใช้เหตุการณ์ของกลุ่มหลัก
  const drivenGroupIds = new Set(groupEvents.keys());
  for (const group of partsSpec.groups) {
    if (group.motion.follows && drivenGroupIds.has(group.motion.follows)) drivenGroupIds.add(group.id);
  }
  const eventsOfGroup = (groupId) => {
    const leaderId = groupsById.get(groupId).motion.follows;
    return groupEvents.get(leaderId && groupEvents.has(leaderId) ? leaderId : groupId) ?? [];
  };

  const programEnd = Math.max(...entries.map(({ seqId, start }) => start + sequencesById.get(seqId).keyframes.at(-1).t));

  return {
    programId,
    duration: programEnd + END_HOLD_SECONDS,
    eggTracks,
    messages,
    drivenGroupIds: [...drivenGroupIds],
    lightIds: [...lightEvents.keys()],

    /** ชื่อสถานะของกลุ่ม ณ เวลา t */
    groupState(groupId, t) {
      return stateAt(eventsOfGroup(groupId), t, groupsById.get(groupId).motion.default).state;
    },

    /**
     * ค่าของกลุ่ม ณ เวลา t: rotate = องศา, translate = มม. (tween 0.2 s แบบ smoothstep),
     * spin = มุมสะสม (องศา) ของ rpm ตามสถานะ
     */
    groupValue(groupId, t) {
      const { motion } = groupsById.get(groupId);
      const events = eventsOfGroup(groupId);
      if (motion.type === 'spin') {
        const steps = events.map((event) => ({ t: event.t, rpm: motion.states[event.state] }));
        const defaultRpm = motion.states[motion.default];
        if (defaultRpm !== 0) steps.unshift({ t: 0, rpm: defaultRpm });
        return integrateRpm(steps, t) % 360;
      }
      const { state, previous, since } = stateAt(events, t, motion.default);
      const progress = smoothstep(since / ACTUATOR_TWEEN_SECONDS);
      return lerp(motion.states[previous], motion.states[state], progress);
    },

    lightState(lightId, t) {
      return stateAt(lightEvents.get(lightId) ?? [], t, lights[lightId]?.default ?? 'OFF').state;
    },

    /** ข้อความ event/note ที่เกิดขึ้นในช่วง windowSeconds ก่อนเวลา t (ใหม่สุดก่อน) */
    recentMessages(t, windowSeconds) {
      return messages.filter((message) => message.t <= t && message.t > t - windowSeconds).reverse();
    },
  };
}
