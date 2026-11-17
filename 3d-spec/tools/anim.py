"""Egg path keyframes for each lane / outcome -> animation.json"""
import os
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

import json, math

t = lambda d: math.tan(math.radians(d))
s = lambda d: math.sin(math.radians(d))
c = lambda d: math.cos(math.radians(d))
PARTS = json.load(open(os.path.join(OUT, "parts.json"), encoding="utf-8"))   # รัน gen.py ก่อน anim.py
META = PARTS["meta"]
EGG_RADII = tuple(META["egg"]["radii_long_axis_y"])   # (a, b, a): แกนยาวขนาน Y
r = EGG_RADII[0]                                      # รัศมีตามแนวกลิ้ง
Ztray = lambda x: 123.4 + (180 - x) * t(6)
CHUTES = {"AB": META["chute_surface"], "reject": META["chute_surface_reject"]}   # ผิวโฟมราง A/B และรางเสีย
def Ztop(y, ch="AB"):
    CH = CHUTES[ch]
    return CH["z0"] + y * t(CH["slope_back_deg"] if y >= 0 else CH["slope_front_deg"])
R = lambda v: [round(a, 1) for a in v]
LANE = {k: v["y_center"] for k, v in META["lanes"].items()}
PART = {p["id"]: p for p in PARTS["parts"]}

# ลูกกลิ้งทั้งสองหมุนรอบ +Y ไข่ที่วางอยู่บนลูกกลิ้งจึงหมุนสวนทาง (รอบ −Y)
EGG_SPIN_AXIS = [-v for v in next(g for g in PARTS["groups"] if g["id"] == "roller.F")["motion"]["axis"]]

def on_chute_z(y, la, ch="AB"):
    """Z กึ่งกลางไข่ที่วางบนผิวรางเอียงตามแกน Y (ทรงรีแตะผิวเอียง ไม่ใช่ r ตรงๆ)"""
    CH = CHUTES[ch]
    ang = CH["slope_back_deg"] if y >= 0 else CH["slope_front_deg"]
    a, b = EGG_RADII[0], EGG_RADII[1]
    ry = b if la == "y" else a                 # รัศมีของไข่ในทิศที่ผิวเอียง (แกน Y)
    return Ztop(y, ch) + math.hypot(ry * s(ang), a * c(ang)) / c(ang)

def roller_valley_z(L):
    """ไข่วางในร่องระหว่างลูกกลิ้ง 2 ลูก"""
    r1, r2 = PART[f"ai.{L}.roller1"], PART[f"ai.{L}.roller2"]
    half = (r2["center"][0] - r1["center"][0]) / 2
    return r1["center"][2] + math.sqrt((r + r1["radius"]) ** 2 - half ** 2)


def platform_z(L, x):
    """ผิวบนแท่นชั่ง (เอียง 3°) ที่ตำแหน่ง x"""
    (x0, z0), (x1, z1) = PART[f"sc.{L}.platform"]["points"][:2]
    return z0 + (x - x0) * (z1 - z0) / (x1 - x0)


def gate_rest(L, y):
    """กึ่งกลางไข่ฟองแรกที่พิงหมุดคู่ P1 (ก้ามปู) บนพื้นถาดเอียง 6°
    อ่านตำแหน่ง/ความสูงหมุดจาก parts.json แล้วเลื่อนไข่ลงตามพื้นถาดจนแตะหมุด (bisection)
    ไข่แตะขอบบนของหมุด ไม่ใช่แนวเส้นศูนย์สูตรของไข่ จึงพักลึกกว่าสูตร 168 − 3 − r"""
    pins = [p for p in PARTS["parts"] if p["id"].startswith(f"esc.{L}.pinP1")]
    hold = next(g for g in PARTS["groups"] if g["id"] == f"esc.{L}.p1")["motion"]
    lift = hold["states"][hold["default"]]
    a, b, cz = EGG_RADII
    ux, uz = (c(6), -s(6)), (s(6), c(6))          # แกนของไข่ตามแนวพื้นถาด (ระนาบ XZ)
    centre = lambda x: (x, y, Ztray(x) + cz / c(6))
    samples = []                                  # จุดบนผิวหมุด (ท่า HOLD)
    for p in pins:
        px, py, pz = p["center"]; top = pz + p["length"] / 2 + lift; bottom = pz - p["length"] / 2 + lift
        for i in range(41):
            zz = bottom + (top - bottom) * i / 40
            for k in range(48):
                th = 2 * math.pi * k / 48
                for rr in (0.0, p["radius"] / 2, p["radius"]):
                    samples.append((px + rr * math.cos(th), py + rr * math.sin(th), zz))
    def touches(x):
        cx, cy, cc = centre(x)
        for qx, qy, qz in samples:
            dx, dy, dz = qx - cx, qy - cy, qz - cc
            if ((dx * ux[0] + dz * ux[1]) / a) ** 2 + (dy / b) ** 2 + ((dx * uz[0] + dz * uz[1]) / cz) ** 2 < 1:
                return True
        return False
    lo = min(p["center"][0] for p in pins) - 60
    hi = min(p["center"][0] for p in pins)
    for _ in range(40):
        mid = (lo + hi) / 2
        lo, hi = (lo, mid) if touches(mid) else (mid, hi)
    return centre(lo)

