"""Verify parts.json + animation.json: static overlaps, motion sweeps, insert removal, egg rest poses."""
import os
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

import json, math, itertools, fnmatch
import numpy as np

P = json.load(open(os.path.join(OUT, "parts.json"), encoding="utf-8"))
A = json.load(open(os.path.join(OUT, "animation.json"), encoding="utf-8"))
parts = {p["id"]: p for p in P["parts"]}
groups = {g["id"]: g for g in P["groups"]}
part_group = {pid: g["id"] for g in P["groups"] for pid in g["parts"]}
EGG = P["meta"]["egg"]["radii_long_axis_y"]           # [a, b, a] แกนยาวขนาน Y
LANES = P["meta"]["lanes"]
CHUTES = {"AB": P["meta"]["chute_surface"], "reject": P["meta"]["chute_surface_reject"]}
def Ztop(y, ch="AB"):
    CH = CHUTES[ch]
    return CH["z0"] + y * math.tan(math.radians(CH["slope_back_deg"] if y >= 0 else CH["slope_front_deg"]))
def on_chute_z(y, la, ch="AB"):
    CH = CHUTES[ch]
    ang = math.radians(CH["slope_back_deg"] if y >= 0 else CH["slope_front_deg"])
    ry = EGG[1] if la == "y" else EGG[0]
    return Ztop(y, ch) + math.hypot(ry * math.sin(ang), EGG[0] * math.cos(ang)) / math.cos(ang)

AX = {"x": 0, "y": 1, "z": 2}
PLANE = {"xz": (0, 2, 1), "yz": (1, 2, 0), "xy": (0, 1, 2)}

def rotm(axis, deg):
    a = np.array(axis, float); a /= np.linalg.norm(a)
    th = math.radians(deg); K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(th) * K + (1 - math.cos(th)) * K @ K

def part_rot(p):
    tr = p.get("transform", {}).get("rotate")
    if not tr: return None
    return rotm(tr["axis"], tr["deg"]), np.array(tr["pivot"], float)

def pip(u, v, poly):
    inside = False
    n = len(poly)
    for i in range(n):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
        if (y1 > v) != (y2 > v):
            xi = x1 + (v - y1) * (x2 - x1) / (y2 - y1)
            if u < xi: inside = not inside
    return inside

def edge_dist(u, v, poly):
    d = 1e9
    n = len(poly)
    for i in range(n):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
        dx, dy = x2 - x1, y2 - y1
        L2 = dx * dx + dy * dy
        tt = 0 if L2 == 0 else max(0, min(1, ((u - x1) * dx + (v - y1) * dy) / L2))
        d = min(d, math.hypot(u - (x1 + tt * dx), v - (y1 + tt * dy)))
    return d

def inside(p, pt, tol):
    pt = np.array(pt, float)
    rr = part_rot(p)
    if rr is not None:
        Rm, pv = rr
        pt = Rm.T @ (pt - pv) + pv
    sh = p["shape"]
    if sh == "box":
        mn, mx = np.array(p["min"]), np.array(p["max"])
        return bool(np.all(pt > mn + tol) and np.all(pt < mx - tol))
    if sh == "cylinder":
        a = AX[p["axis"]]; cc = np.array(p["center"])
        if abs(pt[a] - cc[a]) > p["length"] / 2 - tol: return False
        rad = np.delete(pt - cc, a)
        return np.linalg.norm(rad) < p["radius"] - tol
    if sh == "prism":
        iu, iv, iw = PLANE[p["plane"]]
        e0, e1 = p["extrude"]
        if not (e0 + tol < pt[iw] < e1 - tol): return False
        poly = p["points"]
        return pip(pt[iu], pt[iv], poly) and edge_dist(pt[iu], pt[iv], poly) > tol
    if sh == "ellipsoid":
        return False
    raise ValueError(sh)

