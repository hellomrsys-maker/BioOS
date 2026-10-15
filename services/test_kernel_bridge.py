"""
Verification Test for BioOS Zero-Bridge Synchronous Memory Link
Tests:
1. Physical memory mapping of 64-byte AMSV across Rust/C-ABI and Python
2. 1000 Hz microkernel stepping with direct memory updates
3. CLSI C56-A potassium gate C-ABI verification
4. 2021 CKD-EPI race-free eGFR C-ABI verification
5. Metformin NTI boundary verification
"""

import ctypes
import math
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kernel_bridge import BioOsKernelBridge, AtomicMemoryStateVector, TriPlaneAmsv

def test_kernel_bridge():
    print("[TEST] Loading bioos_kernel.dll via Zero-Bridge Interface...")
    bridge = BioOsKernelBridge()
    
    # 1. Verify shared AMSV address and initial state
    amsv = bridge.amsv_shared
    print(f" -> Initial AMSV seq_ctr in physical memory: {amsv.seq_ctr}")
    
    # 2. Step kernel through nominal cycle
    state_code = bridge.step(
        t_ns=1_000_000,
        hb_ns=1_000_000,
        pressure=150,
        bubble=0,
        h_index=10,
        k_val=4.25
    )
    assert state_code == 0, f"Expected State 0 (Normal), got {state_code}"
    assert amsv.occlusion_mmhg == 150
    assert amsv.hil_h == 10
    assert amsv.value_x1000 == 4250  # 4.25 * 1000
    print(f" -> Nominal Step PASS: seq_ctr={amsv.seq_ctr}, occlusion={amsv.occlusion_mmhg} mmHg, value_x1000={amsv.value_x1000}")
    
    # 3. Step kernel with occlusion spike (540 mmHg > 525 mmHg) -> State 2 (Hardware Lockout)
    lockout_code = bridge.step(
        t_ns=2_000_000,
        hb_ns=2_000_000,
        pressure=540,
        bubble=0,
        h_index=10,
        k_val=4.25
    )
    assert lockout_code == 2, f"Expected State 2 (Lockout), got {lockout_code}"
    assert amsv.limit_state == 2
    assert amsv.rate_actual_x10 == 0  # Motor cut
    print(f" -> Occlusion Trip Lockout PASS: limit_state={amsv.limit_state}, rate_actual_x10={amsv.rate_actual_x10}")

    # 4. CLSI C56-A Potassium Gate via FFI
    k_val_valid, is_void_valid = bridge.validate_potassium(4.3, 15)
    assert not is_void_valid
    assert round(k_val_valid, 2) == 4.30

    k_val_hemolyzed, is_void_hemolyzed = bridge.validate_potassium(6.8, 25)
    assert is_void_hemolyzed
    assert math.isnan(k_val_hemolyzed)
    print(" -> CLSI C56-A Potassium Gate FFI: PASS (H > 20 is strictly NaN)")

    # 5. 2021 CKD-EPI Race-Free eGFR via FFI
    egfr_val = bridge.calculate_egfr(65.0, 1.2, False) # 65 yo male, Scr 1.2
    assert 60.0 <= egfr_val <= 75.0, f"eGFR {egfr_val} out of range"
    print(f" -> 2021 CKD-EPI FFI: PASS (Calculated eGFR: {egfr_val:.1f} mL/min/1.73m2)")

    # 6. Metformin NTI Check
    assert bridge.verify_metformin(22.0, 1500.0) == 2  # Hard lockout (< 30)
    assert bridge.verify_metformin(38.0, 1500.0) == 1  # Dose clamped (30-44)
    assert bridge.verify_metformin(75.0, 1500.0) == 0  # Approved (>= 45)
    print(" -> Metformin NTI C-ABI Verification: PASS (Lockout < 30 strictly enforced)")

    # 7. Engine 2: Dynamic Physiological Envelope & Kalman Stall Protection
    tri = bridge.triplane_shared
    print(f" -> TriPlane AMSV Physical Address: 0x{ctypes.addressof(tri):016X} (Size: {ctypes.sizeof(tri)} bytes)")
    assert ctypes.sizeof(tri) == 128

    # Nominal step
    env_nominal = bridge.step_envelope(map_mmhg=82.0, hr_bpm=74.0, sbp_mmhg=118.0, requested_rate=125.0, dt_seconds=0.1)
    assert env_nominal["alpha_floor_state"] == 0
    assert env_nominal["allowed_rate_ml_h"] > 100.0
    print(f" -> Kalman Envelope Nominal: Estimated MAP={env_nominal['estimated_map_mmhg']} mmHg, Rate={env_nominal['allowed_rate_ml_h']} mL/h")

    # Hemodynamic stall crash step (Plunging MAP < 55)
    env_stall = bridge.step_envelope(map_mmhg=46.0, hr_bpm=138.0, sbp_mmhg=62.0, requested_rate=125.0, dt_seconds=0.1)
    assert env_stall["alpha_floor_state"] == 2 # Stall Emergency
    assert env_stall["allowed_rate_ml_h"] == 0.0 # Emergency 0 mL/h cut
    assert tri.plane_c.alpha_floor_state == 2
    assert tri.plane_c.permissible_rate_x10 == 0
    print(" -> Kalman Alpha-Floor Stall Protection: PASS (Emergency Rate Clamp to 0.0 mL/h on MAP Crash)")

if __name__ == "__main__":
    test_kernel_bridge()
    print("\n>>> ALL TRIPLANE ZERO-BRIDGE TESTS PASSED WITH 100% SUCCESS! <<<")
