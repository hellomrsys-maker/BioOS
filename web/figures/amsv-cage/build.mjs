/**
 * BioOS AMSV Tri-Plane Card-Cage Figure
 * ============================================================
 * Anatomy isometric figure: explains the 128-byte Atomic Memory
 * State Vector (AMSV) shared between:
 *   Plane A — Rust 1000 Hz Safety Kernel (crimson)
 *   Plane C — Kalman 100 Hz Observer (cyan)
 *   Plane B — Meta Muse-Spark (816B/A42B) Cognitive FMS (blue)
 *
 * Object: A 3-slot card cage with a gold backplane bus and 64 contact
 * pins per cache line. All three PCB cards plug into one shared
 * 128-byte bus — that IS the zero-bridge synchronous memory.
 *
 * Run:  node web/figures/amsv-cage/build.mjs [--light]
 * Out:  web/figures/amsv-cage/amsv-cage.html
 */

import { writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as k from '../../../anatomy/kit/iso-kit.mjs';
import { kitScript } from '../../../anatomy/scripts/inline-kit.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const theme = process.argv.includes('--light') ? 'light' : 'dark';

const W = 720, H = 460;

// ── World geometry ─────────────────────────────────────────────────────────
// Chassis base plate
const CHASSIS      = { x: -170, y: -80, w: 340, d: 160, r: 8 };
const CHASSIS_H    = 14;
const FOOT_H       = 6;

// Three PCB cards, stacked side-by-side along X
const CARD_W = 86, CARD_D = 130, CARD_H = 120, CARD_R = 3;
const CARD_GAP = 10;
const CARDS = [
  { cx: -100, cy: -55, label: 'PLANE A', accent: '#ff1744', fill: '#1a0304', fillSide: '#120203' },
  { cx:  -4,  cy: -55, label: 'PLANE C', accent: '#00e5ff', fill: '#02282e', fillSide: '#011519' },
  { cx:   92, cy: -55, label: 'PLANE B', accent: '#0084ff', fill: '#051428', fillSide: '#030c18' },
];
const CARD_BASE_Z = CHASSIS_H + FOOT_H + 2;

// Backplane bus strip (gold — the AMSV shared bus)
const BUS_STRIP = { x: -155, y: 50, w: 310, d: 20, r: 2 };
const BUS_Z     = CHASSIS_H + FOOT_H;
const BUS_H     = 6;

// Contact pins on bus (2 rows × 32 pins = 64 per cache-line)
const PIN_R    = 1.4;
const PIN_H    = 10;
const PIN_COLS = 32;
const PIN_PITCH= 9;
const PIN_ROW_Y= [54, 62]; // two rows

// Camera
const P = k.fitProjection(
  [
    [CHASSIS.x - 20, CHASSIS.y - 20, 0],
    [CHASSIS.x + CHASSIS.w + 20, CHASSIS.y + CHASSIS.d + 20, CARD_BASE_Z + CARD_H + 20],
  ],
  W, H,
  { pad: 44, azimuth: 42 }
);

// ── Helpers ─────────────────────────────────────────────────────────────────
const solidOf = (rect, z0, h, tone) =>
  k.solidSvg(k.slabOf(rect, z0, h, P, 8, 1.5), { tone });

const lineOf = (d, style) => k.lineSvg(d, style);

const dot = (x, y, z, size = 1) =>
  k.dotsSvg([k.iso([x, y, z], P)], { size });

function byDepth(pts) {
  return [...pts].sort((a, b) => k.depthOf(a, P) - k.depthOf(b, P));
}

// ── Parts ───────────────────────────────────────────────────────────────────
function chassis() {
  const out = [];
  // Halo shadow
  out.push(`<path class="iso-halo" d="${k.haloOf(CHASSIS, 0, CHASSIS_H + FOOT_H, P)}"/>`);
  // Feet at corners
  for (const [fx, fy] of k.corners(CHASSIS, 18)) {
    out.push(solidOf({ x: fx - 7, y: fy - 7, w: 14, d: 14, r: 2 }, -FOOT_H, FOOT_H, 'lo'));
  }
  // Base slab
  out.push(solidOf(CHASSIS, 0, CHASSIS_H, 'lo'));
  // Inset groove
  out.push(lineOf(k.planOutline(k.insetPlan(CHASSIS, 8), CHASSIS_H, P), { tone: 'faint' }));
  // Corner screws
  const screws = k.corners(CHASSIS, 14);
  out.push(lineOf(screws.map(([x, y]) => k.ring(x, y, 2.4, CHASSIS_H, P, 16)).join(''), { tone: 'lo' }));
  out.push(k.dotsSvg(screws.map(([x, y]) => k.iso([x, y, CHASSIS_H], P)), { size: 0.5 }));
  // Label plate strip
  const label = { x: CHASSIS.x + 12, y: CHASSIS.y + CHASSIS.d - 20, w: 100, d: 10, r: 1 };
  out.push(solidOf(label, CHASSIS_H, 1.5, 'lo'));
  out.push(lineOf(k.planOutline(k.insetPlan(label, 2), CHASSIS_H + 1.5, P), { tone: 'faint' }));
  return out.join('');
}

function busBar() {
  const out = [];
  // Gold bus strip
  const slab = k.slabOf(BUS_STRIP, BUS_Z, BUS_H, P, 4, 1);
  const svg  = k.solidSvg(slab, { tone: 'hi' });
  // Override fill with amber/gold for the bus
  out.push(svg.replace(/iso-fill[^"]*"/g, 'iso-fill" style="fill:#2a1a00"')
              .replace(/iso-top[^"]*"/g,  'iso-top"  style="fill:#3d2600"'));
  // Cache-line boundary marker (dashed line at centre)
  const midX = BUS_STRIP.x + BUS_STRIP.w / 2;
  out.push(lineOf(
    k.iso([midX, BUS_STRIP.y, BUS_Z + BUS_H + 1], P) + ' ' +
    k.iso([midX, BUS_STRIP.y + BUS_STRIP.d, BUS_Z + BUS_H + 1], P),
    { stroke: '#ffab00', w: 1.5, dash: '5 3' }
  ));
  return out.join('');
}

function pins() {
  const out = [];
  const baseX = BUS_STRIP.x + (BUS_STRIP.w - PIN_COLS * PIN_PITCH) / 2;
  for (const py of PIN_ROW_Y) {
    for (let i = 0; i < PIN_COLS; i++) {
      const px   = baseX + i * PIN_PITCH;
      const tone = i < PIN_COLS / 2 ? 'hi' : 'mid'; // CL0 brighter than CL1
      out.push(solidOf(
        { x: px - PIN_R, y: py - PIN_R, w: PIN_R * 2, d: PIN_R * 2, r: PIN_R },
        BUS_Z, PIN_H,
        tone
      ));
    }
  }
  return out.join('');
}

function card({ cx, cy, accent, fill, fillSide }) {
  const rect = { x: cx - CARD_W / 2, y: cy - CARD_D / 2, w: CARD_W, d: CARD_D, r: CARD_R };
  const slab = k.slabOf(rect, CARD_BASE_Z, CARD_H, P, 5, 1.2);
  const out  = [];

  // Build SVG and tint with plane colour
  const svg = k.solidSvg(slab, { tone: 'mid' });
  out.push(
    svg.replace(/iso-fill[^"]*"/g, `iso-fill" style="fill:${fill}"`)
       .replace(/iso-top[^"]*"/g,  `iso-top" style="fill:${fill}" stroke="${accent}" stroke-width="0.8" stroke-opacity="0.5"`)
  );

  // Accent top-edge stripe
  const stripe = { x: rect.x + 3, y: rect.y + 3, w: CARD_W - 6, d: 5, r: 1 };
  out.push(solidOf(stripe, CARD_BASE_Z + CARD_H - 1, 2.5, 'hi')
    .replace(/iso-fill[^"]*"/g, `iso-fill" style="fill:${accent}" opacity="0.6"`)
    .replace(/iso-top[^"]*"/g,  `iso-top" style="fill:${accent}" opacity="0.7"`)
  );

  // Component bumps on card surface (ICs)
  const ics = [
    [cx - 20, cy - 25], [cx + 10, cy - 25],
    [cx - 20, cy],      [cx + 10, cy],
  ];
  for (const [ix, iy] of ics) {
    const ic = { x: ix - 8, y: iy - 5, w: 16, d: 10, r: 1 };
    out.push(solidOf(ic, CARD_BASE_Z + CARD_H, 3, 'mid')
      .replace(/iso-fill[^"]*"/g, `iso-fill" style="fill:#111820"`)
    );
  }

  // Connector fingers at card bottom (into bus)
  for (let f = 0; f < 7; f++) {
    const fx = rect.x + 6 + f * 11;
    out.push(solidOf(
      { x: fx - 2.5, y: rect.y + CARD_D - 6, w: 5, d: 8, r: 0.5 },
      CARD_BASE_Z - 4, 5, 'hi'
    ).replace(/iso-fill[^"]*"/g, `iso-fill" style="fill:#998844"`));
  }

  return out.join('');
}

function annotations() {
  const out = [];
  const labels = [
    { x: CARDS[0].cx, y: CARDS[0].cy - CARD_D / 2 - 2, z: CARD_BASE_Z + CARD_H + 12,
      text: 'Plane A: 1000 Hz Rust', accent: '#ff1744' },
    { x: CARDS[1].cx, y: CARDS[1].cy - CARD_D / 2 - 2, z: CARD_BASE_Z + CARD_H + 12,
      text: 'Plane C: 100 Hz Kalman', accent: '#00e5ff' },
    { x: CARDS[2].cx, y: CARDS[2].cy - CARD_D / 2 - 2, z: CARD_BASE_Z + CARD_H + 12,
      text: 'Plane B: Meta Muse-Spark (816B/A42B)', accent: '#0084ff' },
    { x: BUS_STRIP.x + BUS_STRIP.w / 4, y: BUS_STRIP.y + BUS_STRIP.d + 4, z: BUS_Z + BUS_H + 2,
      text: 'CL0: 0x00–0x3F (Actuator)', accent: '#ffab00' },
    { x: BUS_STRIP.x + BUS_STRIP.w * 3 / 4, y: BUS_STRIP.y + BUS_STRIP.d + 4, z: BUS_Z + BUS_H + 2,
      text: 'CL1: 0x40–0x7F (Kalman)', accent: '#ffab00' },
  ];

  for (const { x, y, z, text, accent } of labels) {
    const [sx, sy] = k.iso([x, y, z], P);
    out.push(`
      <circle cx="${sx}" cy="${sy}" r="2.5" fill="${accent}" opacity="0.9"/>
      <line x1="${sx}" y1="${sy}" x2="${sx}" y2="${sy - 24}" stroke="${accent}" stroke-width="0.8" opacity="0.5"/>
      <text x="${sx}" y="${sy - 28}" text-anchor="middle"
            font-family="'JetBrains Mono',monospace" font-size="8.5"
            fill="${accent}" opacity="0.92">${text}</text>`);
  }
  return out.join('');
}

// ── Compose ─────────────────────────────────────────────────────────────────
const parts = [
  chassis(),
  busBar(),
  pins(),
  ...byDepth(CARDS.map(c => [c.cx, c.cy, 0])).map((_, i) => card(CARDS[i])),
  annotations(),
].join('\n');

const readout = `
  <tspan style="fill:#ffab00;font-weight:700">AMSV </tspan>
  <tspan style="fill:#94a3b8">128 B · 3 planes · 0 ns sync · addr 0x00007FFE2C7600C0</tspan>`;

const figure = k.figureSvg({
  width: W,
  height: H,
  theme,
  title: '128-byte Tri-Plane AMSV — Zero-Bridge Memory Bus',
  fig: 'Fig\u00a01',
  hint: 'Three plane cards share one physical bus — no serialisation, no bridge',
  readout,
  parts,
});

const page = k.pageHtml({
  title: 'BioOS AMSV Tri-Plane Card-Cage',
  theme,
  figure,
  script: kitScript(),
});

mkdirSync(HERE, { recursive: true });
const out = join(HERE, `amsv-cage${theme === 'light' ? '-light' : ''}.html`);
writeFileSync(out, page, 'utf8');
console.log(`Written: ${out}`);