def samples(p, n=5):
    sh = p["shape"]; pts = []
    if sh == "box":
        mn, mx = np.array(p["min"]), np.array(p["max"])
        for f in itertools.product(np.linspace(0, 1, n), repeat=3):
            pts.append(mn + (mx - mn) * np.array(f))
    elif sh == "cylinder":
        a = AX[p["axis"]]; cc = np.array(p["center"]); o = [i for i in range(3) if i != a]
        for w in np.linspace(-p["length"] / 2, p["length"] / 2, n):
            for rf in (0, 0.5, 1.0):
                for k in range(8):
                    q = cc.copy(); q[a] += w
                    q[o[0]] += rf * p["radius"] * math.cos(k * math.pi / 4)
                    q[o[1]] += rf * p["radius"] * math.sin(k * math.pi / 4)
                    pts.append(q)
    elif sh == "prism":
        iu, iv, iw = PLANE[p["plane"]]; poly = p["points"]; e0, e1 = p["extrude"]
        uv = []
        for i in range(len(poly)):
            (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % len(poly)]
            for f in np.linspace(0, 1, 6)[:-1]:
                uv.append((x1 + f * (x2 - x1), y1 + f * (y2 - y1)))
        cu = sum(a for a, _ in poly) / len(poly); cv = sum(b for _, b in poly) / len(poly)
        uv += [(cu, cv)] + [((a + cu) / 2, (b + cv) / 2) for a, b in uv]
        for w in np.linspace(e0, e1, n):
            for a, b in uv:
                q = np.zeros(3); q[iu], q[iv], q[iw] = a, b, w; pts.append(q)
    rr = part_rot(p)
    if rr is not None:
        Rm, pv = rr
        pts = [Rm @ (q - pv) + pv for q in pts]
    return np.array(pts)

def aabb(pts):
    return pts.min(0), pts.max(0)

SAMP = {pid: samples(p) for pid, p in parts.items()}
BB = {pid: aabb(SAMP[pid]) for pid in parts}

def overlap_bb(a, b, tol=0.5):
    return np.all(a[0] < b[1] - tol) and np.all(b[0] < a[1] - tol)

WHITE = [("esc.*.pin*", "tray.floor"), ("ai.*.shaft*", "ai.*.roller*"), ("ai.F.shaft1", "ai.wall.front.a"),
         ("ai.B.shaft1", "ai.wall.back"), ("ai.*.shaft*", "ai.divider"), ("disp.*", "disp.*"),
         ("ai.camera.lens", "ai.camera"), ("btn.*", "btn.*"), ("bay.psu", "bay.psu.case"),
         ("ai.F.n20", "ai.wall.front.a"), ("ai.B.n20", "ai.wall.back"), ("ai.*.led.candle", "ai.*.led.post"),
         ("esc.*.pin*", "esc.*.rocker*"),
         # แผ่นรับ/ทางลาด/เนิน/กันชนโฟม ฝังฐานลงในโฟมราง (พื้นเอียงตาม Y) ; ชิ้นที่ต่อชนกันในรางเดียวกัน
         ("out.*.runout.*", "out.*.chute.surface*"), ("out.*.stop.foam", "out.*.chute.surface*"), ("out.reject.bump.*", "out.reject.chute.surface"),
         ("out.reject.bump.*", "out.reject.bump.*"), ("out.reject.bump.*", "out.reject.stop.foam"), ("out.reject.runout.*", "out.reject.bump.*"),
         ("out.reject.runout.*", "out.reject.runout.*"), ("out.A.runout.*", "out.A.runout.*"),
         ("out.B.ramp.*", "out.B.chute.surface*"), ("out.B.post.*", "out.B.ramp.*"), ("out.B.ramp.*", "out.B.ramp.*"),
         # แอ่งโค้ง (ลานโค้ง + โค้งผนังหลัง + มุมมน): ชิ้นจริงเป็นชิ้นเดียว ในโมเดลแบ่งเป็นรูปนูนที่ซ้อนกัน
         # ฐานฝังในโฟมราง แนบผิวกันชน/ผนังหลัง และต่อจากปลายแผ่นรับ/ทางลาดที่ร่อง G
         ("out.*.pocket.*", "out.*.pocket.*"), ("out.*.pocket.*", "out.*.chute.*"), ("out.*.pocket.*", "out.*.stop.foam"),
         ("out.*.pocket.*", "out.*.back"), ("out.*.pocket.*", "out.*.runout.*"), ("out.B.pocket.*", "out.B.ramp.*"),
         ("out.*.pocket.*", "out.*.tray.*"), ("out.*.pocket.*", "out.*.bumper")]

