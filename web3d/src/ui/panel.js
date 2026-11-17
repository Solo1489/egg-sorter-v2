// แผงควบคุม (lil-gui): การเล่น, มุมกล้อง, การแสดงผล, actuator, ไฟ, ชุดราง/ฝาตู้
import GUI from 'lil-gui';
import { listPrograms } from '../animation/compile.js';
import { SPEED_RANGE } from '../animation/player.js';
import { VIEW_NAMES } from '../cameraPresets.js';

const VIEW_LABELS = { front: 'หน้า', side: 'ข้าง (+X)', top: 'บน', iso: 'iso' };
/** กลุ่มที่เป็นการถอด/ดึงชิ้นส่วน ไม่ใช่ actuator ที่โปรแกรมสั่ง */
const isServiceGroup = (groupId) => groupId.startsWith('insert.') || groupId === 'ai.window';

function addPlaybackFolder(gui, { player, animationSpec }) {
  const folder = gui.addFolder('เล่นแอนิเมชัน');
  const programOptions = Object.fromEntries(listPrograms(animationSpec).map(({ id, label }) => [label, id]));

  let timeControl;
  folder
    .add(player.state, 'programId', programOptions)
    .name('ลำดับ')
    .onChange((programId) => {
      player.load(programId);
      timeControl.max(player.state.duration).updateDisplay();
    });

  const actions = {
    toggle() {
      if (player.state.playing) player.pause();
      else player.play();
    },
    restart() {
      player.seek(0);
      player.play();
    },
  };
  folder.add(actions, 'toggle').name('▶ เล่น / ⏸ หยุด');
  folder.add(actions, 'restart').name('⏮ เริ่มใหม่');
  timeControl = folder
    .add(player.state, 'time', 0, player.state.duration, 0.01)
    .name('เวลา (วินาที)')
    .listen()
    .onChange((time) => {
      player.pause();
      player.seek(time);
    });
  folder.add(player.state, 'speed', SPEED_RANGE.min, SPEED_RANGE.max, SPEED_RANGE.step).name('ความเร็ว (เท่า)');
  folder.add(player.state, 'loop').name('เล่นวนซ้ำ');
}

function addCameraFolder(gui, sceneContext) {
  const folder = gui.addFolder('มุมกล้อง');
  for (const viewName of VIEW_NAMES) {
    folder.add({ go: () => sceneContext.setView(viewName) }, 'go').name(VIEW_LABELS[viewName] ?? viewName);
  }
  // คำแนะนำการใช้เมาส์ (ปุ่มนี้ไม่ทำอะไร)
  folder.add({ hint() {} }, 'hint').name('ล้อเมาส์ = ซูมเข้าหาจุดที่ชี้ · ดับเบิลคลิก = ย้ายจุดหมุน').disable();
  folder.close();
}

function addDisplayFolder(gui, { machine, visibility, pivotGizmos, labels, dimensions, initial }) {
  const folder = gui.addFolder('การแสดงผล');
  const settings = {
    ghost: initial.ghost,
    edges: true,
    gizmos: initial.gizmos,
    names: initial.labels,
    states: initial.stateLabels,
    dimensions: initial.dimensions,
    dimensionDetail: initial.dimensionDetail,
  };
  folder.add(settings, 'ghost').name('โหมดโปร่งใส').onChange(machine.materials.setGhostMode);
  folder.add(settings, 'names').name('ป้ายชื่อโมดูล').onChange(labels.setNamesVisible);
  folder.add(settings, 'states').name('ป้ายสถานะกลไก').onChange(labels.setStatesVisible);
  folder.add(settings, 'dimensions').name('เส้นวัดระยะ (ขนาดรวม)').onChange(dimensions.setOverallVisible);
  folder
    .add(settings, 'dimensionDetail')
    .name('เส้นวัดละเอียด (โมดูล / ชุดราง)')
    .onChange(dimensions.setDetailVisible);
  folder.add(settings, 'edges').name('เส้นขอบชิ้นส่วน').onChange(visibility.setEdgesVisible);
  folder
    .add(settings, 'gizmos')
    .name('แกนของกลุ่มที่ขยับได้')
    .onChange((isVisible) => {
      pivotGizmos.visible = isVisible;
    });

  const moduleFolder = folder.addFolder('แสดงโมดูล');
  for (const module of machine.modules) {
    moduleFolder
      .add({ visible: true }, 'visible')
      .name(module)
      .onChange((isVisible) => visibility.setModuleVisible(module, isVisible));
  }
  moduleFolder.close();

  const wallFolder = folder.addFolder('ซ่อนผนัง');
  for (const module of visibility.modulesWithWalls()) {
    wallFolder
      .add({ hidden: false }, 'hidden')
      .name(module)
      .onChange((isHidden) => visibility.setWallsHidden(module, isHidden));
  }
  wallFolder.close();
}

/** ปุ่มเลือกสถานะของกลุ่ม: ผูกกับ stateModel แบบ listen เพื่อให้ตามแอนิเมชันด้วย */
function addGroupControls(folder, groupIds, { machine, player, stateModel }) {
  for (const groupId of groupIds) {
    const { spec, motion } = machine.motionGroups.get(groupId);
    const control = folder
      .add(stateModel, groupId, Object.keys(motion.states))
      .name(groupId)
      .listen()
      .onChange((stateName) => {
        player?.pause(); // สั่งเองแล้วหยุดเล่น เพื่อไม่ให้ timeline ทับสถานะที่เลือก
        machine.controller.setState(groupId, stateName);
      });
    control.domElement.title = spec.name;
  }
}

/**
 * @param {object} context { machine, sceneContext, visibility, pivotGizmos, labels, lights,
 *                           player, animationSpec, stateModel, initial }
 *   stateModel = { groupId: ชื่อสถานะ } ที่ main.js อัปเดตทุกเฟรม
 */
export function createPanel(context) {
  const { machine, lights, player, stateModel } = context;
  const gui = new GUI({ title: 'เครื่องคัดแยกไข่ v2' });

  if (player) addPlaybackFolder(gui, context);
  addCameraFolder(gui, context.sceneContext);
  addDisplayFolder(gui, context);

  const groupIds = [...machine.motionGroups.keys()].filter((groupId) => !machine.controller.isFollower(groupId));
  const actuatorFolder = gui.addFolder('Actuators (สลับสถานะ)');
  addGroupControls(
    actuatorFolder,
    groupIds.filter((groupId) => !isServiceGroup(groupId)),
    context,
  );
  actuatorFolder.add(
    {
      reset() {
        player?.pause();
        machine.controller.setAllToDefault({ immediate: false });
        lights.setAllToDefault();
      },
    },
    'reset',
  ).name('รีเซ็ตเป็นค่าเริ่มต้น');
  actuatorFolder.close();

  if (lights.ids.length > 0) {
    const lightFolder = gui.addFolder('ไฟ');
    for (const lightId of lights.ids) {
      lightFolder
        .add(lights.states, lightId, lights.stateNames(lightId))
        .listen()
        .onChange((stateName) => {
          player?.pause();
          lights.setState(lightId, stateName);
        });
    }
    lightFolder.close();
  }

  const serviceFolder = gui.addFolder('ชุดราง / ฝาตู้ AI');
  addGroupControls(serviceFolder, groupIds.filter(isServiceGroup), { ...context, player: null });
  return gui;
}