def common_ai(L, y):
    """keyframes from gate to inspection done (t 0 .. 3.6)"""
    gate = gate_rest(L, y)
    ramp = (195, y, 123.1 - 12 * t(10) + r / c(10))
    valley = (235, y, roller_valley_z(L))
    return [
        {"t": 0.0, "egg": {"pos": R(gate), "long_axis": "y"}, "rest": True,
         "set": {f"esc.{L}": "HOLD", f"f1.{L}": "STOP", f"k0.{L}": "REST", f"k1.{L}": "REST", f"k2.{L}": "STOP", f"roller.{L}": "OFF"},
         "note": "ไข่ฟองแรกพิงหมุด P1 รอปล่อย"},
        {"t": 0.05, "set": {f"esc.{L}": "RELEASE"}, "note": "escapement ปล่อย 1 ฟอง"},
        {"t": 0.35, "egg": {"pos": R(ramp), "long_axis": "y"}, "set": {f"esc.{L}": "HOLD"}, "event": f"S1.{L} นับ +1"},
        {"t": 0.7, "egg": {"pos": R(valley), "long_axis": "y"}, "rest": True, "note": "ไข่ตกร่องลูกกลิ้ง F1 กั้นไว้"},
        {"t": 1.2, "set": {f"roller.{L}": "ON", "light.top": "ON"}, "egg": {"spin_rpm": 56, "spin_axis": EGG_SPIN_AXIS},
         "note": "หมุนไข่ ถ่าย ~10 เฟรม ไฟบน"},
        {"t": 2.4, "set": {"light.top": "OFF", f"light.candle.{L}": "ON"}, "note": "ถ่ายโหมดส่องล่าง (candling)"},
        {"t": 3.6, "set": {f"roller.{L}": "OFF", f"light.candle.{L}": "OFF"}, "egg": {"spin_rpm": 0}, "note": "YOLO ตัดสินผล"},
    ]

GROUP = {g["id"]: g for g in PARTS["groups"]}

def f1_geom(L):
    """บาน F1: (บานพับ x, z), ความยาว, สถานะ → มุม"""
    mo = GROUP[f"f1.{L}"]["motion"]; p = PART[f"ai.{L}.f1"]
    return (mo["pivot"][0], mo["pivot"][2]), p["max"][0] - p["min"][0], mo["states"]

def on_line(px, pz, ang, x):
    """กึ่งกลางไข่ (ทรงกลม r) ที่วางบนผิวตรงผ่านจุด (px, pz) ลาด ang ณ ตำแหน่ง x ของกึ่งกลางไข่"""
    return pz + (x - px) * t(ang) + r / c(ang)

def circle_cross(c1, r1, c2, r2):
    """จุดตัดของวงกลม 2 วง (เลือกจุดที่สูงกว่า)"""
    dx, dz = c2[0] - c1[0], c2[1] - c1[1]; d = math.hypot(dx, dz)
    a = (r1 * r1 - r2 * r2 + d * d) / (2 * d); h = math.sqrt(max(r1 * r1 - a * a, 0))
    mx, mz = c1[0] + a * dx / d, c1[1] + a * dz / d
    cands = [(mx + h * dz / d, mz - h * dx / d), (mx - h * dz / d, mz + h * dx / d)]
    return max(cands, key=lambda q: q[1])

def arc(center, rad, th0, th1, n):
    """จุดบนส่วนโค้งรอบ center จากมุม th0 ถึง th1 (องศา) n จุด ไม่รวมจุดเริ่ม"""
    return [(center[0] + rad * c(th0 + (th1 - th0) * k / n), center[1] + rad * s(th0 + (th1 - th0) * k / n)) for k in range(1, n + 1)]

