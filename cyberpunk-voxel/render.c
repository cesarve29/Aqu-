// Cyberpunk voxel city - CPU ray tracer (vertical 1080x1920 @ 60 fps)
// Build: gcc -O3 -march=native -ffast-math -fopenmp render.c -o render -lm
// Usage: ./render <firstFrame> <lastFrame> <ss> [W H]   -> raw rgb24 frames on stdout
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <stdint.h>
#include <string.h>
#include <omp.h>

#define NX 64
#define NY 128
#define NZ 128
#define IDX(x, y, z) (((((x) & 63) * NY) + (y)) * NZ + ((z) & 127))
#define FPS 60.0f
#define MAXD 300.0f
#define PXS 0.059375f // character pixel size (32 px = 1.9 blocks)

typedef struct { float x, y, z; } v3;
static inline v3 V(float x, float y, float z) { v3 r = {x, y, z}; return r; }
static inline v3 add(v3 a, v3 b) { return V(a.x + b.x, a.y + b.y, a.z + b.z); }
static inline v3 sub(v3 a, v3 b) { return V(a.x - b.x, a.y - b.y, a.z - b.z); }
static inline v3 mul(v3 a, float s) { return V(a.x * s, a.y * s, a.z * s); }
static inline v3 mulv(v3 a, v3 b) { return V(a.x * b.x, a.y * b.y, a.z * b.z); }
static inline float dot(v3 a, v3 b) { return a.x * b.x + a.y * b.y + a.z * b.z; }
static inline v3 cross(v3 a, v3 b) { return V(a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x); }
static inline v3 norm(v3 a) { return mul(a, 1.0f / sqrtf(dot(a, a))); }
static inline v3 mix3(v3 a, v3 b, float t) { return add(mul(a, 1 - t), mul(b, t)); }
static inline float clampf(float x, float a, float b) { return x < a ? a : (x > b ? b : x); }
static inline float smooth(float t) { t = clampf(t, 0, 1); return t * t * (3 - 2 * t); }

static inline uint32_t hsh(uint32_t a) { a ^= a >> 16; a *= 0x7feb352du; a ^= a >> 15; a *= 0x846ca68bu; a ^= a >> 16; return a; }
static inline uint32_t h3(int x, int y, int z) { return hsh((uint32_t)x * 73856093u ^ (uint32_t)y * 19349663u ^ (uint32_t)z * 83492791u); }
static inline float hf(uint32_t h) { return (h & 0xffffff) / 16777216.0f; }

// ---------------------------------------------------------------- world
enum { AIR = 0, ASPHALT, SIDEWALK, WALL, WIN_DARK, WIN_LIT, NEON, SIGN, METAL, ROADLINE, HOLO, TUNNEL, TNEON };
#define LOOPT 24.0f
#define TWO_PI 6.2831853f
static uint8_t *M, *C, *B;
static float *Lv, *Fv;

static const v3 PAL[9] = {
    {0.08f, 0.85f, 1.0f},  // 0 cyan
    {1.0f, 0.08f, 0.75f},  // 1 magenta
    {0.55f, 0.18f, 1.0f},  // 2 purple
    {1.0f, 0.55f, 0.2f},   // 3 warm
    {1.0f, 0.12f, 0.25f},  // 4 red-pink
    {0.25f, 1.0f, 0.45f},  // 5 acid green
    {1.0f, 0.85f, 0.2f},   // 6 yellow
    {0.12f, 0.3f, 1.0f},   // 7 blue
    {0.8f, 0.9f, 1.0f}};   // 8 cool white
static const v3 TINT[8] = {
    {0.20f, 0.22f, 0.28f}, {0.14f, 0.18f, 0.24f}, {0.24f, 0.20f, 0.28f}, {0.16f, 0.16f, 0.18f},
    {0.12f, 0.20f, 0.22f}, {0.26f, 0.24f, 0.24f}, {0.10f, 0.12f, 0.18f}, {0.20f, 0.16f, 0.14f}};

static uint32_t rs = 20261112u;
static inline uint32_t rnd(void) { rs = rs * 1664525u + 1013904223u; return rs >> 8; }

typedef struct { int wy, wh, wu, ww, style, bp, accent, wc[3], tint; float lit; } Bld;
static Bld bl[256];
static int nb = 1;

static inline void setv(int x, int y, int z, int m, int c) {
    if (y < 0 || y >= NY) return;
    int i = IDX(x, y, z); M[i] = m; C[i] = c;
}
static inline int getm(int x, int y, int z) { if (y < 0) return WALL; if (y >= NY) return AIR; return M[IDX(x, y, z)]; }

#define ROAD0 27
#define ROAD1 38 // road x in [27,38), center 32.5
#define CR0 91
#define CR1 101

