// BioOS Flight Deck Reactive Application Engine
// Standard Compliance: IEC 62304 Class C, ASTM F2761, ISO/IEEE 11073 SDC
// Tri-Plane Aerospace Architecture: Engine 1 (Actuation) + Engine 2 (Kalman Envelope) + Engine 3 (Cognitive FMS)

const state = {
  regime: 'ROUTINE',
  watchdogState: 'NORMAL', // 'NORMAL', 'CAUTION', 'LOCKED'
  ssrEnergized: true,
  mechRelayClosed: true,
  heartbeatOk: true,
  heartbeatDeadlineMs: 50,
  
  // Actuator Telemetry (Engine 1 Fly-by-Wire)
  infusionRate: 125.0,
  pressureMmhg: 180,
  bubbleSizeUl: 0,
  
  // ESE Biomarkers (Engine 1)
  hemolysisIndex: 12,
  potassiumVal: 4.40,
  
  // Dynamic Physiological Envelope & Kalman Observer (Engine 2)
  patientMap: 80,
  patientHr: 75,
  patientSbp: 120,
  kalmanMap: 80.0,
  kalmanHr: 75.0,
  dMapDt: 0.0,
  alphaFloorState: 0, // 0=Nominal, 1=Soft Clamp, 2=Stall Emergency
  permissibleRate: 125.0,
  envSeqCtr: 148292,

  // BPE Biometrics (Engine 2 clearance)
  serumCr: 1.1,
  age: 65,
  sex: 'Male',
  weightKg: 84,
  egfr: 68.0,
  crcl: 64.5,
  
  // OCE Command Center (Engine 6 / Engine 3)
  escalationIndex: 0.345,
  edCensus: 32,
  edBays: 40,
  icuCensus: 18,
  icuBeds: 25,
  nursesOnDuty: 45,
  mandatedNurses: 45,
  activeOrs: 3,
  totalOrs: 10,
  supplyRatio: 0.95,

  // RTLS Bed State
  bedStep: 0, // 0..4
  
  // 128-Byte Tri-Plane Dual-Cache-Line Memory (Line 0: 64B, Line 1: 64B)
  seqCtr: 148292,
  bytes: new Uint8Array(128),
};

// -----------------------------------------------------------------------------
// Initialization
// -----------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
  initAmsvGrid();
  recalculateBiometrics();
  updateEscalationIndex();
  startKernelTicker();
  startRtlsBedLoop();
});

// -----------------------------------------------------------------------------
// Operating Regime Selection
// -----------------------------------------------------------------------------
function setRegime(regime) {
  state.regime = regime;
  document.querySelectorAll('.regime-btn').forEach(btn => btn.classList.remove('active'));
  
  if (regime === 'ROUTINE') {
    document.getElementById('regimeRoutineBtn').classList.add('active');
    state.escalationIndex = 0.345;
  } else if (regime === 'SURGE') {
    document.getElementById('regimeSurgeBtn').classList.add('active');
    state.escalationIndex = 0.580;
  } else if (regime === 'DISASTER') {
    document.getElementById('regimeDisasterBtn').classList.add('active');
    state.escalationIndex = 0.880;
  }
  updateEscalationIndex();
  syncAmsv();
}

// -----------------------------------------------------------------------------
// Engine 1 (ESE): CLSI C56-A Hemolysis Gate
// -----------------------------------------------------------------------------
function updateHemolysis(val) {
  state.hemolysisIndex = parseInt(val, 10);
  document.getElementById('hIndexDisplay').textContent = `${state.hemolysisIndex} mg/dL`;

  const kResultCard = document.getElementById('kResultCard');
  const kNumberDisplay = document.getElementById('kValDisplay');
  const kStatusBox = document.getElementById('gateStatusBox');
  const kStatusBadge = document.getElementById('kStatusPill');

  if (state.hemolysisIndex > 20) {
    kNumberDisplay.textContent = 'VOID (NaN)';
    kNumberDisplay.style.color = 'var(--color-crimson)';
    kStatusBadge.textContent = 'HEMOLYSIS VOID';
    kStatusBadge.style.color = 'var(--color-crimson)';
    kStatusBox.innerHTML = `
      <span class="status-indicator-tag red">CLSI C56-A VOID</span>
      <span class="status-sub text-danger">H-index > 20. Cardiac arrest prevention interlock active.</span>
    `;
    kResultCard.style.borderColor = 'var(--color-crimson)';
  } else {
    kNumberDisplay.textContent = `${state.potassiumVal.toFixed(2)} mmol/L`;
    kNumberDisplay.style.color = 'var(--color-cyan)';
    kStatusBadge.textContent = 'K+ VALID';
    kStatusBadge.style.color = 'var(--color-green)';
    kStatusBox.innerHTML = `
      <span class="status-indicator-tag green">Sample Valid</span>
      <span class="status-sub">Normal physiological electrolyte profile</span>
    `;
    kResultCard.style.borderColor = 'var(--border-subtle)';
  }
  syncAmsv();
}

// -----------------------------------------------------------------------------
// Engine 2 (Plane C): Dynamic Physiological Envelope & Alpha-Floor Protection
// -----------------------------------------------------------------------------
function updateMapTelemetry(val) {
  state.patientMap = parseInt(val, 10);
  document.getElementById('mapValDisplay').textContent = `${state.patientMap} mmHg`;
  evaluateEnvelope(0.1);
}

function simulateHemodynamicCrash() {
  document.getElementById('mapSlider').value = 42;
  updateMapTelemetry(42);
}

function restoreHemodynamicStability() {
  document.getElementById('mapSlider').value = 80;
  updateMapTelemetry(80);
}

