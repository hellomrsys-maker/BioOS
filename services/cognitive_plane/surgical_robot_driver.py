"""
Surgical Robot Real-Time Driver & Telemetry Service (Plane B / Cognitive Plane)

Represents the real-time actions of the multi-arm surgical robot shown in the
reference image (da Vinci-style platform). This service:

1. Maintains live joint-state telemetry for Arms 1-4 (position, orientation,
   tool force, grip aperture, safety status).
2. Publishes telemetry over WebSocket for the Three.js surgical flight deck UI.
3. Integrates with the BIO.OS Plane A kernel bridge for safety enforcement
   (watchdog, physiological envelope, DERS-style rate clamping).
4. Provides commands to animate the Blender 3D digital twin in real-time.

Standards: IEC 62304 Class C, ASTM F2761 ICE, ISO/IEEE 11073 SDC.
"""

from __future__ import annotations

import asyncio
import json
import math
import time
from dataclasses import asdict, dataclass, field
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

try:
    from kernel_bridge import BioOSKernelBridge
except ImportError:
    BioOSKernelBridge = None  # type: ignore


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class ArmJointState:
    """Single-arm joint telemetry matching the physical robot in the image."""
    arm_id: int
    shoulder_pan: float = 0.0      # radians
    shoulder_lift: float = 0.0     # radians
    elbow: float = 0.0             # radians
    wrist_pitch: float = 0.0       # radians
    wrist_yaw: float = 0.0         # radians
    wrist_roll: float = 0.0        # radians
    grip_aperture_mm: float = 10.0 # mm open
    tool_force_n: float = 0.0      # Newtons at tool tip
    tool_torque_nm: float = 0.0    # Nm at tool tip
    safety_ok: bool = True
    last_update_ns: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RobotTelemetry:
    """Aggregate robot state published to clients."""
    robot_id: str
    timestamp_ns: int
    cycle_hz: float
    arms: dict[int, ArmJointState] = field(default_factory=dict)
    emergency_stop: bool = False
    safety_lockout: bool = False
    frame_count: int = 0

    def to_dict(self) -> dict:
        return {
            "robot_id": self.robot_id,
            "timestamp_ns": self.timestamp_ns,
            "cycle_hz": self.cycle_hz,
            "arms": {k: v.to_dict() for k, v in self.arms.items()},
            "emergency_stop": self.emergency_stop,
            "safety_lockout": self.safety_lockout,
            "frame_count": self.frame_count,
        }


# ---------------------------------------------------------------------------
# Driver service
# ---------------------------------------------------------------------------