static void build_world(void) {
    // ground
    for (int x = 0; x < NX; x++) for (int z = 0; z < NZ; z++) {
        int inMain = x >= ROAD0 && x < ROAD1, inCross = z >= CR0 && z < CR1;
        int m = WALL, c = 3;
        if (inMain || inCross) { m = ASPHALT; c = 0; }
        else if ((x >= 24 && x < 41) || (z >= 88 && z < 104)) { m = SIDEWALK; c = 0; }
        if (inMain && !(z >= 88 && z < 104)) {
            if (x == 32 && (z & 7) < 5) { m = ROADLINE; c = 1; }
            if (x == 28 || x == 36) { m = ROADLINE; c = 0; }
        }
        if (inMain && ((z >= 88 && z < 91) || (z >= 101 && z < 104)) && (x & 1)) { m = ROADLINE; c = 8 | 0x80; }
        if (inCross && !inMain && z == 96 && (x & 7) < 5) { m = ROADLINE; c = 3 | 0x40; }
        setv(x, 0, z, m, c);
    }
    // buildings
    for (int side = 0; side < 2; side++) {
        int z = 104;
        while (z < 216) {
            int w = 12 + rnd() % 11;
            if (216 - (z + w) < 12) w = 216 - z;
            int gap = (rnd() % 3 == 0) ? 2 : 0;
            int zs = z, ze = z + w - gap;
            int r = rnd() % 100, H;
            if (r < 55) H = 28 + rnd() % 32; else if (r < 88) H = 60 + rnd() % 35; else H = 95 + rnd() % 28;
            int sb = rnd() % 2;
            int H1 = (int)(H * (0.55f + (rnd() % 30) * 0.01f)), ti = 2 + rnd() % 3;
            int id = nb++;
            Bld *b = &bl[id];
            b->wy = 3 + rnd() % 3; b->wh = b->wy - 1 - (rnd() % 2); if (b->wh < 1) b->wh = 1;
            b->wu = 2 + rnd() % 3; b->ww = b->wu - 1;
            b->style = rnd() % 4; b->bp = 10 + rnd() % 14; b->accent = rnd() % 8;
            b->wc[0] = rnd() % 9; b->wc[1] = (rnd() % 2) ? 3 : 8; b->wc[2] = rnd() % 9;
            b->tint = rnd() % 8; b->lit = 0.14f + (rnd() % 30) * 0.01f;
            int x0 = side == 0 ? 41 + sb : 0, x1 = side == 0 ? 64 : 24 - sb;
            for (int x = x0; x < x1; x++) for (int zz = zs; zz < ze; zz++) for (int y = 1; y < H; y++) {
                if (y >= H1) {
                    int fx = side == 0 ? x - x0 : x1 - 1 - x;
                    if (fx < ti || zz - zs < ti || ze - 1 - zz < ti) continue;
                }
                int i = IDX(x, y, zz); M[i] = WALL; C[i] = b->tint; B[i] = id;
            }
            // antenna
            if (H > 70) {
                int ax = side == 0 ? x0 + ti + 3 : x1 - ti - 4, az = (zs + ze) / 2, ah = 5 + rnd() % 8;
                for (int y = H; y < H + ah && y < NY - 2; y++) setv(ax, y, az, METAL, 0);
                if (H + ah < NY - 2) setv(ax, H + ah, az, NEON, 4);
            }
            b->bp = b->bp; // keep
            // store lot info in spare fields via statics for props pass
            static int lots[256][8];
            lots[id][0] = side; lots[id][1] = zs; lots[id][2] = ze; lots[id][3] = side == 0 ? x0 : x1 - 1; lots[id][4] = H1; lots[id][5] = H;
            z += w;
            // ---- props are added after the facade pass; remember via second loop below
            if (z >= 216) {
                if (side == 1) {
                    // facade pass
                    for (int x = 0; x < NX; x++) for (int y = 1; y < NY - 1; y++) for (int zz = 0; zz < NZ; zz++) {
                        int i = IDX(x, y, zz);
                        if (!B[i] || M[i] != WALL) continue;
                        Bld *q = &bl[B[i]];
                        int ex = !M[IDX(x + 1, y, zz)] || !M[IDX(x - 1, y, zz)];
                        int ez = !M[IDX(x, y, zz + 1)] || !M[IDX(x, y, zz - 1)];
                        int top = !M[IDX(x, y + 1, zz)];
                        if (!ex && !ez) { if (top && (q->style & 1) && 0) M[i] = NEON; continue; }
                        if (ex && ez) { if (q->style == 2 && y > 4) { M[i] = NEON; C[i] = q->accent; } continue; }
                        if (top) { if (q->style != 0) { M[i] = NEON; C[i] = q->accent; } continue; }
                        int u = ex ? zz : x;
                        if (y < 4) { // shop level
                            if (u % 5 != 0 && y < 3) {
                                uint32_t hh = h3(u / 5, B[i] * 31, ex);
                                if (hf(hh) < 0.8f) { M[i] = WIN_LIT; C[i] = (hh >> 24) % 9; } else M[i] = WIN_DARK;
                            }
                            continue;
                        }
                        if (y == 4) { if (q->style != 3) { M[i] = NEON; C[i] = (q->accent + (u / 9)) % 8; } continue; }
                        if (q->style == 1 && y > 8 && y % q->bp == q->bp - 1) { M[i] = NEON; C[i] = q->accent; continue; }
                        int ym = y % q->wy;
                        if (ym >= 1 && ym <= q->wh && (u % q->wu) < q->ww) {
                            uint32_t hh = h3(u / q->wu, y / q->wy, B[i] * 7 + ex);
                            if (hf(hh) < q->lit) { M[i] = WIN_LIT; C[i] = q->wc[(hh >> 24) % 3]; } else M[i] = WIN_DARK;
                        }
                    }
                    // props
                    for (int k = 1; k < nb; k++) {
                        int sd = lots[k][0], a = lots[k][1], e = lots[k][2], fx = lots[k][3], h1 = lots[k][4];
                        int out = sd == 0 ? -1 : 1, len = e - a;
                        if (len >= 10 && rnd() % 100 < 55) { // hologram billboard
                            int bw = 6 + rnd() % 4; if (bw > len - 3) bw = len - 3;
                            int u0 = a + 1 + rnd() % (len - bw - 1), y0 = 7 + rnd() % 12, bh = 8 + rnd() % 10;
                            if (y0 + bh < h1 - 1)
                                for (int zz = u0; zz < u0 + bw; zz++) for (int y = y0; y < y0 + bh; y++) setv(fx, y, zz, HOLO, bl[k].accent);
                        }
                        int ns = 1 + rnd() % 2;
                        for (int s = 0; s < ns; s++) { // protruding signs
                            int zz = a + 1 + rnd() % (len - 2), y0 = 6 + rnd() % 14, h = 5 + rnd() % 8, p = 2 + rnd() % 2, c = rnd() % 8;
                            if (y0 + h >= h1) continue;
                            for (int y = y0; y < y0 + h; y++) for (int j = 1; j <= p; j++) setv(fx + out * j, y, zz, SIGN, c);
                        }
                    }
                }
            }
        }
    }
    // neon tunnel across the street, z in [0,40)
    for (int z = 0; z < 40; z++) for (int x = 24; x < 41; x++) for (int y = 1; y < 14; y++) {
        int inside = x >= 27 && x <= 37 && y <= 7 && !((y == 7 && (x <= 28 || x >= 36)) || (y == 6 && (x == 27 || x == 37)));
        if (inside) { setv(x, y, z, AIR, 0); continue; }
        int m = TUNNEL, c = 0;
        if (z % 4 == 1) { m = TNEON; c = (z / 4) % 3; }
        if (z == 0 || z == 39) {
            if (x >= 26 && x <= 38 && y <= 8) { m = NEON; c = 1; }
            else if (y >= 10 && y <= 12 && x >= 27 && x <= 37) { m = HOLO; c = 0; }
            else if (y == 13) { m = NEON; c = 0; }
        }
        setv(x, y, z, m, c);
    }
    // street lamps
    for (int z = 4; z < NZ; z += 16) {
        if (z < 46 || (z > 84 && z < 108)) continue;
        for (int s = 0; s < 2; s++) {
            int x = s ? 39 : 25, d = s ? -1 : 1;
            for (int y = 1; y <= 6; y++) setv(x, y, z, METAL, 0);
            setv(x + d, 6, z, METAL, 0);
            setv(x + d, 5, z, NEON, (z / 16) % 3 == 0 ? 0 : 8);
        }
    }
    // sky bridges
    static const int bz[2] = {62, 114};
    for (int k = 0; k < 2; k++) {
        int z0 = bz[k], nc = k & 1;
        for (int x = 20; x < 46; x++) for (int dz = 0; dz < 4; dz++) for (int y = 13; y < 17; y++) {
            if (getm(x, y, z0 + dz)) continue;
            int edge = dz == 0 || dz == 3;
            int m = METAL, c = 0;
            if (y == 13 && edge) { m = NEON; c = nc; }
            else if ((y == 14 || y == 15) && edge) { m = (h3(x, y, z0) & 3) ? WIN_LIT : WIN_DARK; c = nc ? 3 : 8; }
            setv(x, y, z0 + dz, m, c);
        }
    }
}

static inline v3 emisOf(int m, int c, int x, int y, int z) {
    switch (m) {
    case WIN_LIT: return mul(PAL[c], 0.75f * (0.5f + 0.9f * hf(h3(x, y, z))));
    case NEON: return mul(PAL[c], 4.0f);
    case SIGN: return mul(PAL[c], 1.4f);
    case HOLO: return mul(PAL[c], 1.1f);
    case TNEON: return mul(PAL[c], 1.5f);
    case ROADLINE: return mul(PAL[c & 15], (c & 0x80) ? 0.5f : 0.45f);
    }
    return V(0, 0, 0);
}