function evaluateEnvelope(dt = 0.1) {
  // Simple discrete Kalman estimate simulation for client display
  const prevMap = state.kalmanMap;
  state.kalmanMap = Math.round((prevMap * 0.7 + state.patientMap * 0.3) * 10) / 10;
  state.dMapDt = Math.round(((state.kalmanMap - prevMap) / dt) * 10) / 10;

  const shockIndex = Math.round((state.patientHr / (state.patientMap * 1.35)) * 100) / 100;

  document.getElementById('kalmanMapDisplay').textContent = `${state.kalmanMap.toFixed(1)} mmHg`;
  document.getElementById('kalmanDmapDisplay').textContent = `d(MAP)/dt: ${state.dMapDt > 0 ? '+' : ''}${state.dMapDt.toFixed(1)} mmHg/s`;
  document.getElementById('shockIndexDisplay').textContent = `Shock Index: ${shockIndex}`;

  const envelopeCard = document.getElementById('alphaFloorCard');
  const alphaBadge = document.getElementById('alphaFloorStateBadge');
  const allowedRateDisplay = document.getElementById('allowedRateDisplay');

  // Alpha Floor Logic:
  if (state.kalmanMap < 55.0 || state.dMapDt < -2.0) {
    state.alphaFloorState = 2; // Hemodynamic Stall Emergency
    state.permissibleRate = 0.0;
    envelopeCard.classList.add('stall');
    alphaBadge.className = 'state-indicator locked';
    alphaBadge.textContent = 'ALPHA-FLOOR: STALL EMERGENCY';
    allowedRateDisplay.textContent = '0.0 mL/h (CLAMPED)';
    allowedRateDisplay.className = 'relay-status tripped';
  } else if (state.kalmanMap < 65.0 || shockIndex >= 1.0) {
    state.alphaFloorState = 1; // Soft Clamped
    state.permissibleRate = state.infusionRate * 0.5;
    envelopeCard.classList.remove('stall');
    alphaBadge.className = 'state-indicator caution';
    alphaBadge.textContent = 'ALPHA-FLOOR: ENVELOPE CLAMPED';
    allowedRateDisplay.textContent = `${state.permissibleRate.toFixed(1)} mL/h`;
    allowedRateDisplay.className = 'relay-status active';
  } else {
    state.alphaFloorState = 0; // Nominal
    state.permissibleRate = state.infusionRate;
    envelopeCard.classList.remove('stall');
    alphaBadge.className = 'state-indicator';
    alphaBadge.textContent = 'ALPHA-FLOOR: NOMINAL';
    allowedRateDisplay.textContent = `${state.permissibleRate.toFixed(1)} mL/h`;
    allowedRateDisplay.className = 'relay-status active';
  }

  // Update backend via POST if connected
  fetch('/api/envelope/step', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      raw_map_mmhg: state.patientMap,
      raw_hr_bpm: state.patientHr,
      raw_sbp_mmhg: state.patientMap * 1.35,
      requested_rate_ml_h: state.infusionRate,
      dt_seconds: dt,
    })
  }).catch(() => {});

  syncAmsv();
}

// -----------------------------------------------------------------------------
// Engine 1 Actuator Telemetry & Watchdog Trips
// -----------------------------------------------------------------------------
function updatePressure(val) {
  state.pressureMmhg = parseInt(val, 10);
  document.getElementById('pressureValDisplay').textContent = `${state.pressureMmhg} mmHg`;
  evaluateWatchdog();
}

function updateBubble(val) {
  state.bubbleSizeUl = parseInt(val, 10);
  document.getElementById('bubbleValDisplay').textContent = `${state.bubbleSizeUl} \u03bcL`;
  evaluateWatchdog();
}

function simulateOcclusionTrip() {
  document.getElementById('pressureSlider').value = 545;
  updatePressure(545);
}

function simulateAirBubbleTrip() {
  document.getElementById('bubbleSlider').value = 35;
  updateBubble(35);
}

function evaluateWatchdog() {
  const isOcclusion = state.pressureMmhg >= 525; // 10.2 psi
  const isBubble = state.bubbleSizeUl >= 25;      // 25 uL
  const isMetforminContra = state.egfr < 30.0;

  if (isOcclusion || isBubble || isMetforminContra) {
    triggerHardwareLockout(
      isOcclusion ? "OCCLUSION TRIP: Line pressure exceeded 525 mmHg (10.2 psi)" :
      isBubble ? "AIR BUBBLE TRIP: Ultrasonic sensor detected bubble >= 25 \u03bcL" :
      "PHARMA TRIP: Metformin contraindicated at eGFR < 30 mL/min/1.73m\u00b2"
    );
  } else if (state.pressureMmhg > 413) {
    setWatchdogCaution("CAUTION: Pressure approaching 8.0 psi soft boundary.");
  } else {
    resetWatchdog();
  }
}

function triggerHardwareLockout(reason) {
  state.watchdogState = 'LOCKED';
  state.ssrEnergized = false;
  state.mechRelayClosed = false;

  const card = document.getElementById('watchdogCard');
  const badge = document.getElementById('watchdogStateBadge');
  const ssr = document.getElementById('ssrStatus');
  const mech = document.getElementById('mechRelayStatus');
  const msg = document.getElementById('tripMessageBox');
  const pumpPill = document.getElementById('pumpRateDisplay');

  card.classList.add('locked');
  badge.className = 'state-indicator locked';
  badge.textContent = 'STATE 2: HARDWARE LOCKOUT';

  ssr.className = 'relay-status tripped';
  ssr.textContent = 'TRIPPED (2 ms)';
  mech.className = 'relay-status tripped';
  mech.textContent = 'OPEN (12 ms)';

  pumpPill.textContent = '0.0 mL/h (CUTOFF)';
  pumpPill.style.color = 'var(--color-crimson)';

  msg.textContent = `${reason}. Motor power de-energized. Safety air-gap active.`;
  msg.style.color = 'var(--color-crimson)';

  // Send to backend
  fetch('/api/kernel/step', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      pressure_mmhg: state.pressureMmhg,
      bubble_ul: state.bubbleSizeUl,
      h_index: state.hemolysisIndex,
      k_val: state.potassiumVal
    })
  }).catch(() => {});

  syncAmsv();
}

function setWatchdogCaution(reason) {
  state.watchdogState = 'CAUTION';
  const card = document.getElementById('watchdogCard');
  const badge = document.getElementById('watchdogStateBadge');
  const msg = document.getElementById('tripMessageBox');

  card.classList.remove('locked');
  badge.className = 'state-indicator caution';
  badge.textContent = 'STATE 1: CAUTION';
  msg.textContent = reason;
  msg.style.color = 'var(--color-amber)';
  syncAmsv();
}

