// BioOS Flight Deck Reactive Application Engine
// Standard Compliance: IEC 62304 Class C, ASTM F2761, ISO/IEEE 11073 SDC
// Tri-Plane Aerospace Architecture: Engine 1 (Actuation) + Engine 2 (Kalman Envelope) + Engine 3 (Cognitive FMS)

let hospitalApiConnected = false;

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
  initRoboticsView();
  initHospitalExplorer();
  setRegime('ROUTINE');
});

// =============================================================================
// Digital hospital rooms and equipment catalog
// =============================================================================
const hospitalRooms = {
  operating: {
    label: 'OPERATING ROOM', kicker: 'OPERATING ROOM', title: 'Surgical guidance', model: 'models/equipment/surgical-robot.glb', alt: 'Interactive patient-side surgical robot model',
    modelName: 'Patient-side surgical robot', modelNote: 'SimReady USD converted to GLB · interactive 3D', format: 'GLB · browser ready', connection: '3D model · no live device feed',
    description: 'Relate anatomy and instrument guidance to BioOS’s safety workflow. The current view is an interactive model, not a live surgical camera.',
    workflow: 'Surgical safety', workflowDescription: 'View the surgical guidance console and virtual fixture demonstration.', action: 'Open surgical guidance', view: 'ROBOTICS'
  },
  bedside: {
    label: 'BEDSIDE CARE', kicker: 'BEDSIDE CARE', title: 'Bedside monitoring & patient safety', model: 'models/equipment/hospital-bed.glb', alt: 'Interactive 3D model of the hospital bedside setup with patient bed and monitor',
    modelName: 'Hospital bed & patient monitor', modelNote: 'Separate bedside models · SimReady USD converted to GLB', format: 'Bedside GLB models · browser ready', connection: '3D models · no live device feed',
    description: 'A separate bedside view for the hospital bed, patient monitor, and bedside devices. Models are illustrative; they do not stream measurements or control equipment.',
    workflow: 'Bedside safety checks', workflowDescription: 'Explore patient context, simulated vitals, and safety guard demonstrations.', action: 'Open patient safety', view: 'BEDSIDE_DECK'
  },
  monitoring: {
    label: 'VITALS & EARLY WARNING', kicker: 'MONITORING STATION', title: 'Patient monitoring', model: '', alt: 'Interactive monitoring station model',
    modelName: 'Monitoring station', modelNote: 'Select an available model from this station’s catalog.', format: 'Choose an available catalog model', connection: '3D model · no live device feed',
    description: 'Review observation capture and early warning trends. Values shown in the workspace may be demo defaults until a supported data feed is configured.',
    workflow: 'Early warning review', workflowDescription: 'Review NEWS2 observations and advisory deterioration trends.', action: 'Open early warning', view: 'EARLY_WARNING'
  },
  sterile: {
    label: 'EQUIPMENT READINESS', kicker: 'STERILE PROCESSING', title: 'Hospital operations', model: '', alt: 'Sterile equipment catalog preview',
    modelName: 'Sterile equipment', modelNote: 'Choose an available model from this room’s equipment catalog.', format: 'Select a converted GLB asset', connection: '3D model · no live device feed',
    description: 'Explore the operational context around equipment, bed capacity, and workforce readiness. These catalog models are not asset-tracking feeds.',
    workflow: 'Capacity & readiness', workflowDescription: 'Open the hospital bed board and explore capacity and turnover workflows.', action: 'Open hospital overview', view: 'BED_BOARD'
  }
};

const equipmentCatalog = [
  { category: 'SURGICAL SYSTEMS', name: 'Patient-side surgical robot', asset: 'robotic_system_a01', format: 'USD → GLB', room: 'operating', description: 'Operating-room surgical robot', view: 'ROBOTICS', model: 'models/equipment/surgical-robot.glb', available: true },
  { category: 'SURGICAL SYSTEMS', name: 'Surgeon console', asset: 'robotic_system_console_b01', format: 'USD → GLB', room: 'operating', description: 'Operating-room master teleoperation cockpit', view: 'ROBOTICS', model: 'models/equipment/surgeon-console.glb', available: true },
  { category: 'SURGICAL SYSTEMS', name: 'Robotic arm system', asset: 'raise_a3_ultra_t3d0', format: 'USD', room: 'operating', description: 'Articulated robotics system', view: 'ROBOTICS' },
  { category: 'SURGICAL SYSTEMS', name: 'Surgical robot concept', asset: 'Meshy surgical robot', format: 'FBX', room: 'operating', description: 'Textured multi-arm model', view: 'ROBOTICS' },
  { category: 'OR EQUIPMENT', name: 'Anesthesia machine', asset: 'anesthesia_machine_a01', format: 'USD', room: 'operating', description: 'Anesthesia workstation', view: 'ROBOTICS' },
  { category: 'OR EQUIPMENT', name: 'Endoscopy video tower', asset: 'video_system_a01', format: 'USD', room: 'operating', description: 'Laparoscopic imaging tower', view: 'ROBOTICS' },
  { category: 'OR EQUIPMENT', name: 'Surgical suction pump', asset: 'pump_suction_surgical_a01', format: 'USD', room: 'operating', description: 'Mobile suction equipment', view: 'ROBOTICS' },
  { category: 'OR EQUIPMENT', name: 'Fluid drainage pump', asset: 'drainage_pumpSystem_a01', format: 'USD', room: 'operating', description: 'Fluid drainage system', view: 'ROBOTICS' },
  { category: 'OR EQUIPMENT', name: 'Imaging contrast injector', asset: 'sm_CT_injection_system_a01_01', format: 'USD', room: 'operating', description: 'CT contrast delivery system', view: 'ROBOTICS' },
  { category: 'PATIENT MONITORING', name: 'Patient monitor', asset: 'monitor_patient_a01', format: 'USD → GLB', room: 'bedside', description: 'Multi-parameter bedside monitor', view: 'EARLY_WARNING', model: 'models/equipment/patient-monitor.glb', available: true },
  { category: 'PATIENT MONITORING', name: 'Portable vitals pad', asset: 'pad_vital_a01', format: 'USD', room: 'monitoring', description: 'Portable vital signs device', view: 'EARLY_WARNING' },
  { category: 'PATIENT MONITORING', name: 'Vein finder', asset: 'device_vein_finder_a01', format: 'USD', room: 'bedside', description: 'Infrared vein visualization', view: 'BEDSIDE_DECK' },
  { category: 'PATIENT MONITORING', name: 'Blood line', asset: 'blood_line_a02', format: 'USD', room: 'bedside', description: 'IV and dialysis line', view: 'PHARMACY' },
  { category: 'PATIENT MONITORING', name: 'Inhaler', asset: 'device_inhaler_a01', format: 'USD', room: 'bedside', description: 'Respiratory medication device', view: 'PHARMACY' },
  { category: 'PATIENT MONITORING', name: 'Glucose lancing device', asset: 'device_insulin_lancing_a01', format: 'USD', room: 'bedside', description: 'Point-of-care glucose accessory', view: 'PHARMACY' },
  { category: 'PATIENT MONITORING', name: 'Nebulizer mask', asset: 'mask_nebulization_a01', format: 'USD', room: 'bedside', description: 'Nebulizer patient interface', view: 'BEDSIDE_DECK' },
  { category: 'CARE ENVIRONMENT', name: 'Hospital bed', asset: 'bed_hospital_standard_a01', format: 'USD → GLB', room: 'bedside', description: 'Articulated patient bed', view: 'BED_BOARD', model: 'models/equipment/hospital-bed.glb', available: true },
  { category: 'CARE ENVIRONMENT', name: 'Clinical workstation desk', asset: 'desk_a01', format: 'USD', room: 'monitoring', description: 'Clinical workstation furniture', view: 'WORKFORCE' },
  { category: 'CARE ENVIRONMENT', name: 'Privacy screen', asset: 'screen_hospital_b03', format: 'USD', room: 'bedside', description: 'Mobile care-space divider', view: 'BED_BOARD' },
  { category: 'CARE ENVIRONMENT', name: 'Sterilization containers', asset: 'container_system_sterilising_b02', format: 'USD', room: 'sterile', description: 'Reusable instrument trays', view: 'WORKFORCE' },
  { category: 'ANATOMY', name: 'Visceral anatomy', asset: 'a-fully-anatomy-stomach-lungs-heart', format: 'GLB', room: 'operating', description: 'Interactive browser model', view: 'ROBOTICS', available: true },
  { category: 'ANATOMY', name: 'Human heart', asset: 'human-heart', format: 'OBJ', room: 'monitoring', description: 'High-resolution mesh', view: 'EARLY_WARNING' }
];