def white(a, b):
    for x, y in WHITE:
        if (fnmatch.fnmatch(a, x) and fnmatch.fnmatch(b, y)) or (fnmatch.fnmatch(b, x) and fnmatch.fnmatch(a, y)):
            return True
    return False

def collide(ptsA, idsB, tol, skip=lambda b: False):
    hits = {}
    for b in idsB:
        if skip(b): continue
        pb = parts[b]
        lo, hi = BB[b]
        m = np.all((ptsA > lo - 1) & (ptsA < hi + 1), axis=1)
        if not m.any(): continue
        cnt = sum(1 for q in ptsA[m] if inside(pb, q, tol))
        if cnt: hits[b] = cnt
    return hits

# ---------------- 1. static overlaps (default states, groups at modeled pose are checked in step 2)
static_ids = [pid for pid in parts if pid not in part_group or part_group[pid].startswith("insert.")]
print("== 1. static overlaps ==")
bad = 0
for a, b in itertools.combinations(static_ids, 2):
    if white(a, b) or not overlap_bb(BB[a], BB[b]): continue
    n1 = sum(1 for q in SAMP[a] if inside(parts[b], q, 0.5))
    n2 = sum(1 for q in SAMP[b] if inside(parts[a], q, 0.5))
    if n1 + n2:
        bad += 1; print(f"  {a}  x  {b}  ({n1}+{n2})")
print("  total", bad)

# ---------------- 2. moving groups through their states
def transform_pts(pts, motion, state):
    v = motion["states"][state]
    if motion["type"] == "rotate":
        Rm = rotm(motion["axis"], v); pv = np.array(motion["pivot"], float)
        return (Rm @ (pts - pv).T).T + pv
    if motion["type"] == "translate":
        return pts + np.array(motion["axis"], float) * v
    return pts

def group_pts(gid, state):
    g = groups[gid]
    return {pid: transform_pts(SAMP[pid], g["motion"], state) for pid in g["parts"]}

def default_obstacles(exclude_gid):
    ids = list(static_ids)
    extra = {}
    for gid, g in groups.items():
        if gid == exclude_gid or gid.startswith("insert."): continue
        if g["motion"]["type"] == "spin": ids += g["parts"]; continue
        extra.update(group_pts(gid, g["motion"]["default"]))
    return ids, extra

print("== 2. moving groups (all states, swept 10 steps) ==")
for gid, g in groups.items():
    mo = g["motion"]
    if mo["type"] == "spin" or gid.startswith("insert.") or gid == "ai.window": continue
    obst, extra = default_obstacles(gid)
    vals = list(mo["states"].values())
    lo, hi = min(vals + [0]), max(vals + [0])
    issues = {}
    for v in np.linspace(lo, hi, 11):
        mo2 = dict(mo); mo2["states"] = {"_": float(v)}
        for pid in g["parts"]:
            pts = transform_pts(SAMP[pid], mo2, "_")
            h = collide(pts, obst, 0.5, skip=lambda b: white(pid, b))
            for b, n in h.items(): issues.setdefault(b, set()).add(round(float(v), 1))
            for oid, opts in extra.items():
                if white(pid, oid): continue
                # moving point inside other group's (moved) part: approximate using its modeled part + inverse motion
                og = groups[part_group[oid]]
                omo = og["motion"]; ov = omo["states"][omo["default"]]
                if omo["type"] == "rotate":
                    Rm = rotm(omo["axis"], -ov); pv = np.array(omo["pivot"], float)
                    back = (Rm @ (pts - pv).T).T + pv
                else:
                    back = pts - np.array(omo["axis"], float) * ov
                n = sum(1 for q in back if inside(parts[oid], q, 0.5))
                if n: issues.setdefault(oid, set()).add(round(float(v), 1))
    print(f"  {gid:10s} {'OK' if not issues else issues}")

