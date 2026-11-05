#!/usr/bin/env python3
"""
Test suite for BioOS SAM 3.1 Vision Engine (Engine 5).
Tests the mock mode which requires no GPU dependencies.
"""

import sys
import os
import numpy as np

# Add cognitive_plane to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../cognitive_plane"))

from sam31_vision import (
    SAM31VisionEngine,
    SAM31ClinicalIntegration,
    SurgicalStructure,
    SegmentationMode,
    SegmentationResult,
    VirtualFixture,
    create_sam31_engine_from_env,
)


def test_sam31_mock_mode():
    """Test SAM 3.1 in MOCK mode (no GPU required)."""
    print("[TEST] SAM 3.1 MOCK mode initialization...")
    
    engine = SAM31VisionEngine(mode="MOCK")
    assert engine.mode == "MOCK"
    assert engine._model_loaded is True
    print("  -> Engine initialized successfully")
    
    # Create a test frame (simulated surgical video)
    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
    # Test automatic segmentation
    print("[TEST] Automatic segmentation...")
    result = engine.segment_frame(frame, mode=SegmentationMode.AUTOMATIC)
    
    assert isinstance(result, SegmentationResult)
    assert result.frame_shape == (480, 640)
    assert result.mode == SegmentationMode.AUTOMATIC
    assert len(result.masks) > 0
    assert len(result.scores) == len(result.masks)
    assert len(result.structures) == len(result.masks)
    assert len(result.bboxes) == len(result.masks)
    assert result.processing_ms > 0
    assert result.model_version == "SAM-3.1-MOCK"
    print(f"  -> Segmented {len(result.masks)} structures")
    for i, (struct, score) in enumerate(zip(result.structures, result.scores)):
        print(f"    [{i}] {struct.value}: IoU={score:.3f}, bbox={result.bboxes[i]}")
    
    # Test point prompt segmentation
    print("[TEST] Point prompt segmentation...")
    prompt_points = [(320, 240), (400, 300)]
    prompt_labels = [1, 1]
    result2 = engine.segment_frame(
        frame, 
        mode=SegmentationMode.POINT_PROMPT,
        prompt_points=prompt_points,
        prompt_labels=prompt_labels
    )
    assert result2.mode == SegmentationMode.POINT_PROMPT
    assert result2.prompt_points == prompt_points
    print("  -> Point prompt segmentation successful")
    
    # Test virtual fixture generation
    print("[TEST] Virtual fixture generation...")
    fixtures = engine.generate_virtual_fixtures(result)
    assert isinstance(fixtures, list)
    for fixture in fixtures:
        assert isinstance(fixture, VirtualFixture)
        assert fixture.fixture_id.startswith("VF_")
        assert fixture.structure in SurgicalStructure
        assert fixture.enforcement_level in ("HARD_STOP", "SOFT_DAMP", "ADVISORY")
        assert fixture.plane_a_metric_code > 0
        assert fixture.safety_margin_px == 10
    print(f"  -> Generated {len(fixtures)} virtual fixtures")
    for f in fixtures:
        print(f"    {f.fixture_id}: {f.structure.value} ({f.enforcement_level})")
    
    # Test performance stats
    print("[TEST] Performance statistics...")
    stats = engine.get_performance_stats()
    assert stats["mode"] == "MOCK"
    assert stats["model_loaded"] is True
    assert stats["frames_processed"] >= 2
    assert stats["avg_processing_ms"] > 0
    print(f"  -> Stats: {stats}")
    
    engine.shutdown()
    print("  -> Engine shutdown successful")
    
    print("\\n[PASS] All SAM 3.1 MOCK mode tests passed!")

def test_sam31_clinical_integration():
    """Test SAM 3.1 Clinical Integration with ClinicalOversightEngine."""
    print("\\n[TEST] SAM 3.1 Clinical Integration...")
    
    # Import ClinicalOversightEngine
    from engine5_coe import ClinicalOversightEngine
    
    coe = ClinicalOversightEngine(enable_sam31=True)
    assert coe._sam31_engine is not None
    assert coe._sam31_integration is not None
    print("  -> ClinicalOversightEngine with SAM 3.1 initialized")
    
    # Create test frame
    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
    # Process surgical frame
    result = coe.process_surgical_frame(frame, patient_id="PT-12345")
    assert result is not None
    assert "segmentation" in result
    assert "virtual_fixtures" in result
    assert "surgical_phase" in result
    assert "plane_a_payload" in result
    assert "fhir_observation" in result
    assert "merkle_hash" in result
    assert "merkle_root" in result
    
    print(f"  -> Surgical phase: {result['surgical_phase']}")
    print(f"  -> Fixtures generated: {len(result['virtual_fixtures'])}")
    print(f"  -> FHIR observation: {result['fhir_observation']['resourceType']}")
    print(f"  -> Merkle hash: {result['merkle_hash'][:16]}...")
    print(f"  -> Merkle root: {result['merkle_root'][:16]}...")
    
    # Test performance stats
    stats = coe.get_sam31_performance_stats()
    assert stats is not None
    print(f"  -> Performance stats: {stats}")
    
    # Test surgical phase
    phase = coe.get_surgical_phase()
    assert phase is not None
    print(f"  -> Current phase: {phase}")
    
    coe.shutdown_sam31()
    print("  -> SAM 3.1 shutdown successful")
    
    print("\\n[PASS] SAM 3.1 Clinical Integration tests passed!")

