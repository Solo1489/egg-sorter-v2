---
tags: [egg-sorter, threejs, 3d-model]
created: 2026-11-15
updated: 2026-11-15
type: project
---
[[2026-11-15]]

# Egg — เครื่องคัดแยกไข่อัตโนมัติ v2

เว็บโมเดล 3D ของเครื่องคัดแยกไข่ (ถาดป้อน → ตู้ AI → กล่องชั่ง → ถาด เสีย / A / B) สร้างจากสเปกใน `3d-spec/` ใช้ตรวจขนาด ตำแหน่ง และจังหวะการทำงานของกลไกก่อนสร้างเครื่องจริง

## โครงสร้าง

| โฟลเดอร์ | เนื้อหา |
| --- | --- |
| `3d-spec/` | สเปกของโมเดล: `README.md`, `parts.json`, `animation.json`, `preview.png`, `tools/` (สคริปต์ Python ที่สร้างและตรวจไฟล์) |
| `web3d/` | เว็บ Vite + vanilla JS + Three.js ที่อ่านสเปกแล้วสร้างโมเดล |
| `specs/` | เอกสารออกแบบที่ตกลงแล้วแต่ยังไม่ได้ใส่ลง `3d-spec/` (ดูรายการด้านล่าง) |

## งานออกแบบที่รอลงมือ

- [specs/reject-ramp-redesign.md](specs/reject-ramp-redesign.md) — บาน F1 ยาวบานพับซ้าย + ทางลาดไข่เสีย + ย้าย load cell / K2 / ราง (ล็อกแบบ 2026-11-16) ต้องอ่านก่อนแก้ `3d-spec/tools/*.py`
- [specs/curved-guide-wall.md](specs/curved-guide-wall.md) — ผนังโค้งนำไข่แทนครีบเฉียงในแอ่งปลายรางทั้ง 3 ราง (ร่าง 2026-11-17 รอตอบคำถาม Q1–Q4)

## วิธีรัน

```
cd web3d
npm install
npm run dev      # เปิดเว็บ (เล่น demo_playlist อัตโนมัติ)
npm run verify   # self-check สเปก + เทียบตำแหน่ง mesh และ timeline แอนิเมชันกับสเปก (ไม่ต้องเปิดเบราว์เซอร์)
```

ตัวเลือกใน URL สำหรับตรวจงาน เช่น `?program=F_good_A&t=6.6&ghost=1` (หยุดที่เวลานั้น), `?state=insert.A:OUT`, `?view=front|side|top|iso`, `?focus=x,y,z&zoom=3`, `?states=1` (ป้ายสถานะกลไก), `?ui=0` (ซ่อนแผงควบคุม) ดูรายการเต็มที่ต้น `web3d/src/main.js`

หลังแก้ `3d-spec/tools/gen.py` ให้รัน `gen.py` → `anim.py` → `check.py` → `render.py` ตามลำดับ แล้วรัน `npm run verify`

## AI Agent Rules

1. `3d-spec/` เป็นแหล่งข้อมูลเดียวของโมเดล และ **อ่านอย่างเดียว** ห้ามแก้จากฝั่ง `web3d/` ถ้าสเปกผิดให้แจ้งผู้ใช้
2. ห้าม hardcode ขนาดหรือตำแหน่งชิ้นส่วนในโค้ด ทุกค่าต้องมาจาก `3d-spec/*.json`
3. อ่าน `3d-spec/README.md` ก่อนแก้โค้ดที่เกี่ยวกับพิกัด รูปทรง กลุ่มที่ขยับได้ หรือแอนิเมชัน
4. สร้างทีละโมดูล (base → input → ai → scale → output → display) โดยปรับ `BUILD_THROUGH_MODULE` ใน `web3d/src/config.js` และไปโมดูลถัดไปเมื่อ `npm run verify` ผ่านเท่านั้น ถ้าไม่ผ่านให้หยุดแล้วแจ้งผู้ใช้
