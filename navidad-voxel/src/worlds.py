"""Procedural voxel worlds for each location of the story."""
import math
import numpy as np
from engine import M, save_world

rng = np.random.default_rng(1225)


def value_noise2(w, h, scale, seed):
    r = np.random.default_rng(seed)
    gw, gh = int(w / scale) + 3, int(h / scale) + 3
    g = r.random((gw, gh))
    xs = np.arange(w) / scale
    zs = np.arange(h) / scale
    xi = xs.astype(int)
    zi = zs.astype(int)
    xf = xs - xi
    zf = zs - zi
    xf = xf * xf * (3 - 2 * xf)
    zf = zf * zf * (3 - 2 * zf)
    a = g[xi][:, zi]
    b = g[xi + 1][:, zi]
    c = g[xi][:, zi + 1]
    d = g[xi + 1][:, zi + 1]
    xf = xf[:, None]
    zf = zf[None, :]
    return (a * (1 - xf) + b * xf) * (1 - zf) + (c * (1 - xf) + d * xf) * zf


def fbm2(w, h, scale, seed, octaves=4):
    s = np.zeros((w, h))
    amp = 0.5
    tot = 0
    for o in range(octaves):
        s += amp * value_noise2(w, h, scale / (2 ** o), seed + o * 17)
        tot += amp
        amp *= 0.5
    return s / tot


