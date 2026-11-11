"""Metadata-only directory discovery; adapters and environments are never loaded."""
from dataclasses import dataclass
import math
from pathlib import Path, PurePosixPath
import re

from .contracts import ModelInfo, check_schema
from .storage import read_json


_ID = r"[a-z0-9][a-z0-9_-]*"
_TYPES = {"integer": int, "number": (int, float), "boolean": bool, "string": str}


def _identifier(value, label):
    if not isinstance(value, str) or not re.fullmatch(_ID, value):
        raise ValueError(f"Invalid {label}")


def _strings(value, label):
    if (not isinstance(value, list) or not value or
            any(not isinstance(item, str) or not item for item in value) or len(set(value)) != len(value)):
        raise ValueError(f"{label} must be a nonempty unique string list")


def _scalar(value, rule, key):
    kind = rule.get("type")
    if not isinstance(kind, str) or kind not in _TYPES:
        raise ValueError(f"Unsupported parameter type for {key}")
    if (not isinstance(value, _TYPES[kind]) or
            (kind in ("integer", "number") and isinstance(value, bool))):
        raise ValueError(f"Invalid type for {key}")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"Non-finite parameter: {key}")
    if "enum" in rule and value not in rule["enum"]:
        raise ValueError(f"Invalid value for {key}")
    if "minimum" in rule and value < rule["minimum"]:
        raise ValueError(f"{key} below minimum")
    if "maximum" in rule and value > rule["maximum"]:
        raise ValueError(f"{key} above maximum")


def validate_parameter_schema(schema: dict) -> None:
    """Explicit scalar subset, including legacy schemas without type/closed-object keys."""
    if not isinstance(schema, dict):
        raise ValueError("Parameter schema must be an object")
    if schema.keys() - {"type", "properties", "required", "additionalProperties", "title", "description"}:
        raise ValueError("Unsupported parameter schema keyword")
    if schema.get("type", "object") != "object" or schema.get("additionalProperties", False) is not False:
        raise ValueError("Parameters must be a closed object")
    properties, required = schema.get("properties", {}), schema.get("required", [])
    if not isinstance(properties, dict) or not isinstance(required, list):
        raise ValueError("Invalid parameter properties / required")
    if (any(not isinstance(key, str) or key not in properties for key in required)
            or len(set(required)) != len(required)):
        raise ValueError("Required parameters must be unique known names")
    for key, rule in properties.items():
        if not isinstance(key, str) or not key or not isinstance(rule, dict):
            raise ValueError("Invalid parameter definition")
        if rule.keys() - {"type", "enum", "minimum", "maximum", "default", "description", "title"}:
            raise ValueError(f"Unsupported parameter rule for {key}")
        if not isinstance(rule.get("type"), str) or rule["type"] not in _TYPES:
            raise ValueError(f"Unsupported parameter type for {key}")
        for bound in ("minimum", "maximum"):
            if bound in rule and (rule["type"] not in ("integer", "number") or
                    type(rule[bound]) not in (int, float) or
                    (isinstance(rule[bound], float) and not math.isfinite(rule[bound]))):
                raise ValueError(f"Invalid {bound} for {key}")
        if "minimum" in rule and "maximum" in rule and rule["minimum"] > rule["maximum"]:
            raise ValueError(f"Reversed bounds for {key}")
        if "enum" in rule:
            enum = rule["enum"]
            if not isinstance(enum, list) or not enum:
                raise ValueError(f"Empty or malformed enum for {key}")
            for index, item in enumerate(enum):
                _scalar(item, {k: v for k, v in rule.items() if k != "enum"}, key)
                if item in enum[:index]:
                    raise ValueError(f"Duplicate enum for {key}")
        if "default" in rule:
            _scalar(rule["default"], rule, key)


def validate_parameters(schema: dict, supplied: dict) -> dict:
    validate_parameter_schema(schema)
    if not isinstance(supplied, dict):
        raise ValueError("Parameters must be an object")
    properties = schema.get("properties", {})
    if supplied.keys() - properties.keys():
        raise ValueError("Unknown model parameters")
    result = {}
    for key, rule in properties.items():
        if key in supplied:
            value = supplied[key]
        elif "default" in rule:
            value = rule["default"]
        elif key in schema.get("required", []):
            raise ValueError(f"Missing parameter: {key}")
        else:
            continue
        _scalar(value, rule, key)
        result[key] = value
    return result


