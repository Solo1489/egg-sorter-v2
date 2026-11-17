// ดัชนีค้นหาจาก parts.json (ไม่ขึ้นกับ DOM ใช้ได้ทั้งในเบราว์เซอร์และ Node)

export function createSpecIndex(partsSpec) {
  const partsById = new Map(partsSpec.parts.map((part) => [part.id, part]));
  const groupsById = new Map(partsSpec.groups.map((group) => [group.id, group]));

  const groupIdOfPart = new Map();
  const followerIdsOf = new Map();
  for (const group of partsSpec.groups) {
    for (const partId of group.parts) groupIdOfPart.set(partId, group.id);
    const leaderId = group.motion.follows;
    if (leaderId) {
      if (!followerIdsOf.has(leaderId)) followerIdsOf.set(leaderId, []);
      followerIdsOf.get(leaderId).push(group.id);
    }
  }

  // ลำดับโมดูลตามที่ปรากฏใน parts[] (base → input → ai → scale → output → display)
  const moduleOrder = [...new Set(partsSpec.parts.map((part) => part.module))];

  return { partsById, groupsById, groupIdOfPart, followerIdsOf, moduleOrder };
}

/** รายชื่อโมดูลตั้งแต่ตัวแรกจนถึง lastModule (รวม) */
export function modulesThrough(moduleOrder, lastModule) {
  const lastIndex = moduleOrder.indexOf(lastModule);
  if (lastIndex === -1) throw new Error(`ไม่พบโมดูล "${lastModule}" ใน parts.json`);
  return moduleOrder.slice(0, lastIndex + 1);
}
