// ตัวเล่นแอนิเมชัน: เวลา → ท่าของกลไก ไข่ ไฟ และข้อความ (ค่าทั้งหมดมาจาก compileProgram)
import { compileProgram, PLAYLIST_ID, sampleEgg } from './compile.js';

/** แสดง event/note ย้อนหลังกี่วินาที และไม่เกินกี่บรรทัด (ใหม่สุดก่อน) */
const MESSAGE_WINDOW_SECONDS = 2.5;
const MAX_MESSAGES = 4;
export const SPEED_RANGE = { min: 0.25, max: 2, step: 0.25 };

/**
 * @param {object} deps { machine, eggLayer, lights, animationSpec, partsSpec, onFrame }
 *   onFrame(messages, playerState) เรียกทุกครั้งที่ประเมินเวลาใหม่
 */
export function createPlayer({ machine, eggLayer, lights, animationSpec, partsSpec, onFrame }) {
  /** แผงควบคุมผูกกับ object นี้โดยตรง */
  const state = { programId: PLAYLIST_ID, time: 0, duration: 0, playing: false, speed: 1, loop: true };
  let program = null;

  function evaluate() {
    const t = state.time;
    for (const groupId of program.drivenGroupIds) {
      if (!machine.motionGroups.has(groupId)) continue;
      machine.controller.setValue(groupId, program.groupValue(groupId, t));
      machine.controller.noteState(groupId, program.groupState(groupId, t));
    }
    eggLayer.update(program.eggTracks.map((track) => sampleEgg(track, t)));
    for (const lightId of program.lightIds) lights.setState(lightId, program.lightState(lightId, t));
    onFrame?.(program.recentMessages(t, MESSAGE_WINDOW_SECONDS).slice(0, MAX_MESSAGES), state);
  }

  function seek(time) {
    state.time = Math.min(Math.max(time, 0), state.duration);
    evaluate();
  }

  function load(programId) {
    program = compileProgram(animationSpec, partsSpec, programId);
    state.programId = programId;
    state.duration = program.duration;
    eggLayer.setCount(program.eggTracks.length);
    seek(0);
  }

  /** เดินเวลาเมื่อกำลังเล่น คืน true ถ้าได้ประเมินเฟรมนี้ */
  function tick(deltaSeconds) {
    if (!state.playing) return false;
    let time = state.time + deltaSeconds * state.speed;
    if (time > state.duration) {
      if (state.loop) {
        time = 0; // วนรอบใหม่: ไข่ทุกฟองกลับไปซ่อนจนถึงเวลาเริ่มของตัวเอง
      } else {
        time = state.duration;
        state.playing = false;
      }
    }
    seek(time);
    return true;
  }

  load(PLAYLIST_ID);

  return {
    state,
    load,
    seek,
    tick,
    play() {
      if (state.time >= state.duration) seek(0);
      state.playing = true;
    },
    pause() {
      state.playing = false;
    },
  };
}
