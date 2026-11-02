// voxrt.c - CPU voxel ray tracer for "Tilo y la Estrella del Alba"
// Reads a scene/frame protocol on stdin, writes raw RGB24 frames to stdout.
//   - DDA voxel traversal accelerated with a Chebyshev distance field
//   - ray traced sun/moon shadows and point-light shadows
//   - mirror reflections (ice, crystal, metal) with Fresnel
//   - smooth per-vertex ambient occlusion
//   - animated voxel instances (characters) as oriented voxel grids
//   - adaptive anti-aliasing (edge pixels get 5 samples)
//   - HDR: glows, beams, particles, bloom, ACES tonemap, grading, dithering
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <stdint.h>
#include <omp.h>

typedef struct { float x, y, z; } v3;
static inline v3 V(float x, float y, float z) { v3 r = {x, y, z}; return r; }
static inline v3 add(v3 a, v3 b) { return V(a.x + b.x, a.y + b.y, a.z + b.z); }
static inline v3 sub(v3 a, v3 b) { return V(a.x - b.x, a.y - b.y, a.z - b.z); }
static inline v3 mul(v3 a, float s) { return V(a.x * s, a.y * s, a.z * s); }
static inline v3 mulv(v3 a, v3 b) { return V(a.x * b.x, a.y * b.y, a.z * b.z); }
static inline float dot(v3 a, v3 b) { return a.x * b.x + a.y * b.y + a.z * b.z; }
static inline v3 cross(v3 a, v3 b) { return V(a.y * b.z - a.z * b.y, a.z * b.x - a.x * b.z, a.x * b.y - a.y * b.x); }
static inline float len(v3 a) { return sqrtf(dot(a, a)); }
static inline v3 norm(v3 a) { float l = len(a); return l > 1e-12f ? mul(a, 1.0f / l) : V(0, 1, 0); }
static inline v3 lerp3(v3 a, v3 b, float t) { return add(a, mul(sub(b, a), t)); }
static inline float clampf(float x, float a, float b) { return x < a ? a : (x > b ? b : x); }
static inline float smooth(float a, float b, float x) { float t = clampf((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); }
static inline float fracf(float x) { return x - floorf(x); }
static inline float maxf(float a, float b) { return a > b ? a : b; }
static inline float minf(float a, float b) { return a < b ? a : b; }
static inline float comp(v3 a, int i) { return i == 0 ? a.x : (i == 1 ? a.y : a.z); }

static inline uint32_t hash3i(int x, int y, int z) {
    uint32_t h = (uint32_t)x * 374761393u + (uint32_t)y * 668265263u + (uint32_t)z * 2147483647u;
    h = (h ^ (h >> 13)) * 1274126177u;
    return h ^ (h >> 16);
}
static inline float hashf(int x, int y, int z) { return (hash3i(x, y, z) & 0xffffff) / 16777216.0f; }
static float vnoise3(float x, float y, float z) {
    int ix = (int)floorf(x), iy = (int)floorf(y), iz = (int)floorf(z);
    float fx = x - ix, fy = y - iy, fz = z - iz;
    fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy); fz = fz * fz * (3 - 2 * fz);
    float a = hashf(ix, iy, iz), b = hashf(ix + 1, iy, iz), c = hashf(ix, iy + 1, iz), d = hashf(ix + 1, iy + 1, iz);
    float e = hashf(ix, iy, iz + 1), f = hashf(ix + 1, iy, iz + 1), g = hashf(ix, iy + 1, iz + 1), h = hashf(ix + 1, iy + 1, iz + 1);
    float l0 = (a + (b - a) * fx) + ((c + (d - c) * fx) - (a + (b - a) * fx)) * fy;
    float l1 = (e + (f - e) * fx) + ((g + (h - g) * fx) - (e + (f - e) * fx)) * fy;
    return l0 + (l1 - l0) * fz;
}
static float fbm3(float x, float y, float z) {
    float s = 0, a = 0.5f;
    for (int i = 0; i < 4; i++) { s += a * vnoise3(x, y, z); x *= 2.03f; y *= 2.03f; z *= 2.03f; a *= 0.5f; }
    return s;
}

// ---------------------------------------------------------------- grids
typedef struct {
    int w, h, d;
    uint8_t *v;     // voxel ids (index = (y*d + z)*w + x)
    uint8_t *dist;  // chebyshev distance to nearest solid (world only)
} Grid;

static inline int gidx(const Grid *g, int x, int y, int z) { return (y * g->d + z) * g->w + x; }
static inline int gget(const Grid *g, int x, int y, int z) {
    if (x < 0 || y < 0 || z < 0 || x >= g->w || y >= g->h || z >= g->d) return 0;
    return g->v[gidx(g, x, y, z)];
}

#define DCAP 15
static void build_dist(Grid *g) {
    int W = g->w, H = g->h, D = g->d;
    size_t n = (size_t)W * H * D;
    if (!g->dist) g->dist = malloc(n);
    uint8_t *a = g->dist, *b = malloc(n);
    for (size_t i = 0; i < n; i++) a[i] = g->v[i] ? 0 : DCAP;
    // x pass
    #pragma omp parallel for
    for (int y = 0; y < H; y++) for (int z = 0; z < D; z++) for (int x = 0; x < W; x++) {
        int best = a[gidx(g, x, y, z)];
        for (int k = 1; k < best && k < DCAP; k++) {
            int c1 = x - k >= 0 ? a[gidx(g, x - k, y, z)] : DCAP; int c2 = x + k < W ? a[gidx(g, x + k, y, z)] : DCAP;
            int m = c1 < c2 ? c1 : c2; int v = m > k ? m : k; if (v < best) best = v;
        }
        b[gidx(g, x, y, z)] = best;
    }
    // z pass
    #pragma omp parallel for
    for (int y = 0; y < H; y++) for (int z = 0; z < D; z++) for (int x = 0; x < W; x++) {
        int best = b[gidx(g, x, y, z)];
        for (int k = 1; k < best && k < DCAP; k++) {
            int c1 = z - k >= 0 ? b[gidx(g, x, y, z - k)] : DCAP; int c2 = z + k < D ? b[gidx(g, x, y, z + k)] : DCAP;
            int m = c1 < c2 ? c1 : c2; int v = m > k ? m : k; if (v < best) best = v;
        }
        a[gidx(g, x, y, z)] = best;
    }
    // y pass
    #pragma omp parallel for
    for (int y = 0; y < H; y++) for (int z = 0; z < D; z++) for (int x = 0; x < W; x++) {
        int best = a[gidx(g, x, y, z)];
        for (int k = 1; k < best && k < DCAP; k++) {
            int c1 = y - k >= 0 ? a[gidx(g, x, y - k, z)] : DCAP; int c2 = y + k < H ? a[gidx(g, x, y + k, z)] : DCAP;
            int m = c1 < c2 ? c1 : c2; int v = m > k ? m : k; if (v < best) best = v;
        }
        b[gidx(g, x, y, z)] = best;
    }
    memcpy(a, b, n);
    free(b);
}

// ---------------------------------------------------------------- materials
typedef struct {
    v3 c1, c2;      // base / secondary color (linear)
    int pattern;
    v3 emit;        // emissive color (linear, HDR)
    float refl;     // mirror reflectivity
    float emitScale;
} Mat;
static Mat mats[256];

// ---------------------------------------------------------------- models / instances
typedef struct {
    Grid g;
    v3 pal[256];
    float palEmit[256];
    float palRefl[256];
    v3 pivot;
} Model;
#define MAXMODELS 128
static Model models[MAXMODELS];

typedef struct {
    int model;
    v3 pos;
    float R[9];       // rows; local->world: world = pos + R*(scale*(l - pivot))
    float scale;
    int shadow;       // casts shadow
    float emitMul;    // multiplies palette emission
    v3 tint;
    v3 bmin, bmax;    // world aabb
    float sx0, sy0, sx1, sy1; // screen rect (pixels) for primary-ray culling
} Inst;
#define MAXINST 512
static Inst inst[MAXINST];
static int ninst = 0;

typedef struct { v3 p; v3 c; float r; int shadow; } Light;
#define MAXLIGHTS 512
static Light lights[MAXLIGHTS];
static int nlights = 0;

typedef struct { v3 p; v3 c; float size; } Glow;
#define MAXGLOWS 512
static Glow glows[MAXGLOWS];
static int nglows = 0;

typedef struct { v3 a, b; v3 c; float w; } Beam;
#define MAXBEAMS 64
static Beam beams[MAXBEAMS];
static int nbeams = 0;

typedef struct { v3 p; float size; v3 c; float a; int type; } Part;
static Part *parts = NULL;
static int nparts = 0, capparts = 0;

