// จุดเริ่มของแอป: ตรวจสเปก → สร้างโมเดล → verify → ไข่/ไฟ/ป้าย/ตัวเล่น → UI → วนเรนเดอร์
import { PLAYLIST_ID } from './animation/compile.js';
import { createPlayer } from './animation/player.js';
import { buildMachine } from './buildMachine.js';
import { BUILD_THROUGH_MODULE } from './config.js';
import { specBoundsToWorldBox, specPointToWorld } from './coords.js';
import { createDimensionLayer } from './dimensions.js';
import { createEggLayer } from './egg.js';
import { createPivotGizmos } from './groups.js';
import { createLabelLayer } from './labels.js';
import { createLightController } from './leds.js';
import { createSceneContext } from './scene.js';
import { checkAnimationSpec, checkPartsSpec } from './selfCheck.js';
import { animationSpec, partsSpec } from './spec.js';
import { createSpecIndex, modulesThrough } from './specIndex.js';
import { createHud } from './ui/hud.js';
import { createPanel } from './ui/panel.js';
import { summarizeByModule, verifyMachine } from './verify.js';
import { createVisibilityController } from './visibility.js';

/** ความยาวลูกศรแกน เป็นสัดส่วนของรัศมีทรงกลมที่ครอบเครื่อง */
const GIZMO_LENGTH_FACTOR = 0.09;
const MAX_FRAME_SECONDS = 0.1;

/**
 * ตัวเลือกจาก URL (ใช้ตอนตรวจงาน/จับภาพ)
 *   ?view=front|side|top|iso   มุมกล้องเริ่มต้น
 *   ?ui=0                      ซ่อนแผงควบคุมและ HUD
 *   ?ghost=1  ?gizmos=1  ?labels=0  ?states=1   โหมดโปร่งใส / แกนของกลุ่ม / ป้ายชื่อ / ป้ายสถานะ
 *   ?dims=0  ?dimsDetail=1     ซ่อนเส้นวัดขนาดรวม / แสดงเส้นวัดละเอียด (ช่วงโมดูล + ความกว้างชุดราง)
 *   ?program=F_good_A&t=6.3    เลือกลำดับและหยุดไว้ที่เวลา t (ไม่เล่นอัตโนมัติ)
 *   ?play=0                    ไม่เล่นอัตโนมัติ
 *   ?state=esc.F:RELEASE,esc.B:RELEASE   ตั้งสถานะกลุ่มตอนเริ่ม (หยุดการเล่น)
 *   ?focus=146,39,120&zoom=3   เล็งกล้องไปที่จุดในพิกัดสเปก (มม.) แล้วซูมเข้า
 */
function readUrlOptions() {
  const params = new URLSearchParams(window.location.search);
  const initialStates = (params.get('state') ?? '')
    .split(',')
    .filter(Boolean)
    .map((pair) => pair.split(':'));
  return {
    view: params.get('view') ?? 'iso',
    showUi: params.get('ui') !== '0',
    ghost: params.get('ghost') === '1',
    gizmos: params.get('gizmos') === '1',
    labels: params.get('labels') !== '0',
    stateLabels: params.get('states') === '1',
    dimensions: params.get('dims') !== '0',
    dimensionDetail: params.get('dimsDetail') === '1',
    focusSpecPoint: params.has('focus') ? params.get('focus').split(',').map(Number) : null,
    zoom: Number(params.get('zoom') ?? 1),
    programId: params.get('program') ?? PLAYLIST_ID,
    time: params.has('t') ? Number(params.get('t')) : null,
    autoplay: params.get('play') !== '0' && !params.has('t') && !params.has('state'),
    initialStates,
  };
}

