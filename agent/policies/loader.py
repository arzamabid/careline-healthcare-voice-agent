from pathlib import Path

import yaml

from agent.policies.models import SOPConfiguration

DEFAULT_SOP_PATH = Path("agent/policies/healthcare_sops.yaml")


def load_sops(path: Path = DEFAULT_SOP_PATH) -> SOPConfiguration:
    with path.open("r", encoding="utf-8") as file:
        raw_data = yaml.safe_load(file)

    return SOPConfiguration.model_validate(raw_data)
