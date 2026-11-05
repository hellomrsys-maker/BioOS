/**
 * BioOS Figure 4 — Plane C Kalman Filter Physiological Observer & Ripple Tank
 * ===========================================================================
 * Object: A laboratory ripple tank apparatus.
 *   - Acrylic fluid reservoir tank on 4 corner vibration-isolated legs
 *   - Two precision motorized dippers vibrating at physiological frequencies
 *     (Dipper 1 = Cardiac cycle pulse 1.25 Hz / 75 bpm; Dipper 2 = Respiratory motion 0.25 Hz / 15 bpm)
 *   - Twin concentric wave rings interfering across the tank surface
 *   - Suspended stroboscopic illuminator arm casting caustics onto a lower projection deck
 *   - Calibrated envelope guide rails on tank edges denoting Airbus-style "Alpha-Floor" safe hemodynamic limits (MAP 55 mmHg cutoff)
 *   - Reverse-phase cancellation actuator modeling tremor cancellation
 *
 * Concept: Plane C runs a continuous 100 Hz Extended Kalman Filter (EKF).
 * The interfering ripples model multi-frequency physiological motion (breathing + heartbeat).
 * The Kalman observer estimates true organ position and phase to continuously cancel jitter
 * and maintain safe drug titration envelopes (Alpha-Floor stall protection).
 *
 * Run:  node web/figures/kalman-tank/build.mjs [--light]
 * Out:  web/figures/kalman-tank/kalman-tank.html
 */

import { writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as k from '../../../anatomy/kit/iso-kit.mjs';
import { kitScript } from '../../../anatomy/scripts/inline-kit.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const theme = process.argv.includes('--light') ? 'light' : 'dark';

const W = 720, H = 480;

// Base Table & Frame
const TABLE = { x: -170, y: -90, w: 340, d: 180, r: 8 };
const TABLE_H = 12;
const LEG_H = 40;

// Lower Projection Screen (where caustics and envelope shadow map appear)
const SCREEN = { x: -130, y: -65, w: 260, d: 130, r: 4 };
const SCREEN_Z = TABLE_H + 2;
const SCREEN_H = 2;

// Upper Acrylic Fluid Tank
const TANK = { x: -140, y: -70, w: 280, d: 140, r: 6 };
const TANK_Z = TABLE_H + LEG_H;
const TANK_WALL_H = 24;

// Twin Dippers (Oscillators)
const DIPPER1_POS = [-45, 0];  // Cardiac pulse source (HR)
const DIPPER2_POS = [45, 0];   // Respiratory drift source (Vent)
const DIPPER_Z = TANK_Z + 12;

// Strobe Overhead Lighting Gantry
const GANTRY_POST = [-120, -60];
const GANTRY_H = 130;

// Projection setup
const P = k.fitProjection(
  [
    [TABLE.x - 20, TABLE.y - 20, 0],
    [TABLE.x + TABLE.w + 20, TABLE.y + TABLE.d + 20, TANK_Z + GANTRY_H + 20],
    [GANTRY_POST[0] + 160, GANTRY_POST[1] + 120, TANK_Z + GANTRY_H + 10]
  ],
  W, H,
  { pad: 40, azimuth: 44 }
);

const slab = (rect, z0, h, tone) => k.solidSvg(k.slabOf(rect, z0, h, P, 8, 1.4), { tone });
const cyl  = (cx, cy, r, z0, h, tone, steps = 28) => k.solidSvg(k.cylinder(cx, cy, r, z0, h, P, steps), { tone });
const line = (d, style) => k.lineSvg(d, style);
const dots = (pts, style) => k.dotsSvg(pts, style);
const isoP = (pt) => k.iso(pt, P);

function lowerTable() {
  const out = [];
  out.push(`<path class="iso-halo" d="${k.haloOf(TABLE, 0, TABLE_H, P)}"/>`);

  // Table base slab
  out.push(slab(TABLE, 0, TABLE_H, 'lo'));

  // Table legs to floor
  for (const [lx, ly] of k.corners(TABLE, 16)) {
    out.push(cyl(lx, ly, 7, -10, 10, 'lo', 16));
  }

  // Lower Projection Screen (Paper deck)
  out.push(slab(SCREEN, SCREEN_Z, SCREEN_H, 'mid')
    .replace(/iso-top[^"]*"/g, 'iso-top" style="fill:#091222"')
  );

  // Projected Alpha-Floor Hemodynamic Corridor on screen deck
  const corridor = { x: -90, y: -35, w: 180, d: 70, r: 4 };
  out.push(line(k.planOutline(corridor, SCREEN_Z + SCREEN_H + 0.5, P), {
    stroke: '#00e5ff',
    w: 1.2,
    dash: '4 3'
  }));

  // Caustic interference ripple patterns on projection deck
  for (let r = 18; r <= 80; r += 16) {
    out.push(line(k.ring(DIPPER1_POS[0], DIPPER1_POS[1], r, SCREEN_Z + SCREEN_H + 0.6, P, 32), {
      stroke: 'rgba(0, 229, 255, 0.22)',
      w: 0.8
    }));
    out.push(line(k.ring(DIPPER2_POS[0], DIPPER2_POS[1], r, SCREEN_Z + SCREEN_H + 0.6, P, 32), {
      stroke: 'rgba(56, 189, 248, 0.18)',
      w: 0.8
    }));
  }

  return out.join('');
}

function tankStructure() {
  const out = [];

  // 4 Vibration-isolating risers / pillars supporting the upper fluid tank
  for (const [tx, ty] of k.corners(TANK, 12)) {
    out.push(cyl(tx, ty, 6, TABLE_H, LEG_H, 'mid', 20));
    // Damping rubber collars
    out.push(cyl(tx, ty, 7.5, TABLE_H + LEG_H * 0.4, 6, 'hi', 18));
  }

  // Acrylic Tank Bottom Rim & Transparent Basin
  out.push(slab(TANK, TANK_Z, 3, 'lo'));

  // Glass/Acrylic Walls (represented by precise tone outline + tinted floor)
  out.push(line(k.planOutline(TANK, TANK_Z, P), { stroke: '#38bdf8', w: 1.2 }));
  out.push(line(k.planOutline(TANK, TANK_Z + TANK_WALL_H, P), { stroke: '#38bdf8', w: 1.6 }));

  // Fluid Water Surface (at Z = TANK_Z + 12)
  const fluidSurface = k.insetPlan(TANK, 3);
  const fluidZ = TANK_Z + 12;
  out.push(slab(fluidSurface, fluidZ - 2, 2, 'mid')
    .replace(/iso-fill[^"]*"/g, 'iso-fill" style="fill:#041a2f"')
    .replace(/iso-top[^"]*"/g,  'iso-top"  style="fill:#062847" fill-opacity="0.85"')
  );

  // Surface Wave Rings originating from Dipper 1 (Cardiac 75 bpm)
  for (const wr of [12, 26, 42, 60, 78]) {
    out.push(line(k.ring(DIPPER1_POS[0], DIPPER1_POS[1], wr, fluidZ, P, 36), {
      stroke: 'rgba(0, 229, 255, 0.65)',
      w: 1.1
    }));
  }

  // Surface Wave Rings originating from Dipper 2 (Respiratory 15 bpm)
  for (const wr of [16, 32, 52, 72]) {
    out.push(line(k.ring(DIPPER2_POS[0], DIPPER2_POS[1], wr, fluidZ, P, 36), {
      stroke: 'rgba(168, 85, 247, 0.65)',
      w: 1.1
    }));
  }

  // Tank Rim Calibrated Ticks (Pressure / MAP scale 40 - 120 mmHg)
  const leftTicks = k.topTicks(
    TANK.y + 10, TANK.y + TANK.d - 10,
    6, 5, TANK.x + 3, TANK_Z + TANK_WALL_H,
    [3, 6], P
  );
  out.push(line(leftTicks.minor, { stroke: '#64748b', w: 0.8 }));
  out.push(line(leftTicks.major, { stroke: '#00e5ff', w: 1.2 }));

  return out.join('');
}

function oscillatorsAndGantry() {
  const out = [];

  // Transverse support bridge across tank
  const bridge = { x: -80, y: -6, w: 160, d: 12, r: 2 };
  const bridgeZ = TANK_Z + TANK_WALL_H + 8;
  out.push(slab(bridge, bridgeZ, 6, 'hi'));

  // Dipper 1 (Cardiac Oscillator - Cyan)
  out.push(cyl(DIPPER1_POS[0], DIPPER1_POS[1], 8, bridgeZ + 6, 16, 'mid', 20));
  out.push(cyl(DIPPER1_POS[0], DIPPER1_POS[1], 2.2, TANK_Z + 4, bridgeZ - TANK_Z + 2, 'hi', 12)
    .replace(/iso-top[^"]*"/g, 'iso-top" style="fill:#00e5ff"')
  );
  out.push(dots([isoP([DIPPER1_POS[0], DIPPER1_POS[1], bridgeZ + 22])], { size: 1.2, fill: '#00e5ff' }));

  // Dipper 2 (Respiratory Oscillator - Violet)
  out.push(cyl(DIPPER2_POS[0], DIPPER2_POS[1], 8, bridgeZ + 6, 16, 'mid', 20));
  out.push(cyl(DIPPER2_POS[0], DIPPER2_POS[1], 2.2, TANK_Z + 4, bridgeZ - TANK_Z + 2, 'hi', 12)
    .replace(/iso-top[^"]*"/g, 'iso-top" style="fill:#c084fc"')
  );
  out.push(dots([isoP([DIPPER2_POS[0], DIPPER2_POS[1], bridgeZ + 22])], { size: 1.2, fill: '#c084fc' }));

  // Stroboscope Overhead Gantry Pillar
  const [gx, gy] = GANTRY_POST;
  out.push(cyl(gx, gy, 8, TANK_Z, GANTRY_H, 'mid', 24));
  out.push(cyl(gx, gy, 10, TANK_Z + GANTRY_H - 6, 6, 'hi', 20));

  // Gantry cantilever over water center
  const gantryArm = { x: gx, y: gy - 4, w: 120, d: 8, r: 2 };
  const gantryZ = TANK_Z + GANTRY_H - 6;
  out.push(slab(gantryArm, gantryZ, 6, 'mid'));

  // Strobe illuminator lamp housing
  const lampX = gx + 110;
  const lampY = gy;
  out.push(cyl(lampX, lampY, 14, gantryZ - 12, 12, 'hi', 24));
  out.push(dots([isoP([lampX, lampY, gantryZ - 12])], { size: 4.5, fill: '#ffffff' }));

  return out.join('');
}

function annotations() {
  const labels = [
    { pt: [DIPPER1_POS[0], DIPPER1_POS[1], TANK_Z + 46], text: 'Cardiac Dipper: 75 bpm (1.25 Hz)', accent: '#00e5ff', dx: -80 },
    { pt: [DIPPER2_POS[0], DIPPER2_POS[1], TANK_Z + 46], text: 'Respiratory Dipper: 15 bpm (0.25 Hz)', accent: '#c084fc', dx: 70 },
    { pt: [0, 0, TANK_Z + 12], text: 'Interference Node: Kalman State Est.', accent: '#34d399', dx: 45 },
    { pt: [TANK.x + 4, TANK.y + TANK.d / 2, TANK_Z + TANK_WALL_H], text: 'Alpha-Floor MAP Limits (55 mmHg)', accent: '#f43f5e', dx: -110 },
    { pt: [0, -25, SCREEN_Z + SCREEN_H], text: 'Projected Hemodynamic Corridor', accent: '#00e5ff', dx: 60 },
    { pt: [GANTRY_POST[0] + 110, GANTRY_POST[1], TANK_Z + GANTRY_H], text: '100 Hz Stroboscopic Observer', accent: '#94a3b8', dx: 30 }
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
  lowerTable(),
  tankStructure(),
  oscillatorsAndGantry(),
  annotations(),
].join('\n');

const readout = `
  <tspan style="fill:#00e5ff;font-weight:700">PLANE C EKF </tspan>
  <tspan style="fill:#94a3b8">100 Hz update · MAP: 80.0 mmHg · est jitter: &plusmn;0.03 mm · Alpha-Floor: Nominal</tspan>`;

const figure = k.figureSvg({
  width: W,
  height: H,
  theme,
  title: 'Plane C 100 Hz Kalman Observer & Physiological Ripple Tank',
  fig: 'Fig\u00a04',
  hint: 'Interfering waves model cardiac + respiratory motion · lower deck shows Alpha-Floor corridor',
  readout,
  parts,
});

const page = k.pageHtml({
  title: 'BioOS Plane C Kalman Observer Ripple Tank',
  theme,
  figure,
  script: kitScript(),
});

mkdirSync(HERE, { recursive: true });
const out = join(HERE, `kalman-tank${theme === 'light' ? '-light' : ''}.html`);
writeFileSync(out, page, 'utf8');
console.log(`Written: ${out}`);
