"""Quick matplotlib preview of parts.json (groups at default state) + a few eggs."""
import os
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

import json, math, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

P = json.load(open(os.path.join(OUT, "parts.json"), encoding="utf-8"))
mats = P["materials"]
groups = {g["id"]: g for g in P["groups"]}
part_group = {pid: g["id"] for g in P["groups"] for pid in g["parts"]}
AX = {"x": 0, "y": 1, "z": 2}
PLANE = {"xz": (0, 2, 1), "yz": (1, 2, 0), "xy": (0, 1, 2)}

def rotm(axis, deg):
    a = np.array(axis, float); a /= np.linalg.norm(a)
    th = math.radians(deg); K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + math.sin(th) * K + (1 - math.cos(th)) * K @ K

def faces(p):
    sh = p["shape"]
    if sh == "box":
        mn, mx = np.array(p["min"]), np.array(p["max"])
        v = np.array([[mn[0] if i & 1 == 0 else mx[0], mn[1] if i & 2 == 0 else mx[1], mn[2] if i & 4 == 0 else mx[2]] for i in range(8)])
        idx = [[0, 1, 3, 2], [4, 5, 7, 6], [0, 1, 5, 4], [2, 3, 7, 6], [0, 2, 6, 4], [1, 3, 7, 5]]
        return [v[i] for i in idx]
    if sh == "cylinder":
        a = AX[p["axis"]]; cc = np.array(p["center"], float); o = [i for i in range(3) if i != a]
        n = 14; ring = []
        for end in (-1, 1):
            r = []
            for k in range(n):
                q = cc.copy(); q[a] += end * p["length"] / 2
                q[o[0]] += p["radius"] * math.cos(2 * math.pi * k / n); q[o[1]] += p["radius"] * math.sin(2 * math.pi * k / n)
                r.append(q)
            ring.append(np.array(r))
        fs = [ring[0], ring[1]] + [np.array([ring[0][k], ring[0][(k + 1) % n], ring[1][(k + 1) % n], ring[1][k]]) for k in range(n)]
        return fs
    if sh == "prism":
        iu, iv, iw = PLANE[p["plane"]]; pts = p["points"]; e0, e1 = p["extrude"]
        def P3(u, v, w):
            q = np.zeros(3); q[iu], q[iv], q[iw] = u, v, w; return q
        top = np.array([P3(u, v, e0) for u, v in pts]); bot = np.array([P3(u, v, e1) for u, v in pts])
        n = len(pts)
        return [top, bot] + [np.array([top[k], top[(k + 1) % n], bot[(k + 1) % n], bot[k]]) for k in range(n)]

def place(p, fs):
    tr = p.get("transform", {}).get("rotate")
    if tr:
        Rm = rotm(tr["axis"], tr["deg"]); pv = np.array(tr["pivot"], float)
        fs = [(Rm @ (f - pv).T).T + pv for f in fs]
    gid = part_group.get(p["id"])
    if gid:
        mo = groups[gid]["motion"]
        st = mo.get("default")
        if mo["type"] == "rotate":
            Rm = rotm(mo["axis"], mo["states"][st]); pv = np.array(mo["pivot"], float)
            fs = [(Rm @ (f - pv).T).T + pv for f in fs]
        elif mo["type"] == "translate":
            fs = [f + np.array(mo["axis"]) * mo["states"][st] for f in fs]
    return fs

def egg(pos, la="y"):
    a, b, _ = P["meta"]["egg"]["radii_long_axis_y"]
    rx, ry, rz = (a, b, a) if la == "y" else (b, a, a)
    u = np.linspace(0, 2 * np.pi, 16); v = np.linspace(0, np.pi, 10)
    return (pos[0] + rx * np.outer(np.cos(u), np.sin(v)), pos[1] + ry * np.outer(np.sin(u), np.sin(v)), pos[2] + rz * np.outer(np.ones_like(u), np.cos(v)))

A = json.load(open(os.path.join(OUT, "animation.json"), encoding="utf-8"))
SEQ = {s["id"]: s["keyframes"] for s in A["sequences"]}
def rest_at(seq_id, t):
    return next(tuple(k["egg"]["pos"]) for k in SEQ[seq_id] if k["t"] == t)
def last_rest(seq_id):
    return tuple([k for k in SEQ[seq_id] if k.get("rest")][-1]["egg"]["pos"])
# ไข่ฟองแรกพิง P1 (เลนหน้า), ไข่ในร่องลูกกลิ้ง (เลนหลัง), บนแท่นชั่ง (เลนหน้า), และในถาดหน้า เสีย / A / B
def rest_note(seq_id, note):
    return next(tuple(k["egg"]["pos"]) for k in SEQ[seq_id] if k.get("note") == note)
eggs = [(rest_at("F_good_A", 0.0), "y"), (rest_at("B_good_A", 0.7), "y"), (rest_note("F_good_A", "ไข่หยุดในแอ่งแท่นชั่ง"), "y"),
        (last_rest("F_good_A"), "x"), (last_rest("F_good_B"), "x"), (last_rest("F_reject"), "x")]

def draw(ax, elev, azim, title, hide=()):
    for p in P["parts"]:
        if any(p["id"].startswith(h) for h in hide): continue
        m = mats[p["material"]]
        alpha = min(1.0, max(0.12, m.get("opacity", 1.0)))
        pc = Poly3DCollection(place(p, faces(p)), facecolor=m["color"], edgecolor=(0, 0, 0, 0.15), linewidths=0.2, alpha=alpha)
        ax.add_collection3d(pc)
    for pos, la in eggs:
        X, Y, Z = egg(pos, la)
        ax.plot_surface(X, Y, Z, color=mats["egg"]["color"], linewidth=0, alpha=1.0)
    lo, hi = P["meta"]["bounding_box"]["min"], P["meta"]["bounding_box"]["max"]
    ax.set_xlim(lo[0], hi[0]); ax.set_ylim(lo[1] - 30, hi[1] + 12); ax.set_zlim(0, hi[2] + 18)
    ax.set_box_aspect((hi[0] - lo[0], hi[1] - lo[1] + 42, hi[2] + 18))
    ax.view_init(elev=elev, azim=azim); ax.set_title(title, fontsize=9)
    ax.set_xlabel("X"); ax.set_ylabel("Y"); ax.set_zlabel("Z")

fig = plt.figure(figsize=(16, 11))
draw(fig.add_subplot(2, 2, 1, projection="3d"), 24, -58, "iso (front-left, base hidden)", hide=("base.",))
draw(fig.add_subplot(2, 2, 2, projection="3d"), 0, -90, "front view (−Y)", hide=("disp",))
draw(fig.add_subplot(2, 2, 3, projection="3d"), 0, 0, "side view from +X", hide=("out.B", "sc.wall.right"))
draw(fig.add_subplot(2, 2, 4, projection="3d"), 88, -90, "top view")
plt.tight_layout()
plt.savefig(os.path.join(OUT, "preview.png"), dpi=110)
print("saved")
