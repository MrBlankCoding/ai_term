import json
import os
from typing import Any, Dict


DEFAULT_SETTINGS: Dict[str, Any] = {"provider": "mistral", "api_key": "", "safety_profile": "standard"}


class Settings:
    def __init__(self, path: str) -> None:
        self.path = path
        self.data: Dict[str, Any] = dict(DEFAULT_SETTINGS)
        self.load()

    def load(self) -> None:
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                obj = json.load(f)
        except Exception:
            return
        if isinstance(obj, dict):
            self.data.update(obj)

    def save(self) -> None:
        tmp_path = self.path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)
        os.replace(tmp_path, self.path)

    @property
    def provider(self) -> str:
        return str(self.data.get("provider", "mistral"))

    @provider.setter
    def provider(self, value: str) -> None:
        self.data["provider"] = value
        self.save()

    @property
    def api_key(self) -> str:
        value = self.data.get("api_key", "")
        return str(value) if value is not None else ""

    @api_key.setter
    def api_key(self, value: str) -> None:
        self.data["api_key"] = value or ""
        self.save()

    @property
    def safety_profile(self) -> str:
        value = self.data.get("safety_profile", "standard")
        return str(value) if value is not None else "standard"

    @safety_profile.setter
    def safety_profile(self, value: str) -> None:
        allowed = {"standard", "lenient", "strict"}
        v = (value or "standard").lower()
        if v not in allowed:
            v = "standard"
        self.data["safety_profile"] = v
        self.save()
