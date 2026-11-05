/**
 * BioOS Figure 2 — Plane A SSR Virtual Fixture Trip (<2 ms lockout)
 * ============================================================
 * Object: A solid-state relay (SSR) panel mounted on a bench rail.
 *   - Heavy aluminium base plate with ruler ticks
 *   - A vertical SSR block (the relay housing)
 *   - A pivot arm that "trips" when the margin drops below 0.80 mm
 *   - An LVDT distance ruler on the left post, with threshold marker
 *   - A red "TRIP" indicator lamp and a green "ARMED" lamp
 *   - A digital readout showing 0.81 ms trip time
 *
 * Concept: When Meta SAM 3.1 detects the robotic tool within 0.80 mm
 * of the hepatic artery, Plane A fires this SSR, cutting motor power
 * in <2 ms — 10× faster than any mechanical relay.
 *
 * Run:  node web/figures/ssr-trip/build.mjs [--light]
 * Out:  web/figures/ssr-trip/ssr-trip.html
 */

import { writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as k from '../../../anatomy/kit/iso-kit.mjs';
import { kitScript } from '../../../anatomy/scripts/inline-kit.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const theme = process.argv.includes('--light') ? 'light' : 'dark';

const W = 720, H = 480;

// ── World geometry ─────────────────────────────────────────────────────────
// Base plate (heavy aluminium bench plate)
const BASE      = { x: -180, y: -90, w: 360, d: 180, r: 8 };
const BASE_H    = 14;
const FOOT_H    = 7;

// Left post (holds LVDT ruler)
const POST_L    = [-148, -60]; // [x, y] floor
const POST_R    = 8;
const POST_H    = 190;

// LVDT ruler strip (attached to left post)
const RULER     = { x: -158, y: -55, w: 18, d: 140, r: 2 };
const RULER_Z   = BASE_H + FOOT_H;
const RULER_H   = 2;

// Threshold marker bar on ruler (0.80 mm boundary)
const THRESH_Z  = BASE_H + FOOT_H + 68; // position on ruler height

// SSR block (the main relay housing) - centre of plate
const SSR       = { x: -28, y: -44, w: 56, d: 88, r: 4 };
const SSR_Z     = BASE_H + FOOT_H;
const SSR_H     = 110;

// Pivot arm – horizontal bar that swings when tripped
const ARM_PIVOT = [-28 + 28, -44 + 20]; // pivot point on SSR top face
const ARM_LEN   = 100;
const ARM_W     = 8;
const ARM_H     = 10;
const ARM_Z     = SSR_Z + SSR_H;         // rests on top of SSR

// Lamps (indicator LEDs on SSR front face)
const LAMP_ARMED = [-28 + 14, -44 + 60];  // green
const LAMP_TRIP  = [-28 + 38, -44 + 60];  // red

// Right post (output terminal strip)
const POST_R_P  = [130, -60];
const POST_RR   = 8;
const POST_RH   = 160;

// Terminal strip on right post
const TERMINAL  = { x: 118, y: -55, w: 36, d: 100, r: 2 };
const TERM_Z    = BASE_H + FOOT_H;
const TERM_H    = 20;

// Camera
const P = k.fitProjection(
  [
    [BASE.x - 20, BASE.y - 20, 0],
    [BASE.x + BASE.w + 20, BASE.y + BASE.d + 20, POST_H + 20],
  ],
  W, H,
  { pad: 44, azimuth: 44 }
);

// ── Helpers ─────────────────────────────────────────────────────────────────
const slab   = (rect, z0, h, tone) => k.solidSvg(k.slabOf(rect, z0, h, P, 8, 1.4), { tone });
const cyl    = (cx, cy, r, z0, h, tone, steps = 24) => k.solidSvg(k.cylinder(cx, cy, r, z0, h, P, steps), { tone });
const line   = (d, style) => k.lineSvg(d, style);
const dots   = (pts, style) => k.dotsSvg(pts, style);
const isoP   = (pt) => k.iso(pt, P);
const seg    = (a, b) => k.segment(a, b, P);
const riseAt = (at, z0, z1) => k.rise(at, z0, z1, P);

function byDepth(pts) {
  return [...pts].sort((a, b) => k.depthOf(a, P) - k.depthOf(b, P));
}

// ── Parts ───────────────────────────────────────────────────────────────────

function base() {
  const out = [];
  out.push(`<path class="iso-halo" d="${k.haloOf(BASE, 0, BASE_H + FOOT_H, P)}"/>`);

  // Rubber feet
  for (const [fx, fy] of k.corners(BASE, 18)) {
    out.push(cyl(fx, fy, 7.5, -FOOT_H, FOOT_H, 'lo', 20));
  }

  // Base plate
  out.push(slab(BASE, 0, BASE_H, 'lo'));

  // Ruler ticks along front edge of base (Y scale)
  const ticks = k.topTicks(
    BASE.y + 10, BASE.y + BASE.d - 10,
    4, 5, BASE.x + BASE.w - 15, BASE_H,
    [2, 4], P
  );
  out.push(line(ticks.minor, { tone: 'lo' }));
  out.push(line(ticks.major, { tone: 'mid' }));

  // Corner screws
  const screws = k.corners(BASE, 14);
  out.push(line(screws.map(([x, y]) => k.ring(x, y, 2.4, BASE_H, P, 16)).join(''), { tone: 'lo' }));
  out.push(dots(screws.map(([x, y]) => isoP([x, y, BASE_H])), { size: 0.55 }));

  // Label plate
  const lp = { x: BASE.x + 10, y: BASE.y + BASE.d - 20, w: 80, d: 11, r: 1 };
  out.push(slab(lp, BASE_H, 1.5, 'lo'));
  out.push(line(k.planOutline(k.insetPlan(lp, 2), BASE_H + 1.5, P), { tone: 'faint' }));

  // "PLANE A SAFETY KERNEL" engraved rule line simulation
  for (let i = 0; i < 3; i++) {
    out.push(line(
      k.lineOnTop([BASE.x + 14, BASE.y + BASE.d - 17 + i * 3],
                  [BASE.x + 86, BASE.y + BASE.d - 17 + i * 3], BASE_H + 1.6, P),
      { tone: 'faint' }
    ));
  }
  return out.join('');
}

function leftPost() {
  const out = [];
  const [px, py] = POST_L;
  // Post cylinder
  out.push(cyl(px, py, POST_R, BASE_H + FOOT_H, POST_H, 'mid', 24));
  // Top cap
  out.push(cyl(px, py, POST_R + 2, BASE_H + FOOT_H + POST_H - 4, 4, 'hi', 20));
  // Clamp ring at mid-height
  out.push(cyl(px, py, POST_R + 4, BASE_H + FOOT_H + 80, 8, 'mid', 20));
  out.push(cyl(px, py, POST_R + 2, BASE_H + FOOT_H + 80, 8, 'lo', 20));
  return out.join('');
}

function lvdtRuler() {
  const out = [];
  // Ruler strip body
  out.push(slab(RULER, RULER_Z, RULER_H, 'mid'));

  // Tick marks every 10 mm on the ruler (fine: every 5)
  const ticks = k.topTicks(
    RULER.y + 4, RULER.y + RULER.d - 4,
    5, 5, RULER.x + RULER.w, RULER_Z + RULER_H,
    [2.5, 5], P
  );
  out.push(line(ticks.minor, { tone: 'lo' }));
  out.push(line(ticks.major, { tone: 'mid' }));

  // Threshold marker — red dashed line at 0.80 mm boundary
  out.push(line(
    k.lineOnTop(
      [RULER.x - 30, RULER.y + 70],
      [RULER.x + RULER.w + 60, RULER.y + 70],
      THRESH_Z, P
    ),
    { stroke: '#ff1744', w: 2, dash: '6 3' }
  ));

  // Threshold dot
  out.push(dots([isoP([RULER.x + RULER.w + 30, RULER.y + 70, THRESH_Z])],
    { size: 3.5, fill: '#ff1744' }));

  // Distance pointer (current margin indicator — moving needle)
  const marginZ = RULER_Z + 92; // above threshold = safe
  out.push(cyl(RULER.x + RULER.w + 20, RULER.y + 60, 4, marginZ - 2, 4, 'hi', 16));
  out.push(line(
    k.lineOnTop(
      [RULER.x - 5, RULER.y + 60],
      [RULER.x + RULER.w + 24, RULER.y + 60],
      marginZ, P
    ),
    { stroke: '#00e5ff', w: 1.5 }
  ));

  return out.join('');
}

function ssrBlock() {
  const out = [];

  // Main SSR housing body — dark charcoal
  const ssrSlab = k.slabOf(SSR, SSR_Z, SSR_H, P, 5, 1.5);
  out.push(k.solidSvg(ssrSlab, { tone: 'mid' })
    .replace(/iso-fill[^"]*"/g, 'iso-fill" style="fill:#111820"')
    .replace(/iso-top[^"]*"/g,  'iso-top"  style="fill:#151f2a"')
  );

  // Heat-sink fins on back face (3 fins)
  for (let f = 0; f < 4; f++) {
    const fin = { x: SSR.x - 10, y: SSR.y + 10 + f * 18, w: 10, d: 12, r: 1 };
    out.push(slab(fin, SSR_Z + 10, SSR_H - 20, 'lo'));
  }

  // Front face panel (lighter face)
  const face = { x: SSR.x + 2, y: SSR.y + SSR.d - 3, w: SSR.w - 4, d: 3, r: 1 };
  out.push(slab(face, SSR_Z + 5, SSR_H - 10, 'mid'));

  // Green ARMED lamp (bottom)
  const [gx, gy] = LAMP_ARMED;
  out.push(cyl(gx, gy, 5, SSR_Z + SSR_H - 24, 6, 'hi', 20)
    .replace(/iso-fill[^"]*"/g, 'iso-fill" style="fill:#001a08"')
    .replace(/iso-top[^"]*"/g,  'iso-top"  style="fill:#00e676" filter="url(#glow-green)"')
  );
  out.push(cyl(gx, gy, 5.5, SSR_Z + SSR_H - 24, 6, 'lo', 20));

  // Red TRIP lamp (top — currently dim = not tripped)
  const [rx, ry] = LAMP_TRIP;
  out.push(cyl(rx, ry, 5, SSR_Z + SSR_H - 24, 6, 'hi', 20)
    .replace(/iso-fill[^"]*"/g, 'iso-fill" style="fill:#1a0004"')
    .replace(/iso-top[^"]*"/g,  'iso-top"  style="fill:#220006"')
  );
  out.push(cyl(rx, ry, 5.5, SSR_Z + SSR_H - 24, 6, 'lo', 20));

  // "SSR" label rule lines on front face
  for (let i = 0; i < 2; i++) {
    out.push(line(
      k.lineOnTop(
        [SSR.x + 6, SSR.y + SSR.d - 2 + i * 5],
        [SSR.x + SSR.w - 6, SSR.y + SSR.d - 2 + i * 5],
        SSR_Z + 55 + i * 6, P
      ),
      { tone: 'lo' }
    ));
  }

  // Input terminals top of SSR (3 screw terminals)
  for (let t = 0; t < 3; t++) {
    const tx = SSR.x + 10 + t * 14;
    out.push(cyl(tx, SSR.y + 10, 5, SSR_Z + SSR_H, 8, 'mid', 16));
    out.push(cyl(tx, SSR.y + 10, 2.5, SSR_Z + SSR_H + 2, 6, 'lo', 10));
    // Screw dot
    out.push(dots([isoP([tx, SSR.y + 10, SSR_Z + SSR_H + 8])], { size: 0.5 }));
  }

  return out.join('');
}

function pivotArm() {
  const out = [];
  const [ax, ay] = ARM_PIVOT;

  // Pivot pin
  out.push(cyl(ax, ay, 5, ARM_Z, 12, 'hi', 20));
  out.push(cyl(ax, ay, 3, ARM_Z + 2, 10, 'lo', 16));

  // Arm body (horizontal bar in ARMED position, nearly horizontal)
  const armRect = { x: ax, y: ay - ARM_W / 2, w: ARM_LEN, d: ARM_W, r: 2 };
  out.push(slab(armRect, ARM_Z + 2, ARM_H, 'mid'));

  // Spring at pivot base
  const spring = k.coil(ax - 6, ay, 6, 3, ARM_Z - 12, 12, 10, P);
  out.push(line(spring.back, { tone: 'lo' }));
  out.push(line(spring.front, { tone: 'mid' }));

  // End stop / contact on arm tip
  out.push(cyl(ax + ARM_LEN, ay, 7, ARM_Z, ARM_H + 4, 'hi', 20)
    .replace(/iso-fill[^"]*"/g, 'iso-fill" style="fill:#0d2010"')
    .replace(/iso-top[^"]*"/g,  'iso-top"  style="fill:#00e676" opacity="0.9"')
  );

  // Arm knurled grip
  out.push(cyl(ax + 20, ay, 4.5, ARM_Z + ARM_H, 6, 'mid', 16));
  out.push(dots([isoP([ax + 20, ay, ARM_Z + ARM_H + 6])], { size: 0.4 }));

  return out.join('');
}

function rightPost() {
  const out = [];
  const [px, py] = POST_R_P;
  out.push(cyl(px, py, POST_RR, BASE_H + FOOT_H, POST_RH, 'mid', 24));
  out.push(cyl(px, py, POST_RR + 2, BASE_H + FOOT_H + POST_RH - 4, 4, 'hi', 20));
  // Terminal strip
  out.push(slab(TERMINAL, TERM_Z, TERM_H, 'mid'));
  // Terminal screws
  for (let t = 0; t < 4; t++) {
    const ty = TERMINAL.y + 12 + t * 20;
    out.push(cyl(TERMINAL.x + TERMINAL.w - 8, ty, 4, TERM_Z + TERM_H, 6, 'mid', 12));
    out.push(dots([isoP([TERMINAL.x + TERMINAL.w - 8, ty, TERM_Z + TERM_H + 6])], { size: 0.45 }));
  }
  return out.join('');
}

function wiring() {
  const out = [];
  // Wire from SSR output terminal to right post terminal (screen-space points)
  const w1a = isoP([SSR.x + SSR.w - 6, SSR.y + 10, SSR_Z + SSR_H + 8]);
  const w1b = isoP([TERMINAL.x + TERMINAL.w - 8, TERMINAL.y + 12, TERM_Z + TERM_H + 6]);
  out.push(k.wireSvg(w1a, w1b, { tone: 'lo' }));

  // Wire from left-base power entry to SSR input terminal (red = power)
  const w2a = isoP([BASE.x + 20, BASE.y + 20, BASE_H + FOOT_H + 8]);
  const w2b = isoP([SSR.x + 10, SSR.y + 10, SSR_Z + SSR_H + 8]);
  out.push(k.wireSvg(w2a, w2b, { tone: 'red' }));

  // Control signal wire from left post to SSR (cyan — Plane A trigger)
  const w3a = isoP([POST_L[0], POST_L[1], BASE_H + FOOT_H + 60]);
  const w3b = isoP([SSR.x + SSR.w - 10, SSR.y + 10, SSR_Z + SSR_H + 8]);
  out.push(k.wireSvg(w3a, w3b, { tone: 'blue' }));

  return out.join('');
}

function annotations() {
  const labels = [
    {
      pt: [SSR.x + SSR.w / 2, SSR.y - 10, SSR_Z + SSR_H + 24],
      dx: 0, text: 'SSR — Solid-State Relay', accent: '#94a3b8'
    },
    {
      pt: [LAMP_ARMED[0], LAMP_ARMED[1] - 2, SSR_Z + SSR_H],
      dx: -60, text: 'ARMED (armed)', accent: '#00e676'
    },
    {
      pt: [LAMP_TRIP[0], LAMP_TRIP[1] - 2, SSR_Z + SSR_H],
      dx: 20, text: 'TRIP indicator', accent: '#ff1744'
    },
    {
      pt: [RULER.x + RULER.w + 30, RULER.y + 70, THRESH_Z + 6],
      dx: 10, text: '0.80\u00a0mm lockout', accent: '#ff1744'
    },
    {
      pt: [RULER.x + RULER.w + 24, RULER.y + 60, RULER_Z + 100],
      dx: 10, text: '1.42\u00a0mm (safe)', accent: '#00e5ff'
    },
    {
      pt: [ARM_PIVOT[0] + ARM_LEN, ARM_PIVOT[1], ARM_Z + ARM_H + 10],
      dx: 8, text: 'Trip arm — ARMED', accent: '#00e676'
    },
    {
      pt: [POST_L[0] + 2, POST_L[1], BASE_H + FOOT_H + 60],
      dx: -80, text: 'Plane\u00a0A signal (<\u00a02\u00a0ms)', accent: '#00e5ff'
    },
  ];

  return labels.map(({ pt, dx, text, accent }) => {
    const [sx, sy] = isoP(pt);
    const tx = sx + dx + (dx >= 0 ? 8 : -8);
    return `
      <circle cx="${sx}" cy="${sy}" r="2.2" fill="${accent}" opacity="0.9"/>
      <line x1="${sx}" y1="${sy}" x2="${tx - (dx>=0?4:-4)}" y2="${sy - 16}"
            stroke="${accent}" stroke-width="0.7" opacity="0.5"/>
      <text x="${tx}" y="${sy - 19}" text-anchor="${dx >= 0 ? 'start' : 'end'}"
            font-family="'JetBrains Mono',monospace" font-size="8.5"
            fill="${accent}" opacity="0.92">${text}</text>`;
  }).join('');
}

// ── Compose ─────────────────────────────────────────────────────────────────
const defs = `
  <defs>
    <filter id="glow-green" x="-40%" y="-40%" width="180%" height="180%">
      <feGaussianBlur stdDeviation="3" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <filter id="glow-red" x="-40%" y="-40%" width="180%" height="180%">
      <feGaussianBlur stdDeviation="3" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>`;

const parts = [
  defs,
  base(),
  leftPost(),
  lvdtRuler(),
  ssrBlock(),
  pivotArm(),
  rightPost(),
  wiring(),
  annotations(),
].join('\n');

const readout = `
  <tspan style="fill:#ff1744;font-weight:700">TRIP </tspan>
  <tspan style="fill:#94a3b8">ARMED · margin 1.42\u00a0mm · lockout at 0.80\u00a0mm · response &lt;2\u00a0ms</tspan>`;

const figure = k.figureSvg({
  width: W,
  height: H,
  theme,
  title: 'Plane\u00a0A Virtual Fixture — SSR Lockout Bench Rig',
  fig: 'Fig\u00a02',
  hint: 'Red dashed threshold: 0.80\u00a0mm boundary — breach fires SSR in <2\u00a0ms',
  readout,
  parts,
});

const page = k.pageHtml({
  title: 'BioOS Plane A SSR Virtual Fixture Trip',
  theme,
  figure,
  script: kitScript(),
});

mkdirSync(HERE, { recursive: true });
const out = join(HERE, `ssr-trip${theme === 'light' ? '-light' : ''}.html`);
writeFileSync(out, page, 'utf8');
console.log(`Written: ${out}`);