// ---------------------------------------------------------------- frame state
static Grid world = {0};
static int W = 1920, H = 1080;
static v3 camP, camT; static float camFov = 40, camRoll = 0;
static v3 sunDir = {0.3f, 0.8f, 0.2f}, sunCol = {1, 1, 1};
static v3 skyZen = {0.02f, 0.03f, 0.08f}, skyHor = {0.08f, 0.1f, 0.2f};
static float starAmt = 1, auroraAmt = 0, moonSize = 0.03f;
static v3 moonDir = {0.3f, 0.6f, -0.7f}; static v3 moonCol = {2, 2, 2.2f};
static v3 ambCol = {0.1f, 0.12f, 0.2f};
static v3 fogCol = {0.08f, 0.1f, 0.2f}; static float fogDen = 0.004f;
static float ftime = 0;
static float exposure = 1, saturation = 1, contrast = 1, vignette = 0.3f, fade = 0;
static v3 gradeTint = {1, 1, 1};
static float bloomStr = 0.08f, bloomThr = 1.0f;
static int planeOn = 1; static float planeY = 0; static int planeMat = 0;
static int frameNo = 0;
static float camClip = 0;

// light grid
#define LGC 8
#define LGMAX 24
static int lgW, lgH, lgD; static int *lgCount = NULL; static int *lgIdx = NULL;

static void build_light_grid(void) {
    lgW = (world.w + LGC - 1) / LGC; lgH = (world.h + LGC - 1) / LGC; lgD = (world.d + LGC - 1) / LGC;
    int n = lgW * lgH * lgD;
    lgCount = realloc(lgCount, sizeof(int) * n);
    lgIdx = realloc(lgIdx, sizeof(int) * n * LGMAX);
    memset(lgCount, 0, sizeof(int) * n);
    for (int i = 0; i < nlights; i++) {
        Light *L = &lights[i];
        int x0 = (int)floorf((L->p.x - L->r) / LGC), x1 = (int)floorf((L->p.x + L->r) / LGC);
        int y0 = (int)floorf((L->p.y - L->r) / LGC), y1 = (int)floorf((L->p.y + L->r) / LGC);
        int z0 = (int)floorf((L->p.z - L->r) / LGC), z1 = (int)floorf((L->p.z + L->r) / LGC);
        if (x0 < 0) x0 = 0; if (y0 < 0) y0 = 0; if (z0 < 0) z0 = 0;
        if (x1 >= lgW) x1 = lgW - 1; if (y1 >= lgH) y1 = lgH - 1; if (z1 >= lgD) z1 = lgD - 1;
        for (int y = y0; y <= y1; y++) for (int z = z0; z <= z1; z++) for (int x = x0; x <= x1; x++) {
            int c = (y * lgD + z) * lgW + x;
            if (lgCount[c] < LGMAX) { lgIdx[c * LGMAX + lgCount[c]] = i; lgCount[c]++; }
            else {
                // replace weakest
                int wi = -1; float wv = 1e30f;
                float s = L->c.x + L->c.y + L->c.z;
                for (int k = 0; k < LGMAX; k++) { Light *O = &lights[lgIdx[c * LGMAX + k]]; float v = O->c.x + O->c.y + O->c.z; if (v < wv) { wv = v; wi = k; } }
                if (wv < s) lgIdx[c * LGMAX + wi] = i;
            }
        }
    }
}

// ---------------------------------------------------------------- tracing
typedef struct {
    float t;
    int axis, sign;     // hit face normal = sign * e_axis (in grid space)
    int cx, cy, cz;     // cell
    int val;
    int inst;           // -1 world, -2 plane, >=0 instance
    v3 lp;              // grid-space hit point
} Hit;

static inline v3 fixdir(v3 d) {
    if (fabsf(d.x) < 1e-7f) d.x = 1e-7f;
    if (fabsf(d.y) < 1e-7f) d.y = 1e-7f;
    if (fabsf(d.z) < 1e-7f) d.z = 1e-7f;
    return d;
}

static int box_isect(v3 o, v3 id, v3 bmin, v3 bmax, float *t0, float *t1, int *eaxis) {
    float tx0 = (bmin.x - o.x) * id.x, tx1 = (bmax.x - o.x) * id.x;
    float ty0 = (bmin.y - o.y) * id.y, ty1 = (bmax.y - o.y) * id.y;
    float tz0 = (bmin.z - o.z) * id.z, tz1 = (bmax.z - o.z) * id.z;
    float ax = minf(tx0, tx1), bx = maxf(tx0, tx1), ay = minf(ty0, ty1), by = maxf(ty0, ty1), az = minf(tz0, tz1), bz = maxf(tz0, tz1);
    float tn = ax; int ea = 0;
    if (ay > tn) { tn = ay; ea = 1; }
    if (az > tn) { tn = az; ea = 2; }
    float tf = minf(bx, minf(by, bz));
    *t0 = tn; *t1 = tf; if (eaxis) *eaxis = ea;
    return tf >= tn && tf > 0;
}

// generic DDA through grid; use distance field if available. Returns 1 on hit.
static int trace_grid(const Grid *g, v3 o, v3 d, float tmin, float tmax, Hit *h) {
    v3 id = V(1.0f / d.x, 1.0f / d.y, 1.0f / d.z);
    float t0, t1; int ea;
    if (!box_isect(o, id, V(0, 0, 0), V((float)g->w, (float)g->h, (float)g->d), &t0, &t1, &ea)) return 0;
    if (t1 < tmin) return 0;
    float t = t0 > tmin ? t0 : tmin;
    if (t > tmax) return 0;
    int lastAxis = t0 > tmin ? ea : -1;
    v3 p = add(o, mul(d, t + 1e-5f));
    int ix = (int)floorf(p.x), iy = (int)floorf(p.y), iz = (int)floorf(p.z);
    if (ix < 0) ix = 0; if (ix >= g->w) ix = g->w - 1;
    if (iy < 0) iy = 0; if (iy >= g->h) iy = g->h - 1;
    if (iz < 0) iz = 0; if (iz >= g->d) iz = g->d - 1;
    int sx = d.x > 0 ? 1 : -1, sy = d.y > 0 ? 1 : -1, sz = d.z > 0 ? 1 : -1;
    float dx = fabsf(id.x), dy = fabsf(id.y), dz = fabsf(id.z);
    float tmx = ((ix + (sx > 0)) - o.x) * id.x;
    float tmy = ((iy + (sy > 0)) - o.y) * id.y;
    float tmz = ((iz + (sz > 0)) - o.z) * id.z;
    float tcur = t;
    for (int it = 0; it < 4096; it++) {
        int idx = gidx(g, ix, iy, iz);
        int v = g->v[idx];
        if (v) {
            h->t = tcur; h->cx = ix; h->cy = iy; h->cz = iz; h->val = v;
            if (lastAxis < 0) { // started inside a solid cell
                h->axis = 1; h->sign = 1;
            } else {
                h->axis = lastAxis;
                h->sign = lastAxis == 0 ? -sx : (lastAxis == 1 ? -sy : -sz);
            }
            h->lp = add(o, mul(d, tcur));
            return 1;
        }
        int dd = g->dist ? g->dist[idx] : 1;
        if (dd > 1) {
            int r = dd - 1;
            float bx = (sx > 0 ? (float)(ix + r + 1) : (float)(ix - r));
            float by = (sy > 0 ? (float)(iy + r + 1) : (float)(iy - r));
            float bz = (sz > 0 ? (float)(iz + r + 1) : (float)(iz - r));
            float ex = (bx - o.x) * id.x, ey = (by - o.y) * id.y, ez = (bz - o.z) * id.z;
            float te = ex; int ax = 0;
            if (ey < te) { te = ey; ax = 1; }
            if (ez < te) { te = ez; ax = 2; }
            if (te > tmax) return 0;
            v3 q = add(o, mul(d, te));
            int nx = (int)floorf(q.x), ny = (int)floorf(q.y), nz = (int)floorf(q.z);
            // clamp non-exit axes into the box range, exit axis just outside
            int lox = ix - r, hix = ix + r, loy = iy - r, hiy = iy + r, loz = iz - r, hiz = iz + r;
            if (nx < lox) nx = lox; if (nx > hix) nx = hix;
            if (ny < loy) ny = loy; if (ny > hiy) ny = hiy;
            if (nz < loz) nz = loz; if (nz > hiz) nz = hiz;
            if (ax == 0) nx = sx > 0 ? hix + 1 : lox - 1;
            else if (ax == 1) ny = sy > 0 ? hiy + 1 : loy - 1;
            else nz = sz > 0 ? hiz + 1 : loz - 1;
            if (nx < 0 || ny < 0 || nz < 0 || nx >= g->w || ny >= g->h || nz >= g->d) return 0;
            ix = nx; iy = ny; iz = nz; tcur = te; lastAxis = ax;
            tmx = ((ix + (sx > 0)) - o.x) * id.x;
            tmy = ((iy + (sy > 0)) - o.y) * id.y;
            tmz = ((iz + (sz > 0)) - o.z) * id.z;
            continue;
        }
        if (tmx < tmy && tmx < tmz) {
            tcur = tmx; ix += sx; tmx += dx; lastAxis = 0;
            if (ix < 0 || ix >= g->w) return 0;
        } else if (tmy < tmz) {
            tcur = tmy; iy += sy; tmy += dy; lastAxis = 1;
            if (iy < 0 || iy >= g->h) return 0;
        } else {
            tcur = tmz; iz += sz; tmz += dz; lastAxis = 2;
            if (iz < 0 || iz >= g->d) return 0;
        }
        if (tcur > tmax) return 0;
    }
    return 0;
}

