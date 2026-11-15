"""Animation for the cast (runs inside Blender): locomotion timed to the ground covered, faces, and Tiny's check.

  import anim
  a = anim.Actor(root)                       # a robot built by robot.build
  f = a.walk([(0, -38), (0, -32.4)], start=1, speed=0.45)        # returns the frame it arrives
  f = a.check(f + 4)                         # Tiny's routine: antenna amber, eyes left, right, antenna green
  a.walk([(0, -32.4), (0.6, -30.6), (0, -28.8)], start=f + 2, speed=0.4)
  a.idle(1, 200)                             # breathing and blinks wherever it is not moving

Rules the cast follows (from the bible and our walk-cycle notes):
- Feet are timed by distance, not frames: one stride per STRIDE x height travelled, so feet never skate.
- Every robot moves the way its spec says: walk (feet), hop (Tiny's little bounce on top of its walk), treads and
  wheels (wheels turn by distance / radius), hover (a slow bob), sweeper (a glide with a brush wiggle).
- Faces read at a distance: eyes look by sliding the eye group across the screen, expressions are the eye shape
  keys (blink, happy, sad, angry, wide, squint), and Tiny's antenna tip carries its state: amber means thinking,
  green means go.
"""
import math

import bpy
from mathutils import Vector

FPS = 24
AMBER = (1.0, 0.55, 0.12, 1.0)
GREEN = (0.35, 1.0, 0.45, 1.0)


def _ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