function resetWatchdog() {
  state.watchdogState = 'NORMAL';
  state.ssrEnergized = true;
  state.mechRelayClosed = true;

  const card = document.getElementById('watchdogCard');
  const badge = document.getElementById('watchdogStateBadge');
  const ssr = document.getElementById('ssrStatus');
  const mech = document.getElementById('mechRelayStatus');
  const msg = document.getElementById('tripMessageBox');
  const pumpPill = document.getElementById('pumpRateDisplay');

  card.classList.remove('locked');
  badge.className = 'state-indicator';
  badge.textContent = 'STATE 0: NORMAL';

  ssr.className = 'relay-status active';
  ssr.textContent = 'ENERGIZED';
  mech.className = 'relay-status active';
  mech.textContent = 'CLOSED';

  pumpPill.textContent = `${state.permissibleRate.toFixed(1)} mL/h`;
  pumpPill.style.color = 'var(--color-cyan)';

  msg.textContent = 'All safety-critical interlocks active. No trip conditions detected.';
  msg.style.color = 'var(--text-muted)';
  syncAmsv();
}

// -----------------------------------------------------------------------------
// Engine 2 & 3: Biometrics, CKD-EPI 2021 & Metformin Check
// -----------------------------------------------------------------------------
function recalculateBiometrics() {
  const scr = parseFloat(document.getElementById('serumCrInput').value) || 1.1;
  const age = parseFloat(document.getElementById('patientAgeInput').value) || 65;
  const sex = document.getElementById('patientSexSelect').value;
  const weight = parseFloat(document.getElementById('patientWeightInput').value) || 84;

  state.serumCr = scr;
  state.age = age;
  state.sex = sex;
  state.weightKg = weight;

  const kappa = sex === 'Female' ? 0.7 : 0.9;
  const alpha = sex === 'Female' ? -0.241 : -0.302;
  const sexMult = sex === 'Female' ? 1.012 : 1.0;

  const ratio = scr / kappa;
  const minPart = Math.min(ratio, 1.0);
  const maxPart = Math.max(ratio, 1.0);

  const egfr = 142.0 * Math.pow(minPart, alpha) * Math.pow(maxPart, -1.200) * Math.pow(0.9938, age) * sexMult;
  state.egfr = Math.round(egfr * 10) / 10;

  document.getElementById('egfrPillDisplay').textContent = `eGFR: ${state.egfr} mL/min`;

  const ntiCard = document.getElementById('renalAlertBox');
  const resText = document.getElementById('renalResultText');
  const detText = document.getElementById('renalDetailText');

  if (state.egfr < 30.0) {
    ntiCard.className = 'renal-alert-box locked';
    resText.className = 'text-danger';
    resText.textContent = 'CONTRAINDICATED (eGFR < 30)';
    detText.textContent = 'ABSOLUTE LOCKOUT: Severe risk of fatal lactic acidosis.';
    triggerHardwareLockout('PHARMA TRIP: Metformin contraindicated at eGFR < 30 mL/min/1.73m\u00b2');
  } else if (state.egfr < 45.0) {
    ntiCard.className = 'renal-alert-box';
    resText.className = 'text-warning';
    resText.textContent = 'DOSE CLAMPED (eGFR 30-44)';
    detText.textContent = 'Dettli ceiling enforces 50% dose reduction (1000 mg/day max).';
  } else {
    ntiCard.className = 'renal-alert-box';
    resText.className = 'text-success';
    resText.textContent = 'SAFE (\u2265 45 mL/min/1.73m\u00b2)';
    detText.textContent = 'Standard dosing permitted (2000 mg/day max).';
  }
  syncAmsv();
}

// -----------------------------------------------------------------------------
// Engine 6 (OCE): Hospital Escalation Index
// -----------------------------------------------------------------------------
function updateEscalationIndex() {
  const edCrowd = (state.edCensus / state.edBays);
  const icuStrain = (state.icuCensus / state.icuBeds);
  const nurseDeficit = Math.max(0, 1 - (state.nursesOnDuty / state.mandatedNurses));
  const orBacklog = (state.activeOrs / state.totalOrs);
  const supplyDepletion = 1 - state.supplyRatio;

  const ei = (0.35 * edCrowd) + (0.25 * icuStrain) + (0.20 * nurseDeficit) + (0.10 * orBacklog) + (0.10 * supplyDepletion);
  state.escalationIndex = Math.min(1.5, Math.round(ei * 1000) / 1000);

  document.getElementById('eiPillDisplay').textContent = `E_I = ${state.escalationIndex}`;
  const pct = Math.min(100, (state.escalationIndex / 1.0) * 100);
  document.getElementById('eiProgressBar').style.width = `${pct}%`;

  document.getElementById('edCensusDisplay').textContent = `${state.edCensus} / ${state.edBays} Bays`;
  document.getElementById('icuCensusDisplay').textContent = `${state.icuCensus} / ${state.icuBeds} Beds`;
  document.getElementById('nurseRatioDisplay').textContent = `${state.nursesOnDuty} / ${state.mandatedNurses} Staffed`;
  document.getElementById('orCountDisplay').textContent = `${state.activeOrs} / ${state.totalOrs} Theaters`;
  syncAmsv();
}

function simulateSurgeScenario() {
  state.edCensus = 94;
  state.icuCensus = 25;
  state.nursesOnDuty = 24;
  state.activeOrs = 10;
  state.supplyRatio = 0.35;
  setRegime('DISASTER');
}

function triggerReverseTriageBatch() {
  alert("BioOS Reverse Triage (RTTL / Kelen Methodology):\n\nIdentified 14 stable inpatients with < 4.0% 48-hour mortality risk.\nExpedited early discharge initiated. 14 acute beds unlocked.");
  state.icuCensus = Math.max(12, state.icuCensus - 6);
  state.edCensus = Math.max(20, state.edCensus - 14);
  setRegime('SURGE');
}

// -----------------------------------------------------------------------------
// RTLS Bed Lifecycle Stepper
// -----------------------------------------------------------------------------
function startRtlsBedLoop() {
  const steps = ['stepOccupied', 'stepDirty', 'stepCleaning', 'stepInspected', 'stepAvailable'];
  setInterval(() => {
    state.bedStep = (state.bedStep + 1) % steps.length;
    steps.forEach((id, idx) => {
      const el = document.getElementById(id);
      if (idx === state.bedStep) {
        el.classList.add('active');
      } else {
        el.classList.remove('active');
      }
    });
  }, 2500);
}