static inline v3 inst_to_local_p(const Inst *I, v3 p) {
    v3 q = sub(p, I->pos);
    const float *R = I->R;
    v3 l = V(R[0] * q.x + R[3] * q.y + R[6] * q.z, R[1] * q.x + R[4] * q.y + R[7] * q.z, R[2] * q.x + R[5] * q.y + R[8] * q.z);
    return add(mul(l, 1.0f / I->scale), models[I->model].pivot);
}
static inline v3 inst_to_local_d(const Inst *I, v3 d) {
    const float *R = I->R;
    v3 l = V(R[0] * d.x + R[3] * d.y + R[6] * d.z, R[1] * d.x + R[4] * d.y + R[7] * d.z, R[2] * d.x + R[5] * d.y + R[8] * d.z);
    return mul(l, 1.0f / I->scale);
}
static inline v3 inst_to_world_d(const Inst *I, v3 d) {
    const float *R = I->R;
    return V(R[0] * d.x + R[1] * d.y + R[2] * d.z, R[3] * d.x + R[4] * d.y + R[5] * d.z, R[6] * d.x + R[7] * d.y + R[8] * d.z);
}

static void inst_bounds(Inst *I) {
    Model *M = &models[I->model];
    v3 mn = V(1e30f, 1e30f, 1e30f), mx = V(-1e30f, -1e30f, -1e30f);
    for (int c = 0; c < 8; c++) {
        v3 l = V((c & 1) ? M->g.w : 0, (c & 2) ? M->g.h : 0, (c & 4) ? M->g.d : 0);
        l = mul(sub(l, M->pivot), I->scale);
        const float *R = I->R;
        v3 w = add(I->pos, V(R[0] * l.x + R[1] * l.y + R[2] * l.z, R[3] * l.x + R[4] * l.y + R[5] * l.z, R[6] * l.x + R[7] * l.y + R[8] * l.z));
        mn = V(minf(mn.x, w.x), minf(mn.y, w.y), minf(mn.z, w.z));
        mx = V(maxf(mx.x, w.x), maxf(mx.y, w.y), maxf(mx.z, w.z));
    }
    I->bmin = sub(mn, V(0.01f, 0.01f, 0.01f)); I->bmax = add(mx, V(0.01f, 0.01f, 0.01f));
}

// full scene trace. shadowOnly: ignore non-shadow instances
static int trace_scene_px(v3 o, v3 d, float tmax, Hit *h, int shadowRay, const float *pix) {
    int hit = 0;
    float best = tmax;
    Hit tmp;
    if (trace_grid(&world, o, d, pix ? camClip : 0, best, &tmp)) { *h = tmp; h->inst = -1; best = tmp.t; hit = 1; if (shadowRay) return 1; }
    v3 id = V(1.0f / d.x, 1.0f / d.y, 1.0f / d.z);
    for (int i = 0; i < ninst; i++) {
        Inst *I = &inst[i];
        if (shadowRay && !I->shadow) continue;
        if (pix && (pix[0] < I->sx0 || pix[0] > I->sx1 || pix[1] < I->sy0 || pix[1] > I->sy1)) continue;
        float t0, t1;
        if (!box_isect(o, id, I->bmin, I->bmax, &t0, &t1, NULL)) continue;
        if (t0 > best) continue;
        v3 lo = inst_to_local_p(I, o), ld = fixdir(inst_to_local_d(I, d));
        if (trace_grid(&models[I->model].g, lo, ld, 0, best, &tmp)) {
            if (tmp.t < best) { *h = tmp; h->inst = i; best = tmp.t; hit = 1; if (shadowRay) return 1; }
        }
    }
    if (!shadowRay && planeOn && !hit && d.y < 0) {
        float t = (planeY - o.y) / d.y;
        if (t > 0 && t < tmax) {
            h->t = t; h->inst = -2; h->axis = 1; h->sign = 1; h->lp = add(o, mul(d, t));
            h->cx = (int)floorf(h->lp.x); h->cy = (int)floorf(planeY) - 1; h->cz = (int)floorf(h->lp.z); h->val = planeMat;
            hit = 1;
        }
    }
    return hit;
}

static int trace_scene(v3 o, v3 d, float tmax, Hit *h, int shadowRay) { return trace_scene_px(o, d, tmax, h, shadowRay, NULL); }

static int occluded(v3 o, v3 d, float tmax) {
    Hit h;
    return trace_scene(o, d, tmax, &h, 1);
}