# ---------------- 3. inserts pulled out (F1, K2 at STOP)
print("== 3. insert removal path ==")
for gid in [g for g in groups if g.startswith("insert.")]:
    g = groups[gid]
    obst, extra = default_obstacles(gid)
    obst = [o for o in obst if part_group.get(o) != gid]
    issues = {}
    for d in range(0, 291, 10):
        for pid in g["parts"]:
            pts = SAMP[pid] + np.array([0, -d, 0])
            for b, n in collide(pts, obst, 0.5).items():
                if part_group.get(b, "").startswith("insert."): continue
                issues.setdefault(b, []).append(d)
            for oid, opts in extra.items():
                og = groups[part_group[oid]]; omo = og["motion"]; ov = omo["states"][omo["default"]]
                if omo["type"] == "rotate":
                    Rm = rotm(omo["axis"], -ov); pv = np.array(omo["pivot"], float)
                    back = (Rm @ (pts - pv).T).T + pv
                else:
                    back = pts - np.array(omo["axis"], float) * ov
                if any(inside(parts[oid], q, 0.5) for q in back):
                    issues.setdefault(oid, []).append(d)
    print(f"  {gid:14s} {'OK' if not issues else {k: (min(v), max(v)) for k, v in issues.items()}}")

# ---------------- 4. egg rest poses
print("== 4. egg rest poses ==")
def egg_pts(pos, long_axis):
    rx, ry, rz = (EGG[0], EGG[1], EGG[2]) if long_axis == "y" else (EGG[1], EGG[0], EGG[2])
    pts = []
    for th in np.linspace(0, math.pi, 9):
        for ph in np.linspace(0, 2 * math.pi, 16, endpoint=False):
            pts.append([pos[0] + rx * math.sin(th) * math.cos(ph), pos[1] + ry * math.sin(th) * math.sin(ph), pos[2] + rz * math.cos(th)])
    return np.array(pts)

def egg_hits(pos, la, state, tol=1.0):
    pts = egg_pts(pos, la)
    hits = collide(pts, static_ids, tol)
    for gid, g in groups.items():
        if gid.startswith("insert.") or g["motion"]["type"] == "spin":
            if g["motion"]["type"] == "spin":
                hits.update(collide(pts, g["parts"], tol))
            continue
        mo = g["motion"]; v = mo["states"][state[gid]]
        for pid in g["parts"]:
            if mo["type"] == "rotate":
                Rm = rotm(mo["axis"], -v); pv = np.array(mo["pivot"], float); back = (Rm @ (pts - pv).T).T + pv
            else:
                back = pts - np.array(mo["axis"], float) * v
            n = sum(1 for q in back if inside(parts[pid], q, tol))
            if n: hits[pid] = n
    return hits

def walk(sq):
    """ไล่ keyframe พร้อมสถานะกลุ่ม: ได้ (kf, state ก่อน set ของ kf นี้, state หลัง set, long_axis, pos ก่อนหน้า)"""
    state = {gid: g["motion"].get("default") for gid, g in groups.items()}
    la, prev = "y", None
    for kf in sq["keyframes"]:
        before = dict(state)
        for k, v in kf.get("set", {}).items():
            if k in groups:
                state[k] = v
                for gid2, g2 in groups.items():
                    if g2["motion"].get("follows") == k: state[gid2] = v
        prev_la = la
        if "egg" in kf and "long_axis" in kf["egg"]: la = kf["egg"]["long_axis"]
        yield kf, before, dict(state), prev_la, la, prev
        if "pos" in kf.get("egg", {}): prev = kf["egg"]["pos"]

for sq in A["sequences"]:
    for kf, before, state, prev_la, la, prev in walk(sq):
        if not kf.get("rest") or "pos" not in kf.get("egg", {}): continue
        hits = egg_hits(kf["egg"]["pos"], la, state)
        print(f"  {sq['id']:9s} t={kf['t']:4}: {'OK' if not hits else hits}")

