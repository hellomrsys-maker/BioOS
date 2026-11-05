# -*- coding: utf-8 -*-
"""
BioOS Cognitive Plane SAM 3.1 Vision
"""

import os
import time
import json
import base64
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

try:
    import cv2  # type: ignore
    _CV2_AVAILABLE = True
except ImportError:  # pragma: no cover
    _CV2_AVAILABLE = False
    cv2 = None  # type: ignore

try:
    import torch  # type: ignore
    _TORCH_AVAILABLE = True
except ImportError:  # pragma: no cover
    _TORCH_AVAILABLE = False
    torch = None  # type: ignore

try:
    from segment_anything import sam_model_registry, SamPredictor  # type: ignore
    _SAM_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SAM_AVAILABLE = False
    sam_model_registry = None  # type: ignore
    SamPredictor = None  # type: ignore


class SurgicalStructure(Enum):
    TISSUE_GENERIC = "tissue_generic"
    LIVER = "liver"
    GALLBLADDER = "gallbladder"
    BILE_DUCT = "bile_duct"
    HEPATIC_ARTERY = "hepatic_artery"
    PORTAL_VEIN = "portal_vein"
    URETER = "ureter"
    VESSEL_SMALL = "vessel_small"
    VESSEL_LARGE = "vessel_large"
    TOOL_GRASPER = "tool_grasper"
    TOOL_SCISSORS = "tool_scissors"
    TOOL_CAUTERY = "tool_cautery"
    TOOL_SUCTION = "tool_suction"
    TOOL_NEEDLE_DRIVER = "tool_needle_driver"
    TOOL_CLIP_APPLIER = "tool_clip_applier"
    SUTURE = "suture"
    CLIP = "clip"
    UNKNOWN = "unknown"


class SegmentationMode(Enum):
    AUTOMATIC = "automatic"
    POINT_PROMPT = "point_prompt"
    BOX_PROMPT = "box_prompt"
    MASK_PROMPT = "mask_prompt"
    GRID_PROMPT = "grid_prompt"


@dataclass
class SegmentationResult:
    frame_timestamp_ns: int
    frame_shape: Tuple[int, int]
    mode: SegmentationMode
    masks: List[np.ndarray]
    scores: List[float]
    structures: List[SurgicalStructure]
    bboxes: List[Tuple[int, int, int, int]]
    processing_ms: float
    model_version: str = "SAM-3.1"
    prompt_points: Optional[List[Tuple[int, int]]] = None
    prompt_labels: Optional[List[int]] = None