static void solve_light(void) {
    size_t n = (size_t)NX * NY * NZ;
    float *E = calloc(n * 3, sizeof(float));
    for (int x = 0; x < NX; x++) for (int y = 0; y < NY; y++) for (int z = 0; z < NZ; z++) {
        int i = IDX(x, y, z);
        if (M[i]) { v3 e = emisOf(M[i], C[i], x, y, z); E[i * 3] = e.x; E[i * 3 + 1] = e.y; E[i * 3 + 2] = e.z; }
        else if (y == NY - 1) { E[i * 3] = 0.03f; E[i * 3 + 1] = 0.03f; E[i * 3 + 2] = 0.07f; }
    }
    const float w = 1.6f;
    for (int it = 0; it < 140; it++) for (int col = 0; col < 2; col++) {
#pragma omp parallel for schedule(static)
        for (int x = 0; x < NX; x++) for (int y = 1; y < NY - 1; y++) for (int z = 0; z < NZ; z++) {
            if (((x + y + z) & 1) != col) continue;
            int i = IDX(x, y, z);
            if (M[i]) continue;
            int nbr[6] = {IDX(x + 1, y, z), IDX(x - 1, y, z), i + NZ, i - NZ, IDX(x, y, z + 1), IDX(x, y, z - 1)};
            float s0 = 0, s1 = 0, s2 = 0;
            for (int k = 0; k < 6; k++) { const float *p = E + nbr[k] * 3; s0 += p[0]; s1 += p[1]; s2 += p[2]; }
            float *p = E + i * 3;
            const float a = 0.985f / 6.0f;
            p[0] += w * (s0 * a - p[0]); p[1] += w * (s1 * a - p[1]); p[2] += w * (s2 * a - p[2]);
        }
    }
    // fog volume: blurred copy (emission of solids included -> halos)
    float *T = malloc(n * 3 * sizeof(float));
    memcpy(Fv, E, n * 3 * sizeof(float));
    for (int pass = 0; pass < 2; pass++) for (int ax = 0; ax < 3; ax++) {
#pragma omp parallel for schedule(static)
        for (int x = 0; x < NX; x++) for (int y = 0; y < NY; y++) for (int z = 0; z < NZ; z++) {
            int i = IDX(x, y, z), a, b;
            if (ax == 0) { a = IDX(x - 1, y, z); b = IDX(x + 1, y, z); }
            else if (ax == 1) { a = y > 0 ? i - NZ : i; b = y < NY - 1 ? i + NZ : i; }
            else { a = IDX(x, y, z - 1); b = IDX(x, y, z + 1); }
            for (int k = 0; k < 3; k++) T[i * 3 + k] = 0.25f * Fv[a * 3 + k] + 0.5f * Fv[i * 3 + k] + 0.25f * Fv[b * 3 + k];
        }
        memcpy(Fv, T, n * 3 * sizeof(float));
    }
    free(T);
    for (size_t i = 0; i < n; i++) {
        if (M[i]) { Lv[i * 3] = Lv[i * 3 + 1] = Lv[i * 3 + 2] = 0; }
        else { Lv[i * 3] = E[i * 3]; Lv[i * 3 + 1] = E[i * 3 + 1]; Lv[i * 3 + 2] = E[i * 3 + 2]; }
    }
    free(E);
}

static inline v3 sampleV(const float *Vv, float x, float y, float z) {
    x -= 0.5f; y -= 0.5f; z -= 0.5f;
    float fx0 = floorf(x), fy0 = floorf(y), fz0 = floorf(z);
    int x0 = (int)fx0, y0 = (int)fy0, z0 = (int)fz0;
    float fx = x - fx0, fy = y - fy0, fz = z - fz0;
    int y1 = y0 + 1;
    if (y0 < 0) y0 = 0; if (y0 > NY - 1) y0 = NY - 1;
    if (y1 < 0) y1 = 0; if (y1 > NY - 1) y1 = NY - 1;
    v3 r = {0, 0, 0};
    for (int k = 0; k < 8; k++) {
        int i = IDX(x0 + (k & 1), (k & 2) ? y1 : y0, z0 + ((k >> 2) & 1));
        float w = ((k & 1) ? fx : 1 - fx) * ((k & 2) ? fy : 1 - fy) * ((k & 4) ? fz : 1 - fz);
        r.x += Vv[i * 3] * w; r.y += Vv[i * 3 + 1] * w; r.z += Vv[i * 3 + 2] * w;
    }
    return r;
}

// ---------------------------------------------------------------- dynamic objects
typedef struct { v3 piv; float c, s; v3 bmin, bmax; int part; } Obb;
enum { P_HEAD, P_TORSO, P_PACK, P_ARML, P_ARMR, P_LEGL, P_LEGR, P_ANT };
#define NOBB 8
static Obb obb[NOBB];
typedef struct { v3 p, half; int col; } Car;
#define NCAR 14
static Car cars[NCAR];
static float gTime;
static v3 chPos, camPos, camF, camR, camU;
static float tanHalf;

static void setup_frame(int f) {
    float t = f / FPS; gTime = t;
    float speed = NZ / LOOPT, z = 20.0f + speed * t;
    float ph = TWO_PI * (60.0f / LOOPT) * t;
    float sw = 0.85f * sinf(ph), bob = 0.035f * fabsf(cosf(ph));
    chPos = V(32.5f, 1.0f + bob, z);
    float px = PXS;
    #define SETO(i, P, pvx, pvy, ang, x0, y0, z0, x1, y1, z1) \
        obb[i].part = P; obb[i].piv = add(chPos, V((pvx)*px, (pvy)*px, 0)); obb[i].c = cosf(ang); obb[i].s = sinf(ang); \
        obb[i].bmin = V((x0)*px, (y0)*px, (z0)*px); obb[i].bmax = V((x1)*px, (y1)*px, (z1)*px);
    SETO(0, P_HEAD, 0, 24, 0.04f * sinf(ph * 2), -4, 0, -4, 4, 8, 4)
    SETO(1, P_TORSO, 0, 12, 0, -4, 0, -2, 4, 12, 2)
    SETO(2, P_PACK, 0, 12, 0, -3, 3, -4, 3, 11, -2)
    SETO(3, P_ARML, -6, 22, -sw * 0.85f, -2, -10, -2, 2, 2, 2)
    SETO(4, P_ARMR, 6, 22, sw * 0.85f, -2, -10, -2, 2, 2, 2)
    SETO(5, P_LEGL, -2, 12, sw, -2, -12, -2, 2, 0, 2)
    SETO(6, P_LEGR, 2, 12, -sw, -2, -12, -2, 2, 0, 2)
    SETO(7, P_ANT, 0, 24, 0.04f * sinf(ph * 2), 4, 4, -1, 5, 12, 0)
    // cars
    for (int i = 0; i < NCAR; i++) {
        uint32_t h = hsh(i * 7919 + 13);
        float lane = 29.0f + (h % 4) * 2.3f, y = 19.0f + ((h >> 4) % 9) * 5.5f;
        float sp = (NZ / LOOPT) * (2 + ((h >> 8) % 3)) * (((h >> 12) & 1) ? 1.0f : -1.0f);
        float zz = fmodf(((h >> 13) % NZ) + sp * t, (float)NZ); if (zz < 0) zz += NZ;
        cars[i].p = V(lane, y, zz); cars[i].half = V(0.7f, 0.3f, 1.5f); cars[i].col = (h >> 20) % 8;
        if (i >= NCAR - 3) { // cross street traffic (fly along x)
            sp = (64.0f / LOOPT) * (4 + ((h >> 8) % 4)) * (((h >> 12) & 1) ? 1.0f : -1.0f);
            float xx = fmodf(((h >> 13) % 64) + sp * t, 64.0f); if (xx < 0) xx += 64.0f;
            cars[i].p = V(xx, 16.0f + (i - (NCAR - 3)) * 7.0f, 94.0f + (h % 4)); cars[i].half = V(1.5f, 0.3f, 0.7f);
        }
    }
    // camera: chase view through the tunnel, one full orbit in the open city (periodic over LOOPT)
    float q = clampf((t - 5.0f) / 12.0f, 0, 1); q = q * q * q * (q * (q * 6 - 15) + 10);
    float phi = TWO_PI * q, u = 0.5f + 0.5f * cosf(phi); // u=1 behind, 0 in front
    float R = 4.3f + 0.9f * u;
    float hgt = 0.8f + 1.1f * u;
    v3 base = V(32.5f, 1.0f, z);
    camPos = add(base, V(R * sinf(phi), hgt, -R * cosf(phi)));
    camPos.x += 0.03f * sinf(TWO_PI * t * 8.0f / LOOPT); camPos.y += 0.025f * sinf(TWO_PI * t * 11.0f / LOOPT + 1.0f);
    v3 tgt = add(base, V(0, 2.55f + 0.45f * u, 2.4f * u));
    camF = norm(sub(tgt, camPos));
    camR = norm(cross(V(0, 1, 0), camF));
    camU = cross(camF, camR);
    tanHalf = tanf(0.5f * (78.0f - 6.0f * u) * 3.14159265f / 180.0f);
}

