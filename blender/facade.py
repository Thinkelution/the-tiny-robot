"""Building facades as real geometry: recessed windows with reveals and sills, storey bands, shopfronts with
awnings, AC units, balconies and a roof parapet. One mesh per tower tier (fast to render, easy on memory).

Material slots on every tier mesh: 0 wall, 1 window glass, 2 shopfront glass, 3 trim (sills, bands, awnings,
AC units, parapet). A face attribute "win" (0..1, random per window) lets the glass shader light windows one by one.
"""
import math

import bmesh
import bpy
from mathutils import Vector

WALL, GLASS, SHOP, TRIM = 0, 1, 2, 3


def _quad(bm, pts, mat, win_layer=None, win=0.0):
    vs = [bm.verts.new(p) for p in pts]
    f = bm.faces.new(vs)
    f.material_index = mat
    if win_layer is not None:
        f[win_layer] = win
    return f


def _cube(bm, centre, size, mat):
    res = bmesh.ops.create_cube(bm, size=1.0)
    vs = res["verts"]
    bmesh.ops.scale(bm, vec=size, verts=vs)
    bmesh.ops.translate(bm, vec=centre, verts=vs)
    for f in {f for v in vs for f in v.link_faces}:
        f.material_index = mat


def _wall_face(bm, wl, rnd, origin, u, n, W, H, bay, storey, shop, balconies, style="grid"):
    """One facade face. origin = bottom-left corner on the face, u = unit width direction, n = outward normal.
    style: grid (windows in bays, some skipped), sparse (few windows, lots of wall), blank (no upper windows)."""
    up = Vector((0, 0, 1))
    depth = 0.28
    cols = max(1, int(W // bay))
    margin = (W - cols * bay) / 2
    gf = storey * 1.25 if shop else storey               # ground floor
    rows = max(1, int((H - gf - 0.6) // storey))

    def P(a, b, d=0.0):
        return origin + u * a + up * b - n * d

    # u breakpoints: wall | window | wall per bay
    us = [0.0]
    win_u = []
    for c in range(cols):
        a = margin + c * bay
        us += [a + bay * 0.2, a + bay * 0.8]
        win_u.append((a + bay * 0.2, a + bay * 0.8))
    us.append(W)
    us = sorted(set(round(x, 5) for x in us))
    # v breakpoints
    vs = [0.0, gf]
    win_v = []
    for r in range(rows):
        b = gf + r * storey
        vs += [b + storey * 0.3, b + storey * 0.82]
        win_v.append((b + storey * 0.3, b + storey * 0.82))
    vs.append(H)
    vs = sorted(set(round(x, 5) for x in vs if x <= H))
    keep = {"grid": 0.78, "sparse": 0.35, "blank": 0.0}[style]
    win_cells = {(round(a0, 5), round(b0, 5)) for a0, a1 in win_u for b0, b1 in win_v if rnd.random() < keep}
    lit_bias = rnd.random()
    for i in range(len(us) - 1):
        for j in range(len(vs) - 1):
            a0, a1, b0, b1 = us[i], us[i + 1], vs[j], vs[j + 1]
            if (a0, b0) in win_cells:
                wv = (rnd.random() * 0.8 + lit_bias * 0.2)
                # reveals (4 sides into the wall) + recessed glass
                _quad(bm, [P(a0, b0), P(a0, b0, depth), P(a0, b1, depth), P(a0, b1)], WALL)
                _quad(bm, [P(a1, b0), P(a1, b1), P(a1, b1, depth), P(a1, b0, depth)], WALL)
                _quad(bm, [P(a0, b0), P(a1, b0), P(a1, b0, depth), P(a0, b0, depth)], WALL)
                _quad(bm, [P(a0, b1), P(a0, b1, depth), P(a1, b1, depth), P(a1, b1)], WALL)
                _quad(bm, [P(a0, b0, depth), P(a1, b0, depth), P(a1, b1, depth), P(a0, b1, depth)], GLASS, wl, wv)
                # sill
                c = (P(a0, b0) + P(a1, b0)) / 2 + n * 0.06 - up * 0.05
                sz = [abs(u.x) * (a1 - a0 + 0.16) + abs(n.x) * 0.16, abs(u.y) * (a1 - a0 + 0.16) + abs(n.y) * 0.16,
                      0.09]
                _cube(bm, c, sz, TRIM)
                if rnd.random() < 0.12:                          # an AC unit under the window
                    ac = (P(a0, b0) + P(a1, b0)) / 2 + n * 0.3 - up * 0.45
                    _cube(bm, ac, [abs(u.x) * 0.75 + abs(n.x) * 0.5, abs(u.y) * 0.75 + abs(n.y) * 0.5, 0.5], TRIM)
            else:
                _quad(bm, [P(a0, b0), P(a1, b0), P(a1, b1), P(a0, b1)], WALL)
    # storey bands
    for r in range(rows + 1):
        b = gf + r * storey
        if b < H - 0.3:
            c = origin + u * (W / 2) + up * b + n * 0.05
            _cube(bm, c, [abs(u.x) * W + abs(n.x) * 0.12, abs(u.y) * W + abs(n.y) * 0.12, 0.16], TRIM)
    # shopfront: a recessed glass band with an awning
    if shop:
        for c in range(cols):
            a = margin + c * bay
            box_c = origin + u * (a + bay / 2) + up * (gf * 0.42) - n * 0.12
            _cube(bm, box_c, [abs(u.x) * bay * 0.86 + abs(n.x) * 0.1, abs(u.y) * bay * 0.86 + abs(n.y) * 0.1,
                              gf * 0.62], SHOP)
            if rnd.random() < 0.6:
                aw = origin + u * (a + bay / 2) + up * (gf * 0.82) + n * 0.55
                _cube(bm, aw, [abs(u.x) * bay * 0.9 + abs(n.x) * 1.1, abs(u.y) * bay * 0.9 + abs(n.y) * 1.1, 0.12],
                      TRIM)
    # balconies on a few floors
    if balconies:
        for r in range(1, rows, 2):
            b = gf + r * storey
            for c in range(cols):
                if rnd.random() < 0.35:
                    a = margin + c * bay
                    bc = origin + u * (a + bay / 2) + up * (b + 0.05) + n * 0.55
                    _cube(bm, bc, [abs(u.x) * bay * 0.85 + abs(n.x) * 1.1, abs(u.y) * bay * 0.85 + abs(n.y) * 1.1,
                                   0.12], TRIM)
                    rail = bc + up * 0.55 + n * 0.5
                    _cube(bm, rail, [abs(u.x) * bay * 0.85 + abs(n.x) * 0.05, abs(u.y) * bay * 0.85 + abs(n.y) * 0.05,
                                     0.9], TRIM)


def tier_mesh(name, w, d, h, rnd, bay=2.6, storey=3.2, shop=False, balconies=False, style="grid"):
    bm = bmesh.new()
    wl = bm.faces.layers.float.new("win")
    hw, hd = w / 2, d / 2
    faces = [  # (origin bottom-left, u, outward n, width)
        (Vector((-hw, -hd, 0)), Vector((1, 0, 0)), Vector((0, -1, 0)), w),
        (Vector((hw, -hd, 0)), Vector((0, 1, 0)), Vector((1, 0, 0)), d),
        (Vector((hw, hd, 0)), Vector((-1, 0, 0)), Vector((0, 1, 0)), w),
        (Vector((-hw, hd, 0)), Vector((0, -1, 0)), Vector((-1, 0, 0)), d),
    ]
    for k, (o, u, n, W) in enumerate(faces):
        # side and back faces are often blank party walls
        st = style if k == 0 else rnd.choice([style, "sparse", "blank"])
        _wall_face(bm, wl, rnd, o, u, n, W, h, bay, storey, shop, balconies, st)
    _quad(bm, [Vector((-hw, -hd, h)), Vector((hw, -hd, h)), Vector((hw, hd, h)), Vector((-hw, hd, h))], WALL)
    # parapet ring
    t = 0.25
    for c, s in (((0, -hd + t / 2, h + 0.45), (w, t, 0.9)), ((0, hd - t / 2, h + 0.45), (w, t, 0.9)),
                 ((-hw + t / 2, 0, h + 0.45), (t, d, 0.9)), ((hw - t / 2, 0, h + 0.45), (t, d, 0.9))):
        _cube(bm, Vector(c), s, TRIM)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0005)
    bm.normal_update()
    uv = bm.loops.layers.uv.new("UVMap")
    for f in bm.faces:
        nrm = f.normal
        ax = max(range(3), key=lambda i: abs(nrm[i]))
        u_i, v_i = [(1, 2), (0, 2), (0, 1)][ax]
        for loop in f.loops:
            loop[uv].uv = (loop.vert.co[u_i], loop.vert.co[v_i])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me
