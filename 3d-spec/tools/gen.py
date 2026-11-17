"""Generate 3D spec (parts.json, animation.json) for the egg sorter v2.
Frame: mm, X = flow (left->right), Y = front->back, Z = up. Origin: X0 left end of input
tray, Y0 front face of main rail, Z0 table top.
"""
import os
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

import json, math, os

t = lambda d: math.tan(math.radians(d))
s = lambda d: math.sin(math.radians(d))
c = lambda d: math.cos(math.radians(d))
R1 = lambda v: round(v, 1)

# ไข่ออกแบบ: ไข่ไก่เบอร์ 0 (≥ 70 g) ถึงราว 80 g ทุกรูปทรง + เผื่อ ; ช่องลอดและระยะทั้งหมดคิดจากขนาดนี้
EGG_B, EGG_L = 48.0, 65.0               # เส้นผ่านศูนย์กลาง × ความยาว (มม.)
# แกน Y: ผนังหน้า Y 0–5 | เลนหน้า | ผนังกลาง | เลนหลัง | ผนังหลัง
LANE_W = 74.0                           # ความกว้างเลน (ไข่ยาว 65 เหลือช่องข้างละ 4.5)
DIV_W = 5.0                             # ผนังกลางระหว่างเลน
LANE_Y = {"F": (5.0, 5.0 + LANE_W), "B": (5.0 + LANE_W + DIV_W, 5.0 + 2 * LANE_W + DIV_W)}
LANE = {k: (a + b) / 2 for k, (a, b) in LANE_Y.items()}   # กึ่งกลางเลน
Y_DIV = (LANE_Y["F"][1], LANE_Y["B"][0])                  # ผนังกลาง
Y_IN = LANE_Y["B"][1]                    # ขอบหลังของเลนหลัง = ผิวในของผนังหลัง
YB = Y_IN + 5.0                          # ผิวนอกด้านหลังของตัวเครื่อง (เดิม 151)
Y_MID = (Y_DIV[0] + Y_DIV[1]) / 2        # กึ่งกลางเครื่องตามแกน Y
POSTS = {"f": (0, 5), "m": Y_DIV, "b": (Y_IN, YB)}        # เสาข้างช่องเปิดของตู้
SPAN = LANE_W / 2 - 3                    # ครึ่งความกว้างของบาน/แท่น/สไลด์ที่ขวางเลน (เว้นข้างละ 3)
ROLLER_L = LANE_W - 3                    # ความยาวลูกกลิ้ง

parts, groups, labels = [], [], []

def add(p):
    for k in ("min", "max", "center", "pivot"):
        if k in p:
            p[k] = [R1(v) for v in p[k]]
    if "points" in p:
        p["points"] = [[R1(a), R1(b)] for a, b in p["points"]]
    if "extrude" in p:
        p["extrude"] = [R1(v) for v in p["extrude"]]
    parts.append(p)
    return p["id"]

def box(id, mod, name, mn, mx, mat, **kw):
    return add(dict(id=id, module=mod, name=name, shape="box", min=list(mn), max=list(mx), material=mat, **kw))

def cyl(id, mod, name, center, r, L, axis, mat, **kw):
    return add(dict(id=id, module=mod, name=name, shape="cylinder", center=list(center), radius=r, length=L, axis=axis, material=mat, **kw))

def prism(id, mod, name, plane, pts, ext, mat, **kw):
    return add(dict(id=id, module=mod, name=name, shape="prism", plane=plane, points=[list(p) for p in pts], extrude=list(ext), material=mat, **kw))

def servo(id, mod, name, shaft, side, length_dir=+1):
    """MG90S: shaft axis along Y. side='front' -> body outside wall Y -22.7..0 ;
    'back' -> Y YB..YB+22.7 ; or (y0, y1) explicit. Body 22.8 (X) x 12.2 (Z)."""
    sx, _, sz = shaft
    x0, x1 = (sx - 6, sx + 16.8) if length_dir > 0 else (sx - 16.8, sx + 6)
    if side == "front":
        y0, y1 = -22.7, 0.0
    elif side == "back":
        y0, y1 = YB, YB + 22.7
    else:
        y0, y1 = side
    return box(id, mod, name, (x0, y0, sz - 6.1), (x1, y1, sz + 6.1), "servo")

MG996R = (40.7, 19.7, 42.9)   # ยาว (X) × กว้าง (Z) × สูงรวมแกน (ตามแกนเพลา Y) ; แกนเพลาห่างปลายตัว 10 มม.

def servo_mg996r(id, mod, name, shaft, side, length_dir=+1):
    """MG996R: แกนเพลาตาม Y, ตัวเซอร์โวอยู่นอกผนัง (front: Y −42.9..0 / back: YB..YB+42.9)"""
    sx, _, sz = shaft
    L, W, H = MG996R
    x0, x1 = (sx - 10, sx + L - 10) if length_dir > 0 else (sx - L + 10, sx + 10)
    y0, y1 = (-H, 0.0) if side == "front" else (YB, YB + H)
    return box(id, mod, name, (x0, y0, sz - W / 2), (x1, y1, sz + W / 2), "servo")

def group(id, part_ids, motion, name):
    groups.append(dict(id=id, name=name, parts=part_ids, motion=motion))

# ------------------------------------------------------------------ ผิวราง + ทางลงแบบโค้งรับเข้าพื้น
# ผิวโฟมราง: Z ที่ Y 0 และความชันหลัง/หน้า
#  - หลัง 12° → 9° → 5° (2026-11-16: K2 ต่ำลงตามแท่นชั่งใหม่ ไข่เลนหลังในราง A ต้องลอดใต้สะพาน K2→B)
#  - z0 24.1 → 22.0 (พื้นอะคริลิกถาดหน้ายังสูงกว่าแผ่นฐาน) เพิ่มที่ว่างใต้สะพาน B
CHUTE = {"z0": 22.0, "slope_back_deg": 5, "slope_front_deg": 4}
CHUTE_REJECT = dict(CHUTE)
ztop_of = lambda ch: (lambda y: ch["z0"] + y * t(ch["slope_back_deg"] if y >= 0 else ch["slope_front_deg"]))
Ztop = ztop_of(CHUTE)
Ztop_rej = ztop_of(CHUTE_REJECT)

# ทางลงทุกรางจบแบบ "โค้งรับเข้าพื้น": ต่อจากบาน/สะพานด้วยแผ่นเรียบ RUNOUT_N ท่อนที่ความชันลดลงทีละเท่าๆ กัน
# จนแนบพื้นที่ร่อง X = G ไข่จึงเปลี่ยนทิศทีละน้อย (มุมหักแต่ละจุด = a/(N+1)) แทนการกระแทกพื้นทีเดียว
RUNOUT_N = 3
GAP_PLATE_FIXED = 1.5        # ช่องปลายบานที่ขยับได้ ถึงแผ่นรับตายตัว (≤ 2)

def runout(start, a, floor, G, n=RUNOUT_N):
    """ผิวบนของแผ่นรับ: จาก start ที่ลาด a (องศา ลบ = ลง) ถึง (G, floor) ด้วย n ท่อนช่วงยาวเท่ากัน
    มุมท่อนที่ i = k·a·(n+1−i)/(n+1) ; หา k ให้ลงถึงพื้นพอดี (k = 1 คือหักมุมเท่ากันทุกจุด)"""
    sx, sz = start
    w = (G - sx) / n
    drop = sz - floor
    lo, hi = 0.0, 2.5
    for _ in range(60):
        k = (lo + hi) / 2
        d = sum(w * t(k * a * (n + 1 - i) / (n + 1)) for i in range(1, n + 1))   # ลบ
        lo, hi = (k, hi) if -d < drop else (lo, k)
    pts, (x, z) = [(sx, sz)], (sx, sz)
    for i in range(1, n + 1):
        x, z = x + w, z + w * t(k * a * (n + 1 - i) / (n + 1))
        pts.append((x, z))
    pts[-1] = (G, floor)
    return pts, k

def plate_tip(pivot, length, a):
    return (pivot[0] + length * c(a), pivot[1] + length * s(a))

def runout_len(start, a, floor, n=RUNOUT_N):
    """ความยาวตาม X ของแผ่นรับเมื่อ k = 1"""
    return n * (start[1] - floor) / -sum(t(a * (n + 1 - i) / (n + 1)) for i in range(1, n + 1))

def solve_plate_angle(pivot, length, floor, G, lo=-60.0, hi=-15.0, n=RUNOUT_N):
    """มุมบานที่ทำให้แผ่นรับ (k = 1) ต่อจากปลายบานไปจบที่ร่อง X = G พอดี"""
    f = lambda a: plate_tip(pivot, length, a)[0] + runout_len(plate_tip(pivot, length, a), a, floor, n) - G
    for _ in range(60):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if f(m) * f(lo) > 0 else (lo, m)
    return round((lo + hi) / 2, 1)