// ---------------------------------------------------------------- textures
// returns albedo, writes emission weight
static v3 texture(int matid, int cx, int cy, int cz, int axis, int sign, float u, float v, float *emw, float *roughOut) {
    Mat *m = &mats[matid];
    int tu = (int)floorf(u * 16), tv = (int)floorf(v * 16);
    if (tu > 15) tu = 15; if (tv > 15) tv = 15; if (tu < 0) tu = 0; if (tv < 0) tv = 0;
    int face = axis * 2 + (sign > 0);
    float n1 = hashf(cx * 16 + tu, cy * 16 + tv + face * 977, cz * 16 + matid * 131);
    float n2 = hashf(cx * 7 + tu / 2, cy * 5 + tv / 2 + face, cz * 3 + matid);
    float b = 1.0f;
    v3 col = m->c1;
    *emw = 1.0f;
    *roughOut = 1.0f;
    int top = (axis == 1 && sign > 0), bottom = (axis == 1 && sign < 0);
    switch (m->pattern) {
    case 0: // noise
        b = 0.86f + 0.28f * n1; break;
    case 1: { // planks (horizontal)
        int row = tv / 4; float rn = hashf(cx, cy * 4 + row, cz + face);
        b = 0.82f + 0.12f * rn + 0.1f * n1;
        if (tv % 4 == 3) b *= 0.62f;
        int seam = (int)(hashf(cx, cy * 4 + row, cz * 3) * 16);
        if (tu == seam) b *= 0.7f;
        break; }
    case 2: { // bricks
        int row = tv / 4; int off = (row & 1) * 4; int col8 = (tu + off) % 8;
        if (tv % 4 == 3 || col8 == 7) { col = m->c2; b = 0.9f + 0.1f * n1; }
        else b = 0.85f + 0.15f * hashf(cx * 4 + (tu + off) / 8, cy * 4 + row, cz + face) + 0.06f * n1;
        break; }
    case 3: { // log
        if (axis == 1) { float r = sqrtf((u - .5f) * (u - .5f) + (v - .5f) * (v - .5f)); col = m->c2; b = 0.85f + 0.15f * sinf(r * 40) * 0.5f + 0.1f * n1; }
        else { b = 0.75f + 0.25f * hashf(tu / 2 + face * 31, cx + cz, 0) + 0.1f * n1; if ((tu + (int)(hashf(cx, cz, tv / 5) * 3)) % 5 == 0) b *= 0.7f; }
        break; }
    case 4: { // leaves with snow on top
        float hole = n1;
        b = 0.7f + 0.45f * n2 * n1 + 0.1f;
        if (hole < 0.12f) b *= 0.5f;
        if (top) { float sn = vnoise3((cx * 16 + tu) * 0.3f, cy * 2.0f, (cz * 16 + tv) * 0.3f); if (sn > 0.32f) { col = m->c2; b = 0.92f + 0.08f * n1; } }
        else if (axis != 1 && tv < 3 + (int)(n2 * 3) && gget(&world, cx, cy + 1, cz) == 0) { col = m->c2; b = 0.9f + 0.1f * n1; }
        break; }
    case 5: { // dirt with snow top
        if (top) { col = m->c2; b = 0.93f + 0.07f * n1; }
        else if (bottom) { b = 0.8f + 0.25f * n1; }
        else {
            int band = 3 + (int)(hashf(cx * 16 + tu, cz, cy) * 2.5f);
            if (tv < band && gget(&world, cx, cy + 1, cz) == 0) { col = m->c2; b = 0.92f + 0.08f * n1; }
            else b = 0.75f + 0.3f * n1;
        }
        break; }
    case 6: { // cobble
        float cx2 = (tu + 0.5f) / 16.f, cy2 = (tv + 0.5f) / 16.f;
        float best = 9, best2 = 9;
        for (int i = 0; i < 6; i++) {
            float px = hashf(cx + face * 13, cy * 7 + i, cz), py = hashf(cx, cy + i * 11, cz + face);
            float dd = (cx2 - px) * (cx2 - px) + (cy2 - py) * (cy2 - py);
            if (dd < best) { best2 = best; best = dd; } else if (dd < best2) best2 = dd;
        }
        b = (sqrtf(best2) - sqrtf(best) < 0.05f) ? 0.55f : 0.85f + 0.2f * n1;
        break; }
    case 7: { // crystal facets
        float f = fracf(u * 2 + v * 3 + hashf(cx, cy, cz)), g2 = fracf(u * 3 - v * 2);
        b = 0.75f + 0.35f * smooth(0.3f, 0.7f, f) * smooth(0.2f, 0.9f, g2);
        if (n1 > 0.93f) { col = m->c2; b = 1.4f; }
        *roughOut = 0.0f;
        break; }
    case 8: { // lava animated
        float px = cx + u, pz = cz + v;
        if (axis != 1) { px = (axis == 0 ? cz : cx) + u; pz = cy + v; }
        float nn = fbm3(px * 0.6f, pz * 0.6f, ftime * 0.25f);
        float k = smooth(0.35f, 0.7f, nn);
        col = lerp3(m->c2, m->c1, k);
        *emw = 0.25f + 1.2f * k * k;
        b = 1;
        break; }
    case 9: { // christmas light bulb block: bulb in middle, dark wire around
        float du = u - .5f, dv = v - .5f; float r = sqrtf(du * du + dv * dv);
        float tw = 0.6f + 0.4f * sinf(ftime * 2.0f + hashf(cx, cy, cz) * 6.28f);
        if (r < 0.32f) { *emw = tw * (1.2f - r * 2); b = 1; }
        else { col = m->c2; *emw = 0; b = 0.8f + 0.2f * n1; }
        break; }
    case 10: { // ice
        b = 0.93f + 0.07f * n1;
        float crack = fabsf(sinf((cx + u) * 2.3f + (cz + v) * 1.7f + vnoise3((cx + u) * 1.3f, 0, (cz + v) * 1.3f) * 5));
        if (crack < 0.04f) { col = m->c2; }
        *roughOut = 0.0f;
        break; }
    case 11: { // window: frame color2, inner emissive glass panes
        int fr = (tu < 2 || tu > 13 || tv < 2 || tv > 13 || tu == 7 || tu == 8 || tv == 7 || tv == 8);
        if (fr) { col = m->c2; *emw = 0; b = 0.85f + 0.15f * n1; }
        else { b = 1.0f; *emw = 0.85f + 0.15f * n2; }
        break; }
    case 12: { // roof tiles, snow covered on top
        int row = tv / 3; int off = (row & 1) * 2;
        b = 0.8f + 0.15f * hashf(cx * 4 + (tu + off) / 4, cy * 6 + row, cz + face) + 0.08f * n1;
        if (tv % 3 == 2) b *= 0.65f;
        int openAbove = gget(&world, cx, cy + 1, cz) == 0;
        if (top && openAbove) {
            float sn = vnoise3((cx * 16 + tu) * 0.25f, cy * 3.0f, (cz * 16 + tv) * 0.25f);
            if (sn > 0.3f) { col = V(0.84f, 0.89f, 0.97f); b = 0.95f + 0.05f * n1; }
        } else if (axis != 1 && openAbove) {
            int band = 2 + (int)(hashf(cx * 16 + tu, cz, cy) * 2.5f);
            if (tv < band) { col = V(0.84f, 0.89f, 0.97f); b = 0.93f + 0.07f * n1; }
        }
        break; }
    case 13: // snow
        b = 0.95f + 0.05f * n1; if (n1 > 0.985f) b = 1.25f;
        break;
    case 14: { // moss stone
        float mm = vnoise3((cx * 16 + tu) * 0.15f, (cy * 16 + tv) * 0.15f, cz + face * 3.0f);
        if (mm > 0.55f) col = m->c2;
        b = 0.82f + 0.25f * n1;
        break; }
    case 15: { // metal
        b = 0.9f + 0.1f * n1; if ((tu == 2 || tu == 13) && (tv == 2 || tv == 13)) b = 1.3f;
        *roughOut = 0.3f;
        break; }
    case 16: // cloth
        b = 0.9f + 0.1f * n1; if ((tu + tv) % 4 == 0) b *= 0.92f;
        break;
    case 17: { // glow block (lantern) - frame with emissive center
        int fr = (tu < 3 || tu > 12 || tv < 2 || tv > 13);
        if (fr) { col = m->c2; *emw = 0; b = 0.8f + 0.2f * n1; }
        else { *emw = 1.0f; b = 1; }
        break; }
    case 18: // plain emissive
        *emw = 0.9f + 0.1f * n1; b = 1;
        break;
    case 19: { // polished stone (slightly reflective)
        b = 0.9f + 0.1f * n1;
        if (tu == 0 || tv == 0) b *= 0.8f;
        *roughOut = 0.2f;
        break; }
    case 20: { // present box: ribbon
        if (tu == 7 || tu == 8 || tv == 7 || tv == 8) { col = m->c2; b = 1; } else b = 0.9f + 0.1f * n1;
        break; }
    }
    return mul(col, b);
}

// smooth AO from neighbour occupancy
static float vertex_ao(int s1, int s2, int c) { if (s1 && s2) return 0; return 3.0f - (s1 + s2 + c); }
static float face_ao(const Grid *g, int cx, int cy, int cz, int axis, int sign, float fu, float fv) {
    // neighbour layer
    int nx = cx + (axis == 0 ? sign : 0), ny = cy + (axis == 1 ? sign : 0), nz = cz + (axis == 2 ? sign : 0);
    int ua = axis == 0 ? 2 : 0, va = axis == 1 ? 2 : 1;
    #define OCC(du, dv) (gget(g, nx + (ua == 0 ? du : 0) + (va == 0 ? dv : 0), ny + (ua == 1 ? du : 0) + (va == 1 ? dv : 0), nz + (ua == 2 ? du : 0) + (va == 2 ? dv : 0)) != 0)
    int e_um = OCC(-1, 0), e_up = OCC(1, 0), e_vm = OCC(0, -1), e_vp = OCC(0, 1);
    int c_mm = OCC(-1, -1), c_pm = OCC(1, -1), c_mp = OCC(-1, 1), c_pp = OCC(1, 1);
    #undef OCC
    float a00 = vertex_ao(e_um, e_vm, c_mm), a10 = vertex_ao(e_up, e_vm, c_pm);
    float a01 = vertex_ao(e_um, e_vp, c_mp), a11 = vertex_ao(e_up, e_vp, c_pp);
    float a = (a00 * (1 - fu) + a10 * fu) * (1 - fv) + (a01 * (1 - fu) + a11 * fu) * fv;
    float r = a / 3.0f;
    return 0.35f + 0.65f * r;
}

