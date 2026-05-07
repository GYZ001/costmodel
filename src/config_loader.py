"""
Configuration loader for Stock Analyst Agent
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


class ConfigLoader:
    def __init__(self, config_path: Optional[str] = None):
        if config_path:
            self.config_path = Path(config_path)
        else:
            self.config_path = Path(__file__).parent.parent / "config" / "config.yaml"

        self._config: Optional[Dict[str, Any]] = None

    def load(self) -> Dict[str, Any]:
        if self._config is None:
            if not self.config_path.exists():
                raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f)

        return self._config

    def get(self, key: str, default: Any = None) -> Any:
        config = self.load()
        keys = key.split('.')
        value = config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default

        return value

    def get_ai_config(self) -> Dict[str, Any]:
        return self.get('ai', {})

    def get_stock_config(self) -> Dict[str, Any]:
        return self.get('stock', {})

    def get_news_config(self) -> Dict[str, Any]:
        return self.get('news', {})

    def get_data_source_config(self) -> Dict[str, Any]:
        return self.get('data_source', {})


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    loader = ConfigLoader(config_path)
    return loader.load()