typedef struct { int kind, part, face, sgn, col; int ix, iy, iz; v3 n, lp; } DynHit;

static inline void rotx(float c, float s, v3 p, v3 *o) { o->x = p.x; o->y = p.y * c + p.z * s; o->z = -p.y * s + p.z * c; }

static void hit_dyn(v3 o, v3 d, float *tb, DynHit *dh) {
    // character
    v3 cc = add(chPos, V(0, 0.95f, 0)), oc = sub(o, cc);
    float b = dot(oc, d), c2 = dot(oc, oc) - 1.35f * 1.35f;
    if (b * b - c2 > 0 && (c2 < 0 || b < 0)) {
        for (int i = 0; i < NOBB; i++) {
            Obb *q = &obb[i];
            v3 lo, ld; rotx(q->c, q->s, sub(o, q->piv), &lo); rotx(q->c, q->s, d, &ld);
            float t0 = 0, t1 = *tb; int ax = -1, sg = 0;
            const float *po = &lo.x, *pd = &ld.x, *mn = &q->bmin.x, *mx = &q->bmax.x;
            int ok = 1;
            for (int a = 0; a < 3 && ok; a++) {
                float inv = 1.0f / pd[a], ta = (mn[a] - po[a]) * inv, tb2 = (mx[a] - po[a]) * inv; int s = -1;
                if (ta > tb2) { float tt = ta; ta = tb2; tb2 = tt; s = 1; }
                if (ta > t0) { t0 = ta; ax = a; sg = s; }
                if (tb2 < t1) t1 = tb2;
                if (t0 > t1) ok = 0;
            }
            if (!ok || ax < 0) continue;
            *tb = t0; dh->kind = 1; dh->part = q->part; dh->face = ax; dh->sgn = sg;
            v3 hp = add(lo, mul(ld, t0));
            dh->ix = (int)floorf((hp.x - q->bmin.x) / PXS); dh->iy = (int)floorf((hp.y - q->bmin.y) / PXS); dh->iz = (int)floorf((hp.z - q->bmin.z) / PXS);
            int dx = (int)lroundf((q->bmax.x - q->bmin.x) / PXS), dy = (int)lroundf((q->bmax.y - q->bmin.y) / PXS), dz = (int)lroundf((q->bmax.z - q->bmin.z) / PXS);
            if (dh->ix < 0) dh->ix = 0; if (dh->ix >= dx) dh->ix = dx - 1;
            if (dh->iy < 0) dh->iy = 0; if (dh->iy >= dy) dh->iy = dy - 1;
            if (dh->iz < 0) dh->iz = 0; if (dh->iz >= dz) dh->iz = dz - 1;
            v3 nl = V(0, 0, 0); (&nl.x)[ax] = (float)sg;
            // rotate back (inverse of rotx)
            dh->n = V(nl.x, nl.y * q->c - nl.z * q->s, nl.y * q->s + nl.z * q->c);
        }
    }
    // cars
    for (int i = 0; i < NCAR; i++) for (int im = -1; im <= 1; im++) {
        v3 p = cars[i].p;
        if (i >= NCAR - 3) { p.x += im * 64.0f; p.z += NZ * floorf((o.z - p.z) / NZ + 0.5f); }
        else { p.z += im * (float)NZ; p.x += 64.0f * floorf((o.x - p.x) / 64.0f + 0.5f); }
        v3 lo = sub(o, p);
        float t0 = 0, t1 = *tb; int ax = -1, sg = 0, ok = 1;
        const float *po = &lo.x, *pd = &d.x, *hfz = &cars[i].half.x;
        for (int a = 0; a < 3 && ok; a++) {
            float inv = 1.0f / pd[a], ta = (-hfz[a] - po[a]) * inv, tb2 = (hfz[a] - po[a]) * inv; int s = -1;
            if (ta > tb2) { float tt = ta; ta = tb2; tb2 = tt; s = 1; }
            if (ta > t0) { t0 = ta; ax = a; sg = s; }
            if (tb2 < t1) t1 = tb2;
            if (t0 > t1) ok = 0;
        }
        if (!ok || ax < 0) continue;
        *tb = t0; dh->kind = 2; dh->part = i; dh->face = ax; dh->sgn = sg; dh->col = cars[i].col;
        dh->lp = add(lo, mul(d, t0));
        dh->n = V(0, 0, 0); (&dh->n.x)[ax] = (float)sg;
    }
}