# ------------------------------------------------------------------ materials
materials = {
    "base":           {"color": "#d9dde2", "opacity": 1.0, "roughness": 0.8},
    "acrylic_clear":  {"color": "#dbe8f2", "opacity": 0.28, "roughness": 0.05, "note": "อะคริลิกใส"},
    "acrylic_black":  {"color": "#1c1d22", "opacity": 0.45, "roughness": 0.2, "note": "อะคริลิกดำทึบ (โปร่งแสงในโมเดลเพื่อให้เห็นข้างใน ปรับ opacity=1 ได้)"},
    "acrylic_white":  {"color": "#f1f2f4", "opacity": 1.0, "roughness": 0.5},
    "printed":        {"color": "#e07b39", "opacity": 1.0, "roughness": 0.6, "note": "ชิ้นพิมพ์ 3D (PETG)"},
    "silicone":       {"color": "#8f969e", "opacity": 1.0, "roughness": 0.9, "note": "ลูกกลิ้งหุ้มยาง"},
    "metal":          {"color": "#b8bcc2", "opacity": 1.0, "metalness": 0.8, "roughness": 0.3},
    "load_cell":      {"color": "#c9cdd2", "opacity": 1.0, "metalness": 0.7, "roughness": 0.35},
    "servo":          {"color": "#26282e", "opacity": 1.0, "roughness": 0.5},
    "motor":          {"color": "#c7a76b", "opacity": 1.0, "metalness": 0.6, "roughness": 0.4},
    "pcb_green":      {"color": "#1f6f3a", "opacity": 1.0, "roughness": 0.6},
    "pcb_blue":       {"color": "#1d4fa0", "opacity": 1.0, "roughness": 0.6},
    "pcb_black":      {"color": "#202020", "opacity": 1.0, "roughness": 0.6},
    "psu":            {"color": "#9ea3a8", "opacity": 1.0, "metalness": 0.6, "roughness": 0.4},
    "sensor":         {"color": "#111111", "opacity": 1.0, "roughness": 0.6},
    "led":            {"color": "#ffffff", "opacity": 1.0, "emissive": "#fff6e0", "emissiveIntensity": 1.5},
    "screen_body":    {"color": "#0d0d0f", "opacity": 1.0, "roughness": 0.3},
    "screen_face":    {"color": "#123a6b", "opacity": 1.0, "emissive": "#1e5aa8", "emissiveIntensity": 0.6},
    "button_red":     {"color": "#d32f2f", "opacity": 1.0, "emissive": "#ff3b30", "emissiveIntensity": 0.4},
    "button_green":   {"color": "#2e9d3a", "opacity": 1.0, "emissive": "#2ecc40", "emissiveIntensity": 0.4},
    "eva_reject":     {"color": "#b8483a", "opacity": 1.0, "roughness": 0.95, "note": "โฟม EVA ถาดเสีย"},
    "eva_A":          {"color": "#3a7bd5", "opacity": 1.0, "roughness": 0.95, "note": "โฟม EVA ถาด A"},
    "eva_B":          {"color": "#3aa66b", "opacity": 1.0, "roughness": 0.95, "note": "โฟม EVA ถาด B"},
    "egg":            {"color": "#f1e3cf", "opacity": 1.0, "roughness": 0.7},
}

# ------------------------------------------------------------------ base
# แผ่นฐานสร้างหลังโมดูล output (X_END ขึ้นกับตำแหน่งราง B) แล้วย้ายไปเป็นชิ้นแรก

# ------------------------------------------------------------------ module 1: input + electronics bay
M = "input"
Ztray = lambda x: 123.4 + (180 - x) * t(6)       # tray floor top
box("bay.wall.front", M, "ผนังหน้าช่องอิเล็กทรอนิกส์ (แผงปุ่ม)", (0, 0, 5), (180, 3, 118), "acrylic_white")
box("bay.wall.back", M, "ผนังหลังช่องอิเล็กทรอนิกส์", (0, YB - 3, 5), (180, YB, 118), "acrylic_white")
box("bay.wall.left", M, "ผนังซ้ายช่องอิเล็กทรอนิกส์", (0, 3, 5), (3, YB - 3, 118), "acrylic_white")
box("bay.wall.right", M, "ผนังขวาช่องอิเล็กทรอนิกส์", (177, 3, 5), (180, YB - 3, 118), "acrylic_white")
prism("tray.floor", M, "พื้นถาดป้อน เอียง 6°", "xz",
      [(5, Ztray(5)), (180, Ztray(180)), (180, Ztray(180) - 5), (5, Ztray(5) - 5)], (5, Y_IN), "acrylic_clear",
      note="เจาะร่อง 8×20 มม. ให้หมุดก้ามปู escapement เลนละ 4 ร่อง (กลางเลน ±13 มม.) ที่ X 118.5 และ 168 ร่อง P2 ยาวพอให้ปรับ P2 ได้ X 114–124")
prism("tray.wall.front", M, "ผนังหน้าถาดป้อน (สูงจากพื้น 18)", "xz",
      [(0, 118), (180, 118), (180, Ztray(180) + 18), (0, Ztray(0) + 18)], (0, 5), "acrylic_clear")
prism("tray.wall.back", M, "ผนังหลังถาดป้อน (สูงจากพื้น 45)", "xz",
      [(0, 118), (180, 118), (180, Ztray(180) + 45), (0, Ztray(0) + 45)], (Y_IN, YB), "acrylic_clear")
prism("tray.wall.mid", M, "ผนังกลางถาดป้อน", "xz",
      [(5, Ztray(5)), (180, Ztray(180)), (180, Ztray(180) + 25), (5, Ztray(5) + 25)], Y_DIV, "acrylic_clear")
box("tray.wall.end", M, "ผนังปิดท้ายถาดป้อน", (0, 5, 118), (5, Y_IN, Ztray(0) + 18), "acrylic_clear")

# escapement แบบก้ามปู: แต่ละประตูเป็นหมุดคู่ห่างกัน 2×ESC_PIN_DY ขวางเลน ไข่พิงสองจุดจึงตั้งฉากกับเลนเอง
# (หมุดเดี่ยวกลางเลนแตะไข่จุดเดียว ไข่หมุนเฉียงได้) คานกระดกเป็นรูปตัว H มีคานขวางรับหมุดที่ปลายทั้งสอง
ESC_PIN_DY = 13.0        # ระยะหมุดจากกลางเลน (หมุดคู่ห่างกัน 26)
ESC_PIN_R = 3.0
ESC_BAR_W = 4.5          # ความกว้างคานขวาง (แกน X) แคบพอให้ปลายฝั่ง P1 ไม่ชนเซอร์โวตอนกระดก
ESC_X_P1 = 168.0
# P2 = ค่ากลางที่ใช้ได้กับไข่เบอร์ 5 ถึงไข่ออกแบบ: ไม่แตะไข่ฟองแรก (≤ 119.6) และอยู่หน้ากึ่งกลางไข่ฟองที่ 2 ≥ 5 มม. (≥ 117.2)
ESC_X_P2 = 118.5
ESC_P2_ADJ = (114.0, 124.0)             # ร่องปรับตำแหน่ง P2 บนคานขวาง ใช้จูนกับไข่จริง
ESC_PIVOT_X = (ESC_X_P2 + ESC_X_P1) / 2          # จุดหมุนอยู่กลาง แขนสองข้างยาวเท่ากัน
ESC_TRAVEL = 8.0         # หมุดขึ้นลง ±8: HOLD/RELEASE = ปลายหมุดสูงกว่าพื้น 15 / ต่ำกว่าพื้น 1
ESC_DEG = round(math.degrees(math.asin(ESC_TRAVEL / (ESC_X_P1 - ESC_PIVOT_X))), 1)  # มุมกระดกที่ทำให้ปลายแขนขึ้นลง ±8
ESC_END = 3.0            # คานยื่นเลยหมุดออกไปทางปลาย
for L, yc in LANE.items():
    tipP2 = Ztray(ESC_X_P2) + 7
    tipP1 = Ztray(ESC_X_P1) + 7
    half = ESC_PIN_DY + ESC_PIN_R                  # คานขวางยาวคลุมหมุดทั้งสองตัว
    x0, x1 = ESC_P2_ADJ[0] - ESC_PIN_R, ESC_X_P1 + ESC_END   # คานขวาง P2 กว้างคลุมช่วงปรับ
    xa, xb = ESC_P2_ADJ[1] + ESC_PIN_R, x1 - ESC_BAR_W
    lane_name = 'หน้า' if L == 'F' else 'หลัง'
    # ชิ้นพิมพ์รูปตัว H ชิ้นเดียว แยกเป็นกล่อง 3 กล่อง (คานกลาง + คานขวาง 2 ปลาย) เพราะ check.py รองรับเฉพาะรูปทรงนูน
    rk = [box(f"esc.{L}.rocker", M, f"คานกระดก escapement เลน{lane_name} (คานกลางของตัว H)", (xa, yc - 3, 105.5), (xb, yc + 3, 110.5), "printed"),
          box(f"esc.{L}.rocker.barP2", M, f"คานขวางรับหมุดคู่ P2 (ร่องปรับ X {ESC_P2_ADJ[0]:g}–{ESC_P2_ADJ[1]:g})", (x0, yc - half, 105.5), (xa, yc + half, 110.5), "printed"),
          box(f"esc.{L}.rocker.barP1", M, "คานขวางรับหมุดคู่ P1", (xb, yc - half, 105.5), (x1, yc + half, 110.5), "printed")]
    group(f"esc.{L}", rk, {"type": "rotate", "pivot": [ESC_PIVOT_X, yc, 108], "axis": [0, -1, 0],
                             "states": {"HOLD": ESC_DEG, "RELEASE": -ESC_DEG}, "default": "HOLD",
                             "note": "บวก = ฝั่ง +X ยกขึ้น ; หมุดคู่ P1/P2 เลื่อนแนวตั้งตาม (กลุ่ม esc.*.p1 / p2)"},
          f"escapement เลน {L}")
    p2 = [cyl(f"esc.{L}.pinP2{sfx}", M, f"หมุด P2 (ประตูหลัง) {side}", (ESC_X_P2, yc + dy, (110.5 + tipP2) / 2), ESC_PIN_R, tipP2 - 110.5, "z", "metal")
          for sfx, side, dy in (("a", "ฝั่งหน้า", -ESC_PIN_DY), ("b", "ฝั่งหลัง", ESC_PIN_DY))]
    p1 = [cyl(f"esc.{L}.pinP1{sfx}", M, f"หมุด P1 (ประตูหน้า) {side}", (ESC_X_P1, yc + dy, (110.5 + tipP1) / 2), ESC_PIN_R, tipP1 - 110.5, "z", "metal")
          for sfx, side, dy in (("a", "ฝั่งหน้า", -ESC_PIN_DY), ("b", "ฝั่งหลัง", ESC_PIN_DY))]
    group(f"esc.{L}.p1", p1, {"type": "translate", "axis": [0, 0, 1], "states": {"HOLD": ESC_TRAVEL, "RELEASE": -ESC_TRAVEL}, "default": "HOLD",
                              "follows": f"esc.{L}", "note": "HOLD: ปลายหมุดสูงกว่าพื้น 15 มม. / RELEASE: ต่ำกว่าพื้น 1 มม."}, "หมุดคู่ P1 (ก้ามปู)")
    group(f"esc.{L}.p2", p2, {"type": "translate", "axis": [0, 0, 1], "states": {"HOLD": -ESC_TRAVEL, "RELEASE": ESC_TRAVEL}, "default": "HOLD",
                              "follows": f"esc.{L}"}, "หมุดคู่ P2 (ก้ามปู)")
    servo(f"esc.{L}.servo", M, "เซอร์โว escapement", (ESC_PIVOT_X, 0, 108), (yc + 7, yc + 29.7))