// -----------------------------------------------------------------------------
// 128-Byte Tri-Plane Dual-Cache-Line Live Memory Visualizer
// -----------------------------------------------------------------------------
function initAmsvGrid() {
  const container = document.getElementById('amsvHexGrid');
  container.innerHTML = '';
  for (let i = 0; i < 128; i++) {
    const div = document.createElement('div');
    div.className = 'hex-byte';
    div.id = `hexByte${i}`;
    div.textContent = '00';
    
    // Cache Line 1 distinction
    if (i >= 64) {
      div.classList.add('line1');
    }

    // Highlight key offsets
    // Cache Line 0 (0..63)
    if (i < 8) div.classList.add('highlight-seq');
    else if (i >= 0x20 && i <= 0x23) div.classList.add('highlight-rate');
    else if (i >= 0x28 && i <= 0x2B) div.classList.add('highlight-press');
    else if (i >= 0x2E && i <= 0x2F) div.classList.add('highlight-crc');

    // Cache Line 1 (64..127)
    else if (i >= 64 && i < 72) div.classList.add('highlight-seq'); // env_seq_ctr
    else if (i >= 64 + 0x1C && i <= 64 + 0x1D) div.classList.add('highlight-env-map'); // est_map
    else if (i === 64 + 0x28) div.classList.add('highlight-alpha'); // alpha_floor_state

    container.appendChild(div);
  }
}

function syncAmsv() {
  state.seqCtr += 2;
  state.envSeqCtr += 2;
  document.getElementById('amsvSeqDisplay').textContent = state.seqCtr;
  const envSeqEl = document.getElementById('envSeqDisplay');
  if (envSeqEl) envSeqEl.textContent = state.envSeqCtr;

  // Cache Line 0 (Plane A Actuation)
  let s0 = BigInt(state.seqCtr);
  for (let i = 0; i < 8; i++) {
    state.bytes[i] = Number((s0 >> BigInt(i * 8)) & 0xFFn);
  }
  const rateFixed = Math.round(state.infusionRate * 10);
  state.bytes[0x20] = rateFixed & 0xFF;
  state.bytes[0x21] = (rateFixed >> 8) & 0xFF;

  state.bytes[0x28] = state.pressureMmhg & 0xFF;
  state.bytes[0x29] = (state.pressureMmhg >> 8) & 0xFF;
  state.bytes[0x30] = state.regime === 'ROUTINE' ? 0 : state.regime === 'SURGE' ? 1 : 2;

  // Cache Line 1 (Plane C Dynamic Envelope)
  let s1 = BigInt(state.envSeqCtr);
  for (let i = 0; i < 8; i++) {
    state.bytes[64 + i] = Number((s1 >> BigInt(i * 8)) & 0xFFn);
  }
  const mapFixed = Math.round(state.kalmanMap * 10);
  state.bytes[64 + 0x1C] = mapFixed & 0xFF;
  state.bytes[64 + 0x1D] = (mapFixed >> 8) & 0xFF;

  const hrFixed = Math.round(state.kalmanHr * 10);
  state.bytes[64 + 0x1E] = hrFixed & 0xFF;
  state.bytes[64 + 0x1F] = (hrFixed >> 8) & 0xFF;

  state.bytes[64 + 0x28] = state.alphaFloorState; // alpha_floor_state
  const permRateFixed = Math.round(state.permissibleRate * 10);
  state.bytes[64 + 0x10] = permRateFixed & 0xFF;
  state.bytes[64 + 0x11] = (permRateFixed >> 8) & 0xFF;

  // Update UI hex blocks
  for (let i = 0; i < 128; i++) {
    const el = document.getElementById(`hexByte${i}`);
    if (el) {
      el.textContent = state.bytes[i].toString(16).toUpperCase().padStart(2, '0');
    }
  }
}

function startKernelTicker() {
  setInterval(() => {
    state.seqCtr += 2;
    state.envSeqCtr += 2;
    document.getElementById('amsvSeqDisplay').textContent = state.seqCtr;
    const envSeqEl = document.getElementById('envSeqDisplay');
    if (envSeqEl) envSeqEl.textContent = state.envSeqCtr;
  }, 100);

  // Poll live backend for TriPlane data if available
  setInterval(async () => {
    try {
      const resp = await fetch('/api/amsv/triplane');
      if (resp.ok) {
        const data = await resp.json();
        if (data && data.cache_line_0_actuation) {
          const l0 = data.cache_line_0_actuation;
          const l1 = data.cache_line_1_envelope;
          document.getElementById('amsvCrcDisplay').textContent = l0.crc16.toUpperCase();
          if (l0.seq_ctr > 0) document.getElementById('amsvSeqDisplay').textContent = l0.seq_ctr;
          if (l1.env_seq_ctr > 0 && document.getElementById('envSeqDisplay')) {
            document.getElementById('envSeqDisplay').textContent = l1.env_seq_ctr;
          }
        }
      }
    } catch (e) {}
  }, 800);

  // Poll Wellbeing metrics every 2.5s
  setInterval(async () => {
    try {
      const resp = await fetch('/api/wellbeing/summary');
      if (resp.ok) {
        const wb = await resp.json();
        document.getElementById('avgCliDisplay').textContent = `${wb.average_cognitive_load_index} / 100`;
        document.getElementById('suppressedAlarmsDisplay').textContent = `${wb.total_alarms_suppressed_last_hour} / hr`;
        document.getElementById('wellbeingBadge').textContent = `COGNITIVE LOAD: ${wb.average_cognitive_load_index}`;
        
        const riskEl = document.getElementById('burnoutRiskDisplay');
        if (wb.clinicians_in_critical_burnout > 0) {
          riskEl.textContent = `${wb.clinicians_in_critical_burnout} Staff in Critical Burnout`;
          riskEl.className = 'wb-sub text-danger';
        } else {
          riskEl.textContent = 'Low Burnout Risk';
          riskEl.className = 'wb-sub text-success';
        }
      }
    } catch (e) {}
  }, 2500);
}

