from typing import Any

from pydantic import BaseModel


class SOP(BaseModel):
    id: str
    name: str
    description: str
    rules: dict[str, Any]


class SOPConfiguration(BaseModel):
    version: str
    sops: list[SOP]