function reportChecks(hud, key, label, results) {
  const failed = results.filter((result) => !result.ok);
  console.groupCollapsed(`${failed.length === 0 ? '✅' : '❌'} self-check: ${label}`);
  console.table(results.map(({ check, ok, detail }) => ({ check, ok, detail })));
  console.groupEnd();
  hud.setStatus(key, {
    ok: failed.length === 0,
    text: `self-check ${label}: ${
      failed.length === 0 ? `ผ่าน ${results.length} ข้อ` : `ไม่ผ่าน ${failed.length}/${results.length} ข้อ`
    }`,
    detail: failed.map((result) => result.check).join(' · '),
  });
  return failed.length === 0;
}

function reportVerify(hud, report, moduleOrder) {
  console.groupCollapsed(`${report.ok ? '✅' : '❌'} verify: เทียบ mesh กับสเปก`);
  console.table(summarizeByModule(report, moduleOrder));
  if (!report.ok) console.table(report.failures);
  console.groupEnd();
  hud.setStatus('verify', {
    ok: report.ok,
    text: report.ok
      ? `verify: ผ่าน ${report.rows.length} รายการ (คลาดสูงสุด ${report.maxErrorMm.toFixed(5)} มม.)`
      : `verify: ไม่ผ่าน ${report.failures.length} รายการ`,
    detail: report.failures
      .slice(0, 4)
      .map((row) => `${row.partId} @ ${row.pose}`)
      .join(' · '),
  });
}

/** README §5: ก่อนดึงชุดรางออก F1 และ K2 ต้องอยู่ที่ STOP */
function insertWarning(machine) {
  const stateOf = (groupId) => machine.controller.getStateName(groupId);
  const pulledOut = [...machine.motionGroups.keys()].filter(
    (groupId) => groupId.startsWith('insert.') && stateOf(groupId) !== 'IN',
  );
  if (pulledOut.length === 0) return null;
  const notStopped = [...machine.motionGroups.keys()].filter(
    (groupId) => /^(f1|k2)\./.test(groupId) && stateOf(groupId) !== 'STOP',
  );
  if (notStopped.length === 0) return null;
  return `⚠ ดึง ${pulledOut.join(', ')} ออกอยู่ ขณะที่ ${notStopped.join(', ')} ไม่ได้อยู่ที่ STOP`;
}