def over_roller_onto_f1(L, ang):
    """ไข่จากยอดลูกกลิ้ง 2 กลิ้งลงบาน F1 ที่มุม ang: โค้งรอบลูกกลิ้ง 2 แล้วโค้งรอบขอบบานพับ จนแนบผิวบาน"""
    rl = PART[f"ai.{L}.roller2"]; rc = (rl["center"][0], rl["center"][2]); rr = rl["radius"]
    (hx, hz), _, _ = f1_geom(L)
    p = circle_cross(rc, rr + r, (hx, hz), r)                     # ไข่แตะทั้งลูกกลิ้งและขอบบานพับ
    th_r = math.degrees(math.atan2(p[1] - rc[1], p[0] - rc[0]))
    th_h = math.degrees(math.atan2(p[1] - hz, p[0] - hx))
    th_n = math.degrees(math.atan2(c(ang), -s(ang)))              # แนวตั้งฉากผิวบาน
    pts = arc(rc, rr + r, 90, th_r, 2)
    if th_h > th_n + 1:
        pts += arc((hx, hz), r, th_h, th_n, max(1, round((th_h - th_n) / 15)))
    return pts

def platform_rest_x(L):
    return PART[f"sc.{L}.platform"]["points"][0][0] + 34.3          # เท่าแบบเดิม (ขอบซ้ายแท่น + 34.3)

RUNOUTS = META["egg_runouts"]
Y_MID = (META["lanes"]["F"]["y_range"][1] + META["lanes"]["B"]["y_range"][0]) / 2
lane_of = lambda y: "F" if y < Y_MID else "B"
G_ACC = 9810.0                     # มม./s²
V_START = 300.0                    # ความเร็วไข่ตอนเริ่มเส้นทาง (มม./s) หลัง K0/K1 ดัน

def offset_path(surface, arc_step=10.0):
    """เส้นทางกึ่งกลางไข่ (ทรงกลม r) ที่กลิ้งแนบผิว polyline [(x, z), ...] ไปทาง +X
    มุมเว้า = จุดตัดของเส้นขนาน ; มุมนูน = ส่วนโค้งรอบมุม"""
    # รวมช่องต่อสั้นๆ (ช่องปลายบาน → แผ่นรับ ~1.5 มม.) ไม่ให้จุดตัดเส้นขนานย้อนกลับ ; ไข่ข้ามช่องแคบกว่าตัวเองได้
    pts = [surface[0]]
    for q in surface[1:-1]:
        if math.hypot(q[0] - pts[-1][0], q[1] - pts[-1][1]) >= 2.0: pts.append(q)
    pts.append(surface[-1])
    segs = [(p, q) for p, q in zip(pts, pts[1:]) if math.hypot(q[0] - p[0], q[1] - p[1]) > 1e-6]
    ang = [math.degrees(math.atan2(q[1] - p[1], q[0] - p[0])) for p, q in segs]
    nrm = lambda th: (-s(th), c(th))
    out = [(segs[0][0][0] + r * nrm(ang[0])[0], segs[0][0][1] + r * nrm(ang[0])[1])]
    for i in range(1, len(segs)):
        V = segs[i][0]; a0, a1 = ang[i - 1], ang[i]
        if a1 >= a0:   # เว้า (หรือตรง): จุดตัดเส้นขนาน
            h = r / c((a1 - a0) / 2); bis = (a0 + a1) / 2 + 90
            out.append((V[0] + h * c(bis), V[1] + h * s(bis)))
        else:          # นูน: โค้งรอบมุม
            n = max(1, math.ceil((a0 - a1) / arc_step))
            for k in range(n + 1):
                th = a0 + (a1 - a0) * k / n + 90
                out.append((V[0] + r * c(th), V[1] + r * s(th)))
    E = segs[-1][1]
    out.append((E[0] + r * nrm(ang[-1])[0], E[1] + r * nrm(ang[-1])[1]))
    return out

def clip_x(path, x_max):
    """ตัดเส้นทางที่ x ไม่เกิน x_max (เติมจุดปลายด้วยการ interpolate)"""
    out = [path[0]]
    for p, q in zip(path, path[1:]):
        if q[0] <= x_max:
            out.append(q); continue
        if p[0] < x_max:
            f = (x_max - p[0]) / (q[0] - p[0]); out.append((x_max, p[1] + f * (q[1] - p[1])))
        break
    return out

def thin(path, min_d=1.0):
    """ตัดจุดที่ถี่เกิน (เก็บจุดแรก/สุดท้าย)"""
    out = [path[0]]
    for p in path[1:-1]:
        if math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) >= min_d: out.append(p)
    out.append(path[-1])
    return out

def timed(path, t0, z_top=None):
    """เวลาที่ไข่ถึงแต่ละจุด: ความเร็วจากพลังงาน (กลิ้งไม่ไถล v² = v0² + 10/7·g·Δz)"""
    z_top = path[0][1] if z_top is None else z_top
    ts, tt = [], t0
    for p, q in zip(path, path[1:]):
        v = math.sqrt(V_START ** 2 + 10 / 7 * G_ACC * max(z_top - (p[1] + q[1]) / 2, 0))
        tt += math.hypot(q[0] - p[0], q[1] - p[1]) / v
        ts.append(round(tt, 3))
    return ts

