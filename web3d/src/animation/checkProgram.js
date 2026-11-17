// ตรวจ timeline ที่คอมไพล์แล้วเทียบกับ animation.json ทีละ keyframe (ไม่ขึ้นกับ DOM / THREE)
import { ACTUATOR_TWEEN_SECONDS } from '../config.js';
import { compileProgram, listPrograms, PLAYLIST_ID, sampleEgg } from './compile.js';

const POSITION_TOLERANCE_MM = 1e-6;
const VALUE_TOLERANCE = 1e-6;
/** ตรวจค่าหลัง tween จบ เผื่อทศนิยมนิดหน่อย */
const SETTLE_SECONDS = ACTUATOR_TWEEN_SECONDS + 1e-3;

const distance = (a, b) => Math.hypot(...a.map((value, i) => value - b[i]));

export function checkPrograms(animationSpec, partsSpec) {
  const groupsById = new Map(partsSpec.groups.map((group) => [group.id, group]));
  const sequencesById = new Map(animationSpec.sequences.map((sequence) => [sequence.id, sequence]));
  const rows = [];

  for (const { id: programId } of listPrograms(animationSpec)) {
    const program = compileProgram(animationSpec, partsSpec, programId);
    const problems = [];
    let checks = 0;
    const entries =
      programId === PLAYLIST_ID
        ? animationSpec.demo_playlist.map((entry) => ({ seqId: entry.seq, start: entry.start, endPos: entry.end_pos, queue: entry.queue }))
        : [{ seqId: programId, start: 0, endPos: null }];

    entries.forEach(({ seqId, start, endPos, queue }, eggIndex) => {
      const track = program.eggTracks[eggIndex];
      const keyframes = sequencesById.get(seqId).keyframes;
      const lastPosIndex = keyframes.map((keyframe) => Boolean(keyframe.egg?.pos)).lastIndexOf(true);

      // ไข่ซ่อนก่อนเวลาเริ่ม (ไข่ที่มี queue โผล่ตั้งแต่จุดแรกของคิว)
      const visibleFrom = queue?.length ? Math.min(queue[0].t, start) : start;
      checks += 1;
      if (visibleFrom > 0 && sampleEgg(track, visibleFrom - 1e-3) !== null) problems.push(`${seqId}: ไข่โผล่ก่อนเวลาเริ่ม`);
      // ตำแหน่งไข่ระหว่างรอคิวในถาดป้อน
      for (const point of queue ?? []) {
        checks += 1;
        const sample = sampleEgg(track, point.t);
        const error = sample ? distance(sample.pos, point.pos) : Infinity;
        if (!(error <= POSITION_TOLERANCE_MM)) problems.push(`${seqId} queue t=${point.t}: ไข่คลาด ${error.toFixed(3)} มม.`);
      }

      keyframes.forEach((keyframe, index) => {
        const t = start + keyframe.t;
        if (keyframe.egg?.pos) {
          checks += 1;
          const expected = index === lastPosIndex && endPos ? endPos : keyframe.egg.pos;
          const sample = sampleEgg(track, t);
          const error = sample ? distance(sample.pos, expected) : Infinity;
          if (!(error <= POSITION_TOLERANCE_MM) || !Number.isFinite(sample.roll)) {
            problems.push(`${seqId} t=${keyframe.t}: ไข่คลาด ${error.toFixed(3)} มม.`);
          }
        }
        // สถานะที่ set ต้องเป็นสถานะปัจจุบัน และค่าต้องถึงเป้าหลัง tween (ถ้าไม่มีเหตุการณ์อื่นแทรกก่อน)
        for (const [targetId, stateName] of Object.entries(keyframe.set ?? {})) {
          checks += 1;
          const settleAt = t + SETTLE_SECONDS;
          if (program.lightIds.includes(targetId)) {
            if (program.lightState(targetId, t) !== stateName) problems.push(`${seqId} t=${keyframe.t}: ${targetId} ≠ ${stateName}`);
            continue;
          }
          if (program.groupState(targetId, t) !== stateName) {
            problems.push(`${seqId} t=${keyframe.t}: ${targetId} ≠ ${stateName}`);
            continue;
          }
          const { motion } = groupsById.get(targetId);
          if (motion.type === 'spin' || program.groupState(targetId, settleAt) !== stateName) continue;
          const value = program.groupValue(targetId, settleAt);
          if (Math.abs(value - motion.states[stateName]) > VALUE_TOLERANCE) {
            problems.push(`${seqId} t=${keyframe.t}: ${targetId} ค่า ${value} ≠ ${motion.states[stateName]}`);
          }
        }
      });
    });

    // ท้ายโปรแกรม: ไข่ทุกฟองต้องอยู่ในฉาก
    checks += 1;
    const hidden = program.eggTracks.filter((track) => sampleEgg(track, program.duration) === null);
    if (hidden.length > 0) problems.push(`ท้ายโปรแกรมยังมีไข่ซ่อน ${hidden.length} ฟอง`);

    rows.push({ program: programId, eggs: program.eggTracks.length, duration: Number(program.duration.toFixed(2)), checks, problems });
  }

  return { ok: rows.every((row) => row.problems.length === 0), rows };
}