# ---------------- 5. keep-out zone ของเส้นทางไข่เสีย (แอ่งใต้กล่องชั่งฝั่งซ้าย)
Y_END = LANES["B"]["y_range"][1]
rf = parts["out.reject.chute.surface"]; stop = parts["out.reject.stop.foam"]
zone = (np.array([rf["extrude"][0] + 1, 4, 6]), np.array([stop["extrude"][0] - 1, Y_END - 1, 88]))
print(f"== 5. keep-out zone ทางไข่เสีย X{zone[0][0]:g}-{zone[1][0]:g} Y{zone[0][1]:g}-{zone[1][1]:g} Z{zone[0][2]:g}-{zone[1][2]:g} ==")
for pid in static_ids:
    if pid.startswith("out.reject") or pid == "base.plate": continue
    lo, hi = BB[pid]
    if np.all(lo < zone[1]) and np.all(hi > zone[0]):
        print("  intrudes:", pid)

# ---------------- 6. back-lane eggs rolling forward under the front lane, front actuators in every state
print("== 6. back-lane egg sliding forward under the front lane ==")
def at_state(gid, st):
    g = groups[gid]; mo = g["motion"]; v = mo["states"][st]
    return mo, v
for chute, front_g in [("A", "k2.F"), ("B", "k2.F"), ("reject", "f1.F")]:
    x, la = P["meta"]["egg_runouts"][chute]["rest_x"], "y"     # ไข่พักชิดโค้งรับ แกนยาวขนาน Y แล้วไถลไปด้านหน้า
    for st in groups[front_g]["motion"]["states"]:
        mo, v = at_state(front_g, st)
        worst = None
        for yy in np.arange(LANES["B"]["y_center"], -1, -4):
            pos = (x, float(yy), on_chute_z(float(yy), la, "reject" if chute == "reject" else "AB"))
            pts = egg_pts(pos, la)
            for pid in groups[front_g]["parts"]:
                if mo["type"] == "rotate":
                    Rm = rotm(mo["axis"], -v); pv = np.array(mo["pivot"], float); back = (Rm @ (pts - pv).T).T + pv
                else:
                    back = pts - np.array(mo["axis"], float) * v
                n = sum(1 for q in back if inside(parts[pid], q, 0.0))
                if n: worst = (x, la, float(yy))
            hits = collide(pts, [p for p in static_ids if not p.startswith("out.")], 0.0)
            if hits: print("   static hit", chute, pos, la, hits)
        print(f"  chute {chute:6s} front {front_g} = {st:7s}: {'clear' if worst is None else 'COLLIDES e.g. ' + str(worst)}")

# ---------------- 7. ไข่ตลอดเส้นทาง (ช่วงที่ keyframe ปลายมี path: true) สุ่มทุก ~2 มม.
print("== 7. egg along path segments (tol 1.0) ==")
PATH_SAMPLES = {}
for sq in A["sequences"]:
    bad = []; n_pts = 0; samples_sq = []
    for kf, before, state, prev_la, la, prev in walk(sq):
        if not kf.get("path") or prev is None: continue
        p0, p1 = np.array(prev, float), np.array(kf["egg"]["pos"], float)
        steps = max(2, int(np.linalg.norm(p1 - p0) / 2) + 1)
        for f in np.linspace(0, 1, steps)[1:]:
            q = p0 + (p1 - p0) * f
            use_la = prev_la if f < 0.5 else la
            n_pts += 1; samples_sq.append((q, use_la))
            h = egg_hits(q, use_la, before)
            if h: bad.append((kf["t"], [round(float(v), 1) for v in q], h))
    PATH_SAMPLES[sq["id"]] = samples_sq
    print(f"  {sq['id']:9s} {n_pts:4d} pts: {'OK' if not bad else bad[:4]}")

# ---------------- 8. ไข่ในแอ่งรางเสีย: ผิวบนไข่ต่ำกว่าผิวล่างสะพานตายตัว ≥ 3 มม. และไม่เข้าใต้ load cell
print("== 8. pocket clearance: reject ใต้สะพานตายตัว / ราง A ใต้สะพาน K2→B (≥ 3 mm) ==")
def prism_bottom_z(p, x):
    """Z ต่ำสุดของ prism xz ที่ตำแหน่ง x (None ถ้าอยู่นอกช่วง)"""
    poly = p["points"]; zs = []
    for i in range(len(poly)):
        (x1, z1), (x2, z2) = poly[i], poly[(i + 1) % len(poly)]
        if min(x1, x2) <= x <= max(x1, x2) and x1 != x2:
            zs.append(z1 + (x - x1) * (z2 - z1) / (x2 - x1))
    return min(zs) if zs else None