# buttons: ทั้งสองปุ่มใช้อุปกรณ์รุ่นเดียวกัน (ปุ่มกดมีไฟ ขอบ Ø26 ฝา Ø20) ต่างกันแค่สีและตำแหน่ง X
for btn, btn_name, btn_x, btn_mat in (("estop", "E-STOP", 150, "button_red"), ("start", "START/PAUSE", 95, "button_green")):
    cyl(f"btn.{btn}.bezel", M, f"{btn_name} ขอบ", (btn_x, -3, 75), 13, 6, "y", "metal")
    cyl(f"btn.{btn}.cap", M, f"{btn_name} ปุ่มมีไฟ", (btn_x, -9, 75), 10, 6, "y", btn_mat)
# electronics
box("bay.psu.case", M, "ครอบ PSU", (7, YB - 89, 5), (123, YB - 5, 46), "acrylic_clear")
box("bay.psu", M, "PSU 12V 5A (110×78×38)", (10, YB - 86, 5), (120, YB - 8, 43), "psu")
box("bay.shelf", M, "ชั้นวางบอร์ด", (5, 50, 47), (175, YB - 5, 50), "acrylic_clear")
box("bay.board.esp32", M, "ESP32 DevKit", (20, 60, 50), (75, 88, 63), "pcb_black")
box("bay.board.pca9685", M, "PCA9685", (85, 60, 50), (147, 86, 56), "pcb_blue")
box("bay.board.tb6612", M, "TB6612FNG", (90, 100, 50), (112, 120, 56), "pcb_red" if False else "pcb_green")
box("bay.board.buck", M, "Buck 12→5V 5A", (20, 100, 50), (80, 125, 70), "pcb_blue")
box("bay.board.mosfet", M, "MOSFET ×4", (120, 100, 50), (160, 135, 56), "pcb_green")
box("bay.iec", M, "ขั้วไฟ AC IEC C14", (20, YB, 25), (48, YB + 12, 55), "pcb_black")

# ------------------------------------------------------------------ module 2: AI box
M = "ai"
blk = "acrylic_black"
# left wall X180-183 with lane openings Z118-180
box("ai.wall.left.low", M, "ผนังซ้ายตู้ AI (ล่าง)", (180, 0, 5), (183, YB, 118), blk)
box("ai.wall.left.top", M, "ผนังซ้ายตู้ AI (บน)", (180, 0, 180), (183, YB, 230), blk)
for nm, (y0, y1) in POSTS.items():
    box(f"ai.wall.left.post.{nm}", M, "เสาผนังซ้ายตู้ AI", (180, y0, 118), (183, y1, 180), blk)
# ---- บาน F1 (สเปก 2026-11-16, specs/reject-ramp-redesign.md D1–D3, D12)
# ชิ้นเดียวยาว บานพับฝั่งซ้ายติดลูกกลิ้ง 2 ; pivot = ขอบบนของบานที่บานพับ ; บานชี้ไป +X
F1_HINGE = (268.0, 117.0)               # X, Z ผิวบนของบานที่บานพับ (ระดับยอดลูกกลิ้ง 2)
F1_L, F1_T = 135.0, 3.0                 # ความยาว / ความหนาบาน
F1_STATES = {"STOP": 12.5, "BRIDGE": -5.5}
# ---- แอ่งปลายราง (2026-11-17): ไม่มีครีบหมุนไข่แล้ว ไข่ลงมาแกนยาวขนาน Y ตลอด แล้วไถลไปถาดหน้าตามพื้นเอียง
#  - แอ่งโค้ง = ร่องเว้าตื้นตามแนว Y (หน้าตัดตาม X เป็นส่วนโค้งวงกลม เริ่มที่ระดับพื้นที่ร่อง G
#    ลึกสุดที่ก้นร่อง แล้วโค้งขึ้นไปชนกันชนท้ายแอ่งสูงกว่าพื้นเล็กน้อย) ต่อยาวเข้าไปในถาดหน้าด้วยความชันเท่าพื้นเดิม
#    (5° ในแอ่ง, 4° ในถาด) ไม่มีขั้นที่ขอบหน้า + โค้งผนังหลังราง + มุมมน ; ไข่ทั้งสองเลนไปพักที่ก้นร่อง
#    ชิ้นจริง: แผ่นร่องพิมพ์ 3D แทนพื้นอะคริลิก/โฟมถาดในช่วง X ของร่อง
#  - ใช้ทั้ง 3 ราง: ร่องทำให้ไข่ต่ำลง ราง A (ไข่เลนหลังอยู่ใต้สะพาน K2→B) จึงมีที่ว่างเหนือไข่มากขึ้น ; มุมมนราง A สูงแค่ยอดกันชนราง A
# ความชันพื้นยังไม่เปลี่ยน รอผลทดลองกับไข่จริง ; ความยาวแอ่ง (G → ผิวกันชน) คงไว้เท่าแบบครีบเดิม 2026-11-16
POCKET = {"stop_foam": 5.0, "stop_top": 84.0, "len": {"reject": 81.43, "A": 81.06, "B": 85.07}}
POCKET_CURVED = ("reject", "A", "B")
GROOVE = {"depth": 4.0,      # ก้นร่องต่ำกว่าพื้นเดิม (ร่องลึกกว่านี้ปลายถาดหน้าจะต่ำกว่าแผ่นฐาน)
          "bottom": 35.0,    # ก้นร่องห่างจากร่อง G ตาม X (ราว 43% ของความยาวแอ่ง ตามภาพร่างผู้ใช้)
          "n": 12,           # จำนวนท่อนตาม X (ท่อนละรูปนูน ให้ check.py ตรวจได้)
          "base": 5.0,       # ชิ้นร่องหนาลงไปถึงระดับเดียวกับใต้พื้นอะคริลิก/โฟมถาด (ผิวพื้นเดิม − 5)
          "back_r": 15.0, "back_n": 6,      # โค้งผนังหลังราง (เล็ก ไม่แตะไข่เลนหลังที่ปลายห่างผนังแค่ ~1.5 มม.)
          "corner_r": 20.0, "corner_n": 6,  # มุมมนระหว่างผนังท้ายกับผนังหลัง (มองจากด้านบน) ทำเป็นชิ้นสามเหลี่ยมหลายชิ้น
          "embed": 4.5}                     # ฐานมุมมนฝังลงในชิ้นร่อง (เท่ากันชน)

G_R = 421.0                                          # ร่องท้ายแผ่นรับ
# มุม REJECT ต่างกันตามเลน (พื้นเลนหลังสูงกว่า) หาให้แผ่นรับหักมุมเท่ากันทุกจุด แล้วจบที่ร่องเดียวกัน
F1_REJECT = {L: solve_plate_angle(F1_HINGE, F1_L + GAP_PLATE_FIXED, Ztop_rej(LANE[L]), G_R) for L in LANE}
X_STOP_R = G_R + POCKET["len"]["reject"]
REJ_CX = (337.0, R1(X_STOP_R + POCKET["stop_foam"] + 3))
F1_WALL_CLEAR = 2.0                     # ช่องผนังกั้นแสงต่ำกว่าผิวล่างของบานตอน REJECT

def f1_bottom_z(x, ang):
    """Z ผิวล่างของบาน F1 ที่ตำแหน่ง x (มุม ang, ลบ = ปลายลง)"""
    hx, hz = F1_HINGE
    return hz + (x - hx) * t(ang) - F1_T / c(ang)

def wall_cut_z(x_far):
    """ระดับล่างของช่องผนังเลนละช่อง: ต่ำกว่าผิวล่าง F1 ตอน REJECT ที่ขอบผนังฝั่งไกลบานพับ"""
    return {L: math.floor(f1_bottom_z(x_far, a) - F1_WALL_CLEAR) for L, a in F1_REJECT.items()}

def lane_wall(prefix, mod, name, x0, x1, z_cut, z_top, mat, note):
    """ผนังกั้นระหว่างตู้: เสา 3 ต้นเต็มความสูง + ผนังล่างแยกตามเลน (ช่องเลนเปิดตั้งแต่ z_cut[L] ถึง z_top)"""
    for nm, (y0, y1) in POSTS.items():
        box(f"{prefix}.post.{nm}", mod, f"เสา{name}", (x0, y0, 5), (x1, y1, z_top), mat)
    for L, (y0, y1) in LANE_Y.items():
        box(f"{prefix}.low.{L}", mod, f"{name} (ล่าง เลน{'หน้า' if L == 'F' else 'หลัง'})", (x0, y0, 5), (x1, y1, z_cut[L]), mat, note=note)

