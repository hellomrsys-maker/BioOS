/**
 * BioOS Figure 3 — Meta SAM 3.1 Margin Dial-Indicator Gauge
 * ============================================================
 * Object: Precision Dial Indicator Gauge with sliding stage.
 *   - Base plate on rubber feet with linear guide rail
 *   - Heavy magnetic mount post with knurled locking collar
 *   - Swivel clamp arm holding precision circular dial gauge
 *   - Rotating needle reading distance margin to critical artery (0.00 to 5.00 mm)
 *   - Red danger sector arc (< 0.80 mm lockout zone)
 *   - Sliding specimen carriage simulating instrument tip approaching boundary
 *   - Calibrated feeler probe touching the moving carriage
 *
 * Concept: Meta SAM 3.1 real-time vision segmentation calculates the exact
 * geometric Euclidean distance from the laparoscopic tool center point to
 * the segmented hepatic artery boundary. When the margin drops below 0.80 mm,
 * the gauge enters the lockout sector and trips Plane A.
 *
 * Run:  node web/figures/sam-dial/build.mjs [--light]
 * Out:  web/figures/sam-dial/sam-dial.html
 */

import { writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as k from '../../../anatomy/kit/iso-kit.mjs';
import { kitScript } from '../../../anatomy/scripts/inline-kit.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const theme = process.argv.includes('--light') ? 'light' : 'dark';

const W = 720, H = 480;

// Dimensions & World coordinates
const BASE = { x: -160, y: -80, w: 320, d: 160, r: 8 };
const BASE_H = 14;
const FOOT_H = 6;

// Magnetic Post & Arm
const POST_POS = [-105, -20];
const POST_R = 9;
const POST_H = 175;

const DIAL_CENTER = [40, -10];
const DIAL_R = 34;
const DIAL_Z = 100;
const DIAL_DEPTH = 16;

// Rail & Sliding Carriage (Instrument position simulator)
const RAIL = { x: -30, y: 35, w: 160, d: 18, r: 2 };
const RAIL_Z = BASE_H + 2;
const RAIL_H = 5;

const CARRIAGE = { x: 25, y: 28, w: 46, d: 32, r: 3 };
const CARRIAGE_Z = RAIL_Z + RAIL_H;
const CARRIAGE_H = 12;

// Projection
const P = k.fitProjection(
  [
    [BASE.x - 20, BASE.y - 20, 0],
    [BASE.x + BASE.w + 20, BASE.y + BASE.d + 20, POST_H + 25],
    [DIAL_CENTER[0] + DIAL_R + 25, DIAL_CENTER[1] + DIAL_R + 25, DIAL_Z + DIAL_R + 20]
  ],
  W, H,
  { pad: 38, azimuth: 44 }
);

const slab = (rect, z0, h, tone) => k.solidSvg(k.slabOf(rect, z0, h, P, 8, 1.4), { tone });
const cyl  = (cx, cy, r, z0, h, tone, steps = 28) => k.solidSvg(k.cylinder(cx, cy, r, z0, h, P, steps), { tone });
const line = (d, style) => k.lineSvg(d, style);
const dots = (pts, style) => k.dotsSvg(pts, style);
const isoP = (pt) => k.iso(pt, P);

function basePlate() {
  const out = [];
  out.push(`<path class="iso-halo" d="${k.haloOf(BASE, 0, BASE_H + FOOT_H, P)}"/>`);

  // Feet
  for (const [fx, fy] of k.corners(BASE, 18)) {
    out.push(cyl(fx, fy, 8, -FOOT_H, FOOT_H, 'lo', 20));
  }
  // Base slab
  out.push(slab(BASE, 0, BASE_H, 'lo'));

  // Corner Screws
  const screws = k.corners(BASE, 14);
  out.push(line(screws.map(([x, y]) => k.ring(x, y, 2.5, BASE_H, P, 16)).join(''), { tone: 'lo' }));
  out.push(dots(screws.map(([x, y]) => isoP([x, y, BASE_H])), { size: 0.5 }));

  // Vernier Scale ticks on base plate front
  const ticks = k.topTicks(
    BASE.x + 20, BASE.x + BASE.w - 20,
    5, 5, BASE.y + BASE.d - 12, BASE_H,
    [2, 4.5], P
  );
  out.push(line(ticks.minor, { tone: 'lo' }));
  out.push(line(ticks.major, { tone: 'mid' }));

  return out.join('');
}

function postAndClamp() {
  const out = [];
  const [px, py] = POST_POS;

  // Heavy magnetic base block
  const magBase = { x: px - 22, y: py - 22, w: 44, d: 44, r: 4 };
  out.push(slab(magBase, BASE_H, 22, 'mid'));
  out.push(cyl(px, py, 6, BASE_H + 22, 6, 'hi', 16)); // ON/OFF magnetic switch knob

  // Vertical steel post
  out.push(cyl(px, py, POST_R, BASE_H + 22, POST_H - 22, 'mid', 24));
  out.push(cyl(px, py, POST_R + 1.5, BASE_H + POST_H - 4, 4, 'hi', 20)); // post cap

  // Cross-clamp assembly at gauge height
  const clampZ = DIAL_Z + 12;
  out.push(cyl(px, py, POST_R + 5, clampZ - 10, 20, 'hi', 20));
  out.push(cyl(px - 14, py, 4, clampZ, 12, 'lo', 16)); // thumb screw on clamp

  // Horizontal cantilever arm to dial gauge
  const armLen = DIAL_CENTER[0] - px;
  const armRect = { x: px, y: py - 4, w: armLen, d: 8, r: 2 };
  out.push(slab(armRect, clampZ - 4, 8, 'hi'));

  return out.join('');
}

function dialGauge() {
  const out = [];
  const [dx, dy] = DIAL_CENTER;

  // Dial outer bezel ring / cylinder
  out.push(cyl(dx, dy, DIAL_R, DIAL_Z, DIAL_DEPTH, 'mid', 36));
  out.push(cyl(dx, dy, DIAL_R - 3, DIAL_Z + 2, DIAL_DEPTH - 1, 'lo', 36));

  // Gauge face (bright disc)
  out.push(cyl(dx, dy, DIAL_R - 5, DIAL_Z + DIAL_DEPTH - 1, 2, 'hi', 36)
    .replace(/iso-fill[^"]*"/g, 'iso-fill" style="fill:#0c1322"')
    .replace(/iso-top[^"]*"/g,  'iso-top"  style="fill:#0f172a" stroke="#38bdf8" stroke-width="0.8"')
  );

  // Dial Face Dial markings / ticks
  for (let deg = 0; deg < 360; deg += 15) {
    const rad = (deg * Math.PI) / 180;
    const rInner = (deg % 45 === 0) ? DIAL_R - 13 : DIAL_R - 9;
    const rOuter = DIAL_R - 6;
    const p1 = [dx + Math.cos(rad) * rInner, dy + Math.sin(rad) * rInner, DIAL_Z + DIAL_DEPTH + 1];
    const p2 = [dx + Math.cos(rad) * rOuter, dy + Math.sin(rad) * rOuter, DIAL_Z + DIAL_DEPTH + 1];
    const tone = (deg % 45 === 0) ? 'hi' : 'lo';
    out.push(line(`${k.iso(p1, P)} ${k.iso(p2, P)}`, { tone }));
  }

  // Red Lockout Arc (< 0.80 mm margin zone)
  const dangerPts = [];
  for (let a = 180; a <= 245; a += 5) {
    const rad = (a * Math.PI) / 180;
    dangerPts.push(isoP([dx + Math.cos(rad) * (DIAL_R - 10), dy + Math.sin(rad) * (DIAL_R - 10), DIAL_Z + DIAL_DEPTH + 1.2]));
  }
  out.push(`<path d="${dangerPts.map((pt, i) => (i === 0 ? 'M' : 'L') + pt).join('')}" fill="none" stroke="#f43f5e" stroke-width="3" stroke-linecap="round"/>`);

  // Dial Center Hub
  out.push(cyl(dx, dy, 4.5, DIAL_Z + DIAL_DEPTH, 3, 'hi', 20));
  out.push(dots([isoP([dx, dy, DIAL_Z + DIAL_DEPTH + 3])], { size: 0.8 }));

  // Pointer Needle (pointing at 1.42 mm margin, approx 85 deg)
  const needleAngle = 80 * (Math.PI / 180);
  const nLen = DIAL_R - 9;
  const tipX = dx + Math.cos(needleAngle) * nLen;
  const tipY = dy + Math.sin(needleAngle) * nLen;
  const tailX = dx - Math.cos(needleAngle) * 7;
  const tailY = dy - Math.sin(needleAngle) * 7;
  out.push(line(`${isoP([tailX, tailY, DIAL_Z + DIAL_DEPTH + 2])} ${isoP([tipX, tipY, DIAL_Z + DIAL_DEPTH + 2])}`, {
    stroke: '#00e5ff',
    w: 2
  }));
  out.push(dots([isoP([tipX, tipY, DIAL_Z + DIAL_DEPTH + 2])], { size: 1.5, fill: '#00e5ff' }));

  // Top knurled crown / zero-reset screw
  out.push(cyl(dx, dy - DIAL_R, 5, DIAL_Z + 3, 10, 'mid', 16));

  // Lower plunger shaft reaching down towards carriage
  const plungerX = dx;
  const plungerY = dy + DIAL_R;
  const plungerZ0 = CARRIAGE_Z + CARRIAGE_H + 4;
  const plungerH = DIAL_Z - plungerZ0;
  out.push(cyl(plungerX, plungerY, 2.8, plungerZ0, plungerH, 'hi', 16));

  // Jeweled probe contact tip touching simulated tissue carriage
  out.push(cyl(plungerX, plungerY, 4, plungerZ0 - 3, 4, 'hi', 16)
    .replace(/iso-top[^"]*"/g, 'iso-top" style="fill:#c084fc"')
  );

  return out.join('');
}

function railAndCarriage() {
  const out = [];

  // Linear twin rail guideway
  out.push(slab(RAIL, RAIL_Z, RAIL_H, 'lo'));
  out.push(cyl(RAIL.x + 8, RAIL.y + 9, 3, RAIL_Z + RAIL_H, 2, 'hi', 12));
  out.push(cyl(RAIL.x + RAIL.w - 8, RAIL.y + 9, 3, RAIL_Z + RAIL_H, 2, 'hi', 12));

  // Sliding carriage (instrument trocar simulator)
  out.push(slab(CARRIAGE, CARRIAGE_Z, CARRIAGE_H, 'mid'));

  // Calibrated step block on top of carriage
  const stepBlock = { x: CARRIAGE.x + 6, y: CARRIAGE.y + 6, w: 22, d: 20, r: 1.5 };
  out.push(slab(stepBlock, CARRIAGE_Z + CARRIAGE_H, 4, 'hi'));

  // Fine micrometer adjustment thumbwheel on carriage end
  out.push(cyl(CARRIAGE.x + CARRIAGE.w + 4, CARRIAGE.y + CARRIAGE.d / 2, 7, CARRIAGE_Z + 2, 8, 'hi', 20));

  return out.join('');
}

function annotations() {
  const labels = [
    { pt: [POST_POS[0], POST_POS[1], BASE_H + POST_H], text: 'Rigid Reference Post', accent: '#94a3b8', dx: -65 },
    { pt: [DIAL_CENTER[0], DIAL_CENTER[1] - DIAL_R, DIAL_Z + DIAL_DEPTH], text: 'Zero Calibration Crown', accent: '#94a3b8', dx: 30 },
    { pt: [DIAL_CENTER[0] + 16, DIAL_CENTER[1] + 10, DIAL_Z + DIAL_DEPTH + 3], text: 'Margin Needle: 1.42 mm', accent: '#00e5ff', dx: 35 },
    { pt: [DIAL_CENTER[0] - 22, DIAL_CENTER[1] + 18, DIAL_Z + DIAL_DEPTH], text: 'Lockout Zone (<0.80 mm)', accent: '#f43f5e', dx: -100 },
    { pt: [DIAL_CENTER[0], DIAL_CENTER[1] + DIAL_R + 4, CARRIAGE_Z + CARRIAGE_H + 2], text: 'Feeler Probe Tip (Tissue Surface)', accent: '#c084fc', dx: 50 },
    { pt: [CARRIAGE.x + CARRIAGE.w, CARRIAGE.y + CARRIAGE.d / 2, CARRIAGE_Z + CARRIAGE_H], text: 'Micro-Drive Carriage', accent: '#94a3b8', dx: 45 }
  ];

  return labels.map(({ pt, text, accent, dx }) => {
    const [sx, sy] = isoP(pt);
    const tx = sx + dx;
    return `
      <circle cx="${sx}" cy="${sy}" r="2.2" fill="${accent}" opacity="0.9"/>
      <line x1="${sx}" y1="${sy}" x2="${tx + (dx >= 0 ? -4 : 4)}" y2="${sy - 16}" stroke="${accent}" stroke-width="0.7" opacity="0.5"/>
      <text x="${tx}" y="${sy - 19}" text-anchor="${dx >= 0 ? 'start' : 'end'}"
            font-family="'JetBrains Mono',monospace" font-size="8.5"
            fill="${accent}" opacity="0.92">${text}</text>`;
  }).join('');
}

// Composition
const parts = [
  basePlate(),
  postAndClamp(),
  dialGauge(),
  railAndCarriage(),
  annotations(),
].join('\n');

const readout = `
  <tspan style="fill:#c084fc;font-weight:700">SAM 3.1 </tspan>
  <tspan style="fill:#94a3b8">margin 1.42 mm · critical lockout: &lt; 0.80 mm · target confidence 98.4%</tspan>`;

const figure = k.figureSvg({
  width: W,
  height: H,
  theme,
  title: 'Meta SAM 3.1 Intraoperative Margin Dial-Indicator',
  fig: 'Fig\u00a03',
  hint: 'Dial reads distance to artery · red zone indicates mechanical lockout threshold',
  readout,
  parts,
});

const page = k.pageHtml({
  title: 'BioOS Meta SAM 3.1 Margin Dial-Indicator',
  theme,
  figure,
  script: kitScript(),
});

mkdirSync(HERE, { recursive: true });
const out = join(HERE, `sam-dial${theme === 'light' ? '-light' : ''}.html`);
writeFileSync(out, page, 'utf8');
console.log(`Written: ${out}`);