def surf_pts(key, L, step=0.5):
    """จุดบนผิวทางลง (กึ่งกลางเลน) ถี่ทุก step มม."""
    pl = RUNOUTS[key]["lanes"][L]; pts = []
    for (x0, z0), (x1, z1) in zip(pl, pl[1:]):
        n = max(1, int(math.hypot(x1 - x0, z1 - z0) / step))
        pts += [(x0 + (x1 - x0) * k / n, z0 + (z1 - z0) * k / n) for k in range(n + 1)]
    return pts

Y_CHUTE_END = PART["out.A.chute.surface"]["points"][1][0]   # ขอบหลังผิวพื้นราง
def pocket_z(key, x, y, la, ch):
    """Z กึ่งกลางไข่ที่ (x, y) ในแอ่ง: วางบนพื้นรางเอียง (หรือในร่องเว้าของแอ่งโค้ง ซึ่งต่อยาวถึงถาดหน้า)
    และไม่จมผิวทางลง/เนิน (ทรงรีหน้าตัด XZ) ของทุกเลนที่ไข่คร่อมอยู่ (ทางลงมีเฉพาะในราง Y ≥ 0)"""
    ax = EGG_RADII[0] if la == "y" else EGG_RADII[1]
    ry = EGG_RADII[1] if la == "y" else EGG_RADII[0]
    z = on_chute_z(y, la, ch)
    if RUNOUTS[key]["shape"] == "curved":
        CH = CHUTES[ch]
        z += groove_rise(key, x) / c(CH["slope_back_deg"] if y >= 0 else CH["slope_front_deg"])
    G = RUNOUTS[key]["G"]
    for L, (y0, y1) in (("F", (0, Y_MID)), ("B", (Y_MID, Y_CHUTE_END))):
        if not (y - ry < y1 and y + ry > y0): continue
        for px, pz in surf_pts(key, L):
            if px > G + 0.01: continue                      # ช่วงร่อง คิดแล้วด้านบน
            d = (px - x) / ax
            if abs(d) < 1: z = max(z, pz + r * math.sqrt(1 - d * d) + 0.4)
    return z

def groove_rise(key, x, step=0.5):
    """กึ่งกลางไข่ (หน้าตัด XZ เป็นวงกลม r) ที่ตำแหน่ง x สูงกว่าตอนวางบนพื้นเรียบเท่าไร (ติดลบ = จมลงในร่อง)
    คิดในกรอบพื้นราบ จากหน้าตัดร่อง + พื้นเรียบทางซ้ายของร่อง G"""
    pl = RUNOUTS[key]["groove"]
    pl = [[pl[0][0] - 2 * r, 0.0]] + pl
    rise = -1e9
    for (x0, h0), (x1, h1) in zip(pl, pl[1:]):
        n = max(1, int(math.hypot(x1 - x0, h1 - h0) / step))
        for k in range(n + 1):
            px, ph = x0 + (x1 - x0) * k / n, h0 + (h1 - h0) * k / n
            if abs(px - x) < r: rise = max(rise, ph + math.sqrt(r * r - (px - x) ** 2) - r)
    return rise if rise > -1e8 else 0.0                      # ไกลจากร่อง = พื้นเรียบ

def to_tray(key, ch, L, start, t0):
    """ไข่ (แกนยาวขนาน Y) ไถลตรงไปถาดหน้าตามพื้นเอียง ; ช่วงที่ยังคร่อมราง (Y ≥ 0) ยกตัวข้ามผิวทางลงถ้าจำเป็น
    สมมติว่าไข่ไถลได้เอง (ยังไม่ได้ทดลองว่าพื้นเอียง 5° พอหรือไม่)"""
    x, y = start
    b = EGG_RADII[1]
    kfs, tt = [], t0
    ys = [y - 10] + [v for v in range(int(y - 10) - 8, -int(b) - 4, -8)]
    for i, yy in enumerate(ys):
        tt = round(tt + (0.4 if i == 0 else 0.06), 2)
        kfs.append({"t": tt, "egg": {"pos": R((x, yy, pocket_z(key, x, yy, "y", ch))), "long_axis": "y"}, "path": True})
    kfs[0]["note"] = "ไข่ไถลไปด้านหน้าตามพื้นเอียง (แกนยาวยังขนาน Y — รอผลทดลองความชันพื้น)"
    kfs.append({"t": round(tt + 0.6, 2), "egg": {"pos": R((x, -125 + b, pocket_z(key, x, -125 + b, "y", ch))), "long_axis": "y"}, "rest": True, "path": True,
                "note": f"ถึงถาดหน้า{' ไข่เสีย' if key == 'reject' else ' ' + key}"})
    return kfs