// -----------------------------------------------------------------------------
// Interactive Clinical Wellbeing & Nuisance Alarm Filter
// -----------------------------------------------------------------------------
async function testAlarmFilter(isMotionArtifact) {
  const logBox = document.getElementById('alarmFilterLog');
  logBox.textContent = 'Analyzing multi-sensor plethysmographic vectors...';
  
  const payload = isMotionArtifact 
    ? { spo2_drop: true, hr_variance: false, motion_detected: true }
    : { spo2_drop: true, hr_variance: true, motion_detected: false };

  try {
    const res = await fetch('/api/wellbeing/filter_alarm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    
    if (res.ok) {
      const data = await res.json();
      if (data.action === 'SUPPRESS_NUISANCE_ALARM') {
        logBox.innerHTML = `<strong>[FILTER SUCCESS]</strong> ${data.classification}: ${data.log_message} (Chime Suppressed)`;
        logBox.style.borderLeftColor = '#10b981';
        logBox.style.color = '#6ee7b7';
      } else {
        logBox.innerHTML = `<strong>[CRITICAL ALARM TRIGGERED]</strong> ${data.classification}: ${data.log_message} (Chime Sounding)`;
        logBox.style.borderLeftColor = '#e11d48';
        logBox.style.color = '#fda4af';
      }
    } else {
      fallbackFilterClient(isMotionArtifact);
    }
  } catch (err) {
    fallbackFilterClient(isMotionArtifact);
  }
}

function fallbackFilterClient(isMotionArtifact) {
  const logBox = document.getElementById('alarmFilterLog');
  if (isMotionArtifact) {
    logBox.innerHTML = `<strong>[FILTER SUCCESS]</strong> MOTION_ARTIFACT_TRANSDUCER_SLIP: Transient SpO2 probe artifact suppressed. Zero nurse disruption.`;
    logBox.style.borderLeftColor = '#10b981';
    logBox.style.color = '#6ee7b7';
  } else {
    logBox.innerHTML = `<strong>[CRITICAL ALARM TRIGGERED]</strong> GENUINE_HYPOXIA_CRISIS: Concordant SpO2 drop and autonomic HR response detected. Immediate bedside alarm sounding.`;
    logBox.style.borderLeftColor = '#e11d48';
    logBox.style.color = '#fda4af';
  }
}

// -----------------------------------------------------------------------------
// BioOS Microkernel Terminal Console Handler
// -----------------------------------------------------------------------------
const termHistory = [];
let historyIndex = -1;

async function runConsoleCommand(cmd) {
  const termBody = document.getElementById('termOutputBody');
  const trimmed = cmd.trim();
  if (!trimmed) return;

  if (trimmed.toLowerCase() === 'clear') {
    termBody.innerHTML = '<div class="term-line welcome-text">BioOS Console cleared. Type \'help\' for available commands.</div>';
    return;
  }

  // Echo command
  const cmdLine = document.createElement('div');
  cmdLine.className = 'term-line cmd-echo';
  cmdLine.textContent = `> admin@bioos-core:~$ ${trimmed}`;
  termBody.appendChild(cmdLine);

  try {
    const res = await fetch('/api/os/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command: trimmed })
    });
    if (res.ok) {
      const data = await res.json();
      const outLine = document.createElement('div');
      outLine.className = 'term-line';
      outLine.textContent = data.output;
      termBody.appendChild(outLine);
    } else {
      const errLine = document.createElement('div');
      errLine.className = 'term-line text-danger';
      errLine.textContent = `Error executing '${trimmed}': Server returned HTTP ${res.status}`;
      termBody.appendChild(errLine);
    }
  } catch (err) {
    const errLine = document.createElement('div');
    errLine.className = 'term-line text-danger';
    errLine.textContent = `Connection error executing '${trimmed}': ${err.message}`;
    termBody.appendChild(errLine);
  }

  termBody.scrollTop = termBody.scrollHeight;
}

function submitTermInput() {
  const inputEl = document.getElementById('termInput');
  const val = inputEl.value.trim();
  if (val) {
    termHistory.push(val);
    historyIndex = termHistory.length;
    runConsoleCommand(val);
    inputEl.value = '';
  }
}

function handleTermKey(e) {
  const inputEl = document.getElementById('termInput');
  if (e.key === 'Enter') {
    submitTermInput();
  } else if (e.key === 'ArrowUp') {
    if (termHistory.length > 0 && historyIndex > 0) {
      historyIndex--;
      inputEl.value = termHistory[historyIndex];
    }
  } else if (e.key === 'ArrowDown') {
    if (historyIndex < termHistory.length - 1) {
      historyIndex++;
      inputEl.value = termHistory[historyIndex];
    } else {
      historyIndex = termHistory.length;
      inputEl.value = '';
    }
  }
}

// =============================================================================
// Enterprise Multi-Station View Switcher
// =============================================================================
function switchView(viewName) {
  // Tab buttons
  const tabs = {
    'BED_BOARD': 'tabBedBoard',
    'BEDSIDE_DECK': 'tabBedsideDeck',
    'PHARMACY': 'tabPharmacy',
    'WORKFORCE': 'tabWorkforce',
    'EARLY_WARNING': 'tabEarlyWarning',
    'TERMINAL': 'tabTerminal'
  };

  // Section views
  const views = {
    'BED_BOARD': 'viewBedBoard',
    'BEDSIDE_DECK': 'viewBedsideDeck',
    'PHARMACY': 'viewPharmacy',
    'WORKFORCE': 'viewWorkforce',
    'EARLY_WARNING': 'viewEarlyWarning',
    'TERMINAL': 'viewTerminal'
  };

  for (const [key, tabId] of Object.entries(tabs)) {
    const tabEl = document.getElementById(tabId);
    if (tabEl) {
      if (key === viewName) {
        tabEl.classList.add('active');
      } else {
        tabEl.classList.remove('active');
      }
    }
  }

  for (const [key, viewId] of Object.entries(views)) {
    const viewEl = document.getElementById(viewId);
    if (viewEl) {
      if (key === viewName) {
        viewEl.classList.add('active-view');
      } else {
        viewEl.classList.remove('active-view');
      }
    }
  }

  if (viewName === 'BED_BOARD') {
    fetchHospitalWards();
  } else if (viewName === 'PHARMACY') {
    fetchPharmacySurveillance();
  } else if (viewName === 'WORKFORCE') {
    fetchWorkforceRoster();
  } else if (viewName === 'EARLY_WARNING') {
    fetchEarlyWarning();
  }
}