// character skin: original futuristic suit with neon accents
static void char_tex(const DynHit *h, v3 *alb, v3 *emi) {
    const v3 CY = {0.08f, 0.9f, 1.0f}, MG = {1.0f, 0.08f, 0.8f}, WH = {0.9f, 1.0f, 1.0f};
    int ix = h->ix, iy = h->iy, iz = h->iz, f = h->face, s = h->sgn;
    float n = hf(h3(ix + h->part * 17, iy + f * 5, iz + s * 3));
    v3 base = mul(V(0.05f, 0.055f, 0.075f), 0.8f + 0.5f * n);
    v3 plate = mul(V(0.17f, 0.18f, 0.23f), 0.85f + 0.3f * n);
    v3 a = base, e = V(0, 0, 0);
    float pulse = 0.75f + 0.25f * sinf(gTime * TWO_PI * 0.75f);
    switch (h->part) {
    case P_HEAD:
        a = plate;
        if (f == 2 && s > 0) { // face: visor
            if (iy >= 3 && iy <= 5 && ix >= 1 && ix <= 6) { a = V(0.01f, 0.01f, 0.02f); e = mul(CY, (iy == 4) ? 5.0f : 2.4f); if (iy == 4 && (ix == 2 || ix == 5)) e = mul(WH, 7.0f); }
            else if (iy == 1 && ix >= 3 && ix <= 4) e = mul(MG, 2.5f);
            else if (iy <= 1) a = base;
        } else if (f == 0) { // sides
            if (iy == 4 && iz >= 4) e = mul(CY, 3.5f);
            else if (iy >= 3 && iy <= 5 && iz >= 2 && iz <= 3) { e = mul(MG, iy == 4 ? 4.0f : 1.5f); }
            else if (iy <= 1) a = base;
        } else if (f == 1 && s > 0) { // top: crest
            if (ix >= 3 && ix <= 4) e = mul(MG, 3.5f);
        } else if (f == 2 && s < 0) { // back of helmet
            if (iy == 2 && ix >= 2 && ix <= 5) e = mul(MG, 3.0f);
            else if (iy == 5 && (ix == 1 || ix == 3 || ix == 4 || ix == 6)) e = mul(CY, 3.0f);
            else if (iy <= 1) a = base;
        }
        break;
    case P_TORSO:
        if (iy >= 9 || (iy >= 4 && iy <= 6 && (ix == 1 || ix == 2 || ix == 5 || ix == 6))) a = plate;
        if (f == 2 && s > 0) {
            if ((ix == 3 || ix == 4) && (iy == 7 || iy == 8)) e = mul(WH, 6.0f * pulse);
            else if (iy >= 9 && (ix == 3 - (iy - 8) || ix == 4 + (iy - 8))) e = mul(MG, 3.5f);
            else if ((ix == 2 || ix == 5) && iy >= 2 && iy <= 6) e = mul(CY, 1.6f);
        } else if (f == 2 && s < 0) {
            if ((ix == 3 || ix == 4) && (iy & 1) == 0) e = mul(CY, 3.0f);
            if (iy == 11) e = mul(MG, 3.0f);
        } else if (f == 0) { if (iz >= 1 && iz <= 2 && iy >= 2 && iy <= 9 && (iy & 1)) e = mul(CY, 2.0f); }
        if (iy == 0) { a = base; e = mul(CY, 2.2f); }
        break;
    case P_PACK:
        a = plate;
        if (f == 2 && s < 0) {
            if (ix == 0 || ix == 5 || iy == 0 || iy == 7) e = mul(MG, 3.8f);
            else if ((ix == 2 || ix == 3) && (iy == 3 || iy == 4)) e = mul(CY, 6.0f * pulse);
            else a = base;
        } else if (f == 1 && s > 0) e = mul(MG, 2.0f);
        else if (f == 0 && iy >= 2 && iy <= 5) e = mul(CY, 2.0f);
        break;
    case P_ARML: case P_ARMR: {
        int outer = (h->part == P_ARML) ? (f == 0 && s < 0) : (f == 0 && s > 0);
        if (iy >= 9) a = plate;
        if (iy <= 1) a = mul(plate, 1.3f);
        if (iy == 8) e = mul(CY, 3.5f);
        else if (iy == 2) e = mul(MG, 3.0f);
        else if (outer && iy >= 3 && iy <= 7 && (iz == 1 || iz == 2)) e = mul(CY, (iz == 1) ? 2.2f : 0.0f);
        if (f == 1 && s > 0) { a = plate; if (ix >= 1 && ix <= 2 && iz >= 1 && iz <= 2) e = mul(MG, 3.0f); }
        break; }
    case P_LEGL: case P_LEGR: {
        int outer = (h->part == P_LEGL) ? (f == 0 && s < 0) : (f == 0 && s > 0);
        if (iy <= 2) a = plate;
        if (iy == 0) e = mul(CY, 4.5f);
        else if (outer && iz == 2 && iy >= 3) e = mul(MG, 3.5f);
        else if (f == 2 && iy == 6) e = mul(CY, 2.8f);
        else if (f == 2 && s > 0 && (iy == 7 || iy == 5) && (ix == 1 || ix == 2)) a = plate;
        else if (f == 2 && s < 0 && ix >= 1 && ix <= 2 && iy >= 8 && (iy & 1)) e = mul(MG, 2.0f);
        break; }
    case P_ANT:
        a = base; if (iy >= 5) e = mul(MG, 6.0f * pulse); else e = mul(CY, 0.6f);
        break;
    }
    *alb = a; *emi = e;
}

// ---------------------------------------------------------------- shading
static inline float vnoise(float x, float z) { // tiling value noise (lattice 16 x 64)
    float fx = floorf(x), fz = floorf(z); int ix = (int)fx, iz = (int)fz;
    float ux = x - fx, uz = z - fz; ux = ux * ux * (3 - 2 * ux); uz = uz * uz * (3 - 2 * uz);
    float a = hf(h3(ix & 15, 7, iz & 31)), b = hf(h3((ix + 1) & 15, 7, iz & 31));
    float c = hf(h3(ix & 15, 7, (iz + 1) & 31)), d = hf(h3((ix + 1) & 15, 7, (iz + 1) & 31));
    return (a + (b - a) * ux) * (1 - uz) + (c + (d - c) * ux) * uz;
}

static inline v3 sky(v3 d) {
    float t = clampf(d.y, 0, 1); t = sqrtf(t);
    v3 c = mix3(V(0.11f, 0.04f, 0.13f), V(0.006f, 0.008f, 0.028f), t);
    return c;
}

static const v3 HAZE = {0.060f, 0.028f, 0.085f};
static float densY[NY + 1];

static v3 trace(v3 o, v3 d, int depth, float *tOut);

