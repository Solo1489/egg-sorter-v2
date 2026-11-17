// ป้ายข้อความในฉาก (CSS2D): ป้ายชื่อจาก parts.json → labels และป้ายสถานะของกลุ่มที่ขยับได้
import * as THREE from 'three';
import { CSS2DObject, CSS2DRenderer } from 'three/addons/renderers/CSS2DRenderer.js';

/** ป้ายข้อความ CSS2D (ใช้ร่วมกับเส้นวัดระยะใน dimensions.js) */
export function createLabel(text, className) {
  const element = document.createElement('div');
  element.className = `scene-label ${className}`;
  element.textContent = text;
  return new CSS2DObject(element);
}

/** จุดวางป้ายสถานะ: จุดหมุน (rotate/spin) หรือจุดกึ่งกลางของชิ้นในกลุ่ม (translate) ในพิกัดสเปก */
function anchorOf(motionGroup, partNodes) {
  if (motionGroup.motion.type !== 'translate') return motionGroup.carriers[0].home.clone();
  const centroid = new THREE.Vector3();
  for (const partId of motionGroup.spec.parts) centroid.add(partNodes.get(partId).origin);
  return centroid.divideScalar(motionGroup.spec.parts.length);
}

/**
 * @param {HTMLElement} container กล่องเดียวกับ canvas
 * @param {object} machine ผลจาก buildMachine()
 * @param {Array<{text, pos}>} labelSpecs parts.json → labels
 */
export function createLabelLayer(container, machine, labelSpecs) {
  const renderer = new CSS2DRenderer();
  renderer.domElement.className = 'label-layer';
  container.append(renderer.domElement);

  const nameLabels = labelSpecs.map(({ text, pos }) => {
    const label = createLabel(text, 'scene-label--name');
    label.position.set(...pos);
    machine.root.add(label);
    return label;
  });

  const stateLabels = [];
  for (const [groupId, motionGroup] of machine.motionGroups) {
    if (motionGroup.motion.follows) continue;
    const label = createLabel(groupId, 'scene-label--state');
    label.position.copy(anchorOf(motionGroup, machine.partNodes));
    machine.root.add(label);
    stateLabels.push({ groupId, label, text: '' });
  }

  const setVisible = (labels, isVisible) => {
    for (const label of labels) label.visible = isVisible;
  };

  function resize() {
    renderer.setSize(container.clientWidth, container.clientHeight);
  }
  window.addEventListener('resize', resize);
  resize();

  return {
    setNamesVisible: (isVisible) => setVisible(nameLabels, isVisible),
    setStatesVisible: (isVisible) => setVisible(stateLabels.map(({ label }) => label), isVisible),
    /** @param {(groupId: string) => string} stateNameOf */
    updateStates(stateNameOf) {
      for (const entry of stateLabels) {
        if (!entry.label.visible) continue;
        const text = `${entry.groupId}: ${stateNameOf(entry.groupId) ?? '-'}`;
        if (text !== entry.text) {
          entry.text = text;
          entry.label.element.textContent = text;
        }
      }
    },
    render: (scene, camera) => renderer.render(scene, camera),
  };
}