CURTAIN_NOTE = "ช่องเหนือแผ่นนี้คือทางที่บาน F1 กวาดผ่าน ติดม่านยาง/แปรงกันแสง (ไม่ได้ขึ้นรูปทรง)"
# right wall X315-318: ช่องเลนเปิดจากใต้บาน F1 ตอน REJECT ถึง Z 170 (D11)
lane_wall("ai.wall.right", M, "ผนังขวาตู้ AI", 315, 318, wall_cut_z(318), 170, blk, CURTAIN_NOTE)
box("ai.wall.right.top", M, "ผนังขวาตู้ AI (บน)", (315, 0, 170), (318, YB, 230), blk)
# front wall Y0-3 : ปิดเต็ม (D10 ไม่มีช่องรางเสียใต้ตู้ AI แล้ว) ; removable window Z150-230
box("ai.wall.front.a", M, "ผนังหน้าตู้ AI (ล่าง ปิดเต็ม)", (183, 0, 5), (315, 3, 150), blk)
wid = box("ai.wall.front.window", M, "ฝาหน้าตู้ AI ส่วนบน (ถอดได้)", (180, 0, 150), (318, 3, 230), blk)
group("ai.window", [wid], {"type": "translate", "axis": [0, -1, 0], "states": {"CLOSED": 0, "REMOVED": 60}, "default": "CLOSED"}, "ฝาหน้าตู้ AI ถอดได้")
box("ai.wall.back", M, "ผนังหลังตู้ AI", (183, YB - 3, 5), (315, YB, 230), blk)
box("ai.roof", M, "หลังคาตู้ AI 5 มม.", (180, 0, 230), (318, YB, 235), blk, note="เจาะช่องกล้องและช่องสาย 20×5")
box("ai.divider", M, "ผนังกลางเหนือลูกกลิ้ง", (183, Y_DIV[0], 118), (315, Y_DIV[1], 148), blk)
box("ai.f1.bearing", M, "บล็อกลูกปืนแกน F1 (กลาง ที่บานพับ)", (F1_HINGE[0] - 5, Y_DIV[0], F1_HINGE[1] - 12), (F1_HINGE[0] + 5, Y_DIV[1], F1_HINGE[1]), blk)
# top LED strips
LY_F, LY_B = LANE["F"] - 4, LANE["B"] + 4       # LED เส้นยาวอยู่เหนือขอบในของแต่ละเลน
box("ai.led.top.1", M, "LED บน", (195, LY_F - 10, 226), (300, LY_F, 229), "led")
box("ai.led.top.2", M, "LED บน", (195, LY_B, 226), (300, LY_B + 10, 229), "led")
box("ai.led.top.3", M, "LED บน", (195, LY_F, 226), (205, LY_B, 229), "led")
box("ai.led.top.4", M, "LED บน", (290, LY_F, 226), (300, LY_B, 229), "led")
# camera (lens down)
box("ai.camera", M, "Pi Camera Module 3 Wide", (228, Y_MID - 12.5, 217.6), (252, Y_MID + 12.5, 230), "pcb_green")
cyl("ai.camera.lens", M, "เลนส์กล้อง", (240, Y_MID, 216.6), 4.5, 2, "z", "sensor")

ZR = 108.0
for L, yc in LANE.items():
    ly0, ly1 = LANE_Y[L]
    th = "หน้า" if L == "F" else "หลัง"
    prism(f"ai.{L}.ramp", M, f"ทางลาดเข้าตู้ AI เลน{th}", "xz",
          [(183, 123.1), (206, 119.0), (206, 116.0), (183, 120.1)], (ly0, ly1), "acrylic_clear")
    r1 = cyl(f"ai.{L}.roller1", M, "ลูกกลิ้ง 1 (ขับด้วย N20)", (216, yc, ZR), 10, ROLLER_L, "y", "silicone")
    r2 = cyl(f"ai.{L}.roller2", M, "ลูกกลิ้ง 2 (หมุนฟรี)", (254, yc, ZR), 10, ROLLER_L, "y", "silicone")
    if L == "F":
        cyl("ai.F.shaft1", M, "เพลาลูกกลิ้ง 1", (216, Y_DIV[0] / 2, ZR), 2, Y_DIV[0], "y", "metal")
        cyl("ai.F.shaft2", M, "เพลาลูกกลิ้ง 2", (254, (3 + Y_DIV[0]) / 2, ZR), 2, Y_DIV[0] - 3, "y", "metal")
        box("ai.F.n20", M, "มอเตอร์ N20 เลนหน้า", (210, -25, 102), (222, 0, 114), "motor")
    else:
        cyl("ai.B.shaft1", M, "เพลาลูกกลิ้ง 1", (216, (Y_DIV[1] + YB) / 2, ZR), 2, YB - Y_DIV[1], "y", "metal")
        cyl("ai.B.shaft2", M, "เพลาลูกกลิ้ง 2", (254, (Y_DIV[1] + YB - 3) / 2, ZR), 2, YB - 3 - Y_DIV[1], "y", "metal")
        box("ai.B.n20", M, "มอเตอร์ N20 เลนหลัง", (210, YB, 102), (222, YB + 25, 114), "motor")
    group(f"roller.{L}", [r1, r2], {"type": "spin", "axis": [0, 1, 0], "rpm": 120,
                                    "pivots": {r1: [216, yc, ZR], r2: [254, yc, ZR]},
                                    "states": {"OFF": 0, "ON": 120}, "default": "OFF",
                                    "note": "ลูกกลิ้งทั้งสองหมุนทิศเดียวกัน ไข่หมุนสวน ~56 rpm"}, f"ลูกกลิ้งเลน {L}")
    # K0 vertical lifter
    k0 = [
        box(f"ai.{L}.k0.bar", M, "K0 คานล่าง", (228, yc - 20.5, 63), (234, yc + 20.5, 66), "printed"),
        box(f"ai.{L}.k0.prong1", M, "K0 นิ้วดัน", (228, yc - 20.5, 66), (234, yc - 15.5, 96), "printed"),
        box(f"ai.{L}.k0.prong2", M, "K0 นิ้วดัน", (228, yc + 15.5, 66), (234, yc + 20.5, 96), "printed"),
        box(f"ai.{L}.k0.link", M, "K0 ก้านต่อเซอร์โว", (213, yc + 11.4, 63), (228, yc + 13.4, 66), "printed"),
    ]
    group(f"k0.{L}", k0, {"type": "translate", "axis": [0, 0, 1], "states": {"REST": 0, "KICK": 22}, "default": "REST",
                           "note": "นิ้วดันขึ้นในแนวตั้งผ่านช่อง X 226–244 ดันด้านซ้ายของไข่ให้กลิ้งข้ามลูกกลิ้ง 2"}, f"K0 เลน {L}")
    box(f"ai.{L}.k0.guide1", M, "รางนำ K0", (222, yc - 24, 5), (240, yc - 21, 97), "acrylic_clear")
    box(f"ai.{L}.k0.guide2", M, "รางนำ K0", (222, yc + 21, 5), (240, yc + 24, 97), "acrylic_clear")
    servo(f"ai.{L}.k0.servo", M, "เซอร์โว K0", (213, 0, 70), (yc - 11.4, yc + 11.3), length_dir=-1)
    box(f"ai.{L}.led.post", M, "เสาไฟส่องล่าง", (236, yc - 2, 5), (240, yc + 2, 92), "acrylic_clear")
    cyl(f"ai.{L}.led.candle", M, "COB LED ส่องล่าง", (238, yc, 94), 10, 4, "z", "led")
    # F1
    hx, hz = F1_HINGE
    f1 = box(f"ai.{L}.f1", M, f"บาน F1 {F1_L:g}×{2 * SPAN:g} (บานพับฝั่งซ้าย ติดลูกกลิ้ง 2)", (hx, yc - SPAN, hz - F1_T), (hx + F1_L, yc + SPAN, hz), "acrylic_clear")
    group(f"f1.{L}", [f1], {"type": "rotate", "pivot": [hx, yc, hz], "axis": [0, -1, 0],
                             "states": {**F1_STATES, "REJECT": F1_REJECT[L]}, "default": "STOP",
                             "note": "บานชี้ไป +X จากบานพับ ; บวก = ปลายขวายกขึ้น ; STOP = เนินกั้นไข่ ; BRIDGE = สะพานไปแท่นชั่ง ; "
                                     "REJECT = ทางลาดลงแอ่งรางเสีย (K0 ดีดไข่ลงหลังบานถึงท่าแล้ว)"}, f"F1 เลน {L}")
    servo_mg996r(f"ai.{L}.f1.servo", M, "เซอร์โว F1 MG996R", (hx, 0, hz), "front" if L == "F" else "back")
    # S1 break-beam
    if L == "F":
        box("ai.F.s1.tx", M, "S1 ตัวส่ง", (193, 3, 138), (197, 7, 144), "sensor")
        box("ai.F.s1.rx", M, "S1 ตัวรับ", (193, Y_DIV[0] - 4, 138), (197, Y_DIV[0], 144), "sensor")
    else:
        box("ai.B.s1.tx", M, "S1 ตัวส่ง", (193, Y_DIV[1], 138), (197, Y_DIV[1] + 4, 144), "sensor")
        box("ai.B.s1.rx", M, "S1 ตัวรับ", (193, Y_IN - 2, 138), (197, Y_IN + 2, 144), "sensor")

# ------------------------------------------------------------------ module 3: weighing box
# สเปก 2026-11-16: สะพานตายตัวต่อจาก F1 (D6) → แท่นชั่งบนปลายอิสระของ load cell ที่ยึดฝั่งขวา (D7)
# → แผ่นส่งต่อ → K2 (ยาว ใช้ MG996R) ; กล่องชั่งยาวถึงท้ายเครื่อง คลุม K2 และราง A/B (แทน D8 ที่ให้ K2 อยู่นอกกล่อง)
M = "scale"
cl = "acrylic_clear"
GAP_F1_BRIDGE = GAP_PLATE_FIXED         # ช่องปลายบาน F1 (BRIDGE) ถึงสะพานตายตัว (≤ 2)
GAP_BRIDGE_PLAT = 2.0                   # ช่องสะพานตายตัวถึงแท่นชั่ง (≥ 1.5 ไม่รบกวนการชั่ง)
GAP_PLAT_TRANSFER = 1.5                 # ช่องแท่นชั่งถึงแผ่นส่งต่อ
BRIDGE_L, PLAT_L, PLAT_DEG = 50.0, 60.0, 3.0
BRIDGE2_DEG = -1.5                      # ท่อนต่อ: ลาดน้อยให้แท่นชั่ง/K2 ไม่ต่ำลงมาก (สะพาน B ต้องข้ามแอ่ง A)

