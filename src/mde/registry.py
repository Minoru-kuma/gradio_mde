"""Read a selected manifest; importing adapters belongs to the worker."""
import json
import re
from pathlib import Path

from .contracts import ModelInfo, check_schema


class ModelRegistry:
    def __init__(self, models_root: Path):
        self.models_root = Path(models_root)

    def get_model(self, model_id: str) -> ModelInfo:
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", model_id):
            raise ValueError("Invalid model ID")
        path = self.models_root / model_id / "manifest.json"
        data = json.loads(path.read_text())
        check_schema(data)
        for key in ("model_id", "display_name", "adapter_entrypoint", "upstream_revision",
                    "variants", "default_variant", "environment_refs", "capabilities"):
            if key not in data:
                raise ValueError(f"Manifest missing {key}")
        if data["model_id"] != model_id:
            raise ValueError("Manifest ID mismatch")
        if not re.fullmatch(r"[A-Za-z_][\w.]*(?:\:[A-Za-z_]\w*)", data["adapter_entrypoint"]):
            raise ValueError("Invalid adapter entrypoint")
        return ModelInfo(data)


def validate_parameters(schema: dict, supplied: dict) -> dict:
    """The 01A subset supports integer, number, boolean, string, enum and bounds."""
    properties = schema.get("properties", {})
    if supplied.keys() - properties.keys():
        raise ValueError(f"Unknown model parameters: {sorted(supplied.keys() - properties.keys())}")
    result = {}
    types = {"integer": int, "number": (int, float), "boolean": bool, "string": str}
    for key, rule in properties.items():
        if key in supplied:
            value = supplied[key]
        elif "default" in rule:
            value = rule["default"]
        elif key in schema.get("required", []):
            raise ValueError(f"Missing parameter: {key}")
        else:
            continue
        if not isinstance(value, types[rule["type"]]) or (rule["type"] in ("integer", "number") and isinstance(value, bool)):
            raise ValueError(f"Invalid type for {key}")
        if "enum" in rule and value not in rule["enum"]:
            raise ValueError(f"Invalid value for {key}")
        if "minimum" in rule and value < rule["minimum"]:
            raise ValueError(f"{key} below minimum")
        if "maximum" in rule and value > rule["maximum"]:
            raise ValueError(f"{key} above maximum")
        result[key] = value
    return result
