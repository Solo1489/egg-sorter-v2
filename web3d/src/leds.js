// README §4: light.* สลับ emissive ของชิ้น LED ตาม animation.json → lights

/**
 * @param {object} machine ผลจาก buildMachine()
 * @param {object} lightsSpec animation.json → lights { lightId: { parts, states, default } }
 */
export function createLightController(machine, lightsSpec = {}) {
  const lights = new Map();

  for (const [lightId, spec] of Object.entries(lightsSpec)) {
    const materials = [];
    for (const partId of spec.parts) {
      const node = machine.partNodes.get(partId);
      if (!node) continue; // โมดูลของชิ้นนี้ยังไม่ได้สร้าง
      // วัสดุ led ใช้ร่วมกันทุกชิ้น จึงต้องโคลนให้แต่ละดวงเปิด/ปิดแยกกันได้
      node.mesh.material = node.mesh.material.clone();
      materials.push(node.mesh.material);
    }
    if (materials.length === 0) continue;
    const onIntensity = materials[0].emissiveIntensity;
    lights.set(lightId, { spec, materials, onIntensity });
  }

  const states = {};

  function setState(lightId, stateName) {
    const light = lights.get(lightId);
    if (!light || states[lightId] === stateName) return;
    states[lightId] = stateName;
    const intensity = stateName === 'ON' ? light.onIntensity : 0;
    for (const material of light.materials) material.emissiveIntensity = intensity;
  }

  function setAllToDefault() {
    for (const [lightId, { spec }] of lights) setState(lightId, spec.default ?? 'OFF');
  }

  setAllToDefault();
  return {
    ids: [...lights.keys()],
    /** สถานะปัจจุบัน { lightId: 'ON' | 'OFF' } (แผงควบคุมผูกกับ object นี้) */
    states,
    stateNames: (lightId) => lights.get(lightId)?.spec.states ?? ['OFF', 'ON'],
    setState,
    setAllToDefault,
  };
}
