"""
ACMS Configuration Management
Version: 1.0.0
Date: 2025-11-02
Owner: Platform.Engineering
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class ACMSConfig:
    """Immutable configuration values for ACMS runtime."""

    workspace_root: Path
    ledger_path: Path
    jaeger_endpoint: Optional[str]

    @staticmethod
    def from_env() -> "ACMSConfig":
        """Construct configuration from environment variables with defaults."""
        workspace_root = Path(
            os.getenv("ACMS_WORKSPACE_ROOT", Path.cwd())
        ).resolve()
        ledger_path = Path(
            os.getenv("ACMS_LEDGER_PATH", workspace_root / "ledger.jsonl")
        ).resolve()
        jaeger_endpoint = os.getenv("ACMS_JAEGER_ENDPOINT")
        return ACMSConfig(
            workspace_root=workspace_root,
            ledger_path=ledger_path,
            jaeger_endpoint=jaeger_endpoint,
        )


__all__ = ["ACMSConfig"]