// =============================================================================
// Master Bed Board & Hospital Floor Plan
// =============================================================================
let currentSelectedBedId = "ICU-A-01";

async function fetchHospitalWards() {
  try {
    const [wardsRes, topoRes] = await Promise.all([
      fetch('/api/hospital/wards'),
      fetch('/api/hospital/topology')
    ]);

    if (topoRes.ok) {
      const topo = await topoRes.json();
      document.getElementById('censusOccupied').textContent = topo.occupied_beds;
      document.getElementById('censusAvailable').textContent = topo.available_ready_beds;
      document.getElementById('censusCleaning').textContent = topo.dirty_turnover_beds;
      document.getElementById('censusEi').textContent = topo.escalation_index;
    }

    if (wardsRes.ok) {
      const wards = await wardsRes.json();
      renderWardsContainer(wards);
    }
  } catch (err) {
    console.error("Error fetching hospital wards:", err);
  }
}

function renderWardsContainer(wards) {
  const container = document.getElementById('wardsGridContainer');
  if (!container) return;

  container.innerHTML = '';

  wards.forEach(w => {
    const panel = document.createElement('div');
    panel.className = 'ward-panel';

    const header = document.createElement('div');
    header.className = 'ward-panel-header';
    header.innerHTML = `
      <div class="ward-title-group">
        <span class="ward-name">${w.name}</span>
        <span class="ward-meta-chip">Floor ${w.floor}</span>
        <span class="ward-meta-chip">Type: ${w.ward_type}</span>
      </div>
      <div class="ward-title-group">
        <span class="ward-meta-chip">Census: <strong>${w.occupied} / ${w.capacity}</strong> (${w.occupancy_pct}%)</span>
        <span class="ward-meta-chip ${w.in_staffing_ratio ? 'text-success' : 'text-danger'}">
          RN Staff: <strong>${w.staffed_nurses}</strong> (Req: ${w.required_nurses}) &bull; ${w.in_staffing_ratio ? 'IN RATIO' : 'SHORT STAFFED'}
        </span>
      </div>
    `;
    panel.appendChild(header);

    const bedsGrid = document.createElement('div');
    bedsGrid.className = 'ward-beds-grid';

    w.beds.forEach(b => {
      const bedCard = document.createElement('div');
      const isSelected = (b.bed_id === currentSelectedBedId);
      const occClass = b.is_occupied ? 'occupied' : (b.status === 'AVAILABLE' ? 'available' : 'dirty');
      bedCard.className = `bed-card ${occClass} ${isSelected ? 'selected-bed' : ''}`;
      bedCard.onclick = () => selectBed(b.bed_id);

      let innerHtml = `
        <div class="bed-card-header">
          <span class="bed-number">${b.bed_number}</span>
          <span class="bed-status-pill ${occClass}">${b.status}</span>
        </div>
      `;

      if (b.patient) {
        const p = b.patient;
        innerHtml += `
          <div class="bed-patient-name">${p.name} (${p.age}${p.sex})</div>
          <div class="bed-patient-diag">${p.diagnosis}</div>
          <div class="bed-vitals-row">
            <span class="bed-vital-item">MAP: <strong>${p.vitals.map}</strong></span>
            <span class="bed-vital-item">HR: <strong>${p.vitals.hr}</strong></span>
            <span class="bed-vital-item">SpO2: <strong>${p.vitals.spo2}%</strong></span>
          </div>
          <div class="bed-actions-row">
            <button class="bed-btn-sm" onclick="event.stopPropagation(); selectBed('${b.bed_id}'); switchView('BEDSIDE_DECK');">Flight Deck</button>
            <button class="bed-btn-sm" onclick="event.stopPropagation(); dischargePatient('${p.patient_id}');">Discharge</button>
          </div>
        `;
      } else {
        innerHtml += `
          <div class="bed-patient-name text-muted">${b.status === 'AVAILABLE' ? 'Ready for Inflow' : 'EVS Terminal Cleaning'}</div>
          <div class="bed-patient-diag">${b.is_negative_pressure ? `AIIR Negative Pressure (${b.hvac_pa} Pa)` : 'Standard Pressure Pod'}</div>
          <div class="bed-actions-row">
            <button class="bed-btn-sm" onclick="event.stopPropagation(); quickAdmitPrompt('${w.ward_id}', '${b.bed_id}');">Admit Patient</button>
          </div>
        `;
      }

      bedCard.innerHTML = innerHtml;
      bedsGrid.appendChild(bedCard);
    });

    panel.appendChild(bedsGrid);
    container.appendChild(panel);
  });
}

async function selectBed(bedId) {
  currentSelectedBedId = bedId;
  const footerEl = document.getElementById('footerBoundBed');
  if (footerEl) footerEl.textContent = bedId;

  try {
    const res = await fetch('/api/hospital/select_bed', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bed_id: bedId })
    });
    if (res.ok) {
      const data = await res.json();
      if (data.patient) {
        const p = data.patient;
        document.getElementById('bannerBedId').textContent = bedId;
        document.getElementById('bannerPatientName').textContent = `${p.name} (Age ${p.age} ${p.sex})`;
        document.getElementById('bannerDiagnosis').textContent = p.diagnosis;
        document.getElementById('bannerEsi').textContent = `${p.esi_triage_score} (${p.esi_triage_score === 1 ? 'Critical' : 'Acute'})`;
        document.getElementById('bannerEsi').className = `esi-chip esi-${p.esi_triage_score}`;
        document.getElementById('bannerMap').textContent = `${p.mean_arterial_pressure} mmHg`;
        const infNames = p.active_infusions.map(i => i.drug).join(', ') || 'None';
        document.getElementById('bannerInfusions').textContent = infNames;

        // Sync local flight deck controls to selected patient
        state.patientMap = p.mean_arterial_pressure;
        state.kalmanMap = p.mean_arterial_pressure;
        state.potassiumVal = p.potassium_meq_l;
        state.serumCr = p.serum_creatinine;
        state.egfr = p.egfr;
        updateMapTelemetry(p.mean_arterial_pressure);
        updatePotassium(p.potassium_meq_l);
        updateCreatinine(p.serum_creatinine);
      } else {
        document.getElementById('bannerBedId').textContent = bedId;
        document.getElementById('bannerPatientName').textContent = 'Bed Unoccupied';
        document.getElementById('bannerDiagnosis').textContent = 'Available for Admission';
        document.getElementById('bannerMap').textContent = '--';
        document.getElementById('bannerInfusions').textContent = 'None';
      }
    }
  } catch (err) {
    console.error("Error selecting bed:", err);
  }

  fetchHospitalWards();
}