const selectedEquipmentByRoom = { operating: 'robotic_system_a01', bedside: 'bed_hospital_standard_a01' };

function preferredRoomModel(roomId) {
  const selectedAsset = selectedEquipmentByRoom[roomId];
  const selectedItem = equipmentCatalog.find((item) => item.asset === selectedAsset && item.room === roomId && item.available);
  if (selectedItem) return selectedItem;
  const priorities = {
    operating: ['robotic_system_a01', 'robotic_system_console_b01', 'raise_a3_ultra_t3d0', 'Meshy surgical robot', 'anesthesia_machine_a01', 'video_system_a01', 'pump_suction_surgical_a01', 'drainage_pumpSystem_a01', 'sm_CT_injection_system_a01_01'],
    bedside: ['bed_hospital_standard_a01', 'monitor_patient_a01', 'device_vein_finder_a01', 'pad_vital_a01', 'mask_nebulization_a01', 'blood_line_a02', 'device_inhaler_a01'],
    monitoring: ['pad_vital_a01', 'human-heart', 'desk_a01'],
    sterile: ['container_system_sterilising_b02', 'screen_hospital_b03'],
  };
  const priority = priorities[roomId] || [];
  return priority.map((asset) => equipmentCatalog.find((item) => item.asset === asset))
    .find((item) => item && item.available) || null;
}

function renderBedsideModels() {
  const viewer = document.getElementById('roomModelViewer');
  const placeholder = document.getElementById('modelPlaceholder');
  if (!viewer) return;
  viewer.setAttribute('camera-orbit', '0deg 68deg 5.5m');
  viewer.setAttribute('field-of-view', '30deg');
  viewer.setAttribute('auto-rotate', '');
  viewer.alt = 'Interactive hospital bedside scene with a hospital bed and patient monitor';
  const bedsideStatus = document.getElementById('bedsideModelStatus');
  const bedsideBed = document.getElementById('bedsideBedModel');
  const bedsideMonitor = document.getElementById('bedsideMonitorModel');
  const roomItem = preferredRoomModel('bedside');
  if (!roomItem) return;
  if (placeholder) placeholder.hidden = true;
  if (bedsideStatus) bedsideStatus.hidden = false;
  const bedItem = equipmentCatalog.find((item) => item.asset === 'bed_hospital_standard_a01');
  const monitorItem = equipmentCatalog.find((item) => item.asset === 'monitor_patient_a01');
  if (bedsideBed) bedsideBed.disabled = !bedItem?.available;
  if (bedsideMonitor) bedsideMonitor.disabled = !monitorItem?.available;
  const showingBed = selectedEquipmentByRoom.bedside === 'bed_hospital_standard_a01';
  if (bedsideBed) bedsideBed.classList.toggle('active', showingBed);
  if (bedsideMonitor) bedsideMonitor.classList.toggle('active', !showingBed);
}