bridges = [parts[f"sc.{L}.fixbridge"] for L in LANES]
lc_x0 = min(parts[f"sc.{L}.lc"]["min"][0] for L in LANES)
lc_z0 = min(parts[f"sc.{L}.lc"]["min"][2] for L in LANES)
reject_x = (rf["extrude"][0], rf["extrude"][1])
def pocket_clearance(sid, chute_part, over_parts, check_lc, x_min=-1e9):
    kfs = next(sq for sq in A["sequences"] if sq["id"] == sid)["keyframes"]
    xr = (parts[chute_part]["extrude"][0], parts[chute_part]["extrude"][1])   # แผ่นพื้นเต็มช่วง X ของราง
    pts = [(np.array(k["egg"]["pos"], float), k["egg"].get("long_axis", "y")) for k in kfs
           if k.get("rest") and "pos" in k.get("egg", {}) and xr[0] < k["egg"]["pos"][0] < xr[1] and k["egg"]["pos"][1] > 0]
    pts += [(q, la) for q, la in PATH_SAMPLES[sid] if xr[0] < q[0] < xr[1] and q[2] < 90]
    pts = [(q, la) for q, la in pts if q[0] >= x_min]
    worst, under_lc = 1e9, False
    for q, la in pts:
        rx, ry = (EGG[0], EGG[1]) if la == "y" else (EGG[1], EGG[0])
        top = q[2] + EGG[2]
        for br in over_parts:
            if not (br["extrude"][0] < q[1] + ry and q[1] - ry < br["extrude"][1]): continue
            for x in np.linspace(q[0] - rx * 0.99, q[0] + rx * 0.99, 21):
                zb = prism_bottom_z(br, float(x))
                if zb is not None: worst = min(worst, zb - (q[2] + EGG[2] * math.sqrt(1 - ((x - q[0]) / rx) ** 2)))
        if check_lc and q[0] + rx > lc_x0 and top > lc_z0: under_lc = True
    msg = f"  {sid:9s} min clearance to bridge above = {worst:.1f} mm {'OK' if worst >= 3 else 'FAIL (< 3)'}"
    if check_lc: msg += f" ; {'FAIL egg reaches under load cell' if under_lc else 'clear of load cell'}"
    print(msg)
for sid in ("F_reject", "B_reject"):
    pocket_clearance(sid, "out.reject.chute.floor", bridges, True)
for sid in ("F_good_A", "B_good_A"):
    pocket_clearance(sid, "out.A.chute.floor", [parts[f"sc.{L}.bridge"] for L in LANES], False, P["meta"]["egg_runouts"]["A"]["G"])

# ---------------- 9. ช่องต่อ: ปลาย F1 (BRIDGE) → สะพานตายตัว ≤ 2 ; สะพาน → แท่นชั่ง ≥ 1.5 ; แท่นชั่ง → แผ่นส่งต่อ ≥ 1.5
print("== 9. joint gaps ==")
def poly_gap(pa, pb):
    return min(min(edge_dist(u, v, pb) for u, v in pa), min(edge_dist(u, v, pa) for u, v in pb))
