"""
BioOS Kernel Bridge: Zero-Bridge Synchronous Memory Interface
Standards: IEC 62304 Class C, ASTM F2761 ICE

Directly maps the Python runtime onto the C/Rust memory space via ctypes.
Plane A and Plane B share the exact same 64-byte physical memory address
(Atomic Memory State Vector) for 0-nanosecond data synchronization.
Zero serialization, zero deserialization.
"""

import ctypes
import os
import sys
from typing import Optional


class AtomicMemoryStateVector(ctypes.Structure):
    """Exact 64-byte C-ABI struct matching Rust #[repr(C, align(64))]"""
    _pack_ = 1
    _fields_ = [
        ("seq_ctr", ctypes.c_uint64),                # 0x00..0x07 (8 bytes)
        ("t_write_ns", ctypes.c_uint32),             # 0x08..0x0B (4 bytes)
        ("device_class", ctypes.c_uint16),           # 0x0C..0x0D (2 bytes)
        ("metric_code", ctypes.c_uint16),            # 0x0E..0x0F (2 bytes)
        ("value_x1000", ctypes.c_int32),             # 0x10..0x13 (4 bytes)
        ("quality_flags", ctypes.c_uint32),          # 0x14..0x17 (4 bytes)
        ("hil_h", ctypes.c_uint16),                  # 0x18..0x19 (2 bytes)
        ("hil_i", ctypes.c_uint16),                  # 0x1A..0x1B (2 bytes)
        ("hil_l", ctypes.c_uint16),                  # 0x1C..0x1D (2 bytes)
        ("limit_state", ctypes.c_uint16),            # 0x1E..0x1F (2 bytes)
        ("rate_setpoint_x10", ctypes.c_uint32),      # 0x20..0x23 (4 bytes)
        ("rate_actual_x10", ctypes.c_uint32),        # 0x24..0x27 (4 bytes)
        ("occlusion_mmhg", ctypes.c_uint32),         # 0x28..0x2B (4 bytes)
        ("alarm_class", ctypes.c_uint16),            # 0x2C..0x2D (2 bytes)
        ("crc16", ctypes.c_uint16),                  # 0x2E..0x2F (2 bytes)
        ("global_mode", ctypes.c_uint8),             # 0x30       (1 byte)
        ("active_escalation_tier", ctypes.c_uint8),  # 0x31       (1 byte)
        ("facility_census_bitmap", ctypes.c_uint16), # 0x32..0x33 (2 bytes)
        ("hics_incident_id", ctypes.c_uint32),       # 0x34..0x37 (4 bytes)
        ("system_checksum", ctypes.c_uint64),        # 0x38..0x3F (8 bytes)
    ]


assert ctypes.sizeof(AtomicMemoryStateVector) == 64, f"Struct size error: {ctypes.sizeof(AtomicMemoryStateVector)} != 64"


class PhysiologicalEnvelopeVector(ctypes.Structure):
    """Cache Line 1: Exact 64-byte struct matching Rust PhysiologicalEnvelopeVector"""
    _pack_ = 1
    _fields_ = [
        ("env_seq_ctr", ctypes.c_uint64),                # 0x00..0x07 (8 bytes)
        ("env_checksum", ctypes.c_uint64),               # 0x08..0x0F (8 bytes)
        ("permissible_rate_x10", ctypes.c_uint32),       # 0x10..0x13 (4 bytes)
        ("kalman_variance_p00_x100", ctypes.c_uint32),   # 0x14..0x17 (4 bytes)
        ("kalman_variance_p11_x100", ctypes.c_uint32),   # 0x18..0x1B (4 bytes)
        ("est_map_x10", ctypes.c_uint16),                # 0x1C..0x1D (2 bytes)
        ("est_hr_x10", ctypes.c_uint16),                 # 0x1E..0x1F (2 bytes)
        ("shock_index_x100", ctypes.c_uint16),           # 0x20..0x21 (2 bytes)
        ("d_map_dt_x100", ctypes.c_int16),               # 0x22..0x23 (2 bytes)
        ("dynamic_margin_x100", ctypes.c_uint16),        # 0x24..0x25 (2 bytes)
        ("env_crc16", ctypes.c_uint16),                  # 0x26..0x27 (2 bytes)
        ("alpha_floor_state", ctypes.c_uint8),           # 0x28       (1 byte)
        ("slew_clamped", ctypes.c_uint8),                # 0x29       (1 byte)
        ("reserved", ctypes.c_uint8 * 22),               # 0x2A..0x3F (22 bytes)
    ]


assert ctypes.sizeof(PhysiologicalEnvelopeVector) == 64, f"Envelope size error: {ctypes.sizeof(PhysiologicalEnvelopeVector)} != 64"


class TriPlaneAmsv(ctypes.Structure):
    """128-byte Dual-Cache-Line TriPlane state vector"""
    _pack_ = 1
    _fields_ = [
        ("plane_a", AtomicMemoryStateVector),
        ("plane_c", PhysiologicalEnvelopeVector),
    ]


assert ctypes.sizeof(TriPlaneAmsv) == 128, f"TriPlane size error: {ctypes.sizeof(TriPlaneAmsv)} != 128"