_a = F1_STATES["BRIDGE"]
f1_line = lambda d: (F1_HINGE[0] + d * c(_a), F1_HINGE[1] + d * s(_a))   # ผิวบนแนวบาน F1 ตอน BRIDGE
_n = (s(_a), -c(_a))                                                      # ตั้งฉากลงจากผิวบน
BR0, BR1 = f1_line(F1_L + GAP_F1_BRIDGE), f1_line(F1_L + GAP_F1_BRIDGE + BRIDGE_L)
X_P0 = R1(REJ_CX[1] + 2.6)              # ขอบซ้ายแท่นชั่ง: deck (X_P0 − 1) อยู่ถัดจากชุดรางเสีย
BR2 = (X_P0 - GAP_BRIDGE_PLAT, BR1[1] + (X_P0 - GAP_BRIDGE_PLAT - BR1[0]) * t(BRIDGE2_DEG))
ZP0 = R1(BR2[1] - 0.2)                  # ผิวบนแท่นชั่งที่ขอบซ้าย (ต่ำกว่าปลายสะพานเล็กน้อย)
ZP1 = ZP0 - PLAT_L * t(PLAT_DEG)
plat_bottom = lambda x: ZP0 - 5 - (x - X_P0) * t(PLAT_DEG)
# load cell กลับด้านจากแบบเดิม: บล็อกยึดอยู่ฝั่งขวา ปลายอิสระ (แผ่นรองลิ่ม) อยู่ฝั่งซ้ายใต้แท่น
LC0, LC1 = X_P0 + 2, X_P0 + 82
Z_LC1 = ZP0 - 18.8                      # ผิวบน load cell (ระยะเท่าแบบเดิม)
Z_DECK = Z_LC1 - 12.7 - 10              # ผิวบน deck (บล็อกสูง 10)
X_SR = R1(LC1 + 0.5)                    # ขอบขวาของโซน load cell (ปลาย deck)
X_K2 = R1(X_SR + 7)                     # บานพับ K2 (เผื่อมุมบานกวาดตอน DROP)
XT0, XT1 = X_P0 + PLAT_L + GAP_PLAT_TRANSFER, X_K2 - 3
ZT0 = ZP1 - 0.1
ZT1 = ZT0 - (XT1 - XT0) * t(PLAT_DEG)
K2_Z = R1(ZT1 - 0.2)

# ---- K2 + ราง A: บาน K2 ยาว LK2 ; DROP = ทางลาดลงราง A ต่อด้วยแผ่นรับ (โค้งรับเข้าพื้น) ถึงร่อง G_A
LK2 = 80.0
K2_STATES = {"STOP": 25.0, "BRIDGE": -2.0}
K2_DROP_B = -39.0
RUNOUT_N_A = 3                          # 2026-11-17: 3 ท่อน (เดิม 2) ให้ไข่ลงพื้นราง A ≤ 0.3 m/s ; ท่อนสั้นลงเหลือ ≥ 8 มม. (ผู้ใช้ลดเกณฑ์จาก 10)
_t = plate_tip((X_K2, K2_Z), LK2 + GAP_PLATE_FIXED, K2_DROP_B)
G_A = R1(_t[0] + runout_len(_t, K2_DROP_B, Ztop(LANE["B"]), RUNOUT_N_A))
K2_DROP = {"F": solve_plate_angle((X_K2, K2_Z), LK2 + GAP_PLATE_FIXED, Ztop(LANE["F"]), G_A, n=RUNOUT_N_A), "B": K2_DROP_B}
X_STOP_A = G_A + POCKET["len"]["A"]
A_CX = (R1(X_K2 - 4), R1(X_STOP_A + POCKET["stop_foam"] + 3))

# ---- ราง B: สะพาน K2→B ลาดเท่า K2 ตอน BRIDGE ข้ามราง A แล้วทางลาด: เข้าโค้งนูน → ชันหลัก → โค้งรับเข้าพื้น
B_CX0 = A_CX[1] + 2
_ab = K2_STATES["BRIDGE"]
k2_line = lambda d: (X_K2 + d * c(_ab), K2_Z + d * s(_ab))
BB0 = k2_line(LK2 + GAP_PLATE_FIXED)
BB1 = k2_line((B_CX0 - X_K2) / c(_ab))
RS = k2_line((B_CX0 + GAP_PLATE_FIXED - X_K2) / c(_ab))          # จุดเริ่มทางลาด B
RAMP_IN, RAMP_IN_RUN = (-12.0, -24.0), 6.0                        # ท่อนเข้าโค้งนูน
RAMP_MAIN = -36.0
RAMP_OUT = (-27.0, -18.0, -9.0)                                   # ท่อนโค้งรับเข้าพื้น
def ramp_b(floor, G=None, w=10.0):
    """ผิวบนทางลาด B: กำหนด w (ช่วงท่อนโค้งรับ) หรือกำหนด G แล้วหา w"""
    e = sum(RAMP_IN_RUN * -t(a) for a in RAMP_IN)
    so = sum(-t(a) for a in RAMP_OUT)
    H = RS[1] - floor
    if G is not None:
        R = G - RS[0] - RAMP_IN_RUN * len(RAMP_IN)
        w = (H - e - R * -t(RAMP_MAIN)) / (so - len(RAMP_OUT) * -t(RAMP_MAIN))
    m = (H - e - w * so) / -t(RAMP_MAIN)
    pts, (x, z) = [RS], RS
    for a, run in [(a, RAMP_IN_RUN) for a in RAMP_IN] + [(RAMP_MAIN, m)] + [(a, w) for a in RAMP_OUT]:
        x, z = x + run, z + run * t(a); pts.append((x, z))
    assert w > 3 and m > 0, ("ramp B", w, m)
    return pts
RUNOUT_MIN = 10.0                      # ท่อนโค้งรับยาวอย่างน้อย (รัศมีโค้งต้องใหญ่กว่าตัวไข่มาก)
RAMP_PTS = {L: ramp_b(Ztop(LANE[L]), w=RUNOUT_MIN) for L in LANE}
G_B = R1(max(p[-1][0] for p in RAMP_PTS.values()))          # ร่องไกลสุด (เลนหน้าพื้นต่ำกว่า ทางลาดยาวกว่า)
X_STOP_B = G_B + POCKET["len"]["B"]
B_CX = (R1(B_CX0), R1(X_STOP_B + POCKET["stop_foam"] + 3))
X_END = B_CX[1]                         # ขอบขวาชุดราง B = ผิวในผนังขวากล่อง
RAIL_H = 15.0
B_OPEN_TOP = math.ceil(max(z for pts in RAMP_PTS.values() for _, z in pts) + RAIL_H + 2)

box("sc.deck", M, "พื้นกล่องชั่ง (deck ใต้ load cell เท่านั้น)", (X_P0 - 1, 3, Z_DECK - 5), (X_SR, YB - 3, Z_DECK), cl)
for i, (x0, x1) in enumerate([(X_P0 - 1, X_P0 + 4), (X_SR - 5, X_SR)]):
    for j, (y0, y1) in enumerate([(3, 8), (YB - 8, YB - 3)]):
        box(f"sc.leg.{i}{j}", M, "ขาค้ำ deck", (x0, y0, 5), (x1, y1, Z_DECK - 5), cl)
lane_wall("sc.wall.left", M, "ผนังซ้ายกล่องชั่ง", 318, 321, wall_cut_z(321), 170, cl, CURTAIN_NOTE)
box("sc.wall.left.top", M, "ผนังซ้ายกล่องชั่ง (บน)", (318, 0, 170), (321, YB, 172), cl)
# ผนังหน้า: เจาะช่องล่างให้ดึงชุดรางทั้ง 3 ออกด้านหน้าได้
box("sc.wall.front.a", M, "ผนังหน้ากล่องชั่ง (ซ้าย)", (321, 0, 5), (REJ_CX[0], 3, 172), cl)
box("sc.wall.front.b", M, "ผนังหน้ากล่องชั่ง (เหนือช่องรางเสีย)", (REJ_CX[0], 0, 85), (REJ_CX[1], 3, 172), cl)
box("sc.wall.front.c", M, "ผนังหน้ากล่องชั่ง (ระหว่างรางเสียกับราง A)", (REJ_CX[1], 0, 5), (A_CX[0], 3, 172), cl)
box("sc.wall.front.d", M, "ผนังหน้ากล่องชั่ง (เหนือช่องราง A)", (A_CX[0], 0, 85), (A_CX[1], 3, 172), cl)
box("sc.wall.front.e", M, "ผนังหน้ากล่องชั่ง (ระหว่างราง A กับ B)", (A_CX[1], 0, 5), (B_CX[0], 3, 172), cl)
box("sc.wall.front.f", M, "ผนังหน้ากล่องชั่ง (เหนือช่องราง B)", (B_CX[0], 0, B_OPEN_TOP), (X_END, 3, 172), cl)
box("sc.wall.back", M, "ผนังหลังกล่องชั่ง", (321, YB - 3, 5), (X_END, YB, 172), cl)
box("sc.wall.right", M, "ผนังขวากล่องชั่ง (ท้ายเครื่อง)", (X_END, 0, 5), (X_END + 3, YB, 172), cl)
box("sc.wall.mid.a", M, "ผนังกลางกล่องชั่ง (เหนือแอ่งรางเสีย ไข่เลนหลังลอดได้)", (321, Y_DIV[0], 95), (X_P0 - 1, Y_DIV[1], 172), cl)
box("sc.wall.mid.b", M, "ผนังกลางกล่องชั่ง (เหนือ deck)", (X_P0 - 1, Y_DIV[0], Z_DECK), (X_SR, Y_DIV[1], 172), cl)
box("sc.wall.mid.c", M, "ผนังกลางกล่องชั่ง (รับแกน K2 กลาง)", (X_SR, Y_DIV[0], 88), (X_K2 + 6, Y_DIV[1], 172), cl)
box("sc.wall.mid.d", M, "ผนังกลางกล่องชั่ง (เหนือราง A/B ให้ชุดราง B ดึงลอดได้)", (X_K2 + 6, Y_DIV[0], B_OPEN_TOP), (X_END, Y_DIV[1], 172), cl)
box("sc.lid", M, "ฝากล่องชั่ง (ท่อนขวาเหนือราง A/B ถอดได้)", (318, 0, 172), (X_END + 3, YB, 175), cl)