function initHospitalExplorer() {
  const catalog = document.getElementById('catalogGrid');
  if (catalog) {
    const groups = [...new Set(equipmentCatalog.map((item) => item.category))];
    catalog.innerHTML = groups.map((group) => `<section class="catalog-group"><h4>${group}</h4>${equipmentCatalog.filter((item) => item.category === group).map((item) => {
      const isReady = Boolean(item.available);
      return `<button class="catalog-item ${isReady ? 'catalog-available' : ''}" onclick="selectEquipment('${item.asset}')"><span class="catalog-item-icon">${isReady ? '◉' : '◇'}</span><span class="catalog-item-copy"><strong>${item.name}</strong><small>${item.description}</small></span><span class="catalog-item-state">${isReady ? '3D READY' : `${item.format} → GLB`}</span></button>`;
    }).join('')}</section>`).join('');
    [...catalog.querySelectorAll('.catalog-item')].forEach((button, index) => {
      const item = equipmentCatalog[index];
      if (!item?.model) return;
      fetch(item.model, { method: 'HEAD' }).then((response) => {
        if (!response.ok) return;
        item.available = true;
        button.classList.add('catalog-available');
        button.querySelector('.catalog-item-icon').textContent = '◉';
        button.querySelector('.catalog-item-state').textContent = '3D READY';
        item.available = true;
      }).catch(() => {});
    });
  }
  const viewer = document.getElementById('roomModelViewer');
  if (viewer) {
    let requestedModel = hospitalRooms.operating.model;
    let modelLoadError = false;
    viewer.addEventListener('load', () => {
      modelLoadError = false;
      const room = Object.values(hospitalRooms).find((entry) => entry.model === requestedModel);
      if (room) {
        const item = equipmentCatalog.find((equipment) => equipment.model === requestedModel);
        const caption = document.getElementById('sceneModelName');
        const note = document.getElementById('sceneModelNote');
        if (caption) caption.textContent = item?.name || room.modelName;
        if (note) note.textContent = item ? `${item.format} · interactive 3D asset` : room.modelNote;
      }
      document.getElementById('modelPlaceholder').hidden = true;
    });
    viewer.addEventListener('error', () => {
      modelLoadError = true;
      const placeholder = document.getElementById('modelPlaceholder');
      placeholder.hidden = false;
      placeholder.innerHTML = '<span>3D MODEL FAILED TO LOAD</span><p>Use the local web server so the browser can read model files.</p><small>Do not open index.html directly as a file</small>';
    });
    const viewerFallback = window.setTimeout(() => {
      if (!customElements.get('model-viewer')) {
        const placeholder = document.getElementById('modelPlaceholder');
        placeholder.hidden = false;
        placeholder.innerHTML = '<span>3D VIEWER UNAVAILABLE</span><p>Load this page through the application web server.</p><small>The model viewer module did not load</small>';
      }
    }, 8000);
    customElements.whenDefined('model-viewer').then(() => {
      window.clearTimeout(viewerFallback);
      if (modelLoadError) return;
      const initialItem = preferredRoomModel('operating');
      if (initialItem?.model) viewer.src = initialItem.model;
    });
    document.querySelectorAll('.room-choice').forEach((button) => {
      button.addEventListener('click', () => {
        const item = preferredRoomModel(button.dataset.room);
        if (!item) return;
        requestedModel = item.model || 'models/anatomy.glb';
        showEquipmentModel(requestedModel, item, hospitalRooms[button.dataset.room]);
      });
    });
  }
}

function selectHospitalRoom(roomId) {
  const room = hospitalRooms[roomId];
  if (!room) return;
  document.querySelectorAll('.room-choice').forEach((button) => button.classList.toggle('active', button.dataset.room === roomId));
  document.getElementById('sceneRoomLabel').textContent = room.label;
  document.getElementById('roomKicker').textContent = room.kicker;
  document.getElementById('roomTitle').textContent = room.title;
  document.getElementById('roomDescription').textContent = room.description;
  document.getElementById('sceneModelName').textContent = room.modelName;
  document.getElementById('sceneModelNote').textContent = room.modelNote;
  document.getElementById('roomAssetFormat').textContent = room.format;
  document.getElementById('roomConnection').textContent = room.connection;
  document.getElementById('roomWorkflowTitle').textContent = room.workflow;
  document.getElementById('roomWorkflowDescription').textContent = room.workflowDescription;
  document.getElementById('roomWorkflowButton').innerHTML = `${room.action} <span>→</span>`;
  document.getElementById('roomWorkflowButton').onclick = () => switchView(room.view);
  const roomItem = preferredRoomModel(roomId);
  const modelPath = roomItem?.model || room.model;
  document.getElementById('roomModelViewer').alt = roomItem ? `Interactive 3D model of ${roomItem.name}` : room.alt;
  document.getElementById('roomModelViewer').hidden = !modelPath;
  document.getElementById('modelPlaceholder').hidden = Boolean(modelPath);
  if (modelPath) document.getElementById('roomModelViewer').src = modelPath;
  if (roomId === 'bedside') renderBedsideModels();
  else document.getElementById('bedsideModelStatus').hidden = true;
  if (roomItem) {
    document.getElementById('sceneModelName').textContent = roomItem.name;
    document.getElementById('sceneModelNote').textContent = `${roomItem.format} · interactive 3D asset`;
    document.getElementById('roomAssetFormat').textContent = roomItem.model ? 'GLB · browser ready' : `${roomItem.format} · source asset`;
  }
  else if (!modelPath) document.getElementById('modelPlaceholder').innerHTML = `<span>${room.modelName.toUpperCase()}</span><p>Interactive 3D device view</p><small>${room.modelNote}</small>`;
}

function showEquipmentModel(modelPath, item, room) {
  const viewer = document.getElementById('roomModelViewer');
  const placeholder = document.getElementById('modelPlaceholder');
  selectedEquipmentByRoom[item.room] = item.asset;
  selectHospitalRoom(item.room);
  viewer.hidden = false;
  placeholder.hidden = true;
  viewer.alt = `Interactive 3D model of ${item.name}`;
  viewer.src = modelPath;
  if (item.room === 'bedside') {
    const bedsideStatus = document.getElementById('bedsideModelStatus');
    const bedsideBed = document.getElementById('bedsideBedModel');
    const bedsideMonitor = document.getElementById('bedsideMonitorModel');
    if (bedsideStatus) bedsideStatus.hidden = false;
    if (bedsideBed) bedsideBed.disabled = false;
    if (bedsideMonitor) bedsideMonitor.disabled = false;
    if (bedsideBed) bedsideBed.classList.toggle('active', item.asset === 'bed_hospital_standard_a01');
    if (bedsideMonitor) bedsideMonitor.classList.toggle('active', item.asset === 'monitor_patient_a01');
    document.getElementById('roomConnection').textContent = '3D model · no live device feed';
    document.getElementById('roomAssetFormat').textContent = 'GLB · browser ready';
    document.getElementById('sceneModelName').textContent = `Bedside equipment · ${item.name}`;
    document.getElementById('sceneModelNote').textContent = 'Bedside 3D asset · select bed or monitor below';
  }
}