def _metadata(data):
    capabilities = data.get("capabilities")
    if (not isinstance(capabilities, dict) or not isinstance(capabilities.get("depth"), dict)
            or capabilities["depth"].get("status") not in ("supported", "conditional")):
        raise ValueError("Manifest must declare depth capability")
    for key, capability in capabilities.items():
        if (not isinstance(capability, dict) or
                capability.get("status") not in ("supported", "conditional", "unsupported")):
            raise ValueError(f"Invalid capability: {key}")
        if "condition" in capability and not isinstance(capability["condition"], str):
            raise ValueError(f"Invalid condition description: {key}")
    for key in ("supported_devices", "supported_dtypes"):
        _strings(data.get(key), key)
    validate_parameter_schema(data.get("parameter_schema", {}))
    constraints = data.get("input_constraints", {})
    if not isinstance(constraints, dict):
        raise ValueError("Input constraints must be an object")
    for key in ("min_views", "max_views"):
        if key in constraints and (type(constraints[key]) is not int or constraints[key] < 1):
            raise ValueError(f"Invalid input constraint: {key}")
    if constraints.get("min_views", 1) > constraints.get("max_views", constraints.get("min_views", 1)):
        raise ValueError("Reversed view limits")
    references = data.get("environment_refs")
    if not isinstance(references, list) or not references:
        raise ValueError("No environment references")
    ids = set()
    for reference in references:
        if not isinstance(reference, dict):
            raise ValueError("Malformed environment reference")
        key = reference.get("environment_id")
        _identifier(key, "environment ID")
        if key in ids:
            raise ValueError("Duplicate environment ID")
        ids.add(key)
        path = reference.get("definition_ref")
        if (not isinstance(path, str) or not path or "\\" in path or "\x00" in path or
                not PurePosixPath(path).parts or
                PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts):
            raise ValueError("Invalid environment definition reference")
        if "worker_protocol_version" in reference:
            check_schema({"schema_version": reference["worker_protocol_version"]})


def validate_manifest(data: dict, directory_id: str) -> ModelInfo:
    check_schema(data)
    _identifier(directory_id, "plugin directory")
    if data.get("model_id") != directory_id:
        raise ValueError("Manifest ID mismatch")
    for key in ("display_name", "adapter_entrypoint", "upstream_revision", "default_variant"):
        if not isinstance(data.get(key), str) or not data[key]:
            raise ValueError(f"Manifest missing or invalid {key}")
    if not re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*:[A-Za-z_]\w*", data["adapter_entrypoint"]):
        raise ValueError("Invalid adapter entrypoint")
    variants = data.get("variants")
    if not isinstance(variants, list) or not variants:
        raise ValueError("No variants")
    info, ids = ModelInfo(data), set()
    _metadata(data)
    for variant in variants:
        if not isinstance(variant, dict):
            raise ValueError("Malformed variant")
        key = variant.get("variant_id")
        _identifier(key, "variant ID")
        if key in ids:
            raise ValueError("Duplicate variant ID")
        ids.add(key)
        _metadata(info.effective_variant(key))
    if data["default_variant"] not in ids:
        raise ValueError("Unknown default variant")
    return info


@dataclass(frozen=True)
class RegistryDiscovery:
    models: list[ModelInfo]
    diagnostics: dict[str, str]


class ModelRegistry:
    def __init__(self, models_root: Path):
        self.models_root = Path(models_root)

    def discover(self) -> RegistryDiscovery:
        """Sorted valid models plus per-directory errors; duplicate IDs are fatal."""
        models, diagnostics, owners = [], {}, {}
        for path in sorted(self.models_root.glob("*/manifest.json")):
            directory_id = path.parent.name
            try:
                data = read_json(path)
            except (OSError, ValueError) as error:
                diagnostics[directory_id] = str(error)
                continue
            key = data.get("model_id") if isinstance(data, dict) else None
            if isinstance(key, str):
                if key in owners:
                    raise ValueError(f"Duplicate plugin ID {key}: {owners[key]}, {directory_id}")
                owners[key] = directory_id
            try:
                models.append(validate_manifest(data, directory_id))
            except (ValueError, TypeError, AttributeError) as error:
                diagnostics[directory_id] = str(error)
        return RegistryDiscovery(models, diagnostics)

    def list_models(self) -> list[ModelInfo]:
        return self.discover().models

    def get_model(self, model_id: str) -> ModelInfo:
        _identifier(model_id, "model ID")
        discovery = self.discover()
        if model_id in discovery.diagnostics:
            raise ValueError(f"Invalid manifest for {model_id}: {discovery.diagnostics[model_id]}")
        for info in discovery.models:
            if info.model_id == model_id:
                return info
        raise ValueError(f"Unknown model: {model_id}")