async function dischargePatient(patientId) {
  if (!confirm(`Confirm discharge order for Patient ${patientId}? Bed will immediately cycle to DIRTY and dispatch EVS cleaning.`)) return;

  try {
    const res = await fetch('/api/hospital/discharge', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ patient_id: patientId })
    });
    if (res.ok) {
      const data = await res.json();
      alert(data.message);
      fetchHospitalWards();
    }
  } catch (err) {
    console.error("Discharge error:", err);
  }
}

async function quickAdmitPrompt(wardId, bedId) {
  const name = prompt(`Enter patient full name to admit into ${bedId}:`, "Alex Morgan");
  if (!name) return;
  const diag = prompt("Enter primary admission diagnosis:", "Acute Sepsis / Hypotension");
  if (!diag) return;

  try {
    const res = await fetch('/api/hospital/admit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: name,
        diagnosis: diag,
        ward_id: wardId,
        bed_id: bedId,
        age: 62,
        sex: "M",
        esi: 2
      })
    });
    if (res.ok) {
      const data = await res.json();
      alert(data.message);
      selectBed(bedId);
    }
  } catch (err) {
    console.error("Admit error:", err);
  }
}

// =============================================================================
// Pharmacy & NTI Surveillance
// =============================================================================
async function fetchPharmacySurveillance() {
  try {
    const res = await fetch('/api/pharmacy/surveillance');
    if (res.ok) {
      const data = await res.json();
      document.getElementById('pharmActiveCount').textContent = `${data.total_active_infusions} Infusions`;
      document.getElementById('pharmDdiCount').textContent = `${data.active_ddi_alerts.length} Active Flag(s)`;

      const tbody = document.getElementById('pharmInfusionsBody');
      tbody.innerHTML = '';
      data.infusions.forEach(inf => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><strong class="text-info">${inf.bed}</strong></td>
          <td>${inf.patient_name}</td>
          <td><strong class="text-warning">${inf.drug}</strong></td>
          <td>${inf.rate || 'Standard'}</td>
          <td>${inf.target || 'Physiological Target'}</td>
          <td><span class="status-dot green"></span> DERS Locked</td>
        `;
        tbody.appendChild(tr);
      });

      const ddiContainer = document.getElementById('pharmDdiBody');
      ddiContainer.innerHTML = '';
      if (data.active_ddi_alerts.length === 0) {
        ddiContainer.innerHTML = '<div class="stat-pill text-success">No active drug-drug interaction warnings detected.</div>';
      } else {
        data.active_ddi_alerts.forEach(ddi => {
          const card = document.createElement('div');
          card.className = 'ddi-alert-card';
          card.innerHTML = `
            <strong>[${ddi.severity}] ${ddi.patient_name}</strong>
            <p>${ddi.message}</p>
          `;
          ddiContainer.appendChild(card);
        });
      }
    }
  } catch (err) {
    console.error("Pharmacy surveillance error:", err);
  }
}

// =============================================================================
// Workforce & Staff Wellbeing
// =============================================================================
async function fetchWorkforceRoster() {
  try {
    const [wardsRes, wbRes] = await Promise.all([
      fetch('/api/hospital/wards'),
      fetch('/api/wellbeing/summary')
    ]);

    if (wardsRes.ok) {
      const wards = await wardsRes.json();
      const ubody = document.getElementById('workforceUnitsBody');
      ubody.innerHTML = '';
      wards.forEach(w => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><strong>${w.name}</strong></td>
          <td>${w.occupied} / ${w.capacity}</td>
          <td>${w.staffed_nurses} RNs</td>
          <td>${w.required_nurses} RNs</td>
          <td><span class="status-dot ${w.in_staffing_ratio ? 'green' : 'red'}"></span> ${w.in_staffing_ratio ? 'COMPLIANT' : 'SHORT-STAFFED'}</td>
        `;
        ubody.appendChild(tr);
      });
    }

    if (wbRes.ok) {
      const wb = await wbRes.json();
      const cbody = document.getElementById('workforceCliniciansTable');
      const tbody = document.getElementById('workforceCliniciansBody');
      tbody.innerHTML = '';
      wb.clinicians.forEach(c => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><strong>${c.name}</strong> (${c.clinician_id})</td>
          <td>${c.role}</td>
          <td>${c.shift_hours_elapsed} hrs</td>
          <td>${c.active_patients_count} Patients</td>
          <td><strong class="${c.cognitive_load_index > 80 ? 'text-danger' : 'text-success'}">${c.cognitive_load_index}</strong> / 100</td>
          <td><span class="${c.assignment_locked ? 'badge-lock' : 'status-dot green'}">${c.assignment_locked ? 'LOCKED' : 'AVAILABLE'}</span></td>
        `;
        tbody.appendChild(tr);
      });
    }
  } catch (err) {
    console.error("Workforce error:", err);
  }
}

// Initialize Master Bed Board on startup
fetchHospitalWards();
setInterval(() => {
  fetchHospitalWards();
}, 4000);

// =============================================================================
// Clinical Early Warning (NEWS2) — deterioration trajectories
// =============================================================================
let ewsAlertSeen = 0;

async function fetchEarlyWarning() {
  try {
    const res = await fetch('/api/clinical/news2');
    if (!res.ok) return;
    const data = await res.json();

    document.getElementById('ewsMonitoredCount').textContent = `${data.patients.length} Patients`;
    document.getElementById('ewsLowChip').textContent = `LOW: ${data.band_counts.LOW || 0}`;
    document.getElementById('ewsMediumChip').textContent = `MEDIUM: ${data.band_counts.MEDIUM || 0}`;
    document.getElementById('ewsHighChip').textContent = `HIGH: ${data.band_counts.HIGH || 0}`;

    const totalObs = data.patients.reduce((sum, p) => sum + (p.trend_observations || 0), 0);
    document.getElementById('ewsTrendObsCount').textContent = `${totalObs} Trend Obs`;

    const tbody = document.getElementById('ewsPatientsBody');
    tbody.innerHTML = '';
    if (data.patients.length === 0) {
      tbody.innerHTML = '<tr><td colspan="6">Census empty.</td></tr>';
      return;
    }
    data.patients.forEach(p => {
      const bandClass = p.clinical_risk === 'HIGH' ? 'text-danger'
        : p.clinical_risk === 'MEDIUM' ? 'text-warning' : 'text-success';
      const escalated = p.escalation !== p.clinical_risk ? ` &rarr; ${p.escalation}` : '';
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><strong class="text-info">${p.bed_id || '—'}</strong></td>
        <td>${p.name}</td>
        <td>${p.ward_id}</td>
        <td><strong>${p.total_score}</strong></td>
        <td class="${bandClass}">${p.clinical_risk}${escalated}</td>
        <td>${p.trend_observations || 0}</td>
      `;
      tbody.appendChild(tr);
    });

    // Keep the observation form's patient selector in sync
    const select = document.getElementById('ewsPatientSelect');
    const current = select.value;
    select.innerHTML = '';
    data.patients.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.patient_id;
      opt.textContent = `${p.bed_id || 'NO BED'} — ${p.name} (NEWS2 ${p.total_score})`;
      select.appendChild(opt);
    });
    if (current) select.value = current;
  } catch (err) {
    console.error("Early warning fetch error:", err);
  }
}