for L, yc in LANE.items():
    th = "หน้า" if L == "F" else "หลัง"
    ys = (yc - SPAN, yc + SPAN)
    prism(f"sc.{L}.fixbridge", M, f"สะพานตายตัว F1→แท่นชั่ง {BRIDGE_L:g} มม. ลาด {-_a:g}° เลน{th}", "xz",
          [BR0, BR1, (BR1[0] + F1_T * _n[0], BR1[1] + F1_T * _n[1]), (BR0[0] + F1_T * _n[0], BR0[1] + F1_T * _n[1])], ys, cl,
          note="ใต้สะพานนี้คือแอ่งรางเสีย")
    _n2 = (s(BRIDGE2_DEG), -c(BRIDGE2_DEG))
    prism(f"sc.{L}.fixbridge2", M, f"สะพานตายตัว ท่อนต่อ ลาด {-BRIDGE2_DEG:g}° เลน{th}", "xz",
          [BR1, BR2, (BR2[0] + F1_T * _n2[0], BR2[1] + F1_T * _n2[1]), (BR1[0] + F1_T * _n2[0], BR1[1] + F1_T * _n2[1])], ys, cl,
          note="ต่อจากท่อนแรกเพื่อเลื่อนแท่นชั่งไปทางขวาให้แอ่งรางเสียยาวพอให้ไข่หมุน")
    prism(f"sc.{L}.platform", M, f"แท่นชั่ง {PLAT_L:g}×{2 * SPAN:g} เอียง {PLAT_DEG:g}° (แอ่ง Ø40 ลึก 2.5 ที่ X {X_P0 + 30:g})", "xz",
          [(X_P0, ZP0), (X_P0 + PLAT_L, ZP1), (X_P0 + PLAT_L, ZP1 - 5), (X_P0, ZP0 - 5)], ys, cl,
          note=f"แอ่งทรงกลม Ø40 ลึก 2.5 มม. กึ่งกลาง X {X_P0 + 30:g} (ทำด้วย CSG หรือ decal)")
    box(f"sc.{L}.lc.block", M, "บล็อกยึด load cell (ฝั่งขวา)", (LC1 - 15, yc - 8, Z_DECK), (LC1, yc + 8, Z_LC1 - 12.7), "printed")
    box(f"sc.{L}.lc", M, "Load cell 1 kg (ปลายอิสระฝั่งซ้าย)", (LC0, yc - 6.35, Z_LC1 - 12.7), (LC1, yc + 6.35, Z_LC1), "load_cell")
    xs0, xs1 = X_P0 + 5, X_P0 + 20
    prism(f"sc.{L}.lc.spacer", M, "แผ่นรองลิ่ม 3° ใต้แท่น", "xz",
          [(xs0, Z_LC1), (xs1, Z_LC1), (xs1, plat_bottom(xs1)), (xs0, plat_bottom(xs0))], (yc - 8, yc + 8), "printed")
    hy = (yc - 29, yc - 11) if L == "F" else (yc + 13, yc + 31)
    box(f"sc.{L}.hx711", M, "HX711", (X_P0 + 41, hy[0], Z_DECK), (X_P0 + 61, hy[1], Z_DECK + 2.4), "pcb_green")
    k1x = X_P0 + 52
    k1 = box(f"sc.{L}.k1", M, "K1 ไม้ปัดดันไข่ (จากด้านบน)", (X_P0, yc - 20, 159), (k1x, yc + 20, 162), "printed")
    group(f"k1.{L}", [k1], {"type": "rotate", "pivot": [k1x, yc, 160.5], "axis": [0, -1, 0],
                             "states": {"REST": -8, "KICK": 70}, "default": "REST",
                             "note": "แขนชี้ไป −X ; KICK หมุนให้ปลายกวาดลงและไป +X ดันด้านบนซ้ายของไข่ออกจากแอ่ง"}, f"K1 เลน {L}")
    servo(f"sc.{L}.k1.servo", M, "เซอร์โว K1", (k1x, 0, 160.5), "front" if L == "F" else "back")
    prism(f"sc.{L}.transfer", M, f"แผ่นส่งต่อ แท่นชั่ง→K2 เลน{th}", "xz",
          [(XT0, ZT0), (XT1, ZT1), (XT1, ZT1 - 3), (XT0, ZT0 - 3)], ys, cl)
    k2 = box(f"sc.{L}.k2", M, f"บาน K2 {LK2:g}×{2 * SPAN:g}", (X_K2, yc - SPAN, K2_Z - 3), (X_K2 + LK2, yc + SPAN, K2_Z), cl)
    group(f"k2.{L}", [k2], {"type": "rotate", "pivot": [X_K2, yc, K2_Z], "axis": [0, -1, 0],
                             "states": {**K2_STATES, "DROP": K2_DROP[L]}, "default": "STOP",
                             "note": "บวก = ปลายบานยกขึ้น ; BRIDGE = ทางไป B ; DROP = ทางลาดลงราง A ต่อแผ่นรับตายตัว"}, f"K2 เลน {L}")
    prism(f"sc.{L}.bridge", M, f"สะพานคงที่ K2→ราง B ลาด {-_ab:g}° (ข้ามราง A)", "xz",
          [BB0, BB1, (BB1[0], BB1[1] - 3), (BB0[0], BB0[1] - 3)], ys, cl)
    servo_mg996r(f"sc.{L}.k2.servo", M, "เซอร์โว K2 MG996R", (X_K2, 0, K2_Z), "front" if L == "F" else "back")

# ------------------------------------------------------------------ module 4: chute inserts
M = "output"

def insert(key, cx, tx, foam, label, back_x=None, zt=Ztop, side_r_top=None, groove=None):
    """ชุดรางดึงออกได้ ; groove = (x0, x1) ช่วง X ที่ชิ้นร่อง (pocket_curved) มาแทนพื้นอะคริลิกและโฟมถาด"""
    ids = []
    cx0, cx1 = cx
    tx0, tx1 = tx
    yb = YB - 8
    # ช่วง X ของพื้นอะคริลิก/โฟมถาด: แยกเป็นซ้าย-ขวาของร่อง (ชื่อชิ้นแรกคงเดิม)
    split = lambda a, b: [(a, b)] if groove is None else [(a, groove[0]), (groove[1], b)]
    # chute floor (acrylic) + foam, Y 0..yb
    ids.append(prism(f"out.{key}.chute.floor", M, f"พื้นราง{label}", "yz",
                     [(0, zt(0) - 5), (yb, zt(yb) - 5), (yb, zt(yb) - 8), (0, zt(0) - 8)], (cx0 + 3, cx1 - 3), cl))
    for i, xs in enumerate(split(cx0 + 3, cx1 - 3)):
        ids.append(prism(f"out.{key}.chute.surface{'' if i == 0 else '.end'}", M, f"พื้นแอ่ง/ราง{label} อะคริลิก 5 มม. (ผิวลื่น ไข่กลิ้งออกตัวได้บนพื้นเอียง 5°)", "yz",
                         [(0, zt(0)), (yb, zt(yb)), (yb, zt(yb) - 5), (0, zt(0) - 5)], xs, "acrylic_white"))
    ids.append(prism(f"out.{key}.tray.floor", M, f"พื้นถาดหน้า{label}", "yz",
                     [(-130, zt(-130) - 5), (0, zt(0) - 5), (0, zt(0) - 8), (-130, zt(-130) - 8)], (tx0 + 3, tx1 - 3), cl))
    for i, xs in enumerate(split(tx0 + 3, tx1 - 3)):
        ids.append(prism(f"out.{key}.tray.foam{'' if i == 0 else '.end'}", M, f"โฟมถาดหน้า{label}", "yz",
                         [(-125, zt(-125)), (0, zt(0)), (0, zt(0) - 5), (-125, zt(-125) - 5)], xs, foam))
    wall_c = [(0, 5), (Y_IN, 5), (Y_IN, zt(Y_IN) + 25), (0, zt(0) + 25)]
    wall_r = wall_c if side_r_top is None else [(0, 5), (Y_IN, 5), (Y_IN, side_r_top), (0, side_r_top)]
    wall_t = [(-130, 5), (0, 5), (0, zt(0) + 25), (-130, zt(-130) + 25)]
    ids.append(prism(f"out.{key}.chute.side.l", M, "ผนังข้างราง", "yz", wall_c, (cx0, cx0 + 3), cl))
    ids.append(prism(f"out.{key}.chute.side.r", M, "ผนังข้างราง" if side_r_top is None else "ผนังข้างราง (หลังกันชน)", "yz", wall_r, (cx1 - 3, cx1), cl))
    ids.append(prism(f"out.{key}.tray.side.l", M, "ผนังข้างถาดหน้า", "yz", wall_t, (tx0, tx0 + 3), cl))
    ids.append(prism(f"out.{key}.tray.side.r", M, "ผนังข้างถาดหน้า", "yz", wall_t, (tx1 - 3, tx1), cl))
    if tx0 < cx0:
        ids.append(box(f"out.{key}.shoulder.l", M, "ผนังบ่าถาดหน้า", (tx0 + 3, -3, zt(0) - 5), (cx0, 0, zt(0) + 25), cl))
    if tx1 > cx1:
        ids.append(box(f"out.{key}.shoulder.r", M, "ผนังบ่าถาดหน้า", (cx1, -3, zt(0) - 5), (tx1 - 3, 0, zt(0) + 25), cl))
    bx0, bx1 = back_x or (cx0 + 3, cx1 - 3)
    ids.append(box(f"out.{key}.back", M, "ผนังหลังราง", (bx0, yb, 5), (bx1, Y_IN, zt(Y_IN) + 25), cl))
    ids.append(box(f"out.{key}.bumper", M, "กันชนโฟมขอบหน้า", (tx0 + 3, -130, zt(-130) - 5), (tx1 - 3, -125, 40), foam))
    return ids

yb_c = YB - 8
LANE_HALF = {"F": (0, Y_MID), "B": (Y_MID, yb_c)}       # ช่วง Y ของชิ้นรายเลนในราง (แบ่งที่กึ่งกลางผนังกลาง)

def stop_foam(key, x_stop, foam, zt, top=POCKET["stop_top"]):
    return prism(f"out.{key}.stop.foam", M, "กันชนโฟมท้ายแอ่ง", "yz",
                 [(0, zt(0) - 4.5), (yb_c, zt(yb_c) - 4.5), (yb_c, top), (0, top)],
                 (x_stop, x_stop + POCKET["stop_foam"]), foam)

