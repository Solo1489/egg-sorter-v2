// ซ่อน/แสดงชิ้นส่วนตามโมดูล, ซ่อนผนังรายโมดูล และเส้นขอบ

export function createVisibilityController(machine) {
  const hiddenModules = new Set();
  const modulesWithHiddenWalls = new Set();

  function refresh() {
    for (const { mesh } of machine.partNodes.values()) {
      const { module, isWall } = mesh.userData;
      mesh.visible = !hiddenModules.has(module) && !(isWall && modulesWithHiddenWalls.has(module));
    }
  }

  function toggle(set, module, isOn) {
    if (isOn) set.add(module);
    else set.delete(module);
    refresh();
  }

  return {
    setModuleVisible: (module, isVisible) => toggle(hiddenModules, module, !isVisible),
    setWallsHidden: (module, isHidden) => toggle(modulesWithHiddenWalls, module, isHidden),
    setEdgesVisible(isVisible) {
      machine.root.traverse((object) => {
        if (object.userData.isEdgeOutline) object.visible = isVisible;
      });
    },
    /** โมดูลที่มีชิ้นส่วนประเภทผนังอย่างน้อยหนึ่งชิ้น */
    modulesWithWalls() {
      const modules = new Set();
      for (const { mesh } of machine.partNodes.values()) {
        if (mesh.userData.isWall) modules.add(mesh.userData.module);
      }
      return machine.modules.filter((module) => modules.has(module));
    },
  };
}
