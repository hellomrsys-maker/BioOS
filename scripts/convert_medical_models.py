"""Convert selected SimReady USD/FBX assets into browser-ready GLB files.

Run with Blender:
  blender --background --python scripts/convert_medical_models.py -- \
    --source-root C:/Users/sysyo/Downloads/model --output-root web/models/equipment
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy


ASSETS = {
    "robotic_system_a01": ("robotic_system_a01/simready_usd/sm_robotic_system_a01_01.usd", "surgical-robot"),
    "robotic_system_console_b01": ("robotic_system_console_b01/simready_usd/sm_robotic_system_console_b01_01.usd", "surgeon-console"),
    "bed_hospital_standard_a01": ("bed_hospital_standard_a01/simready_usd/sm_bed_hospital_standard_a01_01.usd", "hospital-bed"),
    "monitor_patient_a01": ("monitor_patient_a01/simready_usd/sm_monitor_patient_a01_01.usd", "patient-monitor"),
    "anesthesia_machine_a01": ("anesthesia_machine_a01/simready_usd/sm_anesthesia_machine_a01_01.usd", "anesthesia-machine"),
    "video_system_a01": ("video_system_a01/simready_usd/sm_video_system_a01_01.usd", "endoscopy-tower"),
    "pump_suction_surgical_a01": ("pump_suction_surgical_a01/simready_usd/sm_pump_suction_surgical_a01_01.usd", "surgical-suction"),
    "pad_vital_a01": ("pad_vital_a01/simready_usd/sm_pad_vital_a01_01.usd", "vitals-tablet"),
    "device_vein_finder_a01": ("device_vein_finder_a01/simready_usd/sm_device_vein_finder_a01_01.usd", "vein-finder"),
    "container_system_sterilising_b02": ("container_system_sterilising_b02/simready_usd/sm_container_system_sterilising_b02_01.usd", "sterilization-tray"),
    "drainage_pumpSystem_a01": ("drainage_pumpSystem_a01/simready_usd/sm_drainage_pumpSystem_a01_01.usd", "drainage-pump"),
    "device_inhaler_a01": ("device_inhaler_a01/simready_usd/sm_device_inhaler_a01_01.usd", "inhaler"),
    "device_insulin_lancing_a01": ("device_insulin_lancing_a01/simready_usd/sm_device_insulin_lancing_a01_01.usd", "glucose-lancing-device"),
    "mask_nebulization_a01": ("mask_nebulization_a01/simready_usd/sm_mask_nebulization_a01_01.usd", "nebulizer-mask"),
    "screen_hospital_b03": ("screen_hospital_b03/simready_usd/sm_screen_hospital_b03_01.usd", "privacy-screen"),
    "desk_a01": ("desk_a01/simready_usd/sm_desk_a01_01.usd", "clinical-desk"),
    "raise_a3_ultra_t3d0": ("raise_a3_ultra_t3d0/simready_usd/raise_a3_ultra_t3d0.usda", "robotic-arm-system"),
    "meshysurgicalrobot": ("Meshy_AI_surgical_operating_robot_20261029_image-to-3d-texture_fbx/Meshy_AI_surgical_operating_robot_20261029_image-to-3d-texture_fbx/Meshy_AI_surgical_operating_robot_20261029_image-to-3d-texture.fbx", "surgical-robot-concept"),
    "ctinjector": ("sm_CT_injection_system_a01_01.usd", "ct-contrast-injector"),
}


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--assets", nargs="*", default=list(ASSETS))
    parser.add_argument("--max-texture-size", type=int, default=1024)
    parser.add_argument("--jpeg-quality", type=int, default=82)
    return parser.parse_args(argv)


def reset_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablock in (bpy.data.meshes, bpy.data.curves, bpy.data.materials, bpy.data.images, bpy.data.cameras, bpy.data.lights):
        for block in list(datablock):
            if block.users == 0:
                datablock.remove(block)


def convert(asset_key: str, source_root: Path, output_root: Path, max_texture_size: int, jpeg_quality: int) -> None:
    relative_source, output_name = ASSETS[asset_key]
    source = source_root / relative_source
    if not source.is_file():
        print(f"SKIP {asset_key}: source file not found: {source}", flush=True)
        return

    reset_scene()
    if source.suffix.lower() in {".usd", ".usda", ".usdc"}:
        bpy.ops.wm.usd_import(
            filepath=str(source),
            import_meshes=True,
            import_materials=True,
            import_usd_preview=True,
            import_render=True,
            import_textures_mode="IMPORT_PACK",
            support_scene_instancing=True,
        )
    elif source.suffix.lower() == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(source), use_image_search=True, automatic_bone_orientation=True)
    else:
        print(f"SKIP {asset_key}: unsupported source extension {source.suffix}", flush=True)
        return

    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not meshes:
        print(f"SKIP {asset_key}: import produced no meshes", flush=True)
        return

    for image in bpy.data.images:
        width, height = image.size
        if width <= 0 or height <= 0:
            continue
        longest = max(width, height)
        if longest > max_texture_size:
            scale = max_texture_size / longest
            image.scale(max(1, round(width * scale)), max(1, round(height * scale)))

    output_root.mkdir(parents=True, exist_ok=True)
    output = output_root / f"{output_name}.glb"
    bpy.ops.export_scene.gltf(
        filepath=str(output),
        export_format="GLB",
        export_image_format="JPEG",
        export_image_quality=jpeg_quality,
        export_materials="EXPORT",
        export_apply=True,
        export_yup=True,
        export_animations=False,
        use_selection=False,
        export_lights=False,
        export_cameras=False,
    )
    print(f"DONE {asset_key}: meshes={len(meshes)} output={output} bytes={output.stat().st_size}", flush=True)


def main() -> None:
    args = parse_args()
    for key in args.assets:
        if key not in ASSETS:
            print(f"SKIP {key}: unknown asset key", flush=True)
            continue
        try:
            convert(key, args.source_root, args.output_root, args.max_texture_size, args.jpeg_quality)
        except Exception as exc:  # Keep processing the remaining catalog assets.
            print(f"ERROR {key}: {type(exc).__name__}: {exc}", flush=True)


if __name__ == "__main__":
    main()
