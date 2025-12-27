"""
Configuration loader and validator for price tracker.
"""

import os
from pathlib import Path
from typing import List, Dict, Any, Optional

import yaml
from pydantic import BaseModel, HttpUrl, field_validator


class ItemConfig(BaseModel):
    """Configuration for a single item to track."""
    url: str
    scrape_frequency: str = "daily"

    @field_validator('url')
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate URL format."""
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        return v

    @field_validator('scrape_frequency')
    @classmethod
    def validate_frequency(cls, v: str) -> str:
        """Validate scrape frequency."""
        valid_frequencies = ['daily', 'weekly', 'hourly']
        if v not in valid_frequencies:
            raise ValueError(f'scrape_frequency must be one of {valid_frequencies}')
        return v


class Config(BaseModel):
    """Main configuration containing all items."""
    items: List[ItemConfig]


def load_config(config_path: str = "config/items.yaml") -> Config:
    """
    Load and validate configuration from YAML file.

    Args:
        config_path: Path to YAML config file

    Returns:
        Validated Config object

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config is invalid
    """
    path = Path(config_path)

    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(path, 'r') as f:
        data = yaml.safe_load(f)

    if not data or 'items' not in data:
        raise ValueError("Config must contain 'items' key")

    try:
        config = Config(**data)
        return config
    except Exception as e:
        raise ValueError(f"Invalid configuration: {e}")


def get_items_from_config(config_path: str = "config/items.yaml") -> List[Dict[str, Any]]:
    """
    Load items from config as dictionaries.

    Args:
        config_path: Path to YAML config file

    Returns:
        List of item dictionaries
    """
    config = load_config(config_path)
    return [item.model_dump() for item in config.items]


def validate_config_file(config_path: str = "config/items.yaml") -> bool:
    """
    Validate config file without raising exceptions.

    Args:
        config_path: Path to YAML config file

    Returns:
        True if valid, False otherwise
    """
    try:
        load_config(config_path)
        return True
    except Exception as e:
        print(f"Config validation failed: {e}")
        return False