// ---------------------------------------------------------------- sky
static v3 sky(v3 d) {
    float h = d.y;
    v3 c = lerp3(skyHor, skyZen, powf(clampf(h, 0, 1), 0.55f));
    if (h < 0) c = mul(skyHor, 1.0f + h * 0.4f);
    if (starAmt > 0 && h > 0.02f) {
        float sc = 220;
        v3 q = mul(d, sc);
        int ix = (int)floorf(q.x), iy = (int)floorf(q.y), iz = (int)floorf(q.z);
        float hs = hashf(ix, iy, iz);
        if (hs > 0.985f) {
            v3 ctr = V(ix + hashf(ix + 7, iy, iz), iy + hashf(ix, iy + 7, iz), iz + hashf(ix, iy, iz + 7));
            float dd = len(sub(q, ctr));
            float br = (hs - 0.985f) / 0.015f;
            float tw = 0.75f + 0.25f * sinf(ftime * (1.5f + 3 * hs) + hs * 50);
            float s = expf(-dd * dd * 18.0f) * br * br * 6.0f * tw;
            v3 sc2 = lerp3(V(0.8f, 0.85f, 1.0f), V(1.0f, 0.9f, 0.7f), hashf(iz, ix, iy));
            c = add(c, mul(sc2, s * starAmt * smooth(0.02f, 0.2f, h)));
        }
    }
    if (auroraAmt > 0 && h > 0.03f) {
        float k = 1.0f / (h + 0.08f);
        float ax = d.x * k * 2.0f, az = d.z * k * 2.0f;
        float n = fbm3(ax * 0.35f + ftime * 0.03f, az * 0.35f, ftime * 0.05f);
        float band = expf(-powf((az * 0.25f + n * 2.6f - 1.3f) * 2.2f, 2));
        float band2 = expf(-powf((az * 0.18f - ax * 0.05f + n * 2.0f + 0.4f) * 2.8f, 2));
        float stripes = 0.6f + 0.4f * vnoise3(ax * 3.0f + ftime * 0.2f, az * 0.3f, 0);
        float fadeh = smooth(0.03f, 0.25f, h) * (1 - smooth(0.6f, 1.0f, h));
        v3 g = lerp3(V(0.1f, 1.0f, 0.5f), V(0.6f, 0.2f, 1.0f), smooth(0.2f, 0.7f, h));
        c = add(c, mul(g, (band + band2 * 0.7f) * stripes * fadeh * auroraAmt * 0.9f));
    }
    if (moonSize > 0) {
        float md = dot(d, moonDir);
        float cosr = cosf(moonSize);
        if (md > cosr) {
            float crater = 0.85f + 0.15f * vnoise3(d.x * 300, d.y * 300, d.z * 300);
            c = add(mul(c, 0.1f), mul(moonCol, crater));
        }
        float ang = acosf(clampf(md, -1, 1));
        c = add(c, mul(moonCol, 0.12f * expf(-ang * ang * 60.0f) + 0.03f * expf(-ang * 8.0f)));
    }
    return c;
}

// ---------------------------------------------------------------- shading
typedef struct { v3 col; float t; uint32_t id; } Sample;

static v3 apply_fog(v3 c, v3 o, v3 d, float t) {
    if (fogDen <= 0) return c;
    float f = 1.0f - expf(-fogDen * t);
    // reduce fog high up
    float hy = o.y + d.y * t * 0.5f;
    f *= clampf(1.25f - (hy - planeY) * 0.006f, 0.35f, 1.0f);
    return lerp3(c, fogCol, clampf(f, 0, 1));
}

static v3 shade_hit(v3 o, v3 d, Hit *h, int depth, uint32_t *idOut, int *shadowBitOut);

static v3 trace_color_px(v3 o, v3 d, int depth, float *tout, uint32_t *idOut, const float *pix) {
    d = fixdir(d);
    Hit h;
    if (trace_scene_px(o, d, 1000.0f, &h, 0, pix)) {
        int sb = 0;
        v3 c = shade_hit(o, d, &h, depth, idOut, &sb);
        if (tout) *tout = h.t;
        return apply_fog(c, o, d, h.t);
    }
    if (tout) *tout = 1e9f;
    if (idOut) *idOut = 0xffffffffu;
    return sky(d);
}

static v3 trace_color(v3 o, v3 d, int depth, float *tout, uint32_t *idOut) { return trace_color_px(o, d, depth, tout, idOut, NULL); }

static v3 shade_hit(v3 o, v3 d, Hit *h, int depth, uint32_t *idOut, int *shadowBitOut) {
    v3 P = add(o, mul(d, h->t));
    v3 N; v3 albedo; v3 emis = V(0, 0, 0); float refl = 0; float rough = 1; float ao = 1;
    float fu, fv;
    // face uv in grid space
    v3 lp = h->lp;
    int ax = h->axis;
    if (ax == 0) { fu = fracf(lp.z); fv = fracf(lp.y); }
    else if (ax == 1) { fu = fracf(lp.x); fv = fracf(lp.z); }
    else { fu = fracf(lp.x); fv = fracf(lp.y); }
    fu = clampf(fu, 0, 0.9999f); fv = clampf(fv, 0, 0.9999f);
    if (h->inst >= 0) {
        Inst *I = &inst[h->inst];
        Model *M = &models[I->model];
        v3 nl = V(ax == 0 ? (float)h->sign : 0, ax == 1 ? (float)h->sign : 0, ax == 2 ? (float)h->sign : 0);
        N = norm(inst_to_world_d(I, nl));
        int v = h->val;
        float n1 = hashf(h->cx, h->cy, h->cz * 31 + I->model);
        albedo = mulv(mul(M->pal[v], 0.93f + 0.14f * n1), I->tint);
        emis = mul(M->pal[v], M->palEmit[v] * I->emitMul);
        refl = M->palRefl[v];
        rough = refl > 0 ? 0 : 1;
        ao = face_ao(&M->g, h->cx, h->cy, h->cz, ax, h->sign, ax == 0 ? fu : fu, fv);
        if (idOut) { int pc = ax == 0 ? h->cx : (ax == 1 ? h->cy : h->cz); *idOut = 0x80000000u | ((uint32_t)h->inst << 20) | (hash3i(pc, v, ax) & 0xffff0u) | (uint32_t)(ax * 2 + (h->sign > 0)); }
    } else {
        N = V(ax == 0 ? (float)h->sign : 0, ax == 1 ? (float)h->sign : 0, ax == 2 ? (float)h->sign : 0);
        int m = h->val;
        float u = fu, vv = fv;
        if (ax != 1) vv = 1.0f - fv; // texture v goes downward on sides
        if (ax == 0 && h->sign < 0) u = 1 - u;
        if (ax == 2 && h->sign > 0) u = 1 - u;
        float emw;
        albedo = texture(m, h->cx, h->cy, h->cz, ax, h->sign, u, vv, &emw, &rough);
        emis = mul(mats[m].emit, emw * mats[m].emitScale);
        refl = mats[m].refl * (rough < 0.5f ? 1.0f : 0.3f);
        if (h->inst == -1) ao = face_ao(&world, h->cx, h->cy, h->cz, ax, h->sign, fu, fv);
        if (idOut) { int pc = ax == 0 ? h->cx : (ax == 1 ? h->cy : h->cz); *idOut = (hash3i(pc, m, ax * 2 + (h->sign > 0)) & 0x7ffffff0u) | (uint32_t)(ax * 2 + (h->sign > 0)); }
    }
    v3 Pn = add(P, mul(N, 0.002f));
    // sun / moon
    v3 light = V(0, 0, 0);
    float ndl = dot(N, sunDir);
    int sh = 0;
    if (ndl > 0 && (sunCol.x + sunCol.y + sunCol.z) > 0.001f) {
        if (!occluded(Pn, fixdir(sunDir), 300.0f)) light = add(light, mul(sunCol, ndl));
        else sh = 1;
    }
    if (shadowBitOut) *shadowBitOut = sh;
    if (idOut && sh) *idOut ^= 0x8u;
    // ambient hemisphere
    float hemi = 0.55f + 0.45f * N.y;
    light = add(light, mul(ambCol, hemi * ao));
    // point lights
    if (nlights > 0) {
        int gx = (int)floorf(P.x / LGC), gy = (int)floorf(P.y / LGC), gz = (int)floorf(P.z / LGC);
        if (gx < 0) gx = 0; if (gy < 0) gy = 0; if (gz < 0) gz = 0;
        if (gx >= lgW) gx = lgW - 1; if (gy >= lgH) gy = lgH - 1; if (gz >= lgD) gz = lgD - 1;
        int c = (gy * lgD + gz) * lgW + gx;
        int nshadow = 0;
        for (int k = 0; k < lgCount[c]; k++) {
            Light *L = &lights[lgIdx[c * LGMAX + k]];
            v3 Ld = sub(L->p, P);
            float d2 = dot(Ld, Ld);
            if (d2 > L->r * L->r) continue;
            float dl = sqrtf(d2);
            v3 l = mul(Ld, 1.0f / (dl + 1e-6f));
            float nl = dot(N, l);
            if (nl <= 0) continue;
            float x = dl / L->r; float win = (1 - x * x); win *= win;
            float att = win / (1.0f + d2 * 0.25f);
            v3 contrib = mul(L->c, att * nl);
            float mag = contrib.x + contrib.y + contrib.z;
            if (mag < 0.003f) continue;
            if (L->shadow && depth == 0 && nshadow < 4) {
                nshadow++;
                if (occluded(Pn, fixdir(l), dl - 0.35f)) continue;
            }
            light = add(light, contrib);
        }
    }
    v3 col = add(mulv(albedo, light), emis);
    // reflections
    if (refl > 0.001f && depth < 1) {
        float cosi = clampf(-dot(d, N), 0, 1);
        float fres = refl + (1 - refl) * powf(1 - cosi, 5) * 0.6f;
        fres = clampf(fres, 0, 1);
        v3 r = sub(d, mul(N, 2 * dot(d, N)));
        float rt;
        v3 rc = trace_color(Pn, r, depth + 1, &rt, NULL);
        col = lerp3(col, rc, fres);
    }
    return col;
}