class World:
    def __init__(self, X, Y, Z):
        self.v = np.zeros((X, Y, Z), np.uint8)
        self.X, self.Y, self.Z = X, Y, Z
        self.height = np.zeros((X, Z), int)
        self.lights = []      # (pos, color, radius, shadow)
        self.markers = {}

    def inb(self, x, y, z):
        return 0 <= x < self.X and 0 <= y < self.Y and 0 <= z < self.Z

    def set(self, x, y, z, m):
        if self.inb(x, y, z):
            self.v[x, y, z] = M[m] if isinstance(m, str) else m

    def get(self, x, y, z):
        if self.inb(x, y, z):
            return self.v[x, y, z]
        return 0

    def box(self, x0, y0, z0, x1, y1, z1, m):
        x0, x1 = max(x0, 0), min(x1, self.X)
        y0, y1 = max(y0, 0), min(y1, self.Y)
        z0, z1 = max(z0, 0), min(z1, self.Z)
        if x0 < x1 and y0 < y1 and z0 < z1:
            self.v[x0:x1, y0:y1, z0:z1] = M[m] if isinstance(m, str) else m

    def ground_y(self, x, z):
        """top solid y + 1 at column"""
        col = self.v[int(x), :, int(z)]
        nz = np.nonzero(col)[0]
        return int(nz[-1]) + 1 if len(nz) else 0

    def spruce(self, x, z, h, base=None, leaves="spruce_leaves", lights=False, r0=None):
        if base is None:
            base = self.ground_y(x, z)
        for y in range(base, base + h):
            self.set(x, y, z, "log")
        top = base + h
        rmax = r0 if r0 else max(2, h // 4)
        layers = h - 2
        for i in range(layers):
            y = top - i
            r = min(rmax, int((i + 1) / layers * rmax + 0.5 + (0.6 if i % 3 == 2 else 0)))
            if i % 3 == 0 and i > 0:
                r = max(r - 1, 0)
            for dx in range(-r, r + 1):
                for dz in range(-r, r + 1):
                    if dx * dx + dz * dz <= r * r + r * 0.6:
                        if self.get(x + dx, y, z + dz) == 0:
                            self.set(x + dx, y, z + dz, leaves)
                            if lights and (dx * dx + dz * dz) >= (r - 1) ** 2 and r >= 2 and rng.random() < 0.10:
                                self.set(x + dx, y, z + dz, rng.choice(["light_red", "light_green", "light_yellow", "light_blue", "light_white"]))
        self.set(x, top + 1, z, leaves)

    def house(self, x0, z0, w, d, h, roof="roof_red", facing="s", wall="planks", lights_eave=True, door_light=True, chimney=True):
        gy = min(self.ground_y(x0 + i, z0 + j) for i in (0, w - 1) for j in (0, d - 1))
        gy = max(gy, 1)
        # foundation
        self.box(x0, gy - 3, z0, x0 + w, gy + 1, z0 + d, "cobble")
        # walls
        self.box(x0, gy + 1, z0, x0 + w, gy + 1 + h, z0 + d, wall)
        self.box(x0 + 1, gy + 1, z0 + 1, x0 + w - 1, gy + 1 + h, z0 + d - 1, 0)
        # floor inside
        self.box(x0 + 1, gy, z0 + 1, x0 + w - 1, gy + 1, z0 + d - 1, "dark_planks")
        # log corners
        for cx in (x0, x0 + w - 1):
            for cz in (z0, z0 + d - 1):
                self.box(cx, gy + 1, cz, cx + 1, gy + 1 + h, cz + 1, "log")
        # windows
        wy = gy + 2
        win_cells = []
        for i in range(2, w - 2, 3):
            for zz, out in ((z0, -1), (z0 + d - 1, 1)):
                self.set(x0 + i, wy, zz, "window")
                win_cells.append((x0 + i + 0.5, wy + 0.5, zz + 0.5 + out * 1.0))
        for j in range(2, d - 2, 3):
            for xx, out in ((x0, -1), (x0 + w - 1, 1)):
                self.set(xx, wy, z0 + j, "window")
                win_cells.append((xx + 0.5 + out * 1.0, wy + 0.5, z0 + j + 0.5))
        # door
        if facing == "s":
            dx, dz, out = x0 + w // 2, z0 + d - 1, (0, 1)
        elif facing == "n":
            dx, dz, out = x0 + w // 2, z0, (0, -1)
        elif facing == "e":
            dx, dz, out = x0 + w - 1, z0 + d // 2, (1, 0)
        else:
            dx, dz, out = x0, z0 + d // 2, (-1, 0)
        self.set(dx, gy + 1, dz, "dark_planks")
        self.set(dx, gy + 2, dz, "dark_planks")
        # remove windows that collide with door column
        if door_light:
            lx, lz = dx + out[0], dz + out[1]
            self.set(lx, gy + 3, lz, "lantern")
            self.lights.append(((lx + 0.5 + out[0] * 0.8, gy + 3.5, lz + 0.5 + out[1] * 0.8), (2.4, 1.5, 0.6), 9.0, 1))
        for p in win_cells:
            self.lights.append((p, (1.6, 1.0, 0.45), 7.0, 1))
        # gable roof along x (ridge along x) if w>=d else along z
        top = gy + 1 + h
        along_x = w >= d
        span = d if along_x else w
        half = (span + 1) // 2 + 1
        for k in range(half):
            y = top + k
            if along_x:
                za, zb = z0 - 1 + k, z0 + d - k
                if za > zb:
                    break
                self.box(x0 - 1, y, za, x0 + w + 1, y + 1, za + 1, roof)
                self.box(x0 - 1, y, zb, x0 + w + 1, y + 1, zb + 1, roof)
                if za + 1 < zb:
                    self.box(x0, y, za + 1, x0 + 1, y + 1, zb, wall)
                    self.box(x0 + w - 1, y, za + 1, x0 + w, y + 1, zb, wall)
                for xx in range(x0 - 1, x0 + w + 1):
                    for zz in (za, zb):
                        pass
            else:
                xa, xb = x0 - 1 + k, x0 + w - k
                if xa > xb:
                    break
                self.box(xa, y, z0 - 1, xa + 1, y + 1, z0 + d + 1, roof)
                self.box(xb, y, z0 - 1, xb + 1, y + 1, z0 + d + 1, roof)
                if xa + 1 < xb:
                    self.box(xa + 1, y, z0, xb, y + 1, z0 + 1, wall)
                    self.box(xa + 1, y, z0 + d - 1, xb, y + 1, z0 + d, wall)
                for zz in range(z0 - 1, z0 + d + 1):
                    for xx in (xa, xb):
                        pass
        # christmas lights along the eaves
        if lights_eave:
            cols = ["light_red", "light_green", "light_yellow", "light_blue"]
            k = 0
            if along_x:
                for xx in range(x0 - 1, x0 + w + 1, 2):
                    for zz in (z0 - 1, z0 + d):
                        if self.get(xx, top - 1, zz) == 0:
                            self.set(xx, top - 1, zz, cols[k % 4]); k += 1
            else:
                for zz in range(z0 - 1, z0 + d + 1, 2):
                    for xx in (x0 - 1, x0 + w):
                        if self.get(xx, top - 1, zz) == 0:
                            self.set(xx, top - 1, zz, cols[k % 4]); k += 1
        if chimney:
            cx = x0 + w - 3 if along_x else x0 + 2
            cz = z0 + 2 if along_x else z0 + d - 3
            for y in range(top, top + half + 2):
                self.set(cx, y, cz, "brick")
        return gy, (dx + out[0], gy + 1, dz + out[1])

    def lamp_post(self, x, z, h=3):
        gy = self.ground_y(x, z)
        for y in range(gy, gy + h):
            self.set(x, y, z, "dark_planks")
        self.set(x, gy + h, z, "lantern")
        self.lights.append(((x + 0.5, gy + h + 1.3, z + 0.5), (2.6, 1.6, 0.6), 10.0, 1))

    def rock(self, x, z, r, m="stone"):
        gy = self.ground_y(x, z)
        for dx in range(-r, r + 1):
            for dy in range(-1, r + 1):
                for dz in range(-r, r + 1):
                    if dx * dx + dy * dy * 1.5 + dz * dz <= r * r + rng.random() * 1.5:
                        self.set(x + dx, gy + dy, z + dz, m)

    def save(self, path):
        save_world(path, self.v)


def terrain(wd, base, amp, scale, seed, mat_top="grass_snow", mat_fill="dirt", mat_deep="stone"):
    X, Z = wd.X, wd.Z
    hm = base + (fbm2(X, Z, scale, seed) - 0.5) * 2 * amp
    hm = hm.astype(int)
    ys = np.arange(wd.Y)[None, :, None]
    h3 = hm[:, None, :]
    v = wd.v
    v[(ys < h3 - 4)] = M[mat_deep]
    v[(ys >= h3 - 4) & (ys < h3 - 1)] = M[mat_fill]
    v[(ys == h3 - 1)] = M[mat_top]
    wd.height = hm
    return hm


# ======================================================================= VILLAGE
VILLAGE_CENTER = (96, 104)


def build_village():
    wd = World(192, 84, 192)
    X, Z = wd.X, wd.Z
    cx, cz = VILLAGE_CENTER
    hm = 12 + (fbm2(X, Z, 48, 3) - 0.5) * 6
    xx, zz = np.meshgrid(np.arange(X), np.arange(Z), indexing="ij")
    dist = np.sqrt((xx - cx) ** 2 + (zz - cz) ** 2)
    # flatten the village area
    flat = np.clip((dist - 30) / 14, 0, 1)
    hm = 12 * (1 - flat) + hm * flat
    # mountains to the north
    mnt = fbm2(X, Z, 30, 11, 5)
    north = np.clip((46 - zz) / 40, 0, 1) ** 1.3
    hm = hm + north * (25 + mnt * 50)
    # side hills
    side = np.clip((np.abs(xx - cx) - 62) / 30, 0, 1)
    hm = hm + side * (8 + mnt * 14)
    hm = np.clip(hm, 4, 78).astype(int)
    ys = np.arange(wd.Y)[None, :, None]
    h3 = hm[:, None, :]
    v = wd.v
    v[(ys < h3 - 4)] = M["stone"]
    v[(ys >= h3 - 4) & (ys < h3 - 1)] = M["dirt"]
    v[(ys == h3 - 1)] = M["grass_snow"]
    # snowy mountain tops and rock faces
    steep = np.zeros_like(hm, bool)
    steep[1:-1, 1:-1] = (np.abs(hm[2:, 1:-1] - hm[:-2, 1:-1]) + np.abs(hm[1:-1, 2:] - hm[1:-1, :-2])) > 5
    for x in range(X):
        for z in range(Z):
            h = hm[x, z]
            if steep[x, z] and h > 20:
                v[x, h - 3:h, z] = M["stone"]
            if h > 40 and not steep[x, z]:
                v[x, h - 1, z] = M["snow"]
    wd.height = hm
    # plaza
    for x in range(cx - 12, cx + 13):
        for z in range(cz - 12, cz + 13):
            d = math.hypot(x - cx, z - cz)
            if d <= 12.2:
                wd.v[x, 12:, z] = 0
                wd.set(x, 11, z, "stone_brick" if d > 10.5 else "path")
                if d > 10.5 and rng.random() < 0.3:
                    wd.set(x, 11, z, "cobble")
    # path north to gate and beyond
    for z in range(0, cz - 10):
        for x in range(cx - 2, cx + 3):
            gy = wd.ground_y(x, z)
            if gy <= 14:
                wd.set(x, gy - 1, z, "path" if rng.random() < 0.85 else "gravel")
    # paths east/west/south (short)
    for d in range(12, 34):
        for w in range(-1, 2):
            for (x, z) in ((cx + d, cz + w), (cx - d, cz + w), (cx + w, cz + d)):
                gy = wd.ground_y(x, z)
                if gy <= 14:
                    wd.set(x, gy - 1, z, "path" if rng.random() < 0.8 else "gravel")
    # great fir in the plaza
    tree_base = 12
    th = 40
    for y in range(tree_base, tree_base + th):
        for dx in (0, 1):
            for dz in (0, 1):
                wd.set(cx + dx - 1, y, cz + dz - 1, "log")
    top = tree_base + th
    for i in range(th - 4):
        y = top - i
        f = (i + 1) / (th - 4)
        r = 1.2 + f * 10.5
        if i % 4 == 3:
            r -= 1.6
        r2 = r * r
        R = int(r) + 1
        for dx in range(-R, R + 1):
            for dz in range(-R, R + 1):
                d2 = (dx + 0.5) ** 2 + (dz + 0.5) ** 2
                if d2 <= r2:
                    x, z = cx + dx, cz + dz
                    if wd.get(x, y, z) == 0:
                        edge = d2 >= (r - 1.3) ** 2
                        if edge and rng.random() < 0.14 and r > 2.5:
                            wd.set(x, y, z, ["light_red", "light_green", "light_yellow", "light_blue", "light_white", "light_red"][rng.integers(6)])
                        else:
                            wd.set(x, y, z, "spruce_leaves")
    # big ornaments (gold & red wool balls)
    for k in range(26):
        ang = rng.random() * 2 * math.pi
        hy = rng.integers(4, th - 8)
        f = (top - (tree_base + hy)) / (th - 4)
        r = 1.2 + f * 10.5 - 0.3
        x, z = int(cx - 0.5 + math.cos(ang) * r), int(cz - 0.5 + math.sin(ang) * r)
        y = tree_base + hy
        wd.set(x, y, z, "wool_red" if k % 2 else "glow_amber")
    wd.markers["tree_top"] = (cx, top + 2.0, cz)
    wd.markers["tree_base"] = (cx, tree_base, cz)
    # presents under the tree
    for k in range(14):
        ang = k / 14 * 2 * math.pi + 0.2
        r = 12.6 + (k % 3) * 0.0
        x, z = int(cx + math.cos(ang) * 12.8), int(cz + math.sin(ang) * 12.8)
        wd.set(x, 12, z, "present_red" if k % 2 else "present_green")
        if k % 3 == 0:
            wd.set(x, 13, z, "present_green" if k % 2 else "present_red")
    # campfire (south-east of plaza)
    fx, fz = cx + 8, cz + 17
    for dx in range(-3, 4):
        for dz in range(-3, 4):
            if dx * dx + dz * dz <= 10:
                wd.set(fx + dx, 11, fz + dz, "cobble")
                wd.box(fx + dx, 12, fz + dz, fx + dx + 1, 20, fz + dz + 1, 0)
    wd.set(fx, 12, fz, "campfire")
    for dx, dz in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        wd.set(fx + dx, 12, fz + dz, "log")
    wd.set(fx, 11, fz, "campfire")
    wd.markers["campfire"] = (fx + 0.5, 13.0, fz + 0.5)
    # logs as benches around the fire
    for (bx, bz, along) in ((fx - 3, fz + 4, "x"), (fx + 4, fz - 1, "z"), (fx - 5, fz - 2, "z")):
        for k in range(3):
            if along == "x":
                wd.set(bx + k, 12, bz, "log")
            else:
                wd.set(bx, 12, bz + k, "log")
    # houses around plaza
    house_specs = [
        (cx - 30, cz - 26, 11, 8, 4, "roof_red", "s"),
        (cx + 18, cz - 27, 12, 8, 4, "roof_dark", "s"),
        (cx - 34, cz - 6, 9, 11, 4, "roof_dark", "e"),
        (cx + 24, cz - 6, 9, 11, 4, "roof_red", "w"),
        (cx - 30, cz + 16, 11, 9, 4, "roof_red", "n"),
        (cx + 20, cz + 26, 12, 8, 4, "roof_dark", "n"),
        (cx - 12, cz + 26, 10, 8, 4, "roof_red", "n"),
        (cx - 18, cz - 40, 10, 8, 4, "roof_dark", "s"),
        (cx + 10, cz - 42, 10, 8, 4, "roof_red", "s"),
        (cx + 40, cz + 12, 9, 10, 4, "roof_dark", "w"),
        (cx - 46, cz + 6, 9, 10, 4, "roof_red", "e"),
    ]
    doors = []
    for i, (x0, z0, w, d, h, roof, fac) in enumerate(house_specs):
        wall = "planks" if i % 3 else "stone_brick"
        gy, door = wd.house(x0, z0, w, d, h, roof=roof, facing=fac, wall=wall)
        doors.append(door)
    wd.markers["doors"] = doors
    # toy workshop: the house at index 3 (east), porch with workbench facing west to plaza
    x0, z0, w, d, h, roof, fac = house_specs[3]
    wd.markers["workshop_door"] = doors[3]
    px = x0 - 1
    for z in range(z0 + 1, z0 + d - 1):
        wd.set(px, 11, z, "dark_planks")
        wd.set(px - 1, 11, z, "dark_planks")
        wd.set(px - 2, 11, z, "dark_planks")
    # workbench
    wbz = z0 + 2
    wd.set(px - 1, 12, wbz, "planks")
    wd.set(px - 1, 12, wbz + 1, "planks")
    wd.markers["workbench"] = (px - 0.5, 13.0, wbz + 1.0)
    wd.set(px, 14, wbz + 3, "lantern")
    wd.lights.append(((px - 0.7, 14.5, wbz + 3.5), (2.6, 1.6, 0.7), 10.0, 1))
    # bell tower (north-west of plaza)
    bx, bz = cx - 18, cz - 18
    wd.box(bx, 11, bz, bx + 5, 13, bz + 5, "cobble")
    for (ox, oz) in ((0, 0), (4, 0), (0, 4), (4, 4)):
        wd.box(bx + ox, 13, bz + oz, bx + ox + 1, 26, bz + oz + 1, "stone_brick")
    wd.box(bx, 26, bz, bx + 5, 27, bz + 5, "stone_brick")
    for k in range(4):
        wd.box(bx - 1 + k, 27 + k, bz - 1 + k, bx + 6 - k, 28 + k, bz + 6 - k, "roof_dark")
    wd.box(bx + 1, 13, bz + 1, bx + 4, 18, bz + 4, "stone_brick")
    wd.markers["bell"] = (bx + 2.5, 25.6, bz + 2.5)
    # palisade with north gate
    for a in range(0, 720):
        ang = a / 720 * 2 * math.pi
        x = int(cx + math.cos(ang) * 50)
        z = int(cz + math.sin(ang) * 50)
        if abs(x - cx) <= 3 and z < cz:
            continue
        gy = wd.ground_y(x, z)
        if gy > 18:
            continue
        for y in range(gy, gy + 3):
            wd.set(x, y, z, "log")
        if rng.random() < 0.5:
            wd.set(x, gy + 3, z, "snow")
    gz = cz - 50
    for x in (cx - 4, cx + 4):
        for y in range(12, 19):
            wd.set(x, y, gz, "log")
    for x in range(cx - 4, cx + 5):
        wd.set(x, 19, gz, "dark_planks")
        wd.set(x, 20, gz, "snow")
    wd.set(cx - 4, 18, gz + 1, "lantern")
    wd.set(cx + 4, 18, gz + 1, "lantern")
    wd.lights.append(((cx - 3.5, 18.5, gz + 2.3), (2.6, 1.6, 0.6), 10.0, 1))
    wd.lights.append(((cx + 4.5, 18.5, gz + 2.3), (2.6, 1.6, 0.6), 10.0, 1))
    wd.markers["gate"] = (cx + 0.5, 12.0, gz + 0.5)
    # lamp posts along paths
    for z in range(cz - 44, cz - 12, 8):
        wd.lamp_post(cx - 4, z)
        wd.lamp_post(cx + 4, z + 4)
    for d in (16, 26):
        wd.lamp_post(cx + d, cz + 3)
        wd.lamp_post(cx - d, cz - 3)
        wd.lamp_post(cx + 3, cz + d)
    # plaza lights ring
    for k in range(8):
        ang = k / 8 * 2 * math.pi + 0.39
        wd.lamp_post(int(cx + math.cos(ang) * 13.5), int(cz + math.sin(ang) * 13.5), 3)
    # spruces outside village and some inside
    placed = 0
    tries = 0
    while placed < 170 and tries < 4000:
        tries += 1
        x = int(rng.integers(4, X - 4))
        z = int(rng.integers(4, Z - 4))
        d = math.hypot(x - cx, z - cz)
        if d < 54 and not (d > 34 and rng.random() < 0.15):
            continue
        if abs(x - cx) < 6 and z < cz:
            continue
        gy = wd.ground_y(x, z)
        if gy > 60:
            continue
        if wd.get(x, gy - 1, z) not in (M["grass_snow"], M["snow"], M["stone"], M["dirt"]):
            continue
        h = int(rng.integers(9, 17))
        if gy + h + 2 >= wd.Y:
            continue
        wd.spruce(x, z, h, base=gy)
        placed += 1
    # rocks
    for k in range(25):
        x = int(rng.integers(10, X - 10)); z = int(rng.integers(30, Z - 10))
        if math.hypot(x - cx, z - cz) < 52:
            continue
        wd.rock(x, z, int(rng.integers(1, 3)))
    # tree lights (aggregated point lights around the great fir)
    for k in range(10):
        ang = k / 10 * 2 * math.pi
        y = 16 + (k % 5) * 6
        f = (top - y) / (th - 4)
        r = 1.2 + f * 10.5 + 1.5
        col = [(2.0, 0.4, 0.3), (0.4, 1.8, 0.5), (2.0, 1.5, 0.4), (0.5, 0.8, 2.4)][k % 4]
        wd.lights.append(((cx + math.cos(ang) * r, y, cz + math.sin(ang) * r), col, 9.0, 0))
    wd.markers["center"] = (cx, 12, cz)
    return wd


# ======================================================================= FOREST
def build_forest():
    wd = World(176, 72, 176)
    X, Z = wd.X, wd.Z
    hm = terrain(wd, 10, 4, 40, 21)
    lx, lz = 88, 96
    xx, zz = np.meshgrid(np.arange(X), np.arange(Z), indexing="ij")
    d = np.sqrt((xx - lx) ** 2 + ((zz - lz) * 1.15) ** 2)
    # flatten around the lake and carve the lake
    for x in range(X):
        for z in range(Z):
            dd = d[x, z]
            if dd < 30:
                target = 10
                wd.v[x, target:, z] = 0
                wd.v[x, :target, z] = M["dirt"]
                wd.v[x, target - 1, z] = M["grass_snow"]
                wd.v[x, :target - 4, z] = M["stone"]
                hm[x, z] = target
    for x in range(X):
        for z in range(Z):
            dd = d[x, z] + (math.sin(x * 0.4) + math.cos(z * 0.33)) * 0.8
            if dd < 16:
                wd.v[x, 9, z] = M["ice"] if dd < 14.5 else M["packed_ice"]
                wd.v[x, 8, z] = M["packed_ice"]
            elif dd < 17.5:
                wd.v[x, 9, z] = M["snow"]
                if rng.random() < 0.3:
                    wd.v[x, 10, z] = M["snow"]
    wd.markers["lake"] = (lx + 0.5, 10.0, lz + 0.5)
    # trail path from south (z high) to lake
    trail = []
    for i in range(70):
        t = i / 69
        px = lx + math.sin(t * 5.0) * 8 * (1 - t)
        pz = Z - 6 - t * (Z - 6 - (lz + 17))
        trail.append((px, pz))
    wd.markers["trail"] = trail
    for (px, pz) in trail:
        for ox in range(-1, 2):
            for oz in range(-1, 2):
                x, z = int(px) + ox, int(pz) + oz
                gy = wd.ground_y(x, z)
                if 0 < gy < 20:
                    wd.set(x, gy - 1, z, "snow")
    # tall spruces
    placed = 0
    tries = 0
    while placed < 150 and tries < 6000:
        tries += 1
        x = int(rng.integers(3, X - 3)); z = int(rng.integers(3, Z - 3))
        if d[x, z] < 26:
            continue
        near_trail = min(math.hypot(x - px, z - pz) for (px, pz) in trail[::3])
        if near_trail < 7:
            continue
        gy = wd.ground_y(x, z)
        h = int(rng.integers(14, 24))
        if gy + h + 3 >= wd.Y:
            continue
        if any(wd.get(x + ox, gy + 2, z + oz) for ox in (-2, 0, 2) for oz in (-2, 0, 2)):
            continue
        wd.spruce(x, z, h, base=gy, r0=int(3 + h / 7))
        placed += 1
    # rocks & fallen logs
    for k in range(40):
        x = int(rng.integers(5, X - 5)); z = int(rng.integers(5, Z - 5))
        if d[x, z] < 18:
            continue
        wd.rock(x, z, int(rng.integers(1, 3)), "moss_stone" if k % 3 == 0 else "stone")
    for k in range(10):
        x = int(rng.integers(10, X - 20)); z = int(rng.integers(10, Z - 10))
        if d[x, z] < 20:
            continue
        gy = wd.ground_y(x, z)
        for i in range(int(rng.integers(4, 8))):
            wd.set(x + i, gy, z, "log")
            if rng.random() < 0.6:
                wd.set(x + i, gy + 1, z, "snow")
    # owl perch tree near lake (north side)
    ox, oz = lx + 6, lz - 24
    gy = wd.ground_y(ox, oz)
    wd.spruce(ox, oz, 22, base=gy, r0=5)
    for i in range(1, 6):
        wd.set(ox - i, gy + 12, oz + 1, "log")
    wd.markers["owl"] = (ox - 4.5, gy + 13.0, oz + 1.5)
    return wd


# ======================================================================= CRYSTAL CAVERNS
def crystal(wd, x, y, z, h, m, lean=(0, 0), thick=1):
    for i in range(h):
        px = x + int(round(lean[0] * i))
        pz = z + int(round(lean[1] * i))
        r = thick if i < h - 2 else 0
        for dx in range(-r, r + 1):
            for dz in range(-r, r + 1):
                if abs(dx) + abs(dz) <= r:
                    wd.set(px + dx, y + i, pz + dz, m)


def build_cavern():
    wd = World(144, 60, 144)
    X, Z = wd.X, wd.Z
    cx, cz = 72, 76
    # solid rock with walls
    wd.v[:, :, :] = M["cave_stone"]
    xx, zz = np.meshgrid(np.arange(X), np.arange(Z), indexing="ij")
    n = fbm2(X, Z, 14, 41)
    d = np.sqrt((xx - cx) ** 2 + ((zz - cz) * 1.1) ** 2)
    # main chamber + tunnel from south
    floor = 12 + (n * 4).astype(int)
    open_area = d + n * 10 < 36
    tunnel = (np.abs(xx - cx - np.sin(zz * 0.12) * 5) < 5 + n * 3) & (zz > cz)
    side = (np.sqrt((xx - cx + 26) ** 2 + (zz - cz + 18) ** 2) + n * 8 < 16)
    side2 = (np.sqrt((xx - cx - 28) ** 2 + (zz - cz + 10) ** 2) + n * 8 < 14)
    carve = open_area | tunnel | side | side2
    for x in range(X):
        for z in range(Z):
            if carve[x, z]:
                f = floor[x, z]
                wd.v[x, f:, z] = 0
                wd.v[x, f - 1, z] = M["cave_floor"]
            else:
                # walls: tall with jagged tops; make the top dark
                top = 34 + int(n[x, z] * 12)
                wd.v[x, top:, z] = 0
                if rng.random() < 0.02:
                    wd.v[x, top, z] = M["crystal_blue"]
    # deepslate patches on walls
    mask = (wd.v == M["cave_stone"])
    noise3 = rng.random(wd.v.shape) < 0.25
    wd.v[mask & noise3] = M["deepslate"]
    # crystals clusters
    def floor_y(x, z):
        return wd.ground_y(x, z)
    for k in range(70):
        ang = rng.random() * 2 * math.pi
        r = 12 + rng.random() * 26
        x = int(cx + math.cos(ang) * r); z = int(cz + math.sin(ang) * r / 1.1)
        if not (0 < x < X and 0 < z < Z) or not carve[x, z]:
            continue
        if abs(x - cx) < 6 and z > cz:
            continue
        y = floor_y(x, z)
        if y > 30:
            continue
        m = "crystal_blue" if rng.random() < 0.7 else "crystal_purple"
        h = int(rng.integers(2, 6))
        lean = ((rng.random() - 0.5) * 0.4, (rng.random() - 0.5) * 0.4)
        crystal(wd, x, y, z, h, m, lean, 1 if h > 4 and r > 22 else 0)
        wd.lights.append(((x + 0.5 + math.cos(ang) * -1.5, y + h * 0.6, z + 0.5 + math.sin(ang) * -1.5),
                          (0.25, 0.6, 1.6) if m == "crystal_blue" else (0.8, 0.3, 1.6), 9.0, 0))
    # wall crystals (on wall edges)
    for k in range(110):
        x = int(rng.integers(2, X - 2)); z = int(rng.integers(2, Z - 2))
        if carve[x, z]:
            continue
        nb = carve[max(x - 1, 0):x + 2, max(z - 1, 0):z + 2].any()
        if not nb:
            continue
        y = int(rng.integers(14, 32))
        m = "crystal_blue" if rng.random() < 0.65 else "crystal_purple"
        for dx in range(-1, 2):
            for dz in range(-1, 2):
                if carve[min(max(x + dx, 0), X - 1), min(max(z + dz, 0), Z - 1)]:
                    for i in range(int(rng.integers(1, 4))):
                        wd.set(x + dx * (i + 1), y + i, z + dz * (i + 1), m)
    # central altar where the big crystal stands (the big crystal is an instance)
    ay = floor_y(cx, cz)
    for dx in range(-4, 5):
        for dz in range(-4, 5):
            if dx * dx + dz * dz <= 18:
                wd.box(cx + dx, ay - 1, cz + dz, cx + dx + 1, ay + 1, cz + dz + 1, "stone_brick")
                wd.box(cx + dx, ay + 1, cz + dz, cx + dx + 1, ay + 12, cz + dz + 1, 0)
    wd.markers["altar"] = (cx + 0.5, ay + 1.0, cz + 0.5)
    # mirror crystals (beam bounce points) at fixed spots around the altar
    bounce = []
    for k, (ang, r) in enumerate(((2.4, 16), (0.9, 18), (-0.6, 15), (-2.2, 17))):
        x = int(cx + math.cos(ang) * r); z = int(cz + math.sin(ang) * r)
        y = floor_y(x, z)
        for dx in range(-1, 2):
            for dz in range(-1, 2):
                wd.box(x + dx, y, z + dz, x + dx + 1, y + 10, z + dz + 1, 0)
        crystal(wd, x, y, z, 5, "crystal_gold" if k == 3 else "crystal_blue", (0, 0), 1)
        bounce.append((x + 0.5, y + 3.5, z + 0.5))
    wd.markers["bounce"] = bounce
    wd.markers["entry"] = (cx + 0.5, floor_y(cx, Z - 6), Z - 6.0)
    wd.markers["center"] = (cx, ay, cz)
    # torches (lanterns) at the tunnel
    for z in range(cz + 30, Z, 10):
        x = int(cx + math.sin(z * 0.12) * 5)
        for side_ in (-6, 6):
            xx_ = x + side_
            while 0 < xx_ < X and wd.v[xx_, 20, z] == 0:
                xx_ += 1 if side_ > 0 else -1
            y = 16
            wd.set(xx_ - (1 if side_ > 0 else -1), y, z, "lantern")
            wd.lights.append(((xx_ - (2 if side_ > 0 else -2) + 0.5, y + 0.5, z + 0.5), (2.2, 1.3, 0.5), 9.0, 1))
    return wd


# ======================================================================= FORGE
def build_forge():
    wd = World(144, 64, 144)
    X, Z = wd.X, wd.Z
    cx, cz = 72, 72
    wd.v[:, :, :] = M["basalt"]
    xx, zz = np.meshgrid(np.arange(X), np.arange(Z), indexing="ij")
    n = fbm2(X, Z, 12, 77)
    d = np.sqrt((xx - cx) ** 2 + (zz - cz) ** 2)
    carve = (d + n * 8 < 40) | ((np.abs(xx - cx) < 5) & (zz > cz))
    for x in range(X):
        for z in range(Z):
            if carve[x, z]:
                f = 12
                wd.v[x, f:, z] = 0
                wd.v[x, f - 1, z] = M["stone_brick"] if (x + z) % 7 else M["cobble"]
            else:
                top = 36 + int(n[x, z] * 14)
                wd.v[x, top:, z] = 0
    mask = wd.v == M["basalt"]
    wd.v[mask & (rng.random(wd.v.shape) < 0.3)] = M["magma_rock"]
    wd.v[mask & (rng.random(wd.v.shape) < 0.15)] = M["deepslate"]
    # lava rivers (two channels crossing, with bridges)
    lava_cells = []
    for x in range(X):
        for z in range(Z):
            if not carve[x, z]:
                continue
            r1 = abs((z - cz + 14) - math.sin(x * 0.1) * 4)
            r2 = abs((x - cx - 18) - math.sin(z * 0.13) * 3)
            if r1 < 2.6 or (r2 < 2.2 and z < cz + 30):
                wd.v[x, 9:12, z] = M["lava"]
                wd.v[x, 8, z] = M["magma_rock"]
                lava_cells.append((x, z))
    for (x, z) in lava_cells[::9]:
        wd.lights.append(((x + 0.5, 12.8, z + 0.5), (3.2, 1.1, 0.2), 9.0, 0))
    # lava moat across the entry corridor, with a wooden bridge
    for x in range(X):
        for z in range(cz + 24, cz + 29):
            if carve[x, z]:
                wd.v[x, 9:12, z] = M["lava"]
                wd.v[x, 8, z] = M["magma_rock"]
                lava_cells.append((x, z))
    for z in range(cz + 23, cz + 30):
        for x in range(cx - 2, cx + 3):
            wd.set(x, 11, z, "dark_planks")
        wd.set(cx - 3, 12, z, "log"); wd.set(cx + 3, 12, z, "log")
    for (x, z) in [(cx - 8, cz + 26), (cx + 8, cz + 26), (cx - 20, cz + 26), (cx + 20, cz + 26)]:
        wd.lights.append(((x + 0.5, 12.8, z + 0.5), (3.2, 1.1, 0.2), 9.0, 0))
    wd.markers["bridge"] = (cx + 0.5, 12.0, cz + 26.5)
    # bridges
    for z in range(cz - 20, cz - 8):
        for x in range(cx - 2, cx + 3):
            if wd.v[x, 11, z] == M["lava"]:
                wd.set(x, 11, z, "dark_planks")
    for x in range(cx + 12, cx + 25):
        for z in range(cz - 2, cz + 3):
            if wd.v[x, 11, z] == M["lava"]:
                wd.set(x, 11, z, "dark_planks")
    # pillars with chains
    for k in range(10):
        ang = k / 10 * 2 * math.pi + 0.3
        x = int(cx + math.cos(ang) * 27); z = int(cz + math.sin(ang) * 27)
        if wd.v[x, 11, z] == M["lava"]:
            continue
        wd.box(x - 1, 12, z - 1, x + 2, 34, z + 2, "stone_brick")
        wd.box(x - 2, 12, z - 2, x + 3, 14, z + 3, "stone_brick")
        wd.set(x, 18, z + 2, "lantern")
        wd.lights.append(((x + 0.5, 18.5, z + 3.6), (2.6, 1.4, 0.5), 10.0, 1))
    for k in range(18):
        x = int(cx + rng.integers(-30, 30)); z = int(cz + rng.integers(-30, 30))
        if not carve[x, z]:
            continue
        L = int(rng.integers(6, 16))
        for y in range(44 - L, 44):
            wd.set(x, y, z, "chain")
    # anvil + big furnace near center
    ax, az = cx - 4, cz + 2
    wd.box(ax - 1, 12, az, ax + 2, 13, az + 1, "anvil")
    wd.box(ax - 2, 13, az, ax + 3, 14, az + 1, "anvil")
    wd.markers["anvil"] = (ax + 0.5, 14.0, az + 0.5)
    fx, fz = cx - 2, cz - 30
    wd.box(fx - 6, 12, fz - 3, fx + 7, 24, fz + 4, "stone_brick")
    wd.box(fx - 3, 12, fz + 3, fx + 4, 17, fz + 4, "lava")
    wd.box(fx - 2, 24, fz - 1, fx + 3, 40, fz + 2, "brick")
    wd.lights.append(((fx + 0.5, 15, fz + 6), (5.0, 1.8, 0.4), 16.0, 1))
    # old bells hanging (gold-ish dull)
    for k, (bx, bz) in enumerate(((cx + 14, cz + 14), (cx - 18, cz + 12), (cx + 20, cz - 6))):
        wd.box(bx - 1, 22, bz - 1, bx + 2, 25, bz + 2, "star_dull")
        wd.box(bx - 2, 20, bz - 2, bx + 3, 22, bz + 3, "star_dull")
        for y in range(25, 40):
            wd.set(bx, y, bz, "chain")
    # golem seat (big stone block)
    wd.box(cx + 3, 12, cz + 3, cx + 8, 14, cz + 8, "moss_stone")
    wd.markers["seat"] = (cx + 5.5, 14.0, cz + 5.5)
    # step stone for Tilo
    wd.box(cx + 1, 12, cz + 9, cx + 3, 13, cz + 11, "cobble")
    wd.markers["step"] = (cx + 2.0, 13.0, cz + 10.0)
    wd.markers["entry"] = (cx + 0.5, 12.0, Z - 4.0)
    wd.markers["center"] = (cx, 12, cz)
    # scattered lanterns along entry
    for z in range(cz + 34, Z, 9):
        for sx in (-5, 5):
            wd.set(cx + sx, 14, z, "lantern")
            wd.lights.append(((cx + sx * 0.7 + 0.5, 14.5, z + 0.5), (2.2, 1.3, 0.5), 8.0, 1))
    return wd


# ======================================================================= PEAK
def build_peak():
    wd = World(176, 100, 176)
    X, Z = wd.X, wd.Z
    cx, cz = 88, 88
    xx, zz = np.meshgrid(np.arange(X), np.arange(Z), indexing="ij")
    n = fbm2(X, Z, 16, 91, 5)
    d = np.sqrt((xx - cx) ** 2 + (zz - cz) ** 2)
    hm = 62 - (d * 0.95) ** 1.12 + n * 10
    plateau = d < 13
    hm = np.where(plateau, 62, hm)
    hm = np.clip(hm, 4, 95).astype(int)
    ys = np.arange(wd.Y)[None, :, None]
    h3 = hm[:, None, :]
    v = wd.v
    v[ys < h3] = M["stone"]
    v[(ys == h3 - 1)] = M["snow"]
    steep = np.zeros_like(hm, bool)
    steep[1:-1, 1:-1] = (np.abs(hm[2:, 1:-1] - hm[:-2, 1:-1]) + np.abs(hm[1:-1, 2:] - hm[1:-1, :-2])) > 4
    for x in range(X):
        for z in range(Z):
            if steep[x, z]:
                h = hm[x, z]
                v[x, h - 1, z] = M["frost_stone"] if rng.random() < 0.5 else M["stone"]
    # plateau: packed snow, a ring of old standing stones
    for x in range(cx - 13, cx + 14):
        for z in range(cz - 13, cz + 14):
            if math.hypot(x - cx, z - cz) < 13:
                v[x, 62:, z] = 0
                v[x, 61, z] = M["snow"]
    for k in range(9):
        ang = k / 9 * 2 * math.pi
        x = int(cx + math.cos(ang) * 11); z = int(cz + math.sin(ang) * 11)
        hgt = int(rng.integers(3, 6))
        if math.sin(ang) > -0.2:
            continue
        wd.box(x, 62, z, x + 2, 62 + hgt, z + 1, "frost_stone")
        wd.set(x, 62 + hgt, z, "snow")
    # icicle spikes around
    for k in range(60):
        ang = rng.random() * 2 * math.pi
        r = 15 + rng.random() * 40
        x = int(cx + math.cos(ang) * r); z = int(cz + math.sin(ang) * r)
        if not (0 < x < X and 0 < z < Z):
            continue
        y = wd.ground_y(x, z)
        crystal(wd, x, y, z, int(rng.integers(2, 6)), "packed_ice", (0, 0), 0)
    # a few frozen spruces on the slopes
    for k in range(70):
        ang = rng.random() * 2 * math.pi
        r = 26 + rng.random() * 50
        x = int(cx + math.cos(ang) * r); z = int(cz + math.sin(ang) * r)
        if not (4 < x < X - 4 and 4 < z < Z - 4):
            continue
        y = wd.ground_y(x, z)
        h = int(rng.integers(7, 12))
        if y + h + 2 < wd.Y:
            wd.spruce(x, z, h, base=y)
    wd.markers["summit"] = (cx + 0.5, 62.0, cz + 0.5)
    wd.markers["center"] = (cx, 62, cz)
    return wd


if __name__ == "__main__":
    import time, os, sys
    from engine import BUILD
    for name, fn in (("village", build_village), ("forest", build_forest), ("cavern", build_cavern), ("forge", build_forge), ("peak", build_peak)):
        t = time.time()
        w = fn()
        w.save(os.path.join(BUILD, name + ".vox"))
        print(name, w.v.shape, len(w.lights), "lights", "%.1fs" % (time.time() - t))
