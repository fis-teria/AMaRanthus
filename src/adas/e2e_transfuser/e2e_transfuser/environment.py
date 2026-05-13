import importlib.util
import json
import os
from pathlib import Path


MODEL_FILES = ("config.json", "args.txt", "README.md")


def resolve_path(value, env_name=None):
    candidate = value or (os.environ.get(env_name, "") if env_name else "")
    if not candidate:
        return None
    return Path(candidate).expanduser()


def module_available(name):
    return importlib.util.find_spec(name) is not None


def inspect_lead_environment(
    lead_project_root=None,
    model_path=None,
    model_variant="tfv6_resnet34",
    runtime_mode="lead_python",
    precision_mode="fp32",
    allow_int8=False,
    disable_aux_heads=True,
    single_checkpoint=True,
):
    lead_root = resolve_path(lead_project_root, "LEAD_PROJECT_ROOT")
    model_dir = resolve_path(model_path)

    pth_files = []
    model_files = {}
    if model_dir is not None and model_dir.exists():
        pth_files = sorted(str(path.name) for path in model_dir.glob("*.pth"))
        model_files = {name: (model_dir / name).exists() for name in MODEL_FILES}

    lead_package = None
    if lead_root is not None:
        lead_package = lead_root / "lead"

    dependencies = {
        "torch": module_available("torch"),
        "onnxruntime": module_available("onnxruntime"),
        "tensorrt": module_available("tensorrt"),
        "lead_importable": module_available("lead"),
    }

    checks = {
        "lead_project_root_set": lead_root is not None,
        "lead_project_root_exists": lead_root.exists() if lead_root is not None else False,
        "lead_package_exists": lead_package.exists() if lead_package is not None else False,
        "model_path_set": model_dir is not None,
        "model_path_exists": model_dir.exists() if model_dir is not None else False,
        "has_checkpoint": bool(pth_files),
    }

    blocking = []
    if runtime_mode == "lead_python":
        if not dependencies["torch"]:
            blocking.append("python module 'torch' is not importable")
        if not checks["lead_project_root_exists"] and not dependencies["lead_importable"]:
            blocking.append("LEAD project root is missing and python module 'lead' is not importable")
        if not checks["has_checkpoint"]:
            blocking.append("model_path does not contain .pth checkpoint files")
    elif runtime_mode == "onnx":
        if not dependencies["onnxruntime"]:
            blocking.append("python module 'onnxruntime' is not importable")
    elif runtime_mode == "tensorrt":
        if precision_mode == "int8" and not allow_int8:
            blocking.append("INT8 requires explicit calibration data and allow_int8=true at runtime")
        if not dependencies["tensorrt"]:
            blocking.append("python module 'tensorrt' is not importable")
    if precision_mode == "int8" and runtime_mode != "tensorrt":
        blocking.append("INT8 is only supported for TensorRT runtime in this adapter")

    return {
        "model_variant": model_variant,
        "runtime_mode": runtime_mode,
        "precision_mode": precision_mode,
        "allow_int8": bool(allow_int8),
        "disable_aux_heads": bool(disable_aux_heads),
        "single_checkpoint": bool(single_checkpoint),
        "lead_project_root": str(lead_root) if lead_root is not None else "",
        "model_path": str(model_dir) if model_dir is not None else "",
        "checks": checks,
        "dependencies": dependencies,
        "model_files": model_files,
        "checkpoint_files": pth_files,
        "blocking_reasons": blocking,
        "ready": not blocking,
    }


def dumps_summary(summary):
    return json.dumps(summary, indent=2, sort_keys=True)