for L in LANES:
    g = groups[f"f1.{L}"]; mo = g["motion"]; f1 = parts[f"ai.{L}.f1"]
    Rm = rotm(mo["axis"], mo["states"]["BRIDGE"]); pv = np.array(mo["pivot"], float)
    corners = [np.array([f1["max"][0], mo["pivot"][1], z]) for z in (f1["min"][2], f1["max"][2])]
    tipc = [(float(q[0]), float(q[2])) for q in ((Rm @ (cc - pv)) + pv for cc in corners)]
    br = parts[f"sc.{L}.fixbridge"]["points"]
    g1 = min(math.hypot(a[0] - b[0], a[1] - b[1]) for a, b in zip(tipc[::-1], [br[0], br[3]]))
    g2 = poly_gap(parts[f"sc.{L}.fixbridge2"]["points"], parts[f"sc.{L}.platform"]["points"])
    g3 = poly_gap(parts[f"sc.{L}.platform"]["points"], parts[f"sc.{L}.transfer"]["points"])
    step = br[0][1] - tipc[1][1]
    print(f"  lane {L}: F1 tip→bridge {g1:.2f} {'OK' if g1 <= 2 else 'FAIL'} (step {step:+.2f}) ; "
          f"bridge→platform {g2:.2f} {'OK' if g2 >= 1.5 else 'FAIL'} ; platform→transfer {g3:.2f} {'OK' if g3 >= 1.5 else 'FAIL'}")
    for gid, pid, st, fixed in ((f"f1.{L}", f"ai.{L}.f1", "REJECT", f"out.reject.runout.{L}"),
                                (f"k2.{L}", f"sc.{L}.k2", "DROP", f"out.A.runout.{L}"),
                                (f"k2.{L}", f"sc.{L}.k2", "BRIDGE", f"sc.{L}.bridge")):
        mo = groups[gid]["motion"]; pp = parts[pid]
        Rm = rotm(mo["axis"], mo["states"][st]); pv = np.array(mo["pivot"], float)
        tip = (Rm @ (np.array([pp["max"][0], mo["pivot"][1], pp["max"][2]]) - pv)) + pv
        f0 = parts[fixed]["points"][0]
        gap = math.hypot(f0[0] - tip[0], f0[1] - tip[2])
        print(f"          {gid} {st:6s} tip→{fixed}: gap {gap:.2f} {'OK' if gap <= 2 else 'FAIL'} (step {f0[1] - tip[2]:+.2f})")
    bb, rp = parts[f"sc.{L}.bridge"]["points"], parts[f"out.B.ramp.{L}.1"]["points"]
    gap = math.hypot(rp[0][0] - bb[1][0], rp[0][1] - bb[1][1])
    print(f"          bridge→ramp B gap {gap:.2f} {'OK' if gap <= 2 else 'FAIL'}")

# ---------------- 10. ความยาวเครื่อง
bb = P["meta"]["bounding_box"]
length = bb["max"][0] - bb["min"][0]
print(f"== 10. machine length X = {length:g} mm {'OK (≤ 1000)' if length <= 1000 else 'FAIL (> 1000)'} ==")

# ---------------- 11. แรงกระแทกตอนไข่ลงถึงพื้นราง: ความเร็วตั้งฉากผิวที่จุดหักมุมเว้า (กลิ้งไม่ไถล v² = v0² + 10/7·g·Δz)
# นับเฉพาะช่วงลง (ท่อนถัดไปไม่ชันขึ้น) ; ช่วงขึ้นเนิน/ชนกันชนคือการหยุดไข่ ไม่นับ
IMPACT_MAX = 300.0     # มม./s
print(f"== 11. landing impact (normal speed at concave kinks ≤ {IMPACT_MAX / 1000:g} m/s) ==")
for sq in A["sequences"]:
    pts = [k["egg"]["pos"] for k in sq["keyframes"] if k.get("path") and "pos" in k.get("egg", {})]
    worst, where = 0.0, None
    z_top = None
    for p0, p1, p2 in zip(pts, pts[1:], pts[2:]):
        if not (abs(p0[1] - p1[1]) < 0.01 and abs(p1[1] - p2[1]) < 0.01): continue
        if p1[0] - p0[0] < 0.3 or p2[0] - p1[0] < 0.3: continue
        z_top = p0[2] if z_top is None else max(z_top, p0[2])
        a0 = math.degrees(math.atan2(p1[2] - p0[2], p1[0] - p0[0])); a1 = math.degrees(math.atan2(p2[2] - p1[2], p2[0] - p1[0]))
        if a1 <= a0 or a1 > 0.5: continue
        v = math.sqrt(300.0 ** 2 + 10 / 7 * 9810 * max(z_top - p1[2], 0))
        vn = v * math.sin(math.radians(a1 - a0))
        if vn > worst: worst, where = vn, (round(p1[0], 1), round(p1[2], 1), round(a0, 1), round(a1, 1))
    print(f"  {sq['id']:9s} max {worst / 1000:.2f} m/s at {where} {'OK' if worst <= IMPACT_MAX else 'FAIL'}")