static v3 shade_voxel(int m, int c, int ix, int iy, int iz, int axis, int sgn, v3 pos, v3 d, float t, int depth) {
    v3 n = V(0, 0, 0); (&n.x)[axis] = (float)sgn;
    float fx = clampf(pos.x - ix, 0, 0.9999f), fy = clampf(pos.y - iy, 0, 0.9999f), fz = clampf(pos.z - iz, 0, 0.9999f);
    ix &= 63; iz &= 127; // hash on wrapped cell so every repeat of the world is identical
    int tu, tv;
    if (axis == 0) { tu = (int)(fz * 16); tv = (int)(fy * 16); }
    else if (axis == 1) { tu = (int)(fx * 16); tv = (int)(fz * 16); }
    else { tu = (int)(fx * 16); tv = (int)(fy * 16); }
    uint32_t hb = h3(ix, iy, iz);
    float nz = hf(hsh(hb ^ (uint32_t)(tu * 131 + tv * 7919 + axis * 31337)));
    float far = 1.0f / (1.0f + t * 0.02f); // fade texel noise far away (anti-shimmer)
    nz = 0.5f + (nz - 0.5f) * far;
    v3 light = sampleV(Lv, pos.x + n.x * 0.5f, pos.y + n.y * 0.5f, pos.z + n.z * 0.5f);
    light = add(light, V(0.012f, 0.012f, 0.022f));
    { // character glow + contact shadow
        v3 cp = add(chPos, V(0, 1.0f, 0)), l = sub(cp, pos);
        float d2 = dot(l, l);
        if (d2 < 36.0f) {
            float nl = dot(n, l) / sqrtf(d2 + 1e-4f); if (nl < 0) nl = 0;
            float k = 0.55f * nl / (0.6f + d2) * (1.0f - d2 / 36.0f);
            light = add(light, mul(V(0.25f, 0.75f, 1.0f), k));
            float hx = pos.x - chPos.x, hz = pos.z - chPos.z, hd = hx * hx + hz * hz;
            if (axis == 1 && pos.y < chPos.y + 0.2f) light = mul(light, 1.0f - 0.6f * expf(-hd / 0.22f));
        }
    }
    v3 alb = V(0.1f, 0.1f, 0.1f), emi = V(0, 0, 0);
    float F0 = 0, rough = 0, rw = 0;
    switch (m) {
    case ASPHALT: case ROADLINE: {
        float wx = (floorf(pos.x * 16) + 0.5f) / 16, wz = (floorf(pos.z * 16) + 0.5f) / 16;
        float p = vnoise(wx * 0.25f, wz * 0.25f) * 0.7f + vnoise(wx * 0.25f * 4 + 3, wz * 0.25f * 4) * 0.3f;
        float g = 0.045f + 0.035f * nz;
        alb = V(g, g, g * 1.15f);
        if (p > 0.50f) { alb = mul(alb, 0.6f); F0 = 0.05f; rough = 0.006f; rw = 1.0f; }
        else { F0 = 0.04f; rough = 0.045f; rw = 0.55f + 0.4f * smooth((p - 0.35f) / 0.15f); }
        if (m == ROADLINE && axis == 1) {
            int q = (c & 0x40) ? tv : tu, on = (c & 0x80) ? (q >= 2 && q < 14) : (q >= 6 && q < 10);
            if (on) { emi = mul(PAL[c & 15], (c & 0x80) ? 0.22f : 1.9f * (0.8f + 0.4f * nz)); alb = V(0.2f, 0.2f, 0.2f); rw *= 0.5f; }
        }
        break; }
    case SIDEWALK: {
        float g = 0.16f + 0.05f * nz;
        if (tu == 0 || tv == 0 || tu == 8 || tv == 8) g *= 0.6f;
        alb = V(g, g, g * 1.08f); F0 = 0.04f; rough = 0.04f; rw = 0.45f;
        break; }
    case WALL: {
        alb = mul(TINT[c & 7], 0.8f + 0.4f * nz);
        if (tu == 0 || tv == 0) alb = mul(alb, 0.72f);
        if ((hb & 31) == 3 && tu > 3 && tu < 12 && tv > 3 && tv < 12) alb = mul(alb, 0.6f); // vents
        break; }
    case METAL: {
        float g = 0.10f + 0.05f * nz;
        alb = V(g, g * 1.03f, g * 1.1f);
        if ((tu == 2 || tu == 13) && (tv == 2 || tv == 13)) alb = mul(alb, 2.0f);
        if (tu == 0 || tv == 0) alb = mul(alb, 0.6f);
        break; }
    case WIN_DARK: {
        alb = V(0.015f, 0.02f, 0.03f);
        if (tu == 0 || tv == 0) alb = V(0.05f, 0.05f, 0.06f);
        else { F0 = 0.09f; rough = 0.0f; rw = 1.0f; n.x += (hf(hb) - 0.5f) * 0.03f; n.y += (hf(hb >> 8) - 0.5f) * 0.03f; n.z += (hf(hb >> 4) - 0.5f) * 0.03f; }
        break; }
    case WIN_LIT: {
        float br = 0.5f + 0.9f * hf(hb);
        alb = V(0.03f, 0.03f, 0.03f);
        if (tu == 0 || tv == 0) alb = V(0.05f, 0.05f, 0.06f);
        else {
            float k = ((tv & 3) == 0) ? 0.55f : 1.0f; // blinds
            if ((hb >> 9 & 7) == 0 && tv < 9 && tu > 4 && tu < 11) k *= 0.25f; // silhouette / furniture
            emi = mul(PAL[c], 1.15f * br * k * (0.85f + 0.3f * nz));
        }
        break; }
    case NEON: {
        float core = (tu >= 5 && tu <= 10) || (tv >= 5 && tv <= 10) ? 1.0f : 0.0f;
        if (axis != 1 && !(tv >= 4 && tv <= 11)) core = 0;
        emi = add(mul(PAL[c], 3.2f + 2.2f * core), mul(V(1, 1, 1), 1.6f * core));
        alb = V(0.05f, 0.05f, 0.05f);
        break; }
    case SIGN: {
        int gx = tu >> 1, gy = tv >> 1;
        float fl = 1.0f;
        if ((hb & 15) == 1) fl = (hf(h3((int)(gTime * 14), ix + iy, iz)) > 0.35f) ? 1.0f : 0.2f;
        alb = V(0.02f, 0.02f, 0.025f);
        emi = mul(PAL[c], 0.10f);
        if (gx >= 1 && gx <= 6 && gy >= 1 && gy <= 6 && hf(h3(gx + ix * 9, gy + iy * 9, iz + 77)) < 0.5f) emi = mul(PAL[c], 4.2f * fl);
        if (tu == 0 || tu == 15) emi = mul(PAL[(c + 1) & 7], 1.8f * fl);
        break; }
    case TUNNEL: {
        alb = V(0.03f, 0.035f, 0.05f);
        if (tu == 0 || tv == 0) alb = V(0.07f, 0.07f, 0.09f);
        else { F0 = 0.10f; rough = 0.0f; rw = 1.0f; n.x += (hf(hb) - 0.5f) * 0.04f; n.y += (hf(hb >> 8) - 0.5f) * 0.04f; n.z += (hf(hb >> 4) - 0.5f) * 0.04f; }
        break; }
    case TNEON: {
        float wv = 0.5f + 0.5f * sinf(TWO_PI * (iz / 16.0f - gTime * 1.5f)); wv *= wv;
        float core = (axis == 2) ? 1.0f : ((axis == 0 ? tu : tv) >= 5 && (axis == 0 ? tu : tv) <= 10 ? 1.0f : 0.0f);
        float k = (axis == 2) ? 1.0f : ((axis == 0 ? tu : tv) >= 3 && (axis == 0 ? tu : tv) <= 12 ? 1.0f : 0.05f);
        emi = mul(add(mul(PAL[c], 1.6f + 3.4f * wv), mul(V(1, 1, 1), (0.3f + 1.6f * wv) * core)), k);
        alb = V(0.04f, 0.04f, 0.05f);
        break; }
    case HOLO: {
        float wu = (axis == 0) ? pos.z : pos.x;
        int gx = (((int)floorf(wu * 4)) % 512 + 512) % 512, gy = (int)floorf(pos.y * 4);
        int band = gy / 6;
        uint32_t bh = hsh(band * 911 + c * 3);
        int off = (int)floorf(gTime * 2.0f * (1 + (bh & 3))) * ((bh & 8) ? 1 : -1);
        int gxs = gx + off;
        int on = (gy % 6) != 5 && ((gxs % 6 + 6) % 6) != 5 && hf(h3(((gxs % 48) + 48) % 48, gy, band)) < 0.5f;
        int pc = ((bh >> 5) & 3) == 0 ? (c + 1) & 7 : c;
        float scan = 0.75f + 0.25f * (((int)floorf(pos.y * 16)) & 1);
        float sweep = 0.8f + 0.4f * smooth(1.0f - fabsf(fmodf(pos.y * 0.15f - gTime * 0.5f, 1.0f) - 0.5f) * 6.0f);
        emi = mul(PAL[pc], (on ? 2.6f : 0.16f) * scan * sweep);
        alb = V(0.01f, 0.01f, 0.015f);
        break; }
    }
    v3 col = add(mulv(alb, light), emi);
    if (depth == 0 && rw > 0) {
        if (rough > 0) {
            float rr = rough * far;
            uint32_t hq = hsh(hb ^ (uint32_t)(tu * 977 + tv * 6151));
            n.x += (hf(hq) - 0.5f) * 2 * rr; n.z += (hf(hq >> 7) - 0.5f) * 2 * rr;
        }
        n = norm(n);
        float cs = -dot(d, n); if (cs < 0.02f) cs = 0.02f;
        v3 r = add(d, mul(n, 2 * cs));
        v3 gn = V(0, 0, 0); (&gn.x)[axis] = (float)sgn;
        float rg = dot(r, gn); if (rg < 0.03f) { r = add(r, mul(gn, 0.03f - rg)); r = norm(r); }
        float q = 1 - cs, q2 = q * q, fres = F0 + (1 - F0) * q2 * q2 * q;
        fres *= rw;
        float tt;
        v3 rc = trace(add(pos, mul(gn, 0.002f)), r, 1, &tt);
        col = add(mul(col, 1 - fres), mul(rc, fres));
    }
    return col;
}