async function submitNews2Observation() {
  const patientId = document.getElementById('ewsPatientSelect').value;
  const resultBox = document.getElementById('ewsResultBox');
  if (!patientId) {
    resultBox.textContent = 'Select a patient first.';
    return;
  }
  const payload = {};
  const numericFields = {
    respiration_rate: 'ewsRR',
    spo2_percent: 'ewsSpO2',
    systolic_bp_mmhg: 'ewsSBP',
    pulse_bpm: 'ewsPulse',
    temperature_c: 'ewsTemp',
  };
  Object.entries(numericFields).forEach(([key, elId]) => {
    const raw = document.getElementById(elId).value;
    if (raw !== '') payload[key] = parseFloat(raw);
  });
  payload.spo2_scale = parseInt(document.getElementById('ewsScale').value, 10);
  payload.on_supplemental_oxygen = document.getElementById('ewsO2').checked;
  // Checkbox label is "New CVPU (not Alert)": CHECKED means the patient is
  // NOT alert, so is_alert must be the negation. (H-11 override semantics.)
  payload.is_alert = !document.getElementById('ewsAlertState').checked;

  try {
    const res = await fetch(`/api/clinical/news2/${patientId}/observation`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) {
      resultBox.textContent = `REJECTED: ${data.error || 'observation failed'}`;
      return;
    }
    const alerts = data.trend_alerts || [];
    const bandClass = data.clinical_risk === 'HIGH' ? 'text-danger'
      : data.clinical_risk === 'MEDIUM' ? 'text-warning' : 'text-success';
    const defaulted = Object.values(data.defaults_used || {}).filter(Boolean).length;
    resultBox.innerHTML = `OBSERVED: NEWS2 <strong>${data.total_score}</strong> — ` +
      `<span class="${bandClass}">${data.clinical_risk}</span>` +
      ` | escalation: ${data.escalation}` +
      ` | defaulted fields: ${defaulted || 'none'}` +
      (alerts.length ? ` | &#9888; ${alerts.map(a => a.type).join(', ')}` : '');
    appendEwsAlertFeed(alerts, patientId);
    fetchEarlyWarning();
  } catch (err) {
    resultBox.textContent = `ERROR: ${err.message}`;
  }
}

function appendEwsAlertFeed(alerts, patientId) {
  if (!alerts.length) return;
  const feed = document.getElementById('ewsAlertFeed');
  const emptyNote = feed.querySelector('.text-success');
  if (emptyNote) feed.innerHTML = '';
  alerts.forEach(a => {
    ewsAlertSeen += 1;
    const card = document.createElement('div');
    card.className = 'ddi-alert-card';
    card.innerHTML = `<strong>[${a.type}] ${patientId} — NEWS2 ${a.latest_score}</strong><p>${a.message}</p>`;
    feed.prepend(card);
  });
  document.getElementById('ewsAlertCount').textContent = `${ewsAlertSeen} Alerts (session)`;
}

// =============================================================================
// Bedside Deck Interaction Functions (were missing - sliders/buttons were dead)
// =============================================================================
function updatePotassium(val) {
  state.potassiumVal = parseFloat(val);
  document.getElementById('kValDisplay').textContent = state.potassiumVal.toFixed(2) + ' mEq/L';
  updateHemolysis(state.hemolysisIndex);
}

function updateHIndex(val) {
  updateHemolysis(val);
}

function updateCreatinine(val) {
  state.serumCr = parseFloat(val);
  document.getElementById('crValDisplay').textContent = state.serumCr.toFixed(1) + ' mg/dL';
  const crInput = document.getElementById('serumCrInput');
  if (crInput) crInput.value = state.serumCr.toFixed(1);
  recalculateBiometrics();
}

function updateHrTelemetry(val) {
  state.patientHr = parseInt(val, 10);
  document.getElementById('hrValDisplay').textContent = state.patientHr + ' BPM';
  evaluateEnvelope(0.1);
}

function simulateHemodynamicStall() {
  simulateHemodynamicCrash();
}

function recoverFromStall() {
  restoreHemodynamicStability();
}

function triggerOcclusionTrip() {
  simulateOcclusionTrip();
}

function triggerBubbleTrip() {
  simulateAirBubbleTrip();
}

function resetActuator() {
  document.getElementById('pressureSlider').value = 180;
  document.getElementById('bubbleSlider').value = 0;
  updatePressure(180);
  updateBubble(0);
}