def test_surgical_structure_enum():
    """Test SurgicalStructure enum values."""
    print("\\n[TEST] SurgicalStructure enum...")
    
    # Verify all expected structures exist
    expected_structures = [
        "tissue_generic", "liver", "gallbladder", "bile_duct",
        "hepatic_artery", "portal_vein", "ureter",
        "vessel_small", "vessel_large",
        "tool_grasper", "tool_scissors", "tool_cautery",
        "tool_suction", "tool_needle_driver", "tool_clip_applier",
        "suture", "clip", "unknown"
    ]
    
    for struct_name in expected_structures:
        struct = SurgicalStructure(struct_name)
        assert struct.value == struct_name
    
    print(f"  -> All {len(expected_structures)} surgical structures verified")
    print("\\n[PASS] SurgicalStructure enum tests passed!")


def test_segmentation_modes():
    """Test SegmentationMode enum."""
    print("\\n[TEST] SegmentationMode enum...")
    
    expected_modes = ["automatic", "point_prompt", "box_prompt", "mask_prompt", "grid_prompt"]
    for mode_name in expected_modes:
        mode = SegmentationMode(mode_name)
        assert mode.value == mode_name
    
    print(f"  -> All {len(expected_modes)} segmentation modes verified")
    print("\\n[PASS] SegmentationMode enum tests passed!")


def test_factory_function():
    """Test create_sam31_engine_from_env factory."""
    print("\\n[TEST] Factory function...")
    
    # Test with default environment (MOCK mode)
    engine = create_sam31_engine_from_env()
    assert engine.mode == "MOCK"
    engine.shutdown()
    print("  -> Factory creates MOCK engine by default")
    
    print("\\n[PASS] Factory function tests passed!")


if __name__ == "__main__":
    test_sam31_mock_mode()
    test_sam31_clinical_integration()
    test_surgical_structure_enum()
    test_segmentation_modes()
    test_factory_function()
    print("\\n" + "="*60)
    print("ALL SAM 3.1 VISION TESTS PASSED!")
    print("="*60)

def test_sam31_clinical_integration():
    """Test SAM 3.1 Clinical Integration with ClinicalOversightEngine."""
    print("\\n[TEST] SAM 3.1 Clinical Integration...")
    
    # Import ClinicalOversightEngine
    from engine5_coe import ClinicalOversightEngine
    
    coe = ClinicalOversightEngine(enable_sam31=True)
    assert coe._sam31_engine is not None
    assert coe._sam31_integration is not None
    print("  -> ClinicalOversightEngine with SAM 3.1 initialized")
    
    # Create test frame
    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    
    # Process surgical frame
    result = coe.process_surgical_frame(frame, patient_id="PT-12345")
    assert result is not None
    assert "segmentation" in result
    assert "virtual_fixtures" in result
    assert "surgical_phase" in result
    assert "plane_a_payload" in result
    assert "fhir_observation" in result
    assert "merkle_hash" in result
    assert "merkle_root" in result
    
    print(f"  -> Surgical phase: {result['surgical_phase']}")
    print(f"  -> Fixtures generated: {len(result['virtual_fixtures'])}")
    print(f"  -> FHIR observation: {result['fhir_observation']['resourceType']}")
    print(f"  -> Merkle hash: {result['merkle_hash'][:16]}...")
    print(f"  -> Merkle root: {result['merkle_root'][:16]}...")
    
    # Test performance stats
    stats = coe.get_sam31_performance_stats()
    assert stats is not None
    print(f"  -> Performance stats: {stats}")
    
    # Test surgical phase
    phase = coe.get_surgical_phase()
    assert phase is not None
    print(f"  -> Current phase: {phase}")
    
    coe.shutdown_sam31()
    print("  -> SAM 3.1 shutdown successful")
    
    print("\\n[PASS] SAM 3.1 Clinical Integration tests passed!")