class Actor:
    def __init__(self, root):
        self.root = root
        self.rid = root.get("robot_id", root.name.split(":")[0])
        self.h = float(root.get("height_m", 1.0))
        self.loco = root.get("locomotion", "walk")
        self.parts = [o for o in root.children_recursive]
        self.base = {o.name: (o.location.copy(), o.rotation_euler.copy()) for o in self.parts if o.type == "EMPTY"}
        self.busy = []                     # (start, end) frame ranges where locomotion drives the body
        self.track = {}                    # frame -> (x, y, yaw) written by walk(), used by idle()
        self.base_z = root.location.z
        self.start = (root.location.x, root.location.y, root.rotation_euler.z)

    # ------------------------------------------------------------------ rig lookup
    def joints(self, role):
        return [o for o in self.parts if o.get("role") == role and o.type == "EMPTY"]

    def eyes(self):
        return [o for o in self.parts if o.get("role") == "eye"]

    def eye_group(self):
        return next((o for o in self.parts if o.get("role") == "eyes"), None)

    # ------------------------------------------------------------------ locomotion
    def walk(self, points, start, speed=0.5, turn=0.35, stride=None, settle=6):
        """Move along a polyline at `speed` m/s from frame `start`; feet, bob and sway are timed by distance.
        Turns are eased (`turn` = seconds to swing round a corner). Returns the frame it arrives."""
        pts = [Vector((p[0], p[1], self.root.location.z)) for p in points]
        segs = [(a, b, (b - a).length) for a, b in zip(pts, pts[1:]) if (b - a).length > 1e-4]
        total = sum(L for _, _, L in segs)
        frames = max(2, int(round(total / speed * FPS)))
        S = stride or self.h * 0.32 if self.loco in ("walk", "hop") else (stride or self.h * 0.5)
        feet = {"foot_l": 0.0, "foot_r": math.pi}
        yaw0 = self.root.rotation_euler.z
        prev_yaw = yaw0
        for k in range(frames + 1):
            f = start + k
            d = total * (k / frames)
            # position along the polyline
            acc = 0.0
            for (a, b, L) in segs:
                if acc + L >= d - 1e-9:
                    t = (d - acc) / L
                    pos = a + (b - a) * t
                    seg_dir = (b - a).normalized()
                    break
                acc += L
            # facing: robots face -Y, so yaw puts (sin, -cos) along the path; eased so corners swing round
            want = math.atan2(seg_dir.x, -seg_dir.y)
            dy = (want - prev_yaw + math.pi) % (2 * math.pi) - math.pi
            step = 1.0 / max(1.0, turn * FPS)
            yaw = prev_yaw + dy * min(1.0, step * 3.0)
            prev_yaw = yaw
            phase = d / (2 * S) * 2 * math.pi
            self._pose_moving(f, pos, yaw, phase, min(1.0, k / 4, (frames - k) / 4))
            self.track[f] = (pos.x, pos.y, yaw)
        # settle: feet back under the body
        end = start + frames
        for k in range(1, settle + 1):
            self._pose_moving(end + k, pos, prev_yaw, 0.0, 0.0)
        self.busy.append((start, end + settle))
        return end + settle

    def _pose_moving(self, f, pos, yaw, phase, amt):
        r = self.root
        h = self.h
        z = pos.z
        if self.loco in ("walk", "hop"):
            z += abs(math.sin(phase)) * h * (0.06 if self.loco == "hop" or self.rid == "tiny" else 0.02) * amt
        elif self.loco == "hover":
            z += math.sin(f * 0.11) * h * 0.02
        r.location = (pos.x, pos.y, z)
        r.rotation_euler.z = yaw
        r.keyframe_insert("location", frame=f)
        r.keyframe_insert("rotation_euler", index=2, frame=f)
        S = h * 0.32
        for role, ph in (("foot_l", 0.0), ("foot_r", math.pi)):
            for ft in self.joints(role):
                p = phase + ph
                fwd = -math.cos(p) * S / 2 * amt
                lift = max(0.0, math.sin(p)) * h * 0.09 * amt
                ft.delta_location = (0.0, -fwd, lift)
                ft.keyframe_insert("delta_location", frame=f)
        for role, ph in (("hand_l", math.pi), ("hand_r", 0.0)):
            for hd in self.joints(role):
                hd.delta_location = (0.0, math.cos(phase + ph) * h * 0.05 * amt, 0.0)
                hd.keyframe_insert("delta_location", frame=f)
        # a little side-to-side roll with each step (head for Tiny, body for the rest)
        for b in (self.joints("body") or self.joints("head"))[:1]:
            b.delta_rotation_euler = (0.0, math.sin(phase) * 0.06 * amt, 0.0)
            b.keyframe_insert("delta_rotation_euler", frame=f)
        for w in self.joints("wheel"):
            w.delta_rotation_euler = (-phase * 0.5, 0.0, 0.0)
            w.keyframe_insert("delta_rotation_euler", frame=f)

    def turn_to(self, f, yaw_deg=None, look_at=None, frames=8):
        """Swing round on the spot to a heading (degrees) or toward a point."""
        r = self.root
        y0 = r.rotation_euler.z
        if look_at is not None:
            d = Vector((look_at[0], look_at[1], 0)) - Vector((r.location.x, r.location.y, 0))
            y1 = math.atan2(d.x, -d.y)
        else:
            y1 = math.radians(yaw_deg)
        y1 = y0 + (y1 - y0 + math.pi) % (2 * math.pi) - math.pi
        for k in range(frames + 1):
            r.rotation_euler.z = y0 + (y1 - y0) * _ease(k / frames)
            r.keyframe_insert("rotation_euler", index=2, frame=f + k)
        return f + frames

    # ------------------------------------------------------------------ face
    def expr(self, f, **vals):
        """Key an expression on the eye shape keys; no values = neutral."""
        for e in self.eyes():
            keys = e.data.shape_keys.key_blocks[1:] if e.data.shape_keys else []
            for kb in keys:
                kb.value = vals.get(kb.name, 0.0)
                kb.keyframe_insert("value", frame=f)

    def blink(self, f):
        self.expr(f - 2)
        self.expr(f, blink=1.0)
        self.expr(f + 3)

    def look(self, f, dx=0.0, dz=0.0, hold=None):
        """Slide the eyes across the face screen: dx/dz in -1..1 of the travel the screen allows."""
        g = self.eye_group()
        if not g:
            return
        base = self.base.get(g.name, (g.location.copy(),))[0]
        travel = 0.022 if self.rid == "tiny" else self.h * 0.03
        g.location = (base.x + dx * travel, base.y, base.z + dz * travel * 0.6)
        g.keyframe_insert("location", frame=f)

    def antenna(self, f, colour, strength=6.0):
        """Tiny's antenna tip: amber (thinking), green (go) or off."""
        mat = bpy.data.materials.get(f"{self.rid}_glow") or bpy.data.materials.get("tiny_glow")
        if not mat:
            return
        bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        col = {"amber": AMBER, "green": GREEN, "off": (0.2, 0.2, 0.2, 1.0)}[colour]
        bsdf.inputs["Emission Color"].default_value = col
        bsdf.inputs["Base Color"].default_value = col
        bsdf.inputs["Emission Strength"].default_value = 0.0 if colour == "off" else strength
        for name in ("Emission Color", "Base Color", "Emission Strength"):
            bsdf.inputs[name].keyframe_insert("default_value", frame=f)

    def check(self, f):
        """Tiny's routine before every action: stop, antenna amber, eyes sweep left, then right, back to centre,
        a beat, antenna green. About two seconds. Returns the frame it is ready to go."""
        self.antenna(f - 1, "green")
        self.antenna(f + 2, "amber")
        self.look(f, 0.0)
        self.look(f + 6, -1.0)
        self.look(f + 16, -1.0)
        self.look(f + 22, 1.0)
        self.look(f + 32, 1.0)
        self.look(f + 38, 0.0)
        self.blink(f + 42)
        self.antenna(f + 47, "amber")
        self.antenna(f + 50, "green")
        self.expr(f + 47)
        self.expr(f + 52, happy=0.35)
        self.expr(f + 64)
        return f + 52

    # ------------------------------------------------------------------ idle
    def idle(self, f0, f1):
        """Breathing bob and occasional blinks in every frame range where nothing else moves the body."""
        h = self.h
        r = self.root
        for f in range(f0, f1 + 1):
            if any(a <= f <= b for (a, b) in self.busy):
                continue
            pos = self.track.get(f)
            if pos is None:
                known = [k for k in self.track if k < f]
                pos = self.track[max(known)] if known else self.start
            base_z = self.base_z
            r.location = (pos[0], pos[1], base_z + (math.sin(f * 0.13) * 0.5 + 0.5) * h * 0.012)
            r.keyframe_insert("location", frame=f)
        for f in range(f0 + 40, f1, 77):
            if not any(a <= f <= b for (a, b) in self.busy):
                self.blink(f)