def solid_runout(id, name, pts, L, foam, zt):
    """แผ่นรับแบบตัน (พิมพ์ 3D หุ้มโฟม) ฐานฝังในโฟมราง"""
    y0, y1 = LANE_HALF[L]
    zlow = zt(y1) - 4.5
    return prism(id, M, name, "xz", list(pts) + [(pts[-1][0], zlow), (pts[0][0], zlow)], (y0, y1), foam,
                 note="ผิวบนหักมุมทีละน้อยจนแนบพื้น (โค้งรับเข้าพื้น) ชิ้นจริงทำโค้งต่อเนื่องได้")

RUNOUTS = {}

def groove_profile(G, x_stop):
    """หน้าตัดร่อง [(x, ความสูงเทียบพื้นเดิม)] จาก (G, 0) ผ่านก้นร่อง (G + bottom, −depth) ถึงผิวกันชน (x_stop, สูงกว่าพื้นเล็กน้อย)
    เป็นส่วนโค้งวงกลมเดียว รัศมี R = (bottom² + depth²) / (2·depth) (ใหญ่กว่ารัศมีไข่มาก ไข่แตะร่องจุดเดียว)"""
    D, xb = GROOVE["depth"], G + GROOVE["bottom"]
    R = (GROOVE["bottom"] ** 2 + D ** 2) / (2 * D)
    n = GROOVE["n"]
    pts = [(G + (x_stop - G) * i / n, 0.0) for i in range(n + 1)]
    return [(x, -D + R - math.sqrt(R * R - (x - xb) ** 2)) for x, _ in pts], R

def pocket_curved(key, G, x_stop, foam, ch, zt, top=POCKET["stop_top"]):
    """แอ่งโค้ง (ชิ้นจริงพิมพ์ 3D) — ทุกชิ้นแบ่งเป็นรูปนูนให้ check.py ตรวจได้
    1) ร่อง: หน้าตัด XZ วาดบนพื้นราบ Z = z0 แล้วหมุนรอบแกน X ตามความชันพื้น (5° ในแอ่ง Y 0..หลัง, 4° ในถาดหน้า Y −125..0)
       ผิวร่องจึงขนานพื้นเดิมทุก Y ต่อเนื่องจากแอ่งถึงถาดหน้า ไม่มีขั้นที่ขอบหน้า
    2) โค้งผนังหลังราง: หน้าตัด YZ สัมผัสระดับก้นร่องและผนังหลัง ยาวตาม X จาก G ถึงผิวกันชน
    3) มุมมน (มองจากด้านบน) ระหว่างผิวกันชนกับผนังหลัง: ชิ้นสามเหลี่ยมตั้งจากพื้นถึงยอดกันชน"""
    z0, a, af = ch["z0"], ch["slope_back_deg"], ch["slope_front_deg"]
    D = GROOVE["depth"]
    zb = z0 - GROOVE["base"]
    ids = []
    prof, R = groove_profile(G, x_stop)
    n = len(prof) - 1
    for zone, (y0, y1), deg, mat, where in (("floor", (0, yb_c / c(a)), a, "printed", "แอ่ง"),
                                            ("tray", (-125 / c(af), 0), af, foam, "ถาดหน้า")):
        rot = {"rotate": {"axis": [1, 0, 0], "deg": deg, "pivot": [G, 0, z0]}}
        for i, (p, q) in enumerate(zip(prof, prof[1:])):
            ids.append(prism(f"out.{key}.pocket.{zone}.{i + 1}", M, f"ร่องเว้า{where} ลึก {D:g} (R{R:.0f}) ท่อน {i + 1}/{n}", "xz",
                             [(p[0], zb), (q[0], zb), (q[0], z0 + q[1]), (p[0], z0 + p[1])], (y0, y1), mat, transform=rot,
                             note="ไข่ลงมาพักที่ก้นร่องแล้วไถลไปถาดหน้าตามร่อง ; ชิ้นจริงทำผิวโค้งต่อเนื่อง"))
    # โค้งผนังหลังราง: สัมผัสระดับก้นร่อง (พื้นเดิม − D) และผนังหลัง ; ช่วงที่ร่องตื้นกว่าจะจมอยู่ในชิ้นร่อง
    zd = lambda y: zt(y) - D
    rb, nb = GROOVE["back_r"], GROOVE["back_n"]
    yc = yb_c - rb
    zc = zd(yc) + rb / c(a)
    arc = [(yc + rb * c(th), zc + rb * s(th)) for th in (-(90 - a) + (90 - a) * k / nb for k in range(nb + 1))]
    for i, (p, q) in enumerate(zip(arc, arc[1:])):
        ids.append(prism(f"out.{key}.pocket.back.{i + 1}", M, f"โค้งผนังหลังราง R{rb:g} ท่อน {i + 1}/{nb}", "yz",
                         [(p[0], zt(p[0]) - GROOVE["base"]), (q[0], zt(q[0]) - GROOVE["base"]), q, p], (G, x_stop), foam))
    # มุมมน: สามเหลี่ยมจากมุมผนัง ไปยังจุดบนส่วนโค้งรัศมี rc
    rc, ncr = GROOVE["corner_r"], GROOVE["corner_n"]
    corner = (x_stop, yb_c)
    cpts = [(x_stop - rc + rc * c(90 * k / ncr), yb_c - rc + rc * s(90 * k / ncr)) for k in range(ncr + 1)]
    for i, (p, q) in enumerate(zip(cpts, cpts[1:])):
        ids.append(prism(f"out.{key}.pocket.corner.{i + 1}", M, f"มุมมนท้ายแอ่ง R{rc:g} ท่อน {i + 1}/{ncr}", "xy",
                         [corner, p, q], (zt(yb_c) - GROOVE["embed"], top), foam))   # ฐานตามพื้นขอบหลัง (สูงสุด) ไม่ลงถึงแผ่นพื้นใต้โฟม
    return ids

def pocket_meta(key, G, x_stop):
    """meta ของแอ่ง: rest_x = X กึ่งกลางไข่ที่พัก ; groove = หน้าตัดร่อง [x, ความสูงเทียบพื้นเดิม] (เฉพาะแอ่งโค้ง)"""
    if key in POCKET_CURVED:
        prof, R = groove_profile(G, x_stop)
        return {"G": G, "stop_x": R1(x_stop), "shape": "curved", "rest_x": R1(G + GROOVE["bottom"]),
                "groove": [[round(x, 2), round(h, 2)] for x, h in prof], "groove_r": round(R, 1), "lanes": {}}
    return {"G": G, "stop_x": R1(x_stop), "shape": "straight", "rest_x": R1(x_stop - EGG_B / 2 - 0.5), "lanes": {}}

def lane_tail(key, floor, ch):
    """ปลายเส้นผิวทางลงของเลน (ต่อจากแผ่นรับ/ทางลาด): ผนังตรง = พื้นเรียบถึงกันชน ; แอ่งโค้ง = ผิวร่อง (ความชันพื้นตาม Y)"""
    m = RUNOUTS[key]
    if m["shape"] == "straight":
        return [[R1(m["stop_x"]), R1(floor)]]
    k = 1.0 / c(ch["slope_back_deg"])
    return [[R1(x), round(floor + h * k, 2)] for x, h in m["groove"]]
# ---- รางเสีย: แผ่นรับต่อจาก F1 → แอ่งร่องเว้า + โค้งผนังหลัง + มุมมน + กันชนโฟม
rej = insert("reject", REJ_CX, (321, REJ_CX[1]), "eva_reject", "ไข่เสีย", zt=Ztop_rej, side_r_top=POCKET["stop_top"], groove=(G_R, X_STOP_R))
RUNOUTS["reject"] = pocket_meta("reject", G_R, X_STOP_R)
for L in LANE:
    st = plate_tip(F1_HINGE, F1_L + GAP_PLATE_FIXED, F1_REJECT[L])
    pts, _ = runout(st, F1_REJECT[L], Ztop_rej(LANE[L]), G_R)
    rej.append(solid_runout(f"out.reject.runout.{L}", f"แผ่นรับปลาย F1 เลน{'หน้า' if L == 'F' else 'หลัง'}", pts, L, "eva_reject", Ztop_rej))
    RUNOUTS["reject"]["lanes"][L] = [list(map(R1, p)) for p in pts[:-1]] + lane_tail("reject", Ztop_rej(LANE[L]), CHUTE_REJECT)
rej += pocket_curved("reject", G_R, X_STOP_R, "eva_reject", CHUTE_REJECT, Ztop_rej)
rej.append(stop_foam("reject", X_STOP_R, "eva_reject", Ztop_rej))

# ---- ราง A: แผ่นรับต่อจากปลาย K2 (DROP) → แอ่งร่องเว้า + โค้งผนังหลัง + มุมมน (สูงแค่ยอดกันชนใต้สะพาน) + กันชนโฟม
A_STOP_TOP = math.floor(BB0[1] + (A_CX[1] - BB0[0]) * t(_ab) - 3 - 2)   # ใต้สะพาน K2→B (ผิวล่าง − 2)
ra = insert("A", A_CX, (REJ_CX[1] + 3, A_CX[1]), "eva_A", " A", side_r_top=A_STOP_TOP, groove=(G_A, X_STOP_A))
RUNOUTS["A"] = pocket_meta("A", G_A, X_STOP_A)
for L in LANE:
    st = plate_tip((X_K2, K2_Z), LK2 + GAP_PLATE_FIXED, K2_DROP[L])
    pts, _ = runout(st, K2_DROP[L], Ztop(LANE[L]), G_A, RUNOUT_N_A)
    ra.append(solid_runout(f"out.A.runout.{L}", f"แผ่นรับปลาย K2 เลน{'หน้า' if L == 'F' else 'หลัง'}", pts, L, "eva_A", Ztop))
    RUNOUTS["A"]["lanes"][L] = [list(map(R1, p)) for p in pts[:-1]] + lane_tail("A", Ztop(LANE[L]), CHUTE)
ra += pocket_curved("A", G_A, X_STOP_A, "eva_A", CHUTE, Ztop, top=A_STOP_TOP)
ra.append(stop_foam("A", X_STOP_A, "eva_A", Ztop, A_STOP_TOP))