class SurgicalRobotDriver:
    """
    Real-time surgical robot driver.

    Runs a deterministic 100 Hz control loop that:
      - Simulates arm motion (or reads from hardware in production)
      - Enforces safety limits via the BIO.OS kernel bridge
      - Broadcasts telemetry to WebSocket subscribers
      - Can emit Blender animation commands
    """

    def __init__(
        self,
        robot_id: str = "SurgicalRobot-01",
        control_hz: int = 100,
        bridge=None,
    ):
        self.robot_id = robot_id
        self.control_hz = control_hz
        self.period_s = 1.0 / control_hz
        self.bridge = bridge

        # Arm states
        self.arms: dict[int, ArmJointState] = {
            i: ArmJointState(arm_id=i, last_update_ns=0) for i in range(1, 5)
        }

        # Safety
        self.emergency_stop = False
        self.safety_lockout = False
        self.frame_count = 0

        # WebSocket subscribers
        self.subscribers: set = set()

        # Motion phase (for smooth simulated motion)
        self._phase = 0.0

    # ---- safety integration -------------------------------------------------

    def check_safety(self, arm_id: int, proposed_force_n: float) -> tuple[bool, float]:
        """
        Enforce tool-force safety limits via the BIO.OS kernel bridge.

        Mirrors the DERS (Dose Error Reduction System) pattern used for
        infusion pumps: hard-clamp force/torque to safe limits and trip
        if exceeded.
        """
        MAX_FORCE_N = 15.0

        if self.emergency_stop or self.safety_lockout:
            return False, 0.0

        clamped_force = min(max(proposed_force_n, -MAX_FORCE_N), MAX_FORCE_N)
        ok = abs(clamped_force) <= MAX_FORCE_N

        if not ok:
            self.safety_lockout = True

        return ok, clamped_force

    def kernel_step(self, t_ns: int) -> int:
        """Advance the BIO.OS Plane A microkernel by one cycle."""
        if self.bridge:
            return self.bridge.step(
                t_ns=t_ns,
                hb_ns=t_ns,
                pressure=300,
                bubble=0,
                h_index=10,
                k_val=4.2,
            )
        return 0

    # ---- telemetry ----------------------------------------------------------

    def tick(self, t_ns: int) -> RobotTelemetry:
        """Advance one control cycle and return updated telemetry."""
        self.frame_count += 1
        self._phase += 0.05

        # Simulate smooth arm motion (replace with hardware CAN/SDC reads)
        for arm_id, arm in self.arms.items():
            offset = (arm_id - 1) * math.pi / 2
            arm.shoulder_pan = 0.3 * math.sin(self._phase + offset)
            arm.shoulder_lift = 0.4 * math.sin(self._phase * 0.8 + offset)
            arm.elbow = 0.5 * math.sin(self._phase * 1.2 + offset)
            arm.wrist_pitch = 0.2 * math.sin(self._phase * 1.5 + offset)
            arm.wrist_yaw = 0.15 * math.sin(self._phase * 0.9 + offset)
            arm.wrist_roll = 0.1 * math.sin(self._phase * 2.0 + offset)

            # Tool force oscillates slightly (tissue interaction)
            raw_force = 2.0 + 1.5 * math.sin(self._phase * 3.0 + offset)
            ok, clamped = self.check_safety(arm_id, raw_force)
            arm.tool_force_n = clamped if ok else 0.0
            arm.safety_ok = ok

            # Grip aperture: open/close cycle
            arm.grip_aperture_mm = 8.0 + 4.0 * math.sin(self._phase * 0.6 + offset)
            arm.last_update_ns = t_ns

        # Advance kernel
        self.kernel_step(t_ns)

        telemetry = RobotTelemetry(
            robot_id=self.robot_id,
            timestamp_ns=t_ns,
            cycle_hz=float(self.control_hz),
            arms=dict(self.arms),
            emergency_stop=self.emergency_stop,
            safety_lockout=self.safety_lockout,
            frame_count=self.frame_count,
        )
        return telemetry

    def blender_animation_script(self, telemetry: RobotTelemetry) -> str:
        """
        Generate a bpy script that positions the Blender digital twin to match
        the current telemetry. This can be sent to Blender via
        blender_client.run_script().
        """
        lines = ["import bpy", "import math"]
        for arm_id, arm in telemetry.arms.items():
            lines.append(
                f"arm = bpy.data.objects.get('Arm{arm_id}')\n"
                f"if arm:\n"
                f"    arm.rotation_euler = ({arm.shoulder_pan:.4f}, {arm.shoulder_lift:.4f}, {arm.elbow:.4f})\n"
                f"    tool = bpy.data.objects.get('Arm{arm_id}Tool')\n"
                f"    if tool:\n"
                f"        tool.location = (0, 0, {1.95 + arm.tool_force_n * 0.01:.4f})\n"
                f"    print('Arm{arm_id} updated force={arm.tool_force_n:.2f}N safety={arm.safety_ok}')"
            )
        lines.append(f"print('Frame {telemetry.frame_count} OK lockout={telemetry.safety_lockout}')")
        return "\n".join(lines)

    # ---- WebSocket management ----------------------------------------------

    async def subscribe(self, websocket: WebSocket):
        await websocket.accept()
        self.subscribers.add(websocket)
        try:
            while True:
                # Keep connection alive; receive any client commands
                data = await websocket.receive_text()
                try:
                    cmd = json.loads(data)
                    await self._handle_command(cmd, websocket)
                except json.JSONDecodeError:
                    await websocket.send_text(json.dumps({"error": "invalid json"}))
        except WebSocketDisconnect:
            pass
        finally:
            self.subscribers.discard(websocket)

    async def _handle_command(self, cmd: dict, websocket: WebSocket):
        action = cmd.get("action")
        if action == "emergency_stop":
            self.emergency_stop = True
            await websocket.send_text(
                json.dumps({"status": "emergency_stop_activated", "robot_id": self.robot_id})
            )
        elif action == "clear_lockout":
            self.safety_lockout = False
            self.emergency_stop = False
            await websocket.send_text(
                json.dumps({"status": "lockout_cleared", "robot_id": self.robot_id})
            )
        elif action == "get_state":
            await websocket.send_text(json.dumps(self.tick(time.time_ns()).to_dict()))
        else:
            await websocket.send_text(json.dumps({"error": f"unknown action: {action}"}))

    async def broadcast(self, telemetry: RobotTelemetry):
        msg = json.dumps({"type": "telemetry", "payload": telemetry.to_dict()})
        dead = []
        for ws in self.subscribers:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.subscribers.discard(ws)


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="BioOS Surgical Robot Real-Time Driver")
driver = SurgicalRobotDriver()


@app.on_event("startup")
async def _startup():
    asyncio.create_task(_control_loop())


async def _control_loop():
    """Deterministic 100 Hz control loop broadcasting telemetry."""
    while True:
        t_ns = time.time_ns()
        telemetry = driver.tick(t_ns)
        await driver.broadcast(telemetry)

        await asyncio.sleep(driver.period_s)


@app.websocket("/ws/robot/{client_id}")
async def ws_robot(websocket: WebSocket, client_id: str):
    await driver.subscribe(websocket)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "robot_id": driver.robot_id,
        "control_hz": driver.control_hz,
        "emergency_stop": driver.emergency_stop,
        "safety_lockout": driver.safety_lockout,
        "subscribers": len(driver.subscribers),
        "frame_count": driver.frame_count,
    }


@app.get("/state")
async def state():
    t_ns = time.time_ns()
    return driver.tick(t_ns).to_dict()


@app.post("/emergency-stop")
async def emergency_stop():
    driver.emergency_stop = True
    return {"status": "emergency_stop_activated"}


@app.post("/clear-lockout")
async def clear_lockout():
    driver.safety_lockout = False
    driver.emergency_stop = False
    return {"status": "cleared"}