// ---------------------------------------------------------------- camera
static v3 cF, cR, cU; static float cTan;
static void setup_camera(void) {
    cF = norm(sub(camT, camP));
    v3 up = V(sinf(camRoll), cosf(camRoll), 0);
    cR = norm(cross(cF, up));
    cU = cross(cR, cF);
    cTan = tanf(camFov * 0.5f * 3.14159265f / 180.0f);
}
static inline v3 cam_ray(float px, float py) {
    float aspect = (float)W / H;
    float sx = (2 * px / W - 1) * cTan * aspect;
    float sy = (1 - 2 * py / H) * cTan;
    return norm(add(cF, add(mul(cR, sx), mul(cU, sy))));
}
static int project(v3 p, float *sx, float *sy, float *depth) {
    v3 q = sub(p, camP);
    float z = dot(q, cF);
    if (z < 0.05f) return 0;
    float aspect = (float)W / H;
    float x = dot(q, cR) / (z * cTan * aspect), y = dot(q, cU) / (z * cTan);
    *sx = (x + 1) * 0.5f * W; *sy = (1 - y) * 0.5f * H; *depth = len(q);
    return 1;
}

// ---------------------------------------------------------------- frame buffers
static v3 *fb = NULL, *tmpb = NULL;
static float *zb = NULL;
static uint32_t *idb = NULL;
static uint8_t *out8 = NULL;
static v3 *bl[4]; static v3 *blt[4]; static int blw[4], blh[4];

static void alloc_buffers(void) {
    fb = malloc(sizeof(v3) * W * H); tmpb = malloc(sizeof(v3) * W * H);
    zb = malloc(sizeof(float) * W * H); idb = malloc(sizeof(uint32_t) * W * H);
    out8 = malloc(W * H * 3);
    int w = W / 2, h = H / 2;
    for (int i = 0; i < 4; i++) { blw[i] = w; blh[i] = h; bl[i] = calloc(w * h, sizeof(v3)); blt[i] = calloc(w * h, sizeof(v3)); w /= 2; h /= 2; }
}

static void blur(v3 *b, v3 *t, int w, int h) {
    static const float k[7] = {0.0702f, 0.1311f, 0.1907f, 0.2161f, 0.1907f, 0.1311f, 0.0702f};
    #pragma omp parallel for
    for (int y = 0; y < h; y++) for (int x = 0; x < w; x++) {
        v3 s = V(0, 0, 0);
        for (int i = -3; i <= 3; i++) { int xx = x + i * 1; if (xx < 0) xx = 0; if (xx >= w) xx = w - 1; s = add(s, mul(b[y * w + xx], k[i + 3])); }
        t[y * w + x] = s;
    }
    #pragma omp parallel for
    for (int y = 0; y < h; y++) for (int x = 0; x < w; x++) {
        v3 s = V(0, 0, 0);
        for (int i = -3; i <= 3; i++) { int yy = y + i * 1; if (yy < 0) yy = 0; if (yy >= h) yy = h - 1; s = add(s, mul(t[yy * w + x], k[i + 3])); }
        b[y * w + x] = s;
    }
}

static inline v3 aces(v3 x) {
    const float a = 2.51f, b = 0.03f, c = 2.43f, d = 0.59f, e = 0.14f;
    #define AC(v) clampf((v * (a * v + b)) / (v * (c * v + d) + e), 0, 1)
    return V(AC(x.x), AC(x.y), AC(x.z));
    #undef AC
}