# ---- ราง B: ทางลาดแผ่นบาง (เข้าโค้งนูน → ชันหลัก → โค้งรับเข้าพื้น) + รางข้าง + เสาค้ำ + กันชนโฟม
rb = insert("B", B_CX, B_CX, "eva_B", " B", back_x=(G_B, B_CX[1] - 3), side_r_top=POCKET["stop_top"], groove=(G_B, X_STOP_B))
RUNOUTS["B"] = pocket_meta("B", G_B, X_STOP_B)
for L, yc in LANE.items():
    pts = RAMP_PTS[L]
    y0, y1 = yc - SPAN, yc + SPAN
    th = "หน้า" if L == "F" else "หลัง"
    # แผ่นบาง 3 มม. หักเป็นท่อน (แยกชิ้นละท่อนให้ทุกชิ้นนูน) ; รางข้างเฉพาะช่วงบน (ช่วงโค้งรับเปิดให้ไข่เลนหลังกลิ้งผ่าน)
    zmin = Ztop(LANE_HALF[L][1]) - 4.5                 # ผิวล่างไม่ลงต่ำกว่าเนื้อโฟม (ไม่จมพื้นอะคริลิก)
    for i, (p, q) in enumerate(zip(pts, pts[1:])):
        rb.append(prism(f"out.B.ramp.{L}.{i + 1}", M, f"ทางลาด B เลน{th} ท่อน {i + 1} ลาด {math.degrees(math.atan2(q[1] - p[1], q[0] - p[0])):.0f}°", "xz",
                        [p, q, (q[0], max(q[1] - 3, zmin)), (p[0], max(p[1] - 3, zmin))], (y0, y1), cl))
        if i < len(RAMP_IN) + 1:
            for nm, (ry0, ry1) in (("rail1", (y0 - 2, y0)), ("rail2", (y1, y1 + 2))):
                rb.append(prism(f"out.B.ramp.{L}.{nm}.{i + 1}", M, f"รางข้างทางลาด B (สูง {RAIL_H:g})", "xz",
                                [p, q, (q[0], q[1] + RAIL_H), (p[0], p[1] + RAIL_H)], (ry0, ry1), cl))
    px0 = pts[0][0] + 2
    pz = pts[0][1] + (px0 + 3 - pts[0][0]) * t(RAMP_IN[0]) - 3
    for nm, (py0, py1) in (("1", (y0, y0 + 3)), ("2", (y1 - 3, y1))):
        rb.append(box(f"out.B.post.{L}{nm}", M, "เสาค้ำทางลาด B", (px0, py0, Ztop((py0 + py1) / 2)), (px0 + 3, py1, pz), cl))
    RUNOUTS["B"]["lanes"][L] = [list(map(R1, p)) for p in (pts[:-1] if pts[-1][0] >= G_B - 0.05 else pts)] + lane_tail("B", Ztop(yc), CHUTE)
rb += pocket_curved("B", G_B, X_STOP_B, "eva_B", CHUTE, Ztop)
rb.append(stop_foam("B", X_STOP_B, "eva_B", Ztop))

for key, ids, nm in [("reject", rej, "ชุดรางไข่เสีย"), ("A", ra, "ชุดราง A"), ("B", rb, "ชุดราง B")]:
    group(f"insert.{key}", ids, {"type": "translate", "axis": [0, -1, 0], "states": {"IN": 0, "OUT": 290}, "default": "IN",
                                  "note": "ก่อนดึงออก F1/K2 ต้องอยู่ STOP"}, nm)

box("base.plate", "base", "แผ่นฐาน", (0, -130, 0), (X_END + 3, YB, 5), "base")
parts.insert(0, parts.pop())

# ------------------------------------------------------------------ module 5: display + Pi on AI roof
M = "display"
DY = (YB - 151) / 2        # จอเลื่อนตามกึ่งกลางตู้ AI ที่ลึกขึ้น (ออกแบบไว้ที่ YB = 151)
rot = {"axis": [1, 0, 0], "deg": 35, "pivot": [249, 20 + DY, 253]}
box("disp.body", M, "Raspberry Pi Touch Display 2 7\" (189.5×120×15)", (154.25, 20 + DY, 238), (343.75, 140 + DY, 253), "screen_body", transform={"rotate": rot})
box("disp.face", M, "จอภาพ 155×88", (171.25, 36 + DY, 252.8), (326.75, 124 + DY, 253.2), "screen_face", transform={"rotate": rot})
box("disp.pi5", M, "Raspberry Pi 5 + Active Cooler (ยึดหลังจอ)", (206.5, 52 + DY, 212), (291.5, 108 + DY, 238), "pcb_green", transform={"rotate": rot})
for nm, (x0, x1) in {"l": (185, 190), "r": (308, 313)}.items():
    prism(f"disp.bracket.{nm}", M, "ฉากแท่นจอ 35°", "yz",
          [(25 + DY, 235), (127 + DY, 235), (127 + DY, 309), (28.6 + DY, 240.7)], (x0, x1), "acrylic_black")

# ------------------------------------------------------------------ labels
labels = [
    {"text": "ถาดป้อน + escapement", "pos": [90, Y_MID, 200]},
    {"text": "ตู้ AI (กล้อง + ลูกกลิ้ง)", "pos": [249, Y_MID, 345]},
    {"text": "กล่องชั่ง (load cell + K1 + K2 + ราง A/B)", "pos": [(318 + X_END) / 2, Y_MID, 200]},
    {"text": "K2 แยก A/B", "pos": [X_K2 + 40, Y_MID, 150]},
    {"text": "ถาด เสีย / A / B", "pos": [(321 + X_END) / 2, -110, 80]},
    {"text": "แผงปุ่ม E-STOP / START", "pos": [120, -40, 120]},
]

def part_points(p):
    """จุดมุมของชิ้นส่วน (ท่าอ้างอิง รวม transform.rotate) สำหรับคำนวณกรอบรวม"""
    if p["shape"] == "box":
        (x0, y0, z0), (x1, y1, z1) = p["min"], p["max"]
        pts = [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    elif p["shape"] == "cylinder":
        h = [p["radius"]] * 3; h["xyz".index(p["axis"])] = p["length"] / 2
        pts = [tuple(cc + sg * hh for cc, hh, sg in zip(p["center"], h, sgn))
               for sgn in [(a, b, d) for a in (-1, 1) for b in (-1, 1) for d in (-1, 1)]]
    else:
        iu, iv, iw = {"xz": (0, 2, 1), "yz": (1, 2, 0), "xy": (0, 1, 2)}[p["plane"]]
        pts = []
        for u, v in p["points"]:
            for w in p["extrude"]:
                q = [0.0, 0.0, 0.0]; q[iu], q[iv], q[iw] = u, v, w; pts.append(tuple(q))
    tr = p.get("transform", {}).get("rotate")
    if tr:
        ax = tr["axis"]; th = math.radians(tr["deg"]); ct, st = math.cos(th), math.sin(th); pv = tr["pivot"]
        def rot_pt(q):
            v = [q[i] - pv[i] for i in range(3)]
            cr = [ax[1] * v[2] - ax[2] * v[1], ax[2] * v[0] - ax[0] * v[2], ax[0] * v[1] - ax[1] * v[0]]
            dt = sum(ax[i] * v[i] for i in range(3))
            return tuple(pv[i] + v[i] * ct + cr[i] * st + ax[i] * dt * (1 - ct) for i in range(3))
        pts = [rot_pt(q) for q in pts]
    return pts

ALL_PTS = [q for p in parts for q in part_points(p)]
BBOX_MIN = [R1(min(q[i] for q in ALL_PTS)) for i in range(3)]
BBOX_MAX = [R1(max(q[i] for q in ALL_PTS)) for i in range(3)]

meta = {
    "name": "Egg sorter v2 — 3D spec",
    "units": "mm", "up_axis": "Z",
    "axes": {"X": "ทิศไข่ไหล ซ้าย→ขวา (0 = ขอบซ้ายถาดป้อน)", "Y": "หน้า→หลัง (0 = ผิวหน้าราง)", "Z": "ขึ้น (0 = ผิวโต๊ะ)"},
    "bounding_box": {"min": BBOX_MIN, "max": BBOX_MAX},
    "source_doc": "https://claude.ai/artifact/XuhBVGGremGzTkBKat2fBy",
    "egg": {"diameter": EGG_B, "length": EGG_L, "radii_long_axis_y": [EGG_B / 2, EGG_L / 2, EGG_B / 2], "material": "egg",
            "note": "ไข่ออกแบบ: ไข่ไก่เบอร์ 0 ถึงราว 80 g + เผื่อ (escapement รองรับไข่เบอร์ 5 ขึ้นไป)"},
    "lanes": {k: {"y_center": LANE[k], "y_range": list(LANE_Y[k])} for k in LANE},
    "chute_surface": CHUTE,
    "chute_surface_reject": CHUTE_REJECT,
    "egg_runouts": {**RUNOUTS, "note": "ผิวบนของทางลง (แผ่นรับ/ทางลาดตายตัว) ที่กึ่งกลางเลน [x, z] จนถึงผิวโฟมกันชน ; G = ร่องที่แนบพื้น ; "
                                       "shape = curved (ร่องเว้า) | straight (ผนังโฟมตรง) ; rest_x = X กึ่งกลางไข่ที่พักในแอ่ง (แกนยาวขนาน Y) ; "
                                       "groove = หน้าตัดร่อง [x, ความสูงเทียบพื้นเดิม] จาก G ถึง stop_x (ร่องต่อยาวถึงถาดหน้า ความชันเท่าพื้นเดิม)"},
    "version": "2026-11-17",
}

out = {"meta": meta, "materials": materials, "parts": parts, "groups": groups, "labels": labels}
json.dump(out, open(os.path.join(OUT, "parts.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(parts), "parts,", len(groups), "groups")
print("X_P0", X_P0, " G_R", G_R, " X_STOP_R", R1(X_STOP_R), " G_A", G_A, " G_B", G_B, " X_END", X_END, " K2_DROP", K2_DROP, " F1_REJECT", F1_REJECT, " B_OPEN_TOP", B_OPEN_TOP)
