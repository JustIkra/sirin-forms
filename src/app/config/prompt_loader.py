from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml


@dataclass(frozen=True)
class PromptConfig:
    system_prompt: str
    user_template: str
    temperature: float
    max_tokens: int


_PROMPTS_DIR = Path(__file__).parent / "prompts"


@lru_cache(maxsize=None)
def load_prompt(name: str) -> PromptConfig:
    path = _PROMPTS_DIR / f"{name}.yaml"
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return PromptConfig(
        system_prompt=data["system_prompt"].strip(),
        user_template=data["user_template"].strip(),
        temperature=float(data["temperature"]),
        max_tokens=int(data["max_tokens"]),
    )