# ท่อนโค้งรับต้องยาวพอ (รัศมีโค้งของผิว >> รัศมีไข่) ไม่อย่างนั้นไข่หักเลี้ยวแรงเหมือนกระแทก
RUNOUT_MIN = 8.0       # 2026-11-17: ลดจาก 10 (ผู้ใช้ตกลง) ให้แผ่นรับราง A เป็น 3 ท่อนได้
for key, ro in P["meta"]["egg_runouts"].items():
    if key == "note": continue
    for L, pl in ro["lanes"].items():
        segs = [(p, q) for p, q in zip(pl, pl[1:]) if q[0] <= ro["G"] + 0.01]
        angs = [math.degrees(math.atan2(q[1] - p[1], q[0] - p[0])) for p, q in segs]
        # นับเฉพาะท่อนที่ลาด (พื้นเรียบระหว่างปลายทางลาดกับร่อง G ไม่ใช่ท่อนของทางลง)
        conc = [math.hypot(q[0] - p[0], q[1] - p[1]) for i, (p, q) in enumerate(segs)
                if i > 0 and angs[i] > angs[i - 1] and abs(angs[i]) > 0.5]
        mn = min(conc) if conc else float("nan")
        print(f"  runout {key:6s} {L}: shortest concave facet {mn:.1f} mm {'OK' if mn >= RUNOUT_MIN else 'FAIL'}")

# ---------------- 12. ไข่ชนผนังท้ายแอ่ง (กันชนโฟม): ความเร็วส่วนที่ตั้งฉากผนัง (แนว X) ตอนไข่ถึงผนัง
# ความเร็วจากพลังงาน (กลิ้งไม่ไถล v² = v0² + 10/7·g·Δz) นับจากจุดสูงสุดหลังไข่หยุดนิ่งครั้งสุดท้าย (แท่นชั่ง/ร่องลูกกลิ้ง)
# ยังไม่คิดแรงต้านการกลิ้งและการยุบของโฟม ของจริงจึงน่าจะช้ากว่านี้
# เกณฑ์ชั่วคราว: ไข่นอนตะแคงตกพื้นแข็ง 8 มม. (≈ 0.40 m/s) ร้าวราว 5–10% (MIT, Communications Physics 2025)
# → เปลี่ยนเป็นค่าจากการทดลองไข่จริงกับวัสดุกันชนจริงเมื่อมีผล
WALL_IMPACT_MAX = 400.0     # มม./s
V0, G_MM = 300.0, 9810.0
print(f"== 12. wall impact at pocket end (speed normal to wall ≤ {WALL_IMPACT_MAX / 1000:g} m/s, provisional hard-surface limit) ==")
for sq in A["sequences"]:
    m = P["meta"]["egg_runouts"][sq["outcome"]]
    y = LANES[sq["lane"]]["y_center"]
    on_lane = [k for k in sq["keyframes"] if "pos" in k.get("egg", {}) and abs(k["egg"]["pos"][1] - y) < 0.01]
    i_wall = max(range(len(on_lane)), key=lambda i: on_lane[i]["egg"]["pos"][0])
    i_rest = max(i for i in range(i_wall) if on_lane[i].get("rest"))
    wall, prev = on_lane[i_wall]["egg"]["pos"], on_lane[i_wall - 1]["egg"]["pos"]
    z_top = max(k["egg"]["pos"][2] for k in on_lane[i_rest:i_wall])
    v = math.sqrt(V0 ** 2 + 10 / 7 * G_MM * max(z_top - wall[2], 0))
    vn = v * math.cos(math.atan2(wall[2] - prev[2], wall[0] - prev[0]))
    gap = m["stop_x"] - (wall[0] + EGG[0])
    reach = "" if gap < 2 else f" (ไข่ในแอนิเมชันไม่ถึงผนัง เหลือ {gap:.1f} มม.)"
    print(f"  {sq['id']:9s} X {wall[0]:6.1f}: {vn / 1000:.2f} m/s ≈ ตกจาก {vn ** 2 / (2 * G_MM):4.0f} มม. "
          f"{'OK' if vn <= WALL_IMPACT_MAX else 'FAIL'}{reach}")
print("done")
