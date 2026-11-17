// ค่าคงที่ของแอป ไม่มีขนาดชิ้นส่วนอยู่ในนี้ ขนาดทั้งหมดมาจาก 3d-spec/*.json

/** README §1: สเปกเป็น มม. แปลงเป็นเมตรด้วย root.scale */
export const MM_TO_M = 0.001;

/** README §4: actuator เปลี่ยนสถานะแบบ tween ประมาณ 0.2 วินาที */
export const ACTUATOR_TWEEN_SECONDS = 0.2;

/** ค่าคลาดเคลื่อนสูงสุดที่ยอมรับตอนเทียบ mesh กับสเปก */
export const VERIFY_TOLERANCE_MM = 0.01;

/**
 * งานทำทีละโมดูล (base → input → ai → scale → output → display)
 * สร้างถึงโมดูลนี้ แล้วขยับต่อเมื่อ verify ผ่าน
 */
export const BUILD_THROUGH_MODULE = 'display';

/** ชิ้นที่นับเป็น "ผนัง" สำหรับปุ่มซ่อนผนังรายโมดูล (ดูจากรูปแบบ id) */
export const WALL_ID_PATTERN = /\.wall\.|\.(roof|lid|divider)$/;

/** opacity สูงสุดของอะคริลิกในโหมดโปร่งใส */
export const GHOST_OPACITY = 0.15;

/** มุมกล้อง iso เดียวกับ tools/render.py (matplotlib elev/azim) */
export const PREVIEW_ISO_VIEW = { elevDeg: 24, azimDeg: -58 };

/** จำนวนเหลี่ยมของทรงกระบอก ต้องหาร 4 ลงตัวเพื่อให้ bbox ตรงกับรัศมีจริง */
export const CYLINDER_RADIAL_SEGMENTS = 32;