static void render_frame(void) {
    double tstart = omp_get_wtime();
    setup_camera();
    build_light_grid();
    for (int i = 0; i < ninst; i++) {
        Inst *I = &inst[i];
        inst_bounds(I);
        float x0 = 1e30f, y0 = 1e30f, x1 = -1e30f, y1 = -1e30f; int behind = 0;
        for (int c = 0; c < 8; c++) {
            v3 p = V((c & 1) ? I->bmax.x : I->bmin.x, (c & 2) ? I->bmax.y : I->bmin.y, (c & 4) ? I->bmax.z : I->bmin.z);
            float sx, sy, dz;
            if (!project(p, &sx, &sy, &dz)) { behind = 1; break; }
            x0 = minf(x0, sx); y0 = minf(y0, sy); x1 = maxf(x1, sx); y1 = maxf(y1, sy);
        }
        if (behind) { I->sx0 = -1e30f; I->sy0 = -1e30f; I->sx1 = 1e30f; I->sy1 = 1e30f; }
        else { I->sx0 = x0 - 3; I->sy0 = y0 - 3; I->sx1 = x1 + 3; I->sy1 = y1 + 3; }
    }
    // pass 1: one sample per pixel
    #pragma omp parallel for schedule(dynamic, 2)
    for (int y = 0; y < H; y++) {
        for (int x = 0; x < W; x++) {
            float t; uint32_t id = 0;
            float px[2] = {x + 0.5f, y + 0.5f};
            v3 c = trace_color_px(camP, cam_ray(px[0], px[1]), 0, &t, &id, px);
            fb[y * W + x] = c; zb[y * W + x] = t; idb[y * W + x] = id;
        }
    }
    double tp1 = omp_get_wtime();
    // pass 2: adaptive AA on edges
    static const float off[4][2] = {{0.125f, 0.375f}, {0.625f, 0.125f}, {0.875f, 0.625f}, {0.375f, 0.875f}};
    #pragma omp parallel for schedule(dynamic, 2)
    for (int y = 0; y < H; y++) {
        for (int x = 0; x < W; x++) {
            uint32_t id = idb[y * W + x];
            int edge = 0;
            if (x > 0 && idb[y * W + x - 1] != id) edge = 1;
            else if (x < W - 1 && idb[y * W + x + 1] != id) edge = 1;
            else if (y > 0 && idb[(y - 1) * W + x] != id) edge = 1;
            else if (y < H - 1 && idb[(y + 1) * W + x] != id) edge = 1;
            if (!edge) {
                // luminance contrast check (catches texture/light discontinuities)
                v3 c = fb[y * W + x]; float l = c.x + c.y + c.z;
                if (x < W - 1) { v3 c2 = fb[y * W + x + 1]; float l2 = c2.x + c2.y + c2.z; if (fabsf(l - l2) > 1.0f * (minf(l, l2) + 0.2f)) edge = 1; }
                if (!edge && y < H - 1) { v3 c2 = fb[(y + 1) * W + x]; float l2 = c2.x + c2.y + c2.z; if (fabsf(l - l2) > 1.0f * (minf(l, l2) + 0.2f)) edge = 1; }
            }
            if (edge) {
                v3 s = fb[y * W + x];
                for (int k = 0; k < 4; k++) { float px[2] = {x + off[k][0], y + off[k][1]}; s = add(s, trace_color_px(camP, cam_ray(px[0], px[1]), 0, NULL, NULL, px)); }
                tmpb[y * W + x] = mul(s, 0.2f);
            } else tmpb[y * W + x] = fb[y * W + x];
        }
    }
    v3 *sw = fb; fb = tmpb; tmpb = sw;
    double tp2 = omp_get_wtime();

    // glows (depth tested, soft)
    for (int g = 0; g < nglows; g++) {
        Glow *G = &glows[g];
        float sx, sy, dz;
        if (!project(G->p, &sx, &sy, &dz)) continue;
        float rpx = G->size / (dz * cTan) * H * 0.5f;
        float rad = rpx * 7.0f;
        if (rad < 1) rad = 1;
        if (rad > 900) rad = 900;
        int x0 = (int)(sx - rad), x1 = (int)(sx + rad), y0 = (int)(sy - rad), y1 = (int)(sy + rad);
        if (x0 < 0) x0 = 0; if (y0 < 0) y0 = 0; if (x1 >= W) x1 = W - 1; if (y1 >= H) y1 = H - 1;
        float inv = 1.0f / (rpx * rpx + 0.5f);
        #pragma omp parallel for
        for (int y = y0; y <= y1; y++) for (int x = x0; x <= x1; x++) {
            float dx = x + 0.5f - sx, dy = y + 0.5f - sy;
            float r2 = (dx * dx + dy * dy) * inv;
            float zz = zb[y * W + x];
            float vis = zz > dz - G->size * 1.5f ? 1.0f : 0.0f;
            if (vis <= 0) continue;
            float k = expf(-r2 * 1.2f) + 0.06f * expf(-r2 * 0.12f);
            fb[y * W + x] = add(fb[y * W + x], mul(G->c, k));
        }
    }
    // beams (screen space capsules)
    for (int b = 0; b < nbeams; b++) {
        Beam *B = &beams[b];
        float ax, ay, az, bx, by, bz;
        if (!project(B->a, &ax, &ay, &az) || !project(B->b, &bx, &by, &bz)) continue;
        float rpx = B->w / (0.5f * (az + bz) * cTan) * H * 0.5f; if (rpx < 0.8f) rpx = 0.8f;
        float rad = rpx * 6;
        int x0 = (int)(minf(ax, bx) - rad), x1 = (int)(maxf(ax, bx) + rad), y0 = (int)(minf(ay, by) - rad), y1 = (int)(maxf(ay, by) + rad);
        if (x0 < 0) x0 = 0; if (y0 < 0) y0 = 0; if (x1 >= W) x1 = W - 1; if (y1 >= H) y1 = H - 1;
        float vx = bx - ax, vy = by - ay; float vl2 = vx * vx + vy * vy + 1e-6f;
        #pragma omp parallel for
        for (int y = y0; y <= y1; y++) for (int x = x0; x <= x1; x++) {
            float px = x + 0.5f - ax, py = y + 0.5f - ay;
            float tt = clampf((px * vx + py * vy) / vl2, 0, 1);
            float dx = px - vx * tt, dy = py - vy * tt;
            float r2 = (dx * dx + dy * dy) / (rpx * rpx);
            float dep = az + (bz - az) * tt;
            if (zb[y * W + x] < dep - 1.0f) continue;
            float k = expf(-r2 * 1.5f) * 1.0f + 0.15f * expf(-r2 * 0.15f);
            fb[y * W + x] = add(fb[y * W + x], mul(B->c, k));
        }
    }
    // particles (row bands so no two threads write the same pixel)
    {
        const int NB = 64;
        #pragma omp parallel for schedule(dynamic, 1)
        for (int band = 0; band < NB; band++) {
            int by0 = band * H / NB, by1 = (band + 1) * H / NB - 1;
            for (int i = 0; i < nparts; i++) {
                Part *Pp = &parts[i];
                float sx, sy, dz;
                if (!project(Pp->p, &sx, &sy, &dz)) continue;
                if (dz < 2.0f) continue;
                float rpx = Pp->size / (dz * cTan) * H * 0.5f;
                float near = clampf((dz - 2.0f) / 3.0f, 0, 1);
                if (rpx < 0.6f) rpx = 0.6f;
                if (rpx > 14) rpx = 14;
                float rad = rpx * (Pp->type ? 2.5f : 1.3f);
                int x0 = (int)(sx - rad), x1 = (int)(sx + rad), y0 = (int)(sy - rad), y1 = (int)(sy + rad);
                if (y0 < by0) y0 = by0; if (y1 > by1) y1 = by1;
                if (x1 < 0 || y1 < y0 || x0 >= W) continue;
                if (x0 < 0) x0 = 0; if (x1 >= W) x1 = W - 1;
                float inv = 1.0f / (rpx * rpx);
                for (int y = y0; y <= y1; y++) for (int x = x0; x <= x1; x++) {
                    if (zb[y * W + x] < dz) continue;
                    float dx = x + 0.5f - sx, dy = y + 0.5f - sy;
                    float r2 = (dx * dx + dy * dy) * inv;
                    v3 *pix = &fb[y * W + x];
                    if (Pp->type == 0) {
                        float a = Pp->a * near * clampf(1.3f - r2, 0, 1);
                        if (a <= 0) continue;
                        *pix = lerp3(*pix, Pp->c, a);
                    } else {
                        float k = expf(-r2 * 1.5f) * Pp->a * near;
                        *pix = add(*pix, mul(Pp->c, k));
                    }
                }
            }
        }
    }
    // bloom
    {
        int w = blw[0], h = blh[0];
        #pragma omp parallel for
        for (int y = 0; y < h; y++) for (int x = 0; x < w; x++) {
            v3 s = V(0, 0, 0);
            for (int j = 0; j < 2; j++) for (int i = 0; i < 2; i++) {
                v3 c = fb[(y * 2 + j) * W + x * 2 + i];
                float l = maxf(c.x, maxf(c.y, c.z));
                float k = l > bloomThr ? (l - bloomThr) / l : 0;
                s = add(s, mul(c, k * 0.25f));
            }
            bl[0][y * w + x] = s;
        }
        for (int lv = 1; lv < 4; lv++) {
            int w2 = blw[lv], h2 = blh[lv], wp = blw[lv - 1];
            #pragma omp parallel for
            for (int y = 0; y < h2; y++) for (int x = 0; x < w2; x++) {
                v3 s = add(add(bl[lv - 1][(y * 2) * wp + x * 2], bl[lv - 1][(y * 2) * wp + x * 2 + 1]), add(bl[lv - 1][(y * 2 + 1) * wp + x * 2], bl[lv - 1][(y * 2 + 1) * wp + x * 2 + 1]));
                bl[lv][y * w2 + x] = mul(s, 0.25f);
            }
        }
        for (int lv = 0; lv < 4; lv++) { blur(bl[lv], blt[lv], blw[lv], blh[lv]); blur(bl[lv], blt[lv], blw[lv], blh[lv]); }
    }
    // composite + tonemap
    #pragma omp parallel for
    for (int y = 0; y < H; y++) {
        for (int x = 0; x < W; x++) {
            v3 c = fb[y * W + x];
            v3 b = V(0, 0, 0);
            static const float wl[4] = {0.5f, 0.8f, 1.0f, 1.2f};
            for (int lv = 0; lv < 4; lv++) {
                // bilinear sample
                float fx = (x + 0.5f) / W * blw[lv] - 0.5f, fy = (y + 0.5f) / H * blh[lv] - 0.5f;
                int x0 = (int)floorf(fx), y0 = (int)floorf(fy); float tx = fx - x0, ty = fy - y0;
                int x1 = x0 + 1, y1 = y0 + 1;
                if (x0 < 0) x0 = 0; if (y0 < 0) y0 = 0; if (x1 >= blw[lv]) x1 = blw[lv] - 1; if (y1 >= blh[lv]) y1 = blh[lv] - 1; if (x0 >= blw[lv]) x0 = blw[lv] - 1; if (y0 >= blh[lv]) y0 = blh[lv] - 1;
                v3 *B = bl[lv]; int bw = blw[lv];
                v3 s = lerp3(lerp3(B[y0 * bw + x0], B[y0 * bw + x1], tx), lerp3(B[y1 * bw + x0], B[y1 * bw + x1], tx), ty);
                b = add(b, mul(s, wl[lv]));
            }
            c = add(c, mul(b, bloomStr));
            c = mulv(mul(c, exposure), gradeTint);
            c = aces(c);
            // saturation / contrast in display space
            float l = 0.2126f * c.x + 0.7152f * c.y + 0.0722f * c.z;
            c = lerp3(V(l, l, l), c, saturation);
            c = V(powf(clampf(c.x, 0, 1), 1 / 2.2f), powf(clampf(c.y, 0, 1), 1 / 2.2f), powf(clampf(c.z, 0, 1), 1 / 2.2f));
            c = add(mul(sub(c, V(0.5f, 0.5f, 0.5f)), contrast), V(0.5f, 0.5f, 0.5f));
            float vx = (x + 0.5f) / W - 0.5f, vy = (y + 0.5f) / H - 0.5f;
            float vig = 1.0f - vignette * (vx * vx * 1.2f + vy * vy * 1.6f) * 2.2f;
            c = mul(c, vig * (1 - fade));
            float dith = (hashf(x, y, frameNo & 63) - 0.5f) / 255.0f;
            int r = (int)(clampf(c.x + dith, 0, 1) * 255 + 0.5f), g = (int)(clampf(c.y + dith, 0, 1) * 255 + 0.5f), bb = (int)(clampf(c.z + dith, 0, 1) * 255 + 0.5f);
            uint8_t *o = &out8[(y * W + x) * 3]; o[0] = r; o[1] = g; o[2] = bb;
        }
    }
    if (getenv("VOXRT_PROFILE")) fprintf(stderr, "pass1 %.3f pass2 %.3f post %.3f\n", tp1 - tstart, tp2 - tp1, omp_get_wtime() - tp2);
    fwrite(out8, 1, W * H * 3, stdout);
    fflush(stdout);
    frameNo++;
}

// ---------------------------------------------------------------- loading
static int load_grid_file(const char *path, Grid *g, int withDist) {
    FILE *f = fopen(path, "rb");
    if (!f) { fprintf(stderr, "cannot open %s\n", path); return 0; }
    int dims[3];
    if (fread(dims, 4, 3, f) != 3) { fclose(f); return 0; }
    g->w = dims[0]; g->h = dims[1]; g->d = dims[2];
    size_t n = (size_t)g->w * g->h * g->d;
    free(g->v); g->v = malloc(n);
    if (fread(g->v, 1, n, f) != n) { fclose(f); return 0; }
    fclose(f);
    free(g->dist); g->dist = NULL;
    if (withDist) build_dist(g);
    return 1;
}