def follow(L, surface, x_from, x_to, t0, events=None, z_floor=None):
    """keyframe ตามผิว polyline จาก x_from ถึง x_to ; เวลาจากความเร็วตามพลังงาน ; ใส่ event/set ที่จุดแรกที่ผ่าน x ที่กำหนด"""
    y = LANE[L]
    path = [p for p in offset_path(surface) if p[0] >= x_from - 1e-6]
    path = thin(clip_x(path, x_to))
    ts = timed(path, t0)
    for i in range(len(ts)):                               # เวลาต้องเพิ่มขึ้นเสมอหลังปัดเศษ
        ts[i] = max(ts[i], round((ts[i - 1] if i else t0) + 0.001, 3))
    kfs = []
    for (x, z), tt in zip(path[1:], ts):
        if z_floor is not None: z = max(z, z_floor(x))
        kfs.append({"t": tt, "egg": {"pos": R((x, y, z)), "long_axis": "y"}, "path": True})
    events = list(events or [])
    if events and events[0][0] is None:                     # set/event ที่จุดแรก (ไม่ตรวจช่วงดัน)
        kfs[0].update(events[0][1]); kfs[0].pop("path", None); events = events[1:]
    for x_ev, extra in events:
        kf = next((k for k in kfs if k["egg"]["pos"][0] >= x_ev), kfs[-1])
        for k_, v_ in extra.items():
            kf[k_] = {**kf.get(k_, {}), **v_} if isinstance(v_, dict) else v_
    return kfs

def descent(L, key, surface, t0, x_from, events=None):
    """ลงทางลง → แอ่ง (แกนยาวขนาน Y ตลอด) → ไถลไปถาดหน้า
    แอ่งโค้ง: ไข่ลงร่องเว้า เลยก้นร่องขึ้นไปแตะกันชนท้าย แล้วไหลกลับมาพักที่ก้นร่อง ; ผนังตรง: ไข่กลิ้งไปหยุดชิดกันชนโฟม"""
    y = LANE[L]; ch = "reject" if key == "reject" else "AB"
    m = RUNOUTS[key]
    G, x_rest = m["G"], m["rest_x"]
    if m["shape"] == "curved":
        x_wall = m["stop_x"] - r - 0.5                      # ไข่แตะผิวกันชนท้ายแอ่ง
        kfs = follow(L, surface, x_from, x_wall, t0, events,
                     z_floor=lambda x: pocket_z(key, x, y, "y", ch) if x > G else -1e9)
        kfs[-1]["note"] = "ไข่ลงร่องเว้า เลยก้นร่องขึ้นไปแตะกันชนท้ายแอ่ง"
        t_rest = round(kfs[-1]["t"] + 0.4, 2)
        kfs.append({"t": t_rest, "egg": {"pos": R((x_rest, y, pocket_z(key, x_rest, y, "y", ch))), "long_axis": "y"}, "rest": True, "path": True,
                    "note": "ไข่ไหลกลับมาพักที่ก้นร่อง แกนยาวยังขนาน Y"})
    else:
        kfs = follow(L, surface, x_from, x_rest, t0, events,
                     z_floor=lambda x: on_chute_z(y, "y", ch) if x > G else -1e9)
        kfs[-1].update({"rest": True, "note": "ไข่ชนกันชนโฟมตรงท้ายแอ่งแล้วหยุด (แกนยาวขนาน Y)"})
        t_rest = kfs[-1]["t"]
    return kfs + to_tray(key, ch, L, (x_rest, y), t_rest)

def platform_rest_x(L):
    return PART[f"sc.{L}.platform"]["points"][0][0] + 34.3          # เท่าแบบเดิม (ขอบซ้ายแท่น + 34.3)

def plate_surface(gid, state):
    """ผิวบนของบาน (box) ที่หมุนรอบ pivot ตามสถานะ: [(pivot x, z), (ปลาย x, z)]"""
    mo = GROUP[gid]["motion"]; a = mo["states"][state]; pv = mo["pivot"]
    p = PART[GROUP[gid]["parts"][0]]; Lp = p["max"][0] - p["min"][0]
    return [(pv[0], pv[2]), (pv[0] + Lp * c(a), pv[2] + Lp * s(a))]