static v3 trace(v3 o, v3 d, int depth, float *tOut) {
    float tdyn = MAXD; DynHit dh; dh.kind = 0;
    hit_dyn(o, d, &tdyn, &dh);
    float tmax = tdyn;
    int ix = (int)floorf(o.x), iy = (int)floorf(o.y), iz = (int)floorf(o.z);
    int sx = d.x > 0 ? 1 : -1, sy = d.y > 0 ? 1 : -1, sz = d.z > 0 ? 1 : -1;
    float ax = fabsf(d.x) + 1e-9f, ay = fabsf(d.y) + 1e-9f, az = fabsf(d.z) + 1e-9f;
    float dx = 1 / ax, dy = 1 / ay, dz = 1 / az;
    float tx = (d.x > 0 ? (ix + 1 - o.x) : (o.x - ix)) * dx;
    float ty = (d.y > 0 ? (iy + 1 - o.y) : (o.y - iy)) * dy;
    float tz = (d.z > 0 ? (iz + 1 - o.z) : (o.z - iz)) * dz;
    float t = 0, T = 1; v3 ins = {0, 0, 0};
    int hit = 0, axis = 0, m = 0, idx = 0;
    const float sigma = 0.0065f, kS = 1.35f;
    for (;;) {
        float tn; int a;
        if (tx < ty) { if (tx < tz) { tn = tx; a = 0; } else { tn = tz; a = 2; } }
        else { if (ty < tz) { tn = ty; a = 1; } else { tn = tz; a = 2; } }
        float te = tn < tmax ? tn : tmax, seg = te - t;
        if (iy < NY) {
            const float *F = Fv + (size_t)IDX(ix, iy, iz) * 3;
            float aa = sigma * densY[iy] * seg, w = T * aa;
            ins.x += w * (F[0] * kS + HAZE.x); ins.y += w * (F[1] * kS + HAZE.y); ins.z += w * (F[2] * kS + HAZE.z);
            T *= (1 - aa);
        }
        if (tn >= tmax) { t = tmax; break; }
        t = tn;
        if (a == 0) { ix += sx; tx += dx; } else if (a == 1) { iy += sy; ty += dy; } else { iz += sz; tz += dz; }
        if (iy >= NY) { if (sy > 0) { t = 1e9f; break; } continue; }
        idx = IDX(ix, iy, iz); m = M[idx];
        if (m) { hit = 1; axis = a; break; }
    }
    v3 surf;
    if (hit) {
        v3 pos = add(o, mul(d, t));
        int sg = axis == 0 ? -sx : (axis == 1 ? -sy : -sz);
        surf = shade_voxel(m, C[idx], ix, iy, iz, axis, sg, pos, d, t, depth);
    } else if (t < MAXD && dh.kind) {
        v3 pos = add(o, mul(d, t));
        if (dh.kind == 1) {
            v3 alb, emi; char_tex(&dh, &alb, &emi);
            v3 light = sampleV(Lv, pos.x + dh.n.x * 0.35f, pos.y + dh.n.y * 0.35f, pos.z + dh.n.z * 0.35f);
            light = add(mul(light, 1.25f), V(0.03f, 0.035f, 0.05f));
            // fake rim from own neon
            float rim = 1.0f + dot(d, dh.n); rim = rim * rim;
            surf = add(mulv(alb, add(light, mul(V(0.2f, 0.5f, 0.7f), 0.35f * rim))), emi);
        } else {
            v3 lp = dh.lp, hfz = cars[dh.part].half; int la = hfz.x > hfz.z ? 0 : 2; // long axis
            float lon = (&lp.x)[la] / (&hfz.x)[la];
            v3 emi = V(0, 0, 0), alb = V(0.04f, 0.04f, 0.05f);
            if (dh.face == la) emi = dh.sgn > 0 ? V(7, 7, 6) : V(7, 0.4f, 0.3f);
            else if (dh.face == 1 && dh.sgn < 0) emi = mul(PAL[dh.col], 3.0f);
            else if (dh.face != 1 && fabsf(lp.y) < 0.08f) emi = mul(PAL[dh.col], 3.5f);
            else if (dh.face == 1 && lon > -0.3f && lon < 0.4f) alb = V(0.01f, 0.02f, 0.04f);
            surf = add(mulv(alb, V(0.3f, 0.3f, 0.4f)), emi);
        }
    } else {
        surf = sky(d); t = 1e9f;
    }
    *tOut = t;
    return add(ins, mul(surf, T));
}

// ---------------------------------------------------------------- post
static void blur_h(const float *s, float *d, int w, int h, int horiz) {
    static const float k[5] = {0.0625f, 0.25f, 0.375f, 0.25f, 0.0625f};
#pragma omp parallel for schedule(static)
    for (int y = 0; y < h; y++) for (int x = 0; x < w; x++) {
        float r = 0, g = 0, b = 0;
        for (int j = -2; j <= 2; j++) {
            int xx = x, yy = y;
            if (horiz) { xx += j; if (xx < 0) xx = 0; if (xx >= w) xx = w - 1; } else { yy += j; if (yy < 0) yy = 0; if (yy >= h) yy = h - 1; }
            const float *p = s + (yy * w + xx) * 3; r += p[0] * k[j + 2]; g += p[1] * k[j + 2]; b += p[2] * k[j + 2];
        }
        float *q = d + (y * w + x) * 3; q[0] = r; q[1] = g; q[2] = b;
    }
}
static inline v3 bil(const float *s, int w, int h, float u, float v) {
    float x = u * w - 0.5f, y = v * h - 0.5f;
    int x0 = (int)floorf(x), y0 = (int)floorf(y); float fx = x - x0, fy = y - y0;
    int x1 = x0 + 1, y1 = y0 + 1;
    if (x0 < 0) x0 = 0; if (y0 < 0) y0 = 0; if (x1 >= w) x1 = w - 1; if (y1 >= h) y1 = h - 1; if (x0 >= w) x0 = w - 1; if (y0 >= h) y0 = h - 1;
    const float *a = s + (y0 * w + x0) * 3, *b = s + (y0 * w + x1) * 3, *c = s + (y1 * w + x0) * 3, *e = s + (y1 * w + x1) * 3;
    v3 r;
    r.x = (a[0] * (1 - fx) + b[0] * fx) * (1 - fy) + (c[0] * (1 - fx) + e[0] * fx) * fy;
    r.y = (a[1] * (1 - fx) + b[1] * fx) * (1 - fy) + (c[1] * (1 - fx) + e[1] * fx) * fy;
    r.z = (a[2] * (1 - fx) + b[2] * fx) * (1 - fy) + (c[2] * (1 - fx) + e[2] * fx) * fy;
    return r;
}
static inline float aces(float x) { float a = 2.51f, b = 0.03f, c = 2.43f, d = 0.59f, e = 0.14f; x = (x * (a * x + b)) / (x * (c * x + d) + e); return clampf(x, 0, 1); }