function selectEquipment(assetName) {
  const item = equipmentCatalog.find((equipment) => equipment.asset === assetName);
  if (!item) return;
  if (item.model && !item.available) {
    item.available = true;
    const catalogButton = [...document.querySelectorAll('.catalog-item')].find((button) => button.getAttribute('onclick') === `selectEquipment('${item.asset}')`);
    if (catalogButton) {
      catalogButton.classList.add('catalog-available');
      catalogButton.querySelector('.catalog-item-icon').textContent = '◉';
      catalogButton.querySelector('.catalog-item-state').textContent = '3D READY';
    }
  }
  selectHospitalRoom(item.room);
  if (item.available || item.model) {
    showEquipmentModel(item.model || 'models/anatomy.glb', item, hospitalRooms[item.room]);
  } else {
    const room = hospitalRooms[item.room];
    document.getElementById('roomModelViewer').hidden = true;
    document.getElementById('modelPlaceholder').hidden = false;
    document.getElementById('modelPlaceholder').innerHTML = `<span>${item.name.toUpperCase()}</span><p>${item.description}</p><small>${item.format} · source asset pending browser conversion</small>`;
    document.getElementById('sceneRoomLabel').textContent = room.label;
    document.getElementById('sceneModelName').textContent = item.name;
    document.getElementById('sceneModelNote').textContent = `${item.asset} · ${item.format} source asset`;
    document.getElementById('roomAssetFormat').textContent = `${item.format} · source asset`;
    document.getElementById('roomConnection').textContent = 'No device connection';
  }
  document.getElementById('roomScene').scrollIntoView({ behavior: 'smooth', block: 'center' });
}

// -----------------------------------------------------------------------------
// Operating Regime Selection
// -----------------------------------------------------------------------------
function setRegime(regime) {
  const scenarios = {
    ROUTINE: { edCensus: 32, icuCensus: 18, nursesOnDuty: 45, activeOrs: 3, supplyRatio: 0.95 },
    SURGE: { edCensus: 38, icuCensus: 23, nursesOnDuty: 38, activeOrs: 7, supplyRatio: 0.72 },
    DISASTER: { edCensus: 40, icuCensus: 25, nursesOnDuty: 30, activeOrs: 10, supplyRatio: 0.38 },
  };
  if (!scenarios[regime]) return;
  state.regime = regime;
  window.demoWardOverride = null;
  Object.assign(state, scenarios[regime]);
  document.querySelectorAll('.regime-btn').forEach(btn => btn.classList.remove('active'));
  const activeButton = document.getElementById(`regime${regime[0]}${regime.slice(1).toLowerCase()}Btn`);
  if (activeButton) activeButton.classList.add('active');
  document.querySelectorAll('.regime-btn').forEach((btn) => btn.setAttribute('aria-pressed', String(btn === activeButton)));
  updateEscalationIndex();
  const wards = createDemoWards(regime);
  renderWardsContainer(wards);
  renderBedBoardSummary(wards);
  syncAmsv();
}