def seq_good(L, outcome):
    y = LANE[L]
    k = common_ai(L, y)
    (hx, hz), FL, st = f1_geom(L)
    ab = st["BRIDGE"]
    fb = PART[f"sc.{L}.fixbridge"]["points"]
    px = platform_rest_x(L)
    plat = (px, y, platform_z(L, px) + r / c(3))         # บนผิวเรียบ (ของจริงจมในแอ่ง 2.5 มม.)
    kick0 = (241, y, roller_valley_z(L) + 7.9)          # K0 ยกไข่พ้นร่องลูกกลิ้ง
    k1p = GROUP[f"k1.{L}"]["motion"]["pivot"]
    kick1 = (k1p[0], y, platform_z(L, k1p[0]) + r / c(3) + 1.2)   # K1 ดันไข่ออกจากแอ่ง
    rl = PART[f"ai.{L}.roller2"]
    top2 = (rl["center"][0], rl["center"][2] + rl["radius"] + r)
    k += [
        {"t": 3.8, "set": {f"f1.{L}": "BRIDGE"}, "note": "ไข่ดี + ตู้ชั่งว่าง → F1 เป็นสะพาน"},
        {"t": 4.0, "set": {f"k0.{L}": "KICK"}, "egg": {"pos": R(kick0), "long_axis": "y"}},
        {"t": 4.15, "egg": {"pos": R((top2[0], y, top2[1])), "long_axis": "y"}, "set": {f"k0.{L}": "REST"}},
    ]
    tt = 4.15
    for q in over_roller_onto_f1(L, ab):
        tt = round(tt + 0.05, 2)
        k.append({"t": tt, "egg": {"pos": R((q[0], y, q[1])), "long_axis": "y"}, "path": True})
    fb2 = PART[f"sc.{L}.fixbridge2"]["points"]; plp = PART[f"sc.{L}.platform"]["points"]
    surf = plate_surface(f"f1.{L}", "BRIDGE") + [tuple(fb[0]), tuple(fb[1]), tuple(fb2[1]), tuple(plp[0]), tuple(plp[1])]
    on = follow(L, surf, k[-1]["egg"]["pos"][0], px, tt,
                [(300, {"event": "กล้องเห็นรางลูกกลิ้งว่าง"}), (fb[0][0], {"note": "ข้ามสะพานตายตัว"})])
    on[-1].update({"rest": True, "set": {f"f1.{L}": "STOP"}, "event": "น้ำหนัก > 35 g", "note": "ไข่หยุดในแอ่งแท่นชั่ง"})
    t_plat = on[-1]["t"]
    k += on + [{"t": round(t_plat + 1.0, 2), "event": "น้ำหนักนิ่ง → เทียบเกณฑ์ A/B"}]
    pl = PART[f"sc.{L}.platform"]["points"]; tr = PART[f"sc.{L}.transfer"]["points"]
    surface = [(pl[0][0], pl[0][1]), (pl[1][0], pl[1][1]), (tr[0][0], tr[0][1]), (tr[1][0], tr[1][1])]
    ev = [(pl[1][0], {"event": "น้ำหนัก < 2 g → ตู้ชั่งว่าง"})]
    if outcome == "A":
        surface += plate_surface(f"k2.{L}", "DROP") + [tuple(p) for p in RUNOUTS["A"]["lanes"][L]]
        k += [{"t": round(t_plat + 1.1, 2), "set": {f"k2.{L}": "DROP"}, "note": f"K2 พับลง {GROUP[f'k2.{L}']['motion']['states']['DROP']:g}° เป็นทางลาดลงราง A"},
              {"t": round(t_plat + 1.35, 2), "set": {f"k1.{L}": "KICK"}, "egg": {"pos": R(kick1), "long_axis": "y"}}]
    else:  # B
        bb = PART[f"sc.{L}.bridge"]["points"]
        surface += plate_surface(f"k2.{L}", "BRIDGE") + [(bb[0][0], bb[0][1]), (bb[1][0], bb[1][1])] + [tuple(p) for p in RUNOUTS["B"]["lanes"][L]]
        k += [{"t": round(t_plat + 1.1, 2), "set": {f"k2.{L}": "BRIDGE"}, "note": f"K2 เป็นสะพาน {GROUP[f'k2.{L}']['motion']['states']['BRIDGE']:g}°"},
              {"t": round(t_plat + 1.35, 2), "set": {f"k1.{L}": "KICK"}, "egg": {"pos": R(kick1), "long_axis": "y"}}]
    ev.insert(0, (None, {"set": {f"k1.{L}": "REST"}}))
    ev.append((1e9, {"set": {f"k2.{L}": "STOP"}}))          # ไข่ถึงแอ่งแล้ว (พ้นบาน K2) K2 กลับ STOP
    k += descent(L, outcome, surface, round(t_plat + 1.35, 2), kick1[0], ev)
    return k