function start() {
  const options = readUrlOptions();
  document.body.classList.toggle('ui-hidden', !options.showUi);

  const hud = createHud(document.getElementById('hud'));
  const isPartsSpecOk = reportChecks(hud, 'parts', 'parts.json', checkPartsSpec(partsSpec));
  const isAnimationSpecOk = reportChecks(
    hud,
    'animation',
    'animation.json',
    checkAnimationSpec(partsSpec, animationSpec),
  );
  if (!isPartsSpecOk) {
    hud.setTitle('parts.json ไม่ผ่าน self-check จึงไม่สร้างโมเดล');
    return;
  }

  const { moduleOrder } = createSpecIndex(partsSpec);
  const modules = modulesThrough(moduleOrder, BUILD_THROUGH_MODULE);
  hud.setTitle(`โมดูลที่สร้างแล้ว: ${modules.join(' → ')}`);

  const machine = buildMachine(partsSpec, { modules });
  reportVerify(hud, verifyMachine(machine), moduleOrder);

  const viewport = document.getElementById('viewport');
  const sceneContext = createSceneContext(viewport, specBoundsToWorldBox(partsSpec.meta.bounding_box));
  sceneContext.scene.add(machine.root);
  sceneContext.enableDoubleClickFocus(machine.root);

  // ลูกศรอยู่ใต้ root (หน่วย มม.) จึงแปลงความยาวจากเมตรกลับด้วยสเกลของ root
  const gizmoLengthMm = (sceneContext.machineSphere.radius * GIZMO_LENGTH_FACTOR) / machine.root.scale.x;
  const pivotGizmos = createPivotGizmos(machine.motionGroups, machine.partNodes, gizmoLengthMm);
  pivotGizmos.visible = options.gizmos;
  machine.root.add(pivotGizmos);

  // วัดจากท่า default ของทุกกลุ่ม ก่อนตัวเล่นหรือ ?state= จะขยับกลไก
  const dimensions = createDimensionLayer(machine, partsSpec);
  dimensions.setOverallVisible(options.dimensions);
  dimensions.setDetailVisible(options.dimensionDetail);

  const lights = createLightController(machine, animationSpec.lights);
  const labels = createLabelLayer(viewport, machine, partsSpec.labels);
  labels.setNamesVisible(options.labels);
  labels.setStatesVisible(options.stateLabels);
  machine.materials.setGhostMode(options.ghost);

  // ตัวเล่นแอนิเมชัน ใช้ได้เมื่อ animation.json ผ่าน self-check เท่านั้น
  let player = null;
  if (isAnimationSpecOk) {
    const eggLayer = createEggLayer(machine.root, machine.materials, partsSpec.meta.egg);
    player = createPlayer({
      machine,
      eggLayer,
      lights,
      animationSpec,
      partsSpec,
      onFrame: (messages) => hud.setMessages(messages),
    });
    if (options.programId !== PLAYLIST_ID) player.load(options.programId);
    if (options.time !== null) player.seek(options.time);
    if (options.autoplay) player.play();
  } else {
    hud.setPlayback('ปิดการเล่นแอนิเมชัน เพราะ animation.json ไม่ผ่าน self-check');
  }

  for (const [groupId, stateName] of options.initialStates) {
    machine.controller.setState(groupId, stateName, { immediate: true });
  }

  // ชื่อสถานะของทุกกลุ่ม (ไม่รวมกลุ่มที่ follows) สำหรับแผงควบคุม
  const stateModel = {};
  const refreshStateModel = () => {
    for (const groupId of machine.motionGroups.keys()) {
      if (!machine.controller.isFollower(groupId)) stateModel[groupId] = machine.controller.getStateName(groupId);
    }
  };
  refreshStateModel();

  const visibility = createVisibilityController(machine);
  if (options.showUi) {
    createPanel({
      machine,
      sceneContext,
      visibility,
      pivotGizmos,
      labels,
      dimensions,
      lights,
      player,
      animationSpec,
      stateModel,
      initial: {
        ghost: options.ghost,
        gizmos: options.gizmos,
        labels: options.labels,
        stateLabels: options.stateLabels,
        dimensions: options.dimensions,
        dimensionDetail: options.dimensionDetail,
      },
    });
  }
  sceneContext.setView(options.view);
  if (options.focusSpecPoint || options.zoom !== 1) {
    const focusPoint = options.focusSpecPoint
      ? specPointToWorld(options.focusSpecPoint)
      : sceneContext.controls.target.clone();
    sceneContext.focusOn(focusPoint, options.zoom);
  }

  let previousTime = performance.now();
  sceneContext.renderer.setAnimationLoop((time) => {
    const deltaSeconds = Math.min((time - previousTime) / 1000, MAX_FRAME_SECONDS);
    previousTime = time;

    // ขณะเล่น ตัวเล่นตั้งท่าของกลไกเอง ขณะหยุด ตัวควบคุมเดิน tween ของการสั่งด้วยมือ
    const isPlaying = player?.tick(deltaSeconds) ?? false;
    if (!isPlaying) machine.controller.update(deltaSeconds);

    refreshStateModel();
    if (player) {
      const { programId, time: t, duration, playing, speed } = player.state;
      hud.setPlayback(`${playing ? '▶' : '⏸'} ${programId}  ${t.toFixed(2)} / ${duration.toFixed(2)} s  ×${speed}`);
    }
    hud.setWarning(insertWarning(machine));
    labels.updateStates(machine.controller.getStateName);

    sceneContext.render();
    labels.render(sceneContext.scene, sceneContext.camera);
  });

  // ให้ตรวจจาก console ได้ เช่น __egg.player.seek(6.3) หรือ __egg.machine.controller.setState('esc.F', 'RELEASE')
  window.__egg = { machine, sceneContext, player, lights, partsSpec, animationSpec };
}

start();