function resetDemoRegime(regime = 'ROUTINE') {
  setRegime(regime);
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

  // Mirror the verdict into the biometrics-form panel (both locations live)
  const formPanel = document.getElementById('ntiCheckResult');
  const formResult = document.getElementById('metforminResultText');
  const formDetail = document.getElementById('metforminDetailText');
  if (formPanel && formResult && formDetail) {
    formPanel.className = ntiCard.className;
    formResult.className = resText.className;
    formResult.textContent = resText.textContent;
    formDetail.textContent = detText.textContent;
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
  const censusRegime = document.getElementById('censusRegime');
  if (censusRegime) censusRegime.textContent = state.regime;
  syncAmsv();
}

function simulateSurgeScenario() {
  setRegime('SURGE');
}

function triggerReverseTriageBatch() {
  setRegime('SURGE');
  alert("Demo scenario changed to SURGE. Bed and staffing figures are simulated; no real triage, discharge, or backend bed assignments were changed.");
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
      if (el) el.classList.add('active');
      } else {
      if (el) el.classList.remove('active');
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

let lastTriPlaneSeq = 0;  // liveness: TriPlane seq must advance between polls

function setDataSourceStatus(isConnected) {
  const value = document.getElementById('loopHz');
  const monitor = document.getElementById('heartbeatContainer');
  const pulse = document.getElementById('heartbeatPulse');
  if (value) value.textContent = isConnected ? 'BioOS backend connected' : 'Demo simulation';
  if (monitor) monitor.classList.toggle('backend-status-connected', isConnected);
  if (pulse) pulse.classList.toggle('backend-pulse', isConnected);
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
        const backendConnected = Boolean(data && data.cache_line_0_actuation && data.cache_line_1_envelope);
        setDataSourceStatus(backendConnected);
        if (data && data.cache_line_0_actuation) {
          const l0 = data.cache_line_0_actuation;
          const l1 = data.cache_line_1_envelope;
          document.getElementById('amsvCrcDisplay').textContent = l0.crc16.toUpperCase();
          if (l0.seq_ctr > 0) document.getElementById('amsvSeqDisplay').textContent = l0.seq_ctr;
          if (l1.env_seq_ctr > 0 && document.getElementById('envSeqDisplay')) {
            document.getElementById('envSeqDisplay').textContent = l1.env_seq_ctr;
          }

          // Live dual-engine cross-check table (Engine 1 actuation vs Engine 2 envelope)
          const e1Rate = l0.rate_actual_ml_h;
          const e2Rate = l1.permissible_rate_ml_h;
          const e1RateCell = document.getElementById('e1RateCell');
          const e2RateCell = document.getElementById('e2RateCell');
          const rateSyncDot = document.getElementById('rateSyncDot');
          if (e1RateCell) e1RateCell.textContent = e1Rate.toFixed(1) + ' mL/h';
          if (e2RateCell) e2RateCell.textContent = e2Rate.toFixed(1) + ' mL/h Ceiling';
          if (rateSyncDot) {
            const synced = Math.abs(e1Rate - e2Rate) < 0.5;
            rateSyncDot.className = 'status-dot ' + (synced ? 'green' : 'red');
          }

          // Interlock cross-check: Engine 1 watchdog vs Engine 2 alpha-floor
          const e1Stall = l0.limit_state;       // 0 NORMAL, 1 CAUTION, 2 LOCKOUT
          const e2Stall = l1.alpha_floor_state; // 0 NOMINAL, 1 CLAMPED, 2 STALL
          const e1Names = ['Standby', 'Caution', 'Hardware Lockout'];
          const e2Names = ['Nominal', 'Envelope Clamped', 'Stall Emergency'];
          const e1StallCell = document.getElementById('e1StallCell');
          const e2StallCell = document.getElementById('e2StallCell');
          const stallSyncDot = document.getElementById('stallSyncDot');
          if (e1StallCell) e1StallCell.textContent = e1Names[e1Stall] || 'Unknown';
          if (e2StallCell) e2StallCell.textContent = e2Names[e2Stall] || 'Unknown';
          if (stallSyncDot) {
            const emergency = e1Stall === 2 || e2Stall === 2;
            const caution = e1Stall === 1 || e2Stall === 1;
            stallSyncDot.className = 'status-dot ' + (emergency ? 'red' : caution ? 'amber' : 'green');
          }

          // Stall warning box narrative (mirrors the alpha-floor badge)
          const stallTitle = document.getElementById('stallTitle');
          const stallDesc = document.getElementById('stallDesc');
          if (stallTitle && stallDesc) {
            if (e2Stall === 2) {
              stallTitle.textContent = 'ALPHA-FLOOR: STALL EMERGENCY';
              stallDesc.textContent = 'MAP below 55 mmHg or d(MAP)/dt below -2.0 mmHg/s. Rate clamped to 0.0 mL/h.';
            } else if (e2Stall === 1) {
              stallTitle.textContent = 'ALPHA-FLOOR: ENVELOPE CLAMPED';
              stallDesc.textContent = 'Approaching stall boundary. Infusion rate clamped to 50 percent.';
            } else {
              stallTitle.textContent = 'ENVELOPE NOMINAL';
              stallDesc.textContent = 'Hemodynamic state trajectory within safe physiological flight envelope.';
            }
          }

          // Heartbeat liveness: TriPlane sequence counter must advance between polls
          const heartbeatStatus = document.getElementById('heartbeatStatus');
          if (heartbeatStatus) {
            if (lastTriPlaneSeq > 0 && l0.seq_ctr === lastTriPlaneSeq) {
              heartbeatStatus.textContent = 'HEARTBEAT LOST';
              heartbeatStatus.className = 'relay-status tripped';
            } else {
              heartbeatStatus.textContent = '50ms NOMINAL';
              heartbeatStatus.className = 'relay-status active';
            }
          }
          lastTriPlaneSeq = l0.seq_ctr;
        }
      }
    } catch (e) { setDataSourceStatus(false); }
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
    'HOME': 'tabHome',
    'BED_BOARD': 'tabBedBoard',
    'BEDSIDE_DECK': 'tabBedsideDeck',
    'PHARMACY': 'tabPharmacy',
    'WORKFORCE': 'tabWorkforce',
    'EARLY_WARNING': 'tabEarlyWarning',
    'ROBOTICS': 'tabRobotics',
    'TERMINAL': 'tabTerminal'
  };

  // Section views
  const views = {
    'BED_BOARD': 'viewBedBoard',
    'BEDSIDE_DECK': 'viewBedsideDeck',
    'PHARMACY': 'viewPharmacy',
    'WORKFORCE': 'viewWorkforce',
    'EARLY_WARNING': 'viewEarlyWarning',
    'ROBOTICS': 'viewRobotics',
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
        viewEl.hidden = false;
      } else {
        viewEl.classList.remove('active-view');
        viewEl.hidden = true;
      }
    }
  }

  const patientBanner = document.getElementById('activePatientBanner');
  if (patientBanner) patientBanner.hidden = viewName !== 'BEDSIDE_DECK' || !patientBanner.dataset.bedSelected;
  const intro = document.querySelector('.product-intro');
  if (intro) intro.hidden = viewName !== 'HOME';
  const hospitalExplorer = document.querySelector('.hospital-explorer');
  if (hospitalExplorer) hospitalExplorer.hidden = viewName !== 'HOME';
  const systemInspector = document.querySelector('.amsv-inspector-bar');
  if (systemInspector) systemInspector.hidden = viewName !== 'TERMINAL';
  if (viewName !== 'HOME') {
    document.querySelector('.enterprise-nav-tabs')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  } else {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  if (viewName === 'ROBOTICS') {
    initRoboticsView();
  } else if (viewName === 'BED_BOARD') {
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

function createDemoWards(regime = state.regime) {
  const wardDefs = [
    ['ICU-A', 'Intensive Care A', 'ICU', 10, 2, 1], ['ICU-B', 'Intensive Care B', 'ICU', 8, 4, 1],
    ['ED', 'Emergency', 'ED', 9, 3, 1], ['SURG', 'Surgical Care', 'Surgery', 8, 4, 1],
    ['MED', 'Medical Care', 'Medicine', 7, 5, 1], ['STEP', 'Step-down Care', 'Step-down', 6, 5, 2],
  ];
  const [targetOccupied, targetAvailable, targetCleaning] = ({ ROUTINE: [48, 23, 7], SURGE: [68, 3, 7], DISASTER: [76, 0, 2] })[regime] || [48, 23, 7];
  let occupiedLeft = targetOccupied, availableLeft = targetAvailable, cleaningLeft = targetCleaning;
  const wards = wardDefs.map(([id, name, type], wardIndex) => {
    const occupied = Math.min(13, occupiedLeft); occupiedLeft -= occupied;
    const available = Math.min(13 - occupied, availableLeft); availableLeft -= available;
    const cleaning = Math.min(13 - occupied - available, cleaningLeft); cleaningLeft -= cleaning;
    const beds = Array.from({ length: 13 }, (_, bedIndex) => {
      const ordinal = bedIndex + 1;
      const status = ordinal <= occupied ? 'OCCUPIED' : ordinal <= occupied + available ? 'AVAILABLE' : 'CLEANING';
      const bedId = `${id}-${String(ordinal).padStart(2, '0')}`;
      const patient = status === 'OCCUPIED' ? {
        patient_id: `DEMO-${bedId}`, name: `Demo patient ${String(wardIndex * 13 + ordinal).padStart(2, '0')}`,
        age: 34 + ((wardIndex * 7 + ordinal * 3) % 58), sex: ordinal % 2 ? 'F' : 'M',
        diagnosis: ['Post-operative recovery', 'Sepsis observation', 'Respiratory support', 'Cardiac monitoring'][(wardIndex + ordinal) % 4],
        vitals: { map: 66 + ((ordinal + wardIndex) % 22), hr: 72 + ((ordinal * 3) % 34), spo2: 93 + ((ordinal + wardIndex) % 7) },
      } : null;
      return { bed_id: bedId, bed_number: String(ordinal).padStart(2, '0'), is_occupied: status === 'OCCUPIED', status, patient,
        is_negative_pressure: type === 'ICU' && ordinal <= 3, hvac_pa: type === 'ICU' && ordinal <= 3 ? -2.5 : 0 };
    });
    return { ward_id: id, name, floor: wardIndex < 2 ? 3 : wardIndex < 4 ? 2 : 1, ward_type: type, capacity: 13,
      occupied, occupancy_pct: Math.round(occupied / 13 * 100), staffed_nurses: Math.max(3, Math.round(occupied / 2)),
      required_nurses: Math.max(4, Math.ceil(occupied / 2)), in_staffing_ratio: true, beds };
  });
  if (occupiedLeft || availableLeft || cleaningLeft) throw new Error(`Demo census does not fit the 78-bed matrix for ${regime}.`);
  return wards;
}

function renderBedBoardSummary(wards = createDemoWards(state.regime)) {
  const beds = wards.flatMap((ward) => ward.beds || []);
  const values = {
    censusOccupied: beds.filter((bed) => bed.is_occupied).length,
    censusAvailable: beds.filter((bed) => !bed.is_occupied && bed.status === 'AVAILABLE').length,
    censusCleaning: beds.filter((bed) => !bed.is_occupied && bed.status !== 'AVAILABLE').length,
  };
  Object.entries(values).forEach(([id, value]) => { const element = document.getElementById(id); if (element) element.textContent = value; });
  const regimeElement = document.getElementById('censusRegime');
  if (regimeElement) regimeElement.textContent = state.regime;
  const capacity = beds.length;
  const totalElement = document.querySelector('#censusStatsRow .stat-pill');
  if (totalElement) totalElement.innerHTML = `Total Beds: <strong>${capacity}</strong>`;
}

async function fetchHospitalWards() {
  const demoWards = window.demoWardOverride || createDemoWards(state.regime);
  renderWardsContainer(demoWards);
  renderBedBoardSummary(demoWards);
  try {
    const [wardsRes, topoRes] = await Promise.all([
      fetch('/api/hospital/wards'),
      fetch('/api/hospital/topology')
    ]);

    if (topoRes.ok && wardsRes.ok) {
      const topo = await topoRes.json();
      {
        const liveOccupied = document.getElementById('censusOccupied'); if (liveOccupied) liveOccupied.textContent = topo.occupied_beds;
        const liveAvailable = document.getElementById('censusAvailable'); if (liveAvailable) liveAvailable.textContent = topo.available_ready_beds;
        const liveCleaning = document.getElementById('censusCleaning'); if (liveCleaning) liveCleaning.textContent = topo.dirty_turnover_beds;
      }
    }

    if (wardsRes.ok) {
      const wards = await wardsRes.json();
      if (Array.isArray(wards) && wards.length) {
        hospitalApiConnected = true;
        window.demoWardOverride = null;
        setDataSourceStatus(true);
        renderWardsContainer(wards);
        renderBedBoardSummary(wards);
        if (topoRes.ok) {
          const topology = await topoRes.json();
          const ei = document.getElementById('eiPillDisplay');
          const bar = document.getElementById('eiProgressBar');
          if (ei) ei.textContent = `E_I = ${topology.escalation_index}`;
          if (bar) bar.style.width = `${Math.min(100, topology.escalation_index * 100)}%`;
        }
      } else {
        hospitalApiConnected = false;
        setDataSourceStatus(false);
      }
    } else {
      hospitalApiConnected = false;
      setDataSourceStatus(false);
    }
  } catch (err) {
    hospitalApiConnected = false;
    setDataSourceStatus(false);
  }
}

function renderWardsContainer(wards) {
  const container = document.getElementById('wardsGridContainer');
  if (!container) return;

  container.innerHTML = '';
  const demoMode = !hospitalApiConnected;

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
          <span class="bed-number">${w.ward_id}-${b.bed_number}</span>
          <span class="bed-status-pill ${occClass}">${b.status}</span>
        </div>
      `;

      if (b.patient) {
        const p = b.patient;
        innerHtml += `
          <div class="bed-patient-name">${p.name}${demoMode ? ' · DEMO' : ''} <small>(${p.age} · ${p.sex})</small></div>
          <div class="bed-patient-diag">${p.diagnosis}</div>
          <div class="bed-vitals-row">
            <span class="bed-vital-item">MAP: <strong>${p.vitals.map}</strong></span>
            <span class="bed-vital-item">HR: <strong>${p.vitals.hr}</strong></span>
            <span class="bed-vital-item">SpO2: <strong>${p.vitals.spo2}%</strong></span>
          </div>
          <div class="bed-actions-row">
            <button class="bed-btn-sm" onclick="event.stopPropagation(); selectBed('${b.bed_id}'); switchView('BEDSIDE_DECK');">${demoMode ? 'Demo details' : 'Flight Deck'}</button>
            <button class="bed-btn-sm" onclick="event.stopPropagation(); requestBedDischarge('${p.patient_id}', '${b.bed_id}');">Discharge</button>
          </div>
        `;
      } else {
        innerHtml += `
          <div class="bed-patient-name text-muted">${b.status === 'AVAILABLE' ? 'Ready for admission' : 'Cleaning / turnover'}${demoMode ? ' · DEMO' : ''}</div>
          <div class="bed-patient-diag">${b.is_negative_pressure ? `Negative pressure room · ${b.hvac_pa} Pa` : 'Standard pressure room'}</div>
          <div class="bed-actions-row"><button class="bed-btn-sm" onclick="event.stopPropagation(); quickAdmitPrompt('${w.ward_id}', '${b.bed_id}');">Admit demo patient</button></div>
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

  if (!hospitalApiConnected) {
    const bed = (window.demoWardOverride || createDemoWards(state.regime)).flatMap((ward) => ward.beds).find((entry) => entry.bed_id === bedId);
    const banner = document.getElementById('activePatientBanner');
    if (banner) { banner.hidden = false; banner.dataset.bedSelected = 'true'; }
    document.getElementById('bannerBedId').textContent = bedId;
    document.getElementById('bannerPatientName').textContent = bed?.patient ? `${bed.patient.name} (Age ${bed.patient.age} ${bed.patient.sex})` : 'Bed unoccupied';
    document.getElementById('bannerDiagnosis').textContent = bed?.patient?.diagnosis || 'Ready for demo admission';
    document.getElementById('bannerMap').textContent = bed?.patient ? `${bed.patient.vitals.map} mmHg` : '--';
    document.getElementById('bannerInfusions').textContent = 'Demo scenario only';
    return;
  }

  try {
    const res = await fetch('/api/hospital/select_bed', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bed_id: bedId })
    });
    if (res.ok) {
      const data = await res.json();
      const banner = document.getElementById('activePatientBanner');
      if (banner) { banner.hidden = false; banner.dataset.bedSelected = 'true'; }
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

function requestBedDischarge(patientId, bedId) {
  if (!hospitalApiConnected) return runLocalBedAction(bedId, 'discharge');
  return dischargePatient(patientId, bedId);
}

function runLocalBedAction(bedId, action, demoPatientName = 'Demo patient') {
  const wards = window.demoWardOverride || createDemoWards(state.regime);
  const bed = wards.flatMap((ward) => ward.beds).find((entry) => entry.bed_id === bedId);
  if (!bed) return;
  if (action === 'admit') {
    bed.status = 'OCCUPIED';
    bed.is_occupied = true;
    bed.patient = { patient_id: `DEMO-${bedId}`, name: demoPatientName, age: 54, sex: 'F', diagnosis: 'Demo admission', vitals: { map: 78, hr: 82, spo2: 97 } };
  } else if (action === 'discharge') {
    bed.status = 'CLEANING';
    bed.is_occupied = false;
    bed.patient = null;
  }
  // Hold the interactive local changes until the next scenario selection or refresh.
  window.demoWardOverride = wards;
  renderWardsContainer(wards);
  renderBedBoardSummary(wards);
}

async function dischargePatient(patientId, bedId = currentSelectedBedId) {
  if (!hospitalApiConnected) return runLocalBedAction(bedId, 'discharge');
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
  if (!hospitalApiConnected) {
    const name = prompt(`Enter a demo patient label for ${bedId}:`, 'Demo patient');
    if (name) runLocalBedAction(bedId, 'admit', name);
    return;
  }
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


// =============================================================================
// Surgical Robotics & Meta SAM 3.1 Vision Subsystem
// =============================================================================
let roboticsInitialized = false;
let roboticsTripped = false;
let roboticsTimer = null;
let samPromptPoint = { x: 320, y: 180 };
let robotState = {
  x: 142.3,
  y: 88.1,
  z: 34.8,
  r: -1.2,
  p: 4.8,
  yaw: 89.1,
  fx: 0.45,
  fy: 0.22,
  fz: 0.68,
  margin: 1.42
};

function initRoboticsView() {
  const canvas = document.getElementById('samVisionCanvas');
  if (canvas && !roboticsInitialized) {
    canvas.addEventListener('click', (e) => {
      const rect = canvas.getBoundingClientRect();
      const scaleX = canvas.width / rect.width;
      const scaleY = canvas.height / rect.height;
      samPromptPoint = {
        x: (e.clientX - rect.left) * scaleX,
        y: (e.clientY - rect.top) * scaleY
      };
      drawSamSurgicalScene();
    });
    roboticsInitialized = true;
  }

  if (!roboticsTimer) {
    roboticsTimer = setInterval(() => {
      if (!roboticsTripped) {
        // Natural micro-kinematic breathing drift
        const t = Date.now() / 1000;
        robotState.x = 142.0 + Math.sin(t * 1.5) * 0.4;
        robotState.y = 88.0 + Math.cos(t * 1.2) * 0.3;
        robotState.z = 34.8 + Math.sin(t * 0.8) * 0.2;
        robotState.fx = Math.max(0.1, 0.45 + Math.sin(t * 2.0) * 0.15);
        robotState.fy = Math.max(0.1, 0.22 + Math.cos(t * 1.7) * 0.08);
        robotState.fz = Math.max(0.2, 0.68 + Math.sin(t * 1.1) * 0.18);
        robotState.margin = Math.max(1.1, 1.42 + Math.sin(t * 1.4) * 0.25);
        updateRoboticsTelemetryUI();
      }
      drawSamSurgicalScene();
    }, 100);
  }
}

function updateRoboticsTelemetryUI() {
  const posEl = document.getElementById('robotPosDisplay');
  const rotEl = document.getElementById('robotRotDisplay');
  const forceEl = document.getElementById('robotForceDisplay');
  const marginEl = document.getElementById('robotMarginDisplay');

  if (posEl) posEl.textContent = `X: ${robotState.x.toFixed(1)} mm | Y: ${robotState.y.toFixed(1)} mm | Z: ${robotState.z.toFixed(1)} mm`;
  if (rotEl) rotEl.textContent = `R: ${robotState.r.toFixed(1)}° | P: ${robotState.p.toFixed(1)}° | Y: ${robotState.yaw.toFixed(1)}°`;
  if (forceEl) forceEl.textContent = `Fx: ${robotState.fx.toFixed(2)} N | Fy: ${robotState.fy.toFixed(2)} N | Fz: ${robotState.fz.toFixed(2)} N`;
  if (marginEl) {
    if (robotState.margin < 0.8) {
      marginEl.className = 'telem-val text-danger';
      marginEl.textContent = `${robotState.margin.toFixed(2)} mm (CRITICAL BREACH)`;
    } else if (robotState.margin < 1.5) {
      marginEl.className = 'telem-val text-warning';
      marginEl.textContent = `${robotState.margin.toFixed(2)} mm (Warning Zone)`;
    } else {
      marginEl.className = 'telem-val text-success';
      marginEl.textContent = `${robotState.margin.toFixed(2)} mm (Safe Corridor)`;
    }
  }
}

function drawSamSurgicalScene() {
  const canvas = document.getElementById('samVisionCanvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const w = canvas.width;
  const h = canvas.height;

  // Background laparoscopic cavity gradient
  const grad = ctx.createRadialGradient(w/2, h/2, 50, w/2, h/2, w/2);
  grad.addColorStop(0, '#2d0c14');
  grad.addColorStop(0.7, '#140509');
  grad.addColorStop(1, '#050204');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, w, h);

  // Healthy Parenchyma background texture
  ctx.fillStyle = 'rgba(52, 211, 153, 0.08)';
  ctx.beginPath();
  ctx.ellipse(w * 0.45, h * 0.55, 220, 140, 0.2, 0, Math.PI * 2);
  ctx.fill();

  // Resection Target Lesion (Segmented by SAM 3.1)
  ctx.fillStyle = 'rgba(192, 132, 252, 0.35)';
  ctx.strokeStyle = '#c084fc';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.ellipse(w * 0.42, h * 0.45, 65, 45, -0.15, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();

  // Target Label
  ctx.fillStyle = '#c084fc';
  ctx.font = '10px "JetBrains Mono", monospace';
  ctx.fillText('ILLUSTRATIVE TARGET REGION', w * 0.34, h * 0.35);

  // Critical Artery (Plane A Forbidden Virtual Fixture Zone)
  ctx.fillStyle = 'rgba(244, 63, 94, 0.4)';
  ctx.strokeStyle = '#f43f5e';
  ctx.lineWidth = 2.5;
  ctx.beginPath();
  ctx.ellipse(w * 0.65, h * 0.48, 48, 75, 0.35, 0, Math.PI * 2);
  ctx.fill();
  ctx.stroke();

  // Artery Warning Pulse
  const pulseR = 55 + Math.sin(Date.now() / 250) * 4;
  ctx.strokeStyle = 'rgba(244, 63, 94, 0.5)';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.ellipse(w * 0.65, h * 0.48, pulseR * 0.8, pulseR * 1.2, 0.35, 0, Math.PI * 2);
  ctx.stroke();

  ctx.fillStyle = '#f43f5e';
  ctx.font = 'bold 11px "JetBrains Mono", monospace';
  ctx.fillText('NO-FLY ZONE: HEPATIC ARTERY', w * 0.55, h * 0.38);

  // Robotic Micro-Tool (Tracked End-Effector)
  const toolX = roboticsTripped ? w * 0.63 : w * 0.46;
  const toolY = roboticsTripped ? h * 0.47 : h * 0.42;

  // Tool shaft
  ctx.strokeStyle = '#38bdf8';
  ctx.lineWidth = 6;
  ctx.beginPath();
  ctx.moveTo(w * 0.1, h * 0.85);
  ctx.lineTo(toolX, toolY);
  ctx.stroke();

  // Tool jaws
  ctx.fillStyle = '#38bdf8';
  ctx.beginPath();
  ctx.arc(toolX, toolY, 7, 0, Math.PI * 2);
  ctx.fill();

  // Tool tracking bounding box (SAM 3.1)
  ctx.strokeStyle = 'rgba(56, 189, 248, 0.8)';
  ctx.lineWidth = 1;
  ctx.strokeRect(toolX - 18, toolY - 18, 36, 36);
  ctx.fillStyle = '#38bdf8';
  ctx.font = '9px "JetBrains Mono", monospace';
  ctx.fillText('BIPOLAR TOOL', toolX - 22, toolY - 22);

  // User Interactive Prompt Point
  ctx.strokeStyle = '#ffff00';
  ctx.fillStyle = '#ffff00';
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.arc(samPromptPoint.x, samPromptPoint.y, 4, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeRect(samPromptPoint.x - 8, samPromptPoint.y - 8, 16, 16);
  ctx.font = '9px "JetBrains Mono", monospace';
  ctx.fillText('SAM PROMPT', samPromptPoint.x + 10, samPromptPoint.y - 4);
}

function triggerVirtualFixtureTrip() {
  roboticsTripped = true;
  robotState.x = 158.4;
  robotState.y = 92.6;
  robotState.margin = 0.62;
  robotState.fx = 2.15;

  const card = document.querySelector('.robotics-card');
  if (card) card.classList.add('tripped');

  const badge = document.getElementById('robotInterlockBadge');
  if (badge) {
    badge.className = 'state-indicator text-danger';
    badge.textContent = 'TRIP: MECHANICAL LOCKOUT (0.81 ms)';
  }

  const msg = document.getElementById('robotMessageBox');
  if (msg) {
    msg.className = 'trip-message-box danger';
    msg.innerHTML = '<strong>[PLANE A VIRTUAL FIXTURE TRIP]</strong> No-fly zone boundary breach attempted at 0.62 mm. Solid-state relay decoupled motor power in 0.81 ms. Zero tissue violation.';
  }

  updateRoboticsTelemetryUI();
}

function injectMotionCompTremor() {
  const msg = document.getElementById('robotMessageBox');
  if (msg) {
    msg.className = 'trip-message-box';
    msg.innerHTML = '<strong>[PLANE C KALMAN MOTION COMP]</strong> Physiological cardiac tremor of 4.2 mm detected. Continuous EKF velocity tracking applied reverse compensation. Net tool jitter: &plusmn;0.03 mm.';
  }
}

function resetRoboticsInterlock() {
  roboticsTripped = false;
  robotState = {
    x: 142.3,
    y: 88.1,
    z: 34.8,
    r: -1.2,
    p: 4.8,
    yaw: 89.1,
    fx: 0.45,
    fy: 0.22,
    fz: 0.68,
    margin: 1.42
  };

  const card = document.querySelector('.robotics-card');
  if (card) card.classList.remove('tripped');

  const badge = document.getElementById('robotInterlockBadge');
  if (badge) {
    badge.className = 'state-indicator';
    badge.textContent = 'INTERLOCK: ARMED';
  }

  const msg = document.getElementById('robotMessageBox');
  if (msg) {
    msg.className = 'trip-message-box';
    msg.textContent = 'Plane A Virtual Fixture Active: Instrument constrained within nominal surgical envelope.';
  }

  updateRoboticsTelemetryUI();
}