def seq_reject(L):
    y = LANE[L]
    k = common_ai(L, y)
    (hx, hz), FL, st = f1_geom(L)
    ar = st["REJECT"]
    kick0 = (241, y, roller_valley_z(L) + 7.9)
    rl = PART[f"ai.{L}.roller2"]
    top2 = (rl["center"][0], rl["center"][2] + rl["radius"] + r)
    k += [
        {"t": 3.8, "set": {f"f1.{L}": "REJECT"}, "note": f"ไข่เสีย → F1 พับลง {ar:g}° เป็นทางลาดลงแอ่งรางเสีย (ไม่ต้องรอตู้ชั่ง)"},
        {"t": 4.0, "set": {f"k0.{L}": "KICK"}, "egg": {"pos": R(kick0), "long_axis": "y"}, "note": "F1 ถึงท่าแล้ว K0 จึงดีด"},
        {"t": 4.15, "egg": {"pos": R((top2[0], y, top2[1])), "long_axis": "y"}, "set": {f"k0.{L}": "REST"}},
    ]
    tt = 4.15
    arcs = over_roller_onto_f1(L, ar)
    for q in arcs:
        tt = round(tt + 0.03, 2)
        k.append({"t": tt, "egg": {"pos": R((q[0], y, q[1])), "long_axis": "y"}, "path": True})
    surface = plate_surface(f"f1.{L}", "REJECT") + [tuple(p) for p in RUNOUTS["reject"]["lanes"][L]]
    ev = [(RUNOUTS["reject"]["G"] - 30, {"event": "กล้องเห็นรางลูกกลิ้งว่าง → นับไข่เสีย +1"})]
    ev.append((1e9, {"set": {f"f1.{L}": "STOP"}}))          # ไข่ถึงแอ่งแล้ว F1 กลับ STOP
    k += descent(L, "reject", surface, tt, arcs[-1][0], ev)
    return k

seqs = [
    {"id": "F_good_A", "lane": "F", "outcome": "A", "keyframes": seq_good("F", "A")},
    {"id": "F_good_B", "lane": "F", "outcome": "B", "keyframes": seq_good("F", "B")},
    {"id": "B_good_A", "lane": "B", "outcome": "A", "keyframes": seq_good("B", "A")},
    {"id": "B_good_B", "lane": "B", "outcome": "B", "keyframes": seq_good("B", "B")},
    {"id": "F_reject", "lane": "F", "outcome": "reject", "keyframes": seq_reject("F")},
    {"id": "B_reject", "lane": "B", "outcome": "reject", "keyframes": seq_reject("B")},
]
# actuator = กลุ่มใน parts.json ที่ sequence สั่งเปลี่ยนสถานะ (กลุ่มที่ follows จะเปลี่ยนตามกลุ่มหลักเอง)
GROUPS = {g["id"]: g for g in PARTS["groups"]}
ACTUATORS = {gid: list(GROUPS[gid]["motion"]["states"])
             for gid in sorted({k for sq in seqs for kf in sq["keyframes"] for k in kf.get("set", {}) if k in GROUPS})}

# ไฟ: ชื่อที่ sequence ใช้ → ชิ้น LED ที่สลับ emissive (เลือกเฉพาะชิ้นที่วัสดุเป็น led)
def led_parts(prefix):
    return [p["id"] for p in PARTS["parts"] if p["id"].startswith(prefix) and p["material"] == "led"]
LIGHTS = {"light.top": {"parts": led_parts("ai.led.top."), "states": ["OFF", "ON"], "default": "OFF"}}
for L in LANE:
    LIGHTS[f"light.candle.{L}"] = {"parts": led_parts(f"ai.{L}.led."), "states": ["OFF", "ON"], "default": "OFF"}

# ไข่รอในถาดป้อน: ช่องคิวเรียงถอยจากจุดพักที่หมุด P1 ห่างกัน 1 ฟอง (ตามพื้นถาดเอียง 6°) ; ถาดยาวพอเลนละ 3 ฟอง
ESC_HOLD_T = 0.35                            # เวลาใน sequence ที่ escapement กลับ HOLD (ฟองถัดไปไหลลงมาที่ P1)
QUEUE_MOVE_T = 0.3                           # เวลาเลื่อนลงหนึ่งช่อง
def queue_slot(L, k):
    gx, gy, _ = SEQ_BY_ID[next(s for s, _ in PLAYLIST_ORDER if SEQ_BY_ID[s]["lane"] == L)]["keyframes"][0]["egg"]["pos"]
    x = gx - k * EGG_RADII[0] * 2 * c(6)
    return R((x, gy, Ztray(x) + EGG_RADII[2] / c(6)))