@dataclass
class VirtualFixture:
    fixture_id: str
    structure: SurgicalStructure
    mask: np.ndarray
    contour: List[Tuple[int, int]]
    safety_margin_px: int
    enforcement_level: str
    plane_a_metric_code: int
    created_ns: int = field(default_factory=time.time_ns)class SAM31VisionEngine:
    def __init__(
        self,
        mode: str = \"MOCK\",
        model_type: str = \"vit_h\",
        checkpoint_path: Optional[str] = None,
        meta_api_endpoint: Optional[str] = None,
        device: str = \"cuda\",
        confidence_threshold: float = 0.85,
        iou_threshold: float = 0.9,
    ):
        self.mode = mode.upper()
        self.model_type = model_type
        self.checkpoint_path = checkpoint_path
        self.meta_api_endpoint = meta_api_endpoint
        self.device = device
        self.confidence_threshold = confidence_threshold
        self.iou_threshold = iou_threshold
        
        self._predictor: Optional[SamPredictor] = None
        self._model_loaded = False
        self._frame_count = 0
        self._total_processing_ms = 0.0
        
        self._structure_colors = {
            SurgicalStructure.TISSUE_GENERIC: (0, 255, 0),
            SurgicalStructure.LIVER: (139, 69, 19),
            SurgicalStructure.GALLBLADDER: (0, 255, 255),
            SurgicalStructure.BILE_DUCT: (0, 128, 255),
            SurgicalStructure.HEPATIC_ARTERY: (255, 0, 0),
            SurgicalStructure.PORTAL_VEIN: (128, 0, 128),
            SurgicalStructure.URETER: (255, 165, 0),
            SurgicalStructure.VESSEL_SMALL: (255, 100, 100),
            SurgicalStructure.VESSEL_LARGE: (200, 0, 0),
            SurgicalStructure.TOOL_GRASPER: (0, 0, 255),
            SurgicalStructure.TOOL_SCISSORS: (0, 0, 200),
            SurgicalStructure.TOOL_CAUTERY: (255, 0, 255),
            SurgicalStructure.TOOL_SUCTION: (0, 255, 0),
            SurgicalStructure.TOOL_NEEDLE_DRIVER: (128, 128, 255),
            SurgicalStructure.TOOL_CLIP_APPLIER: (255, 128, 0),
            SurgicalStructure.SUTURE: (255, 255, 0),
            SurgicalStructure.CLIP: (255, 255, 255),
            SurgicalStructure.UNKNOWN: (128, 128, 128),
        }
        
        if self.mode == \"LOCAL_GPU\":
            self._init_local_gpu()
        elif self.mode == \"META_API\":
            self._init_meta_api()
        else:
            self._init_mock()
            
        logger.info(f\"SAM 3.1 Vision Engine initialized: mode={self.mode}, model={self.model_type}\")

    def _init_local_gpu(self) -> None:
        if not _TORCH_AVAILABLE or not _SAM_AVAILABLE:
            logger.warning(\"PyTorch or segment-anything not available; falling back to MOCK\")
            self.mode = \"MOCK\"
            self._init_mock()
            return
            
        if not self.checkpoint_path or not Path(self.checkpoint_path).exists():
            default_paths = [
                f\"/models/sam_{self.model_type}.pth\",
                f\"./models/sam_{self.model_type}.pth\",
                os.environ.get(\"SAM_CHECKPOINT\", \"\"),
            ]
            for p in default_paths:
                if p and Path(p).exists():
                    self.checkpoint_path = p
                    break
                    
        if not self.checkpoint_path or not Path(self.checkpoint_path).exists():
            logger.warning(f\"SAM checkpoint not found; falling back to MOCK\")
            self.mode = \"MOCK\"
            self._init_mock()
            return
            
        try:
            sam = sam_model_registry[self.model_type](checkpoint=self.checkpoint_path)
            sam.to(device=self.device)
            sam.eval()
            self._predictor = SamPredictor(sam)
            self._model_loaded = True
            logger.info(f\"Loaded SAM {self.model_type} from {self.checkpoint_path} on {self.device}\")
        except Exception as e:
            logger.error(f\"Failed to load SAM model: {e}; falling back to MOCK\")
            self.mode = \"MOCK\"
            self._init_mock()

    def _init_meta_api(self) -> None:
        if not self.meta_api_endpoint:
            self.meta_api_endpoint = os.environ.get(\"BIOOS_SAM_ENDPOINT\")
        if not self.meta_api_endpoint:
            logger.warning(\"BIOOS_SAM_ENDPOINT not set; falling back to MOCK\")
            self.mode = \"MOCK\"
            self._init_mock()
            return
        self._model_loaded = True
        logger.info(f\"Meta SAM API configured: {self.meta_api_endpoint}\")

    def _init_mock(self) -> None:
        self._model_loaded = True
        logger.info(\"SAM 3.1 running in MOCK mode (deterministic fallback)\")

    def segment_frame(
        self,
        frame: np.ndarray,
        mode: SegmentationMode = SegmentationMode.AUTOMATIC,
        prompt_points: Optional[List[Tuple[int, int]]] = None,
        prompt_labels: Optional[List[int]] = None,
        prompt_box: Optional[Tuple[int, int, int, int]] = None,
    ) -> SegmentationResult:
        start_ns = time.time_ns()
        
        if not _CV2_AVAILABLE:
            return self._mock_segment_frame(frame, mode, prompt_points, prompt_labels, prompt_box)
            
        if self.mode == \"LOCAL_GPU\" and self._predictor is not None:
            return self._segment_local_gpu(frame, mode, prompt_points, prompt_labels, prompt_box)
        elif self.mode == \"META_API\":
            return self._segment_meta_api(frame, mode, prompt_points, prompt_labels, prompt_box)
        else:
            return self._mock_segment_frame(frame, mode, prompt_points, prompt_labels, prompt_box)    def _segment_local_gpu(
        self,
        frame: np.ndarray,
        mode: SegmentationMode,
        prompt_points: Optional[List[Tuple[int, int]]],
        prompt_labels: Optional[List[int]],
        prompt_box: Optional[Tuple[int, int, int, int]],
    ) -> SegmentationResult:
        assert self._predictor is not None
        
        self._predictor.set_image(frame)
        
        if mode == SegmentationMode.POINT_PROMPT and prompt_points:
            point_coords = np.array(prompt_points, dtype=np.float32)
            point_labels = np.array(prompt_labels or [1] * len(prompt_points), dtype=np.int32)
            masks, scores, _ = self._predictor.predict(
                point_coords=point_coords,
                point_labels=point_labels,
                multimask_output=True,
            )
        elif mode == SegmentationMode.BOX_PROMPT and prompt_box:
            box = np.array(prompt_box, dtype=np.float32)
            masks, scores, _ = self._predictor.predict(
                box=box,
                multimask_output=True,
            )
        elif mode == SegmentationMode.AUTOMATIC:
            from segment_anything import SamAutomaticMaskGenerator
            mask_generator = SamAutomaticMaskGenerator(
                model=self._predictor.model,
                points_per_side=32,
                pred_iou_thresh=self.confidence_threshold,
                stability_score_thresh=0.95,
                crop_n_layers=1,
                crop_n_points_downscale_factor=2,
                min_mask_region_area=100,
            )
            anns = mask_generator.generate(frame)
            masks = [ann[\"segmentation\"] for ann in anns]
            scores = [ann[\"predicted_iou\"] for ann in anns]
        else:
            from segment_anything import SamAutomaticMaskGenerator
            mask_generator = SamAutomaticMaskGenerator(model=self._predictor.model)
            anns = mask_generator.generate(frame)
            masks = [ann[\"segmentation\"] for ann in anns]
            scores = [ann[\"predicted_iou\"] for ann in anns]
            prompt_points = None
            prompt_labels = None
            
        return self._postprocess_masks(frame, masks, scores, mode, prompt_points, prompt_labels, start_ns)    def _segment_meta_api(
        self,
        frame: np.ndarray,
        mode: SegmentationMode,
        prompt_points: Optional[List[Tuple[int, int]]],
        prompt_labels: Optional[List[int]],
        prompt_box: Optional[Tuple[int, int, int, int]],
    ) -> SegmentationResult:
        _, buffer = cv2.imencode(\".jpg\", cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
        frame_b64 = base64.b64encode(buffer).decode(\"utf-8\")
        
        payload = {
            \"image\": frame_b64,
            \"mode\": mode.value,
            \"prompt_points\": prompt_points,
            \"prompt_labels\": prompt_labels,
            \"prompt_box\": prompt_box,
            \"confidence_threshold\": self.confidence_threshold,
        }
        
        import urllib.request
        request = urllib.request.Request(
            f\"{self.meta_api_endpoint}/sam/segment\",
            data=json.dumps(payload).encode(\"utf-8\"),
            headers={\"Content-Type\": \"application/json\"},
            method=\"POST\",
        )
        with urllib.request.urlopen(request, timeout=5.0) as resp:
            result = json.loads(resp.read().decode(\"utf-8\"))
            
        masks = []
        for mask_b64 in result[\"masks\"]:
            mask_bytes = base64.b64decode(mask_b64)
            mask_arr = np.frombuffer(mask_bytes, dtype=np.uint8)
            mask = cv2.imdecode(mask_arr, cv2.IMREAD_GRAYSCALE) > 0
            masks.append(mask)
            
        scores = result[\"scores\"]
        return self._postprocess_masks(frame, masks, scores, mode, prompt_points, prompt_labels, start_ns=time.time_ns())

    def _mock_segment_frame(
        self,
        frame: np.ndarray,
        mode: SegmentationMode,
        prompt_points: Optional[List[Tuple[int, int]]],
        prompt_labels: Optional[List[int]],
        prompt_box: Optional[Tuple[int, int, int, int]],
    ) -> SegmentationResult:
        h, w = frame.shape[:2]
        
        np.random.seed(int(frame.mean() * 1000) % 2**32)
        
        masks = []
        scores = []
        structures = []
        bboxes = []
        
        structure_list = [
            SurgicalStructure.LIVER,
            SurgicalStructure.GALLBLADDER,
            SurgicalStructure.BILE_DUCT,
            SurgicalStructure.HEPATIC_ARTERY,
            SurgicalStructure.TOOL_GRASPER,
        ]
        
        for i, struct in enumerate(structure_list):
            cx = np.random.randint(w // 4, 3 * w // 4)
            cy = np.random.randint(h // 4, 3 * h // 4)
            rx = np.random.randint(w // 12, w // 6)
            ry = np.random.randint(h // 12, h // 6)
            
            y, x = np.ogrid[:h, :w]
            mask = ((x - cx) ** 2 / rx ** 2 + (y - cy) ** 2 / ry ** 2) <= 1
            
            noise = np.random.random((h, w)) < 0.05
            mask = mask ^ noise
            
            masks.append(mask)
            scores.append(0.92 + np.random.random() * 0.07)
            structures.append(struct)
            bboxes.append((cx - rx, cy - ry, cx + rx, cy + ry))
            
        return SegmentationResult(
            frame_timestamp_ns=time.time_ns(),
            frame_shape=(h, w),
            mode=mode,
            masks=masks,
            scores=scores,
            structures=structures,
            bboxes=bboxes,
            processing_ms=2.5 + np.random.random() * 1.5,
            model_version=\"SAM-3.1-MOCK\",
            prompt_points=prompt_points,
            prompt_labels=prompt_labels,
        )

    def _postprocess_masks(
        self,
        frame: np.ndarray,
        masks: List[np.ndarray],
        scores: List[float],
        mode: SegmentationMode,
        prompt_points: Optional[List[Tuple[int, int]]],
        prompt_labels: Optional[List[int]],
        start_ns: int,
    ) -> SegmentationResult:
        h, w = frame.shape[:2]
        
        filtered = [(m, s) for m, s in zip(masks, scores) if s >= self.confidence_threshold]
        if not filtered:
            return SegmentationResult(
                frame_timestamp_ns=time.time_ns(),
                frame_shape=(h, w),
                mode=mode,
                masks=[], scores=[], structures=[], bboxes=[],
                processing_ms=(time.time_ns() - start_ns) / 1e6,
                prompt_points=prompt_points,
                prompt_labels=prompt_labels,
            )
            
        masks, scores = zip(*filtered)
        masks = list(masks)
        scores = list(scores)
        
        masks, scores = self._nms_masks(masks, scores)
        
        structures = [self._classify_mask(frame, mask) for mask in masks]
        
        bboxes = [self._mask_to_bbox(mask) for mask in masks]
        
        processing_ms = (time.time_ns() - start_ns) / 1e6
        self._frame_count += 1
        self._total_processing_ms += processing_ms
        
        return SegmentationResult(
            frame_timestamp_ns=time.time_ns(),
            frame_shape=(h, w),
            mode=mode,
            masks=masks,
            scores=scores,
            structures=structures,
            bboxes=bboxes,
            processing_ms=processing_ms,
            prompt_points=prompt_points,
            prompt_labels=prompt_labels,
        )    def _nms_masks(self, masks: List[np.ndarray], scores: List[float]) -> Tuple[List[np.ndarray], List[float]]:
        if len(masks) <= 1:
            return masks, scores
            
        indices = np.argsort(scores)[::-1]
        keep = []
        
        for i in indices:
            keep_mask = True
            for j in keep:
                iou = self._mask_iou(masks[i], masks[j])
                if iou > self.iou_threshold:
                    keep_mask = False
                    break
            if keep_mask:
                keep.append(i)
                
        return [masks[i] for i in keep], [scores[i] for i in keep]

    def _mask_iou(self, mask1: np.ndarray, mask2: np.ndarray) -> float:
        intersection = np.logical_and(mask1, mask2).sum()
        union = np.logical_or(mask1, mask2).sum()
        return intersection / union if union > 0 else 0.0

    def _mask_to_bbox(self, mask: np.ndarray) -> Tuple[int, int, int, int]:
        rows = np.any(mask, axis=1)
        cols = np.any(mask, axis=0)
        if not rows.any() or not cols.any():
            return (0, 0, 0, 0)
        y1, y2 = np.where(rows)[0][[0, -1]]
        x1, x2 = np.where(cols)[0][[0, -1]]
        return (int(x1), int(y1), int(x2), int(y2))

    def _classify_mask(self, frame: np.ndarray, mask: np.ndarray) -> SurgicalStructure:
        masked_pixels = frame[mask]
        if len(masked_pixels) == 0:
            return SurgicalStructure.UNKNOWN
            
        mean_color = masked_pixels.mean(axis=0)
        std_color = masked_pixels.std(axis=0)
        
        y_coords, x_coords = np.where(mask)
        cy = y_coords.mean() / frame.shape[0]
        cx = x_coords.mean() / frame.shape[1]
        
        area = mask.sum()
        rel_area = area / (frame.shape[0] * frame.shape[1])
        
        r, g, b = mean_color
        
        if std_color.mean() < 30 and r > 100 and g < 80 and b < 80:
            return SurgicalStructure.TOOL_CAUTERY
        if std_color.mean() < 30 and r < 80 and g < 80 and b > 100:
            return SurgicalStructure.TOOL_GRASPER
        if std_color.mean() < 30 and r > 100 and g > 100 and b < 80:
            return SurgicalStructure.TOOL_SCISSORS
            
        if rel_area < 0.02 and r > g and r > b:
            return SurgicalStructure.VESSEL_SMALL if rel_area < 0.005 else SurgicalStructure.VESSEL_LARGE
        if rel_area < 0.02 and b > r and b > g:
            return SurgicalStructure.VESSEL_SMALL if rel_area < 0.005 else SurgicalStructure.VESSEL_LARGE
            
        if g > r and g > b and 0.3 < cx < 0.7 and 0.3 < cy < 0.7:
            return SurgicalStructure.BILE_DUCT
            
        if g > r and g > b and cx > 0.5 and cy > 0.5:
            return SurgicalStructure.GALLBLADDER
            
        if rel_area > 0.15 and r > 100 and g > 60 and g < 120 and b < 80:
            return SurgicalStructure.LIVER
            
        return SurgicalStructure.TISSUE_GENERIC    def generate_virtual_fixtures(
        self,
        segmentation: SegmentationResult,
        safety_margin_px: int = 10,
    ) -> List[VirtualFixture]:
        fixtures = []
        
        for i, (mask, struct, score) in enumerate(zip(segmentation.masks, segmentation.structures, segmentation.scores)):
            if score < self.confidence_threshold:
                continue
                
            critical_structures = {
                SurgicalStructure.BILE_DUCT: (\"HARD_STOP\", 1001),
                SurgicalStructure.HEPATIC_ARTERY: (\"HARD_STOP\", 1002),
                SurgicalStructure.PORTAL_VEIN: (\"HARD_STOP\", 1003),
                SurgicalStructure.URETER: (\"HARD_STOP\", 1004),
                SurgicalStructure.VESSEL_LARGE: (\"HARD_STOP\", 1005),
                SurgicalStructure.VESSEL_SMALL: (\"SOFT_DAMP\", 1006),
            }
            
            if struct in critical_structures:
                enforcement, metric_code = critical_structures[struct]
                
                if _CV2_AVAILABLE:
                    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (safety_margin_px * 2 + 1, safety_margin_px * 2 + 1))
                    dilated_mask = cv2.dilate(mask.astype(np.uint8), kernel) > 0
                else:
                    dilated_mask = mask
                    
                if _CV2_AVAILABLE:
                    contours, _ = cv2.findContours(dilated_mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    contour = contours[0].squeeze().tolist() if contours else []
                    if contour and isinstance(contour[0], int):
                        contour = [contour]
                else:
                    contour = []
                    
                fixture = VirtualFixture(
                    fixture_id=f\"VF_{struct.value}_{segmentation.frame_timestamp_ns}\",
                    structure=struct,
                    mask=dilated_mask,
                    contour=contour,
                    safety_margin_px=safety_margin_px,
                    enforcement_level=enforcement,
                    plane_a_metric_code=metric_code,
                )
                fixtures.append(fixture)
                
        return fixtures

    def visualize_segmentation(
        self,
        frame: np.ndarray,
        result: SegmentationResult,
        alpha: float = 0.5,
    ) -> np.ndarray:
        if not _CV2_AVAILABLE:
            return frame
            
        vis = frame.copy()
        
        for mask, struct, score in zip(result.masks, result.structures, result.scores):
            color = self._structure_colors.get(struct, (128, 128, 128))
            
            overlay = np.zeros_like(vis)
            overlay[mask] = color
            
            vis = cv2.addWeighted(vis, 1.0, overlay, alpha, 0)
            
            x1, y1, x2, y2 = self._mask_to_bbox(mask)
            cv2.rectangle(vis, (x1, y1), (x2, y2), color, 2)
            label = f\"{struct.value}: {score:.2f}\"
            cv2.putText(vis, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            
        return vis

    def get_performance_stats(self) -> Dict[str, Any]:
        avg_ms = self._total_processing_ms / self._frame_count if self._frame_count > 0 else 0
        return {
            \"mode\": self.mode,
            \"model_type\": self.model_type,
            \"model_loaded\": self._model_loaded,
            \"frames_processed\": self._frame_count,
            \"avg_processing_ms\": round(avg_ms, 2),
            \"fps\": round(1000 / avg_ms, 1) if avg_ms > 0 else 0,
            \"device\": self.device,
            \"confidence_threshold\": self.confidence_threshold,
        }

    def shutdown(self) -> None:
        if self._predictor is not None:
            del self._predictor
            self._predictor = None
        if _TORCH_AVAILABLE and torch is not None:
            torch.cuda.empty_cache()
        logger.info(\"SAM 3.1 Vision Engine shutdown complete\")
def create_sam31_engine_from_env() -> SAM31VisionEngine:
    mode = os.environ.get(\"BIOOS_SAM_MODE\", \"MOCK\").upper()
    model_type = os.environ.get(\"BIOOS_SAM_MODEL\", \"vit_h\")
    checkpoint = os.environ.get(\"BIOOS_SAM_CHECKPOINT\")
    endpoint = os.environ.get(\"BIOOS_SAM_ENDPOINT\")
    device = os.environ.get(\"BIOOS_SAM_DEVICE\", \"cuda\")
    
    return SAM31VisionEngine(
        mode=mode,
        model_type=model_type,
        checkpoint_path=checkpoint,
        meta_api_endpoint=endpoint,
        device=device,
    )


# ---------------------------------------------------------------------------
# Integration with ClinicalOversightEngine
# ---------------------------------------------------------------------------

class SAM31ClinicalIntegration:
    def __init__(self, sam_engine: SAM31VisionEngine, coe: 'ClinicalOversightEngine'):
        self.sam = sam_engine
        self.coe = coe
        self._phase_history: List[SegmentationResult] = []
        self._current_phase = \"UNKNOWN\"
        
    def process_surgical_frame(
        self,
        frame: np.ndarray,
        patient_id: str,
        prompt_points: Optional[List[Tuple[int, int]]] = None,
    ) -> Dict[str, Any]:
        segmentation = self.sam.segment_frame(
            frame,
            mode=SegmentationMode.AUTOMATIC,
            prompt_points=prompt_points,
        )
        
        fixtures = self.sam.generate_virtual_fixtures(segmentation)
        
        self._phase_history.append(segmentation)
        if len(self._phase_history) > 30:
            self._phase_history.pop(0)
        phase = self._recognize_phase()
        self._current_phase = phase
        
        plane_a_payload = self._encode_fixtures_for_plane_a(fixtures)
        
        fhir_obs = self._generate_fhir_observation(patient_id, segmentation, phase)
        
        audit_record = {
            \"patient_id\": patient_id,
            \"timestamp_ns\": segmentation.frame_timestamp_ns,
            \"phase\": phase,
            \"structures_detected\": [s.value for s in segmentation.structures],
            \"fixtures_generated\": len(fixtures),
            \"plane_a_payload\": plane_a_payload,
            \"fhir_observation\": fhir_obs,
        }
        merkle_hash = self.coe.merkle_tree.append_record(audit_record)
        
        return {
            \"segmentation\": segmentation,
            \"virtual_fixtures\": fixtures,
            \"surgical_phase\": phase,
            \"plane_a_payload\": plane_a_payload,
            \"fhir_observation\": fhir_obs,
            \"merkle_hash\": merkle_hash,
            \"merkle_root\": self.coe.merkle_tree.get_root_hash(),
        }

    def _recognize_phase(self) -> str:
        if len(self._phase_history) < 5:
            return \"INSUFFICIENT_DATA\"
            
        structure_counts = {}
        for seg in self._phase_history[-10:]:
            for s in seg.structures:
                structure_counts[s.value] = structure_counts.get(s.value, 0) + 1
                
        if structure_counts.get(\"tool_cautery\", 0) > 3:
            return \"HEMOSTASIS\"
        if structure_counts.get(\"tool_scissors\", 0) > 2:
            return \"DISSECTION\"
        if structure_counts.get(\"tool_clip_applier\", 0) > 1:
            return \"CLIPPING\"
        if structure_counts.get(\"tool_needle_driver\", 0) > 2:
            return \"SUTURING\"
        if structure_counts.get(\"tool_grasper\", 0) > 5:
            return \"RETRACTION\"
            
        return \"EXPLORATION\"    def _encode_fixtures_for_plane_a(self, fixtures: List[VirtualFixture]) -> Dict[str, Any]:
        return {
            \"fixture_count\": len(fixtures),
            \"fixtures\": [
                {
                    \"fixture_id\": f.fixture_id,
                    \"structure\": f.structure.value,
                    \"enforcement\": f.enforcement_level,
                    \"metric_code\": f.plane_a_metric_code,
                    \"bbox\": self.sam._mask_to_bbox(f.mask) if f.mask.any() else [0, 0, 0, 0],
                    \"safety_margin_px\": f.safety_margin_px,
                }
                for f in fixtures
            ],
            \"timestamp_ns\": time.time_ns(),
        }

    def _generate_fhir_observation(
        self,
        patient_id: str,
        segmentation: SegmentationResult,
        phase: str,
    ) -> Dict[str, Any]:
        return {
            \"resourceType\": \"Observation\",
            \"id\": f\"bioos-surgical-{int(segmentation.frame_timestamp_ns / 1e6)}\",
            \"status\": \"final\",
            \"category\": [{
                \"coding\": [{
                    \"system\": \"http://terminology.hl7.org/CodeSystem/observation-category\",
                    \"code\": \"survey\",
                    \"display\": \"Survey\"
                }]
            }],
            \"code\": {
                \"coding\": [{
                    \"system\": \"http://loinc.org\",
                    \"code\": \"95418-0\",
                    \"display\": \"Surgical field assessment\"
                }]
            },
            \"subject\": {\"reference\": f\"Patient/{patient_id}\"},
            \"effectiveInstant\": f\"{segmentation.frame_timestamp_ns / 1e9:.9f}\",
            \"valueString\": f\"Surgical phase: {phase}; Structures: {', '.join(s.value for s in segmentation.structures)}\",
            \"component\": [
                {
                    \"code\": {\"text\": \"Surgical Phase\"},
                    \"valueString\": phase,
                },
                {
                    \"code\": {\"text\": \"Structures Detected\"},
                    \"valueString\": json.dumps([s.value for s in segmentation.structures]),
                },
                {
                    \"code\": {\"text\": \"SAM 3.1 Confidence\"},
                    \"valueQuantity\": {
                        \"value\": round(np.mean(segmentation.scores), 3) if segmentation.scores else 0,
                        \"unit\": \"IoU\",
                        \"system\": \"http://unitsofmeasure.org\",
                        \"code\": \"1\",
                    }
                }
            ],
            \"meta\": {
                \"extension\": [{
                    \"url\": \"http://bioos.org/fhir/StructureDefinition/sam31-processing-ms\",
                    \"valueDecimal\": round(segmentation.processing_ms, 2),
                }]
            }
        }