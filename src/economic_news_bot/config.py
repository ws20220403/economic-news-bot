import json
import os
from pathlib import Path
from typing import Any, Dict


def load_config(path: str) -> Dict[str, Any]:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        text = handle.read()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "config.yaml is not JSON-compatible and PyYAML is not installed. "
                "Install requirements.txt or keep config.yaml as JSON-compatible YAML."
            ) from exc
        data = yaml.safe_load(text)

    if not isinstance(data, dict):
        raise ValueError("Config root must be an object.")

    data["_config_dir"] = str(config_path.parent.resolve())
    return data


def read_env_file(path: str) -> None:
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)