static v3 srgb2lin(float r, float g, float b) { return V(powf(r / 255.f, 2.2f), powf(g / 255.f, 2.2f), powf(b / 255.f, 2.2f)); }

int main(int argc, char **argv) {
    if (argc >= 3) { W = atoi(argv[1]); H = atoi(argv[2]); }
    alloc_buffers();
    static char line[4096];
    for (int i = 0; i < 256; i++) { mats[i].c1 = V(1, 0, 1); mats[i].emitScale = 1; }
    while (fgets(line, sizeof line, stdin)) {
        char cmd[32];
        if (sscanf(line, "%31s", cmd) != 1) continue;
        if (!strcmp(cmd, "MAT")) {
            int id, pat; float r, g, b, r2, g2, b2, er, eg, eb, rf;
            sscanf(line + 4, "%d %f %f %f %f %f %f %d %f %f %f %f", &id, &r, &g, &b, &r2, &g2, &b2, &pat, &er, &eg, &eb, &rf);
            mats[id].c1 = srgb2lin(r, g, b); mats[id].c2 = srgb2lin(r2, g2, b2); mats[id].pattern = pat;
            mats[id].emit = V(er, eg, eb); mats[id].refl = rf; mats[id].emitScale = 1;
        } else if (!strcmp(cmd, "WORLD")) {
            char path[1024]; sscanf(line + 6, "%1023s", path);
            load_grid_file(path, &world, 1);
            fprintf(stderr, "world %dx%dx%d loaded\n", world.w, world.h, world.d);
        } else if (!strcmp(cmd, "SET")) { // SET x y z v  (no dist rebuild; call REDIST after)
            int x, y, z, v; sscanf(line + 4, "%d %d %d %d", &x, &y, &z, &v);
            if (x >= 0 && y >= 0 && z >= 0 && x < world.w && y < world.h && z < world.d) world.v[gidx(&world, x, y, z)] = v;
        } else if (!strcmp(cmd, "REDIST")) {
            build_dist(&world);
        } else if (!strcmp(cmd, "MODEL")) {
            int id; char path[1024];
            sscanf(line + 6, "%d %1023s", &id, path);
            Model *M = &models[id];
            FILE *f = fopen(path, "rb");
            if (!f) { fprintf(stderr, "no model %s\n", path); continue; }
            int dims[3]; float piv[3]; int npal;
            if (fread(dims, 4, 3, f) != 3 || fread(piv, 4, 3, f) != 3 || fread(&npal, 4, 1, f) != 1) { fclose(f); continue; }
            for (int i = 0; i < npal; i++) {
                float e[6]; if (fread(e, 4, 6, f) != 6) break;
                M->pal[i] = srgb2lin(e[0], e[1], e[2]); M->palEmit[i] = e[3]; M->palRefl[i] = e[4];
            }
            M->g.w = dims[0]; M->g.h = dims[1]; M->g.d = dims[2];
            size_t n = (size_t)dims[0] * dims[1] * dims[2];
            free(M->g.v); M->g.v = malloc(n); if (fread(M->g.v, 1, n, f) != n) fprintf(stderr, "short model\n"); fclose(f);
            M->g.dist = NULL;
            M->pivot = V(piv[0], piv[1], piv[2]);
        } else if (!strcmp(cmd, "FRAME")) {
            ninst = 0; nlights = 0; nglows = 0; nbeams = 0; nparts = 0; camClip = 0;
            for (int i = 0; i < 256; i++) mats[i].emitScale = 1;
        } else if (!strcmp(cmd, "CAM")) {
            sscanf(line + 4, "%f %f %f %f %f %f %f %f", &camP.x, &camP.y, &camP.z, &camT.x, &camT.y, &camT.z, &camFov, &camRoll);
        } else if (!strcmp(cmd, "CLIP")) {
            sscanf(line + 5, "%f", &camClip);
        } else if (!strcmp(cmd, "SUN")) {
            sscanf(line + 4, "%f %f %f %f %f %f", &sunDir.x, &sunDir.y, &sunDir.z, &sunCol.x, &sunCol.y, &sunCol.z);
            sunDir = norm(sunDir);
        } else if (!strcmp(cmd, "SKY")) {
            sscanf(line + 4, "%f %f %f %f %f %f %f %f %f %f %f %f %f %f %f %f", &skyZen.x, &skyZen.y, &skyZen.z, &skyHor.x, &skyHor.y, &skyHor.z,
                   &starAmt, &auroraAmt, &moonDir.x, &moonDir.y, &moonDir.z, &moonSize, &moonCol.x, &moonCol.y, &moonCol.z, &ftime);
            moonDir = norm(moonDir);
        } else if (!strcmp(cmd, "AMB")) {
            sscanf(line + 4, "%f %f %f", &ambCol.x, &ambCol.y, &ambCol.z);
        } else if (!strcmp(cmd, "FOG")) {
            sscanf(line + 4, "%f %f %f %f", &fogCol.x, &fogCol.y, &fogCol.z, &fogDen);
        } else if (!strcmp(cmd, "PLANE")) {
            sscanf(line + 6, "%d %f %d", &planeOn, &planeY, &planeMat);
        } else if (!strcmp(cmd, "EMIT")) {
            int id; float s; sscanf(line + 5, "%d %f", &id, &s); mats[id].emitScale = s;
        } else if (!strcmp(cmd, "GRADE")) {
            sscanf(line + 6, "%f %f %f %f %f %f %f %f %f %f", &exposure, &saturation, &contrast, &gradeTint.x, &gradeTint.y, &gradeTint.z, &vignette, &fade, &bloomStr, &bloomThr);
        } else if (!strcmp(cmd, "I")) {
            if (ninst >= MAXINST) continue;
            Inst *I = &inst[ninst];
            int sh;
            int n = sscanf(line + 2, "%d %f %f %f %f %f %f %f %f %f %f %f %f %f %d %f %f %f %f", &I->model, &I->pos.x, &I->pos.y, &I->pos.z,
                   &I->R[0], &I->R[1], &I->R[2], &I->R[3], &I->R[4], &I->R[5], &I->R[6], &I->R[7], &I->R[8], &I->scale, &sh, &I->emitMul, &I->tint.x, &I->tint.y, &I->tint.z);
            if (n < 19) continue;
            I->shadow = sh;
            if (I->scale <= 0) continue;
            ninst++;
        } else if (!strcmp(cmd, "L")) {
            if (nlights >= MAXLIGHTS) continue;
            Light *L = &lights[nlights];
            sscanf(line + 2, "%f %f %f %f %f %f %f %d", &L->p.x, &L->p.y, &L->p.z, &L->c.x, &L->c.y, &L->c.z, &L->r, &L->shadow);
            nlights++;
        } else if (!strcmp(cmd, "G")) {
            if (nglows >= MAXGLOWS) continue;
            Glow *G = &glows[nglows];
            sscanf(line + 2, "%f %f %f %f %f %f %f", &G->p.x, &G->p.y, &G->p.z, &G->c.x, &G->c.y, &G->c.z, &G->size);
            nglows++;
        } else if (!strcmp(cmd, "B")) {
            if (nbeams >= MAXBEAMS) continue;
            Beam *B = &beams[nbeams];
            sscanf(line + 2, "%f %f %f %f %f %f %f %f %f %f", &B->a.x, &B->a.y, &B->a.z, &B->b.x, &B->b.y, &B->b.z, &B->c.x, &B->c.y, &B->c.z, &B->w);
            nbeams++;
        } else if (!strcmp(cmd, "PARTS")) {
            // binary block follows: n * 9 floats (x y z size r g b a type)
            int n; sscanf(line + 6, "%d", &n);
            if (n > capparts) { capparts = n; parts = realloc(parts, sizeof(Part) * capparts); }
            float *buf = malloc(sizeof(float) * 9 * (n > 0 ? n : 1));
            if (n > 0 && fread(buf, sizeof(float) * 9, n, stdin) != (size_t)n) { free(buf); break; }
            for (int i = 0; i < n; i++) {
                float *e = buf + i * 9;
                parts[i].p = V(e[0], e[1], e[2]); parts[i].size = e[3]; parts[i].c = V(e[4], e[5], e[6]); parts[i].a = e[7]; parts[i].type = (int)e[8];
            }
            nparts = n; free(buf);
        } else if (!strcmp(cmd, "RENDER")) {
            render_frame();
        } else if (!strcmp(cmd, "QUIT")) break;
    }
    return 0;
}