class BioOsKernelBridge:
    """Manages the zero-bridge shared memory interaction with bioos_kernel.dll"""

    def __init__(self, dll_path: Optional[str] = None):
        if dll_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            dll_path = os.path.join(base_dir, "crates", "bioos-kernel", "target", "release", "bioos_kernel.dll")

        if not os.path.exists(dll_path):
            debug_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "crates", "bioos-kernel", "target", "debug", "bioos_kernel.dll")
            if os.path.exists(debug_path):
                dll_path = debug_path
            else:
                raise FileNotFoundError(f"bioos_kernel.dll not found at {dll_path} or {debug_path}")

        self.lib = ctypes.CDLL(dll_path)
        self._setup_ffi_signatures()

        # Retrieve exact physical pointer to 64-byte AMSV and 128-byte TriPlane AMSV
        raw_ptr_amsv = self.lib.bioos_amsv_get_raw_ptr()
        self.amsv_shared = AtomicMemoryStateVector.from_address(raw_ptr_amsv)

        raw_ptr_triplane = self.lib.bioos_triplane_get_raw_ptr()
        self.triplane_shared = TriPlaneAmsv.from_address(raw_ptr_triplane)
        print(f"[BioOS Bridge] Connected to TriPlane AMSV (128 bytes) at physical address: 0x{raw_ptr_triplane:016X}")

    def _setup_ffi_signatures(self):
        # bioos_amsv_get_raw_ptr() -> size_t / pointer
        self.lib.bioos_amsv_get_raw_ptr.restype = ctypes.c_void_p
        self.lib.bioos_amsv_get_raw_ptr.argtypes = []

        # bioos_kernel_step(t_ns, hb_ns, press, bubble, h_idx, k_val) -> u8
        self.lib.bioos_kernel_step.restype = ctypes.c_uint8
        self.lib.bioos_kernel_step.argtypes = [
            ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint16, ctypes.c_float
        ]

        # bioos_amsv_read_atomic(dest_ptr)
        self.lib.bioos_amsv_read_atomic.restype = None
        self.lib.bioos_amsv_read_atomic.argtypes = [ctypes.POINTER(AtomicMemoryStateVector)]

        # bioos_validate_potassium(raw_k, h_idx, out_void_ptr) -> float
        self.lib.bioos_validate_potassium.restype = ctypes.c_float
        self.lib.bioos_validate_potassium.argtypes = [ctypes.c_float, ctypes.c_uint16, ctypes.POINTER(ctypes.c_uint8)]

        # bioos_calculate_ckd_epi(age, scr, is_female) -> float
        self.lib.bioos_calculate_ckd_epi.restype = ctypes.c_float
        self.lib.bioos_calculate_ckd_epi.argtypes = [ctypes.c_float, ctypes.c_float, ctypes.c_bool]

        # bioos_triplane_get_raw_ptr() -> pointer
        self.lib.bioos_triplane_get_raw_ptr.restype = ctypes.c_void_p
        self.lib.bioos_triplane_get_raw_ptr.argtypes = []

        # bioos_envelope_step(map, hr, sbp, rate, dt, out_state, out_rate) -> float
        self.lib.bioos_envelope_step.restype = ctypes.c_float
        self.lib.bioos_envelope_step.argtypes = [
            ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float, ctypes.c_float,
            ctypes.POINTER(ctypes.c_uint8), ctypes.POINTER(ctypes.c_float)
        ]

        # bioos_verify_metformin(egfr, requested_dose) -> u8
        self.lib.bioos_verify_metformin.restype = ctypes.c_uint8
        self.lib.bioos_verify_metformin.argtypes = [ctypes.c_float, ctypes.c_float]

    def step(self, t_ns: int, hb_ns: int, pressure: int, bubble: int, h_index: int, k_val: float) -> int:
        """Executes one 1000 Hz microkernel cycle and updates the shared memory AMSV."""
        return self.lib.bioos_kernel_step(t_ns, hb_ns, pressure, bubble, h_index, k_val)

    def step_envelope(self, map_mmhg: float, hr_bpm: float, sbp_mmhg: float, requested_rate: float, dt_seconds: float = 0.1):
        """Executes one cycle of Engine 2: Dynamic Physiological Envelope & Kalman Observer."""
        out_state = ctypes.c_uint8(0)
        out_rate = ctypes.c_float(0.0)
        est_map = self.lib.bioos_envelope_step(
            map_mmhg, hr_bpm, sbp_mmhg, requested_rate, dt_seconds,
            ctypes.byref(out_state), ctypes.byref(out_rate)
        )
        return {
            "estimated_map_mmhg": round(est_map, 1),
            "alpha_floor_state": out_state.value,
            "allowed_rate_ml_h": round(out_rate.value, 1),
        }

    def read_atomic(self) -> AtomicMemoryStateVector:
        """Performs atomic lockless Seqlock read."""
        dest = AtomicMemoryStateVector()
        self.lib.bioos_amsv_read_atomic(ctypes.byref(dest))
        return dest

    def validate_potassium(self, raw_k: float, h_index: int):
        out_void = ctypes.c_uint8(0)
        val = self.lib.bioos_validate_potassium(raw_k, h_index, ctypes.byref(out_void))
        return val, bool(out_void.value)

    def calculate_egfr(self, age: float, scr: float, is_female: bool) -> float:
        return self.lib.bioos_calculate_ckd_epi(age, scr, is_female)

    def verify_metformin(self, egfr: float, requested_dose: float = 1500.0) -> int:
        return self.lib.bioos_verify_metformin(egfr, requested_dose)