# demo_playlist: end_pos = จุดพักสุดท้ายในถาดหน้า ไข่ที่จะทับฟองที่อยู่ก่อน (ช่วง X ซ้อนกัน) ต่อคิวถอยไปทาง +Y ทีละ 1 ฟอง
PLAYLIST_ORDER = [("F_good_A", 0.0), ("B_reject", 1.5), ("F_good_B", 7.0), ("B_good_B", 8.5), ("F_reject", 14.0), ("B_good_A", 15.5)]
SEQ_BY_ID = {sq["id"]: sq for sq in seqs}
EGG_GAP = 1.0                               # ช่องว่างระหว่างไข่ที่ต่อคิวกัน (มม.)
PLAYLIST, resting = [], []
for seq_id, start in PLAYLIST_ORDER:
    fx, fy, _ = SEQ_BY_ID[seq_id]["keyframes"][-1]["egg"]["pos"]
    y = fy
    # แกนยาวขนาน Y: ไข่กินที่ตาม X = เส้นผ่านศูนย์กลาง, ตาม Y = ความยาว
    while any(abs(fx - ox) < 2 * r and abs(y - oy) < 2 * EGG_RADII[1] for ox, oy in resting):
        y += 2 * EGG_RADII[1] + EGG_GAP
    resting.append((fx, y))
    ch = "reject" if SEQ_BY_ID[seq_id]["outcome"] == "reject" else "AB"
    L = SEQ_BY_ID[seq_id]["lane"]
    before = [st for s, st in PLAYLIST_ORDER if SEQ_BY_ID[s]["lane"] == L and st < start]   # ฟองที่ปล่อยก่อนในเลนเดียวกัน
    queue = [{"t": 0.0, "pos": queue_slot(L, len(before))}]
    for i, st in enumerate(before):
        slot = len(before) - i
        queue += [{"t": round(st + ESC_HOLD_T, 2), "pos": queue_slot(L, slot)},
                  {"t": round(st + ESC_HOLD_T + QUEUE_MOVE_T, 2), "pos": queue_slot(L, slot - 1)}]
    PLAYLIST.append({"seq": seq_id, "start": start, "end_pos": R((fx, y, pocket_z(SEQ_BY_ID[seq_id]["outcome"], fx, y, "y", ch))), "queue": queue})

anim = {
    "meta": {"units": {"length": "mm", "time": "s"}, "egg_radii_long_axis_y": list(EGG_RADII),
             "long_axis": "y = แกนยาวของไข่ขนาน Y (กลิ้งไป ±X ; ในแอ่งไถลไป −Y โดยไม่กลิ้ง) ; x = แกนยาวขนาน X (กลิ้งไป −Y, ตอนนี้ไม่มี sequence ใช้)",
             "interpolation": "egg.pos เชิงเส้นระหว่าง keyframe ที่มี pos (หรือ Catmull-Rom); state ของ actuator เปลี่ยนแบบ tween 0.15–0.25 s",
             "rolling": f"มุมกลิ้งของไข่ = ระยะทาง / {r:g} rad รอบแกนยาว"},
    "actuators": ACTUATORS,
    "lights": LIGHTS,
    "sequences": seqs,
    "demo_playlist": PLAYLIST,
    "rules": [
        "escapement ปล่อยฟองใหม่ได้เมื่อรางลูกกลิ้งเลนนั้นว่าง",
        "F1 → BRIDGE ได้เมื่อแท่นชั่งเลนนั้นว่าง (< 2 g) และ K2 = STOP",
        "F1 → REJECT ก่อน แล้ว K0 จึงดีดไข่ลงทางลาด (ไม่มีขอบกั้นปลายบาน)",
        "ขณะไข่เสียเลนหลังอยู่ในแอ่ง/ไถลไปถาดหน้า: F1 เลนหน้าห้าม REJECT ; ขณะไข่เลนหลังอยู่ในราง A: K2 เลนหน้าห้าม DROP (คงไว้กันเหนียวตาม D14 ; check.py ข้อ 6 ตรวจทางไถลของไข่เลนหลัง)",
        "ไข่ทั้งสองเลนของรางเดียวกันพักที่ X เดียวกัน (ก้นร่องแอ่งโค้ง / ชิดกันชนราง A): ห้ามปล่อยไข่ลงรางที่ยังมีไข่ค้างในแอ่ง",
    ],
}
json.dump(anim, open(os.path.join(OUT, "animation.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for sq in seqs:
    print(sq["id"], "end t =", sq["keyframes"][-1]["t"], "final pos", sq["keyframes"][-1]["egg"]["pos"])