static void draw_rain(float *img, const float *dep, int W, int H) {
    const float BOX = 32.0f; const int N = 3600;
    for (int i = 0; i < N; i++) {
        uint32_t h = hsh(i * 2654435761u + 99);
        float bx = hf(h) * BOX, bz = hf(hsh(h + 1)) * BOX, by = hf(hsh(h + 2)) * BOX;
        float sp = (BOX / LOOPT) * (14 + (hsh(h + 3) % 5));
        by = fmodf(by - gTime * sp, BOX); if (by < 0) by += BOX;
        v3 p;
        p.x = camPos.x + fmodf(bx - camPos.x + 1000 * BOX, BOX) - BOX * 0.5f;
        p.z = camPos.z + fmodf(bz - camPos.z + 1000 * BOX, BOX) - BOX * 0.5f;
        p.y = camPos.y + fmodf(by - camPos.y + 1000 * BOX, BOX) - BOX * 0.4f;
        if (p.y < 1.0f) continue;
        { int cov = 0, cx = (int)floorf(p.x), cz = (int)floorf(p.z); for (int yy = (int)p.y + 1; yy < (int)p.y + 16 && yy < NY; yy++) if (M[IDX(cx, yy, cz)]) { cov = 1; break; } if (cov) continue; }
        v3 q = add(p, V(0.03f, 0.75f, 0.0f));
        v3 a = sub(p, camPos), b = sub(q, camPos);
        float za = dot(a, camF), zb = dot(b, camF);
        if (za < 0.35f || zb < 0.35f) continue;
        float sc = 0.5f * H / tanHalf;
        float xa = W * 0.5f + dot(a, camR) / za * sc, ya = H * 0.5f - dot(a, camU) / za * sc;
        float xb = W * 0.5f + dot(b, camR) / zb * sc, yb = H * 0.5f - dot(b, camU) / zb * sc;
        float dist = sqrtf(dot(a, a));
        v3 lc = sampleV(Fv, p.x, p.y, p.z);
        float k = 0.5f / (1.0f + dist * 0.22f);
        v3 col = mul(add(mul(lc, 1.6f), V(0.05f, 0.06f, 0.09f)), k);
        int n = (int)(fabsf(yb - ya) + fabsf(xb - xa)) + 1; if (n > 600) n = 600;
        float wdt = dist < 3.5f ? 1.0f : 0.0f;
        for (int s = 0; s <= n; s++) {
            float f = (float)s / n; float x = xa + (xb - xa) * f, y = ya + (yb - ya) * f;
            float fade = 4 * f * (1 - f) + 0.2f;
            for (int ox = 0; ox <= (int)wdt; ox++) {
                int xi = (int)x + ox, yi = (int)y;
                if (xi < 0 || yi < 0 || xi >= W || yi >= H) continue;
                if (dep[yi * W + xi] < dist) continue;
                float *px = img + (yi * W + xi) * 3;
                px[0] += col.x * fade; px[1] += col.y * fade; px[2] += col.z * fade;
            }
        }
    }
}

int main(int argc, char **argv) {
    int f0 = argc > 1 ? atoi(argv[1]) : 0, f1 = argc > 2 ? atoi(argv[2]) : 0, ss = argc > 3 ? atoi(argv[3]) : 1;
    int W = argc > 5 ? atoi(argv[4]) : 1080, H = argc > 5 ? atoi(argv[5]) : 1920;
    size_t n = (size_t)NX * NY * NZ;
    M = calloc(n, 1); C = calloc(n, 1); B = calloc(n, 1);
    Lv = calloc(n * 3, sizeof(float)); Fv = calloc(n * 3, sizeof(float));
    for (int y = 0; y <= NY; y++) densY[y] = expf(-y / 55.0f) + 0.12f;
    build_world();
    solve_light();
    fprintf(stderr, "world ready (%d buildings)\n", nb - 1);

    float *hdr = malloc((size_t)W * H * 3 * sizeof(float)), *dep = malloc((size_t)W * H * sizeof(float));
    uint8_t *out = malloc((size_t)W * H * 3);
    int bw[6], bh[6]; float *bl_[6], *tmp[6];
    for (int l = 0; l < 6; l++) { bw[l] = W >> (l + 1); bh[l] = H >> (l + 1); bl_[l] = malloc((size_t)bw[l] * bh[l] * 3 * sizeof(float)); tmp[l] = malloc((size_t)bw[l] * bh[l] * 3 * sizeof(float)); }

    for (int f = f0; f <= f1; f++) {
        setup_frame(f);
        float inv = 1.0f / (ss * ss);
#pragma omp parallel for schedule(dynamic, 4)
        for (int y = 0; y < H; y++) for (int x = 0; x < W; x++) {
            v3 acc = {0, 0, 0}; float tmin = 1e9f;
            for (int sy = 0; sy < ss; sy++) for (int sx = 0; sx < ss; sx++) {
                float px = x + (sx + 0.5f) / ss, py = y + (sy + 0.5f) / ss;
                float u = (2 * px / W - 1) * tanHalf * W / H, v = (1 - 2 * py / H) * tanHalf;
                v3 d = norm(add(camF, add(mul(camR, u), mul(camU, v))));
                float t; v3 c = trace(camPos, d, 0, &t);
                // soft clamp fireflies before resolve
                float mx = c.x > c.y ? c.x : c.y; if (c.z > mx) mx = c.z; if (mx > 12.0f) c = mul(c, 12.0f / mx);
                acc = add(acc, c); if (t < tmin) tmin = t;
            }
            float *p = hdr + ((size_t)y * W + x) * 3; p[0] = acc.x * inv; p[1] = acc.y * inv; p[2] = acc.z * inv;
            dep[(size_t)y * W + x] = tmin;
        }
        draw_rain(hdr, dep, W, H);
        // bloom
        for (int l = 0; l < 6; l++) {
            const float *src = l ? bl_[l - 1] : hdr; int sw = l ? bw[l - 1] : W;
#pragma omp parallel for schedule(static)
            for (int y = 0; y < bh[l]; y++) for (int x = 0; x < bw[l]; x++) {
                float r = 0, g = 0, b = 0;
                for (int k = 0; k < 4; k++) { const float *p = src + ((size_t)(y * 2 + (k >> 1)) * sw + x * 2 + (k & 1)) * 3; r += p[0]; g += p[1]; b += p[2]; }
                r *= 0.25f; g *= 0.25f; b *= 0.25f;
                if (l == 0) { float mx = r > g ? r : g; if (b > mx) mx = b; float kk = clampf((mx - 0.75f) / 1.2f, 0, 1); kk = kk * kk; r *= kk; g *= kk; b *= kk; }
                float *q = bl_[l] + ((size_t)y * bw[l] + x) * 3; q[0] = r; q[1] = g; q[2] = b;
            }
            blur_h(bl_[l], tmp[l], bw[l], bh[l], 1); blur_h(tmp[l], bl_[l], bw[l], bh[l], 0);
        }
        static const float bwgt[6] = {0.30f, 0.26f, 0.22f, 0.18f, 0.14f, 0.12f};
#pragma omp parallel for schedule(static)
        for (int y = 0; y < H; y++) for (int x = 0; x < W; x++) {
            float u = (x + 0.5f) / W, v = (y + 0.5f) / H;
            const float *p = hdr + ((size_t)y * W + x) * 3;
            v3 c = V(p[0], p[1], p[2]);
            for (int l = 0; l < 6; l++) c = add(c, mul(bil(bl_[l], bw[l], bh[l], u, v), bwgt[l] * 0.62f));
            float cx = u - 0.5f, cy = v - 0.5f, vg = 1.0f - 0.55f * (cx * cx * 1.2f + cy * cy * 0.9f);
            c = mul(c, 1.55f * vg);
            // gentle teal/magenta grade
            c.x = aces(c.x * 1.02f); c.y = aces(c.y * 0.98f); c.z = aces(c.z * 1.06f);
            float gr = (hf(h3(x, y, f)) - 0.5f) * 0.012f;
            uint8_t *q = out + ((size_t)y * W + x) * 3;
            q[0] = (uint8_t)(clampf(powf(c.x, 1 / 2.2f) + gr, 0, 1) * 255.0f + 0.5f);
            q[1] = (uint8_t)(clampf(powf(c.y, 1 / 2.2f) + gr, 0, 1) * 255.0f + 0.5f);
            q[2] = (uint8_t)(clampf(powf(c.z, 1 / 2.2f) + gr, 0, 1) * 255.0f + 0.5f);
        }
        fwrite(out, 1, (size_t)W * H * 3, stdout);
        if ((f - f0) % 10 == 0) fprintf(stderr, "frame %d\n", f);
    }
    return 0;
}
