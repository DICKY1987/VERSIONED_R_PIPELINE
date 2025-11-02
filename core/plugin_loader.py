"""ACMS Plugin Discovery and Loading
Version: 1.0.0
Date: 2025-11-02
Implements: Dynamic plugin discovery
Owner: Platform.Engineering
"""
from __future__ import annotations

import importlib.util
import json
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional


class PluginError(RuntimeError):
    """Base class for plugin related issues."""


class PluginValidationError(PluginError):
    """Raised when a plugin fails validation checks."""


class PluginImportError(PluginError):
    """Raised when importing a plugin handler fails."""


@dataclass(frozen=True, slots=True)
class PluginSpec:
    """Representation of the human-authored ``plugin.spec.json`` file."""

    name: str
    version: str
    handles_event: str
    path: Path
    raw: Dict[str, Any]

    @classmethod
    def from_file(cls, path: Path) -> "PluginSpec":
        data = _read_json(path)
        try:
            name = data["name"]
            version = data["version"]
            handles_event = data["handles_event"]
        except KeyError as exc:  # pragma: no cover - defensive branch
            raise PluginValidationError(
                f"Spec missing required field: {exc.args[0]}"
            ) from exc
        return cls(name=name, version=version, handles_event=handles_event, path=path, raw=data)


@dataclass(frozen=True, slots=True)
class PluginManifest:
    """Representation of the generated ``manifest.json`` file."""

    name: str
    version: str
    handles_event: str
    generated_at: Optional[str]
    contract_version: Optional[str]
    path: Path
    raw: Dict[str, Any]

    @classmethod
    def from_file(cls, path: Path) -> "PluginManifest":
        data = _read_json(path)
        try:
            name = data["name"]
            version = data["version"]
            handles_event = data["handles_event"]
        except KeyError as exc:
            raise PluginValidationError(
                f"Manifest missing required field: {exc.args[0]}"
            ) from exc
        generated_at = data.get("generated_at")
        contract_version = data.get("contract_version")
        return cls(
            name=name,
            version=version,
            handles_event=handles_event,
            generated_at=generated_at,
            contract_version=contract_version,
            path=path,
            raw=data,
        )


@dataclass(slots=True)
class PluginDefinition:
    """Loaded plugin definition including the ``handle`` callable."""

    name: str
    version: str
    handles_event: str
    root: Path
    spec: PluginSpec
    manifest: PluginManifest
    module: ModuleType
    handler: Callable[[Dict[str, Any]], List[Dict[str, Any]]]

    def invoke(self, event: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute the plugin's ``handle`` function with validation."""

        proposals = self.handler(event)
        if proposals is None:
            return []
        if not isinstance(proposals, list):
            raise PluginValidationError(
                f"Plugin '{self.name}' returned non-list value: {type(proposals)!r}"
            )
        cleaned: List[Dict[str, Any]] = []
        for proposal in proposals:
            if not isinstance(proposal, dict):
                raise PluginValidationError(
                    f"Plugin '{self.name}' produced non-dict proposal: {proposal!r}"
                )
            action = proposal.get("action")
            payload = proposal.get("payload")
            if not isinstance(action, str) or not action:
                raise PluginValidationError(
                    f"Plugin '{self.name}' proposal missing string action: {proposal!r}"
                )
            if not isinstance(payload, dict):
                raise PluginValidationError(
                    f"Plugin '{self.name}' proposal missing dict payload: {proposal!r}"
                )
            cleaned.append({"action": action, "payload": payload})
        return cleaned


DEFAULT_REQUIRED_FILES = (
    "plugin.spec.json",
    "manifest.json",
    "policy_snapshot.json",
    "ledger_contract.json",
    "handler.py",
)


class PluginLoader:
    """Discover and import ACMS plugins from the ``plugins`` directory."""

    def __init__(
        self,
        plugin_root: Path | str | None = None,
        required_files: Iterable[str] = DEFAULT_REQUIRED_FILES,
    ) -> None:
        self.plugin_root = (
            Path(plugin_root)
            if plugin_root is not None
            else Path(__file__).resolve().parent.parent / "plugins"
        )
        self.required_files = tuple(required_files)

    def discover(self) -> List[PluginManifest]:
        """Return manifests for all valid plugin directories."""

        manifests: List[PluginManifest] = []
        for plugin_dir in self._iter_plugin_dirs():
            manifest_path = plugin_dir / "manifest.json"
            if not manifest_path.exists():
                continue
            try:
                manifest = PluginManifest.from_file(manifest_path)
            except PluginValidationError:
                # Skip malformed manifest, but surface as validation error later on demand
                continue
            manifests.append(manifest)
        manifests.sort(key=lambda item: item.name)
        return manifests

    def load(self, *, event: str | None = None) -> List[PluginDefinition]:
        """Load plugin handlers optionally filtered by ``handles_event``."""

        definitions: List[PluginDefinition] = []
        for plugin_dir in self._iter_plugin_dirs():
            definition = self.load_plugin(plugin_dir)
            if event is not None and definition.handles_event != event:
                continue
            definitions.append(definition)
        definitions.sort(key=lambda item: item.name)
        return definitions

    def load_plugin(self, plugin_dir: Path | str) -> PluginDefinition:
        """Load a single plugin directory."""

        plugin_dir = Path(plugin_dir)
        self._validate_structure(plugin_dir)

        spec = PluginSpec.from_file(plugin_dir / "plugin.spec.json")
        manifest = PluginManifest.from_file(plugin_dir / "manifest.json")

        if spec.name != manifest.name:
            raise PluginValidationError(
                f"Spec/manifest name mismatch in {plugin_dir}: {spec.name!r} != {manifest.name!r}"
            )
        if spec.version != manifest.version:
            raise PluginValidationError(
                f"Spec/manifest version mismatch in {plugin_dir}: {spec.version!r} != {manifest.version!r}"
            )
        if spec.handles_event != manifest.handles_event:
            raise PluginValidationError(
                f"Spec/manifest handles_event mismatch in {plugin_dir}: {spec.handles_event!r} != {manifest.handles_event!r}"
            )

        handler_module = self._import_handler(plugin_dir / "handler.py", manifest.name)
        handler = getattr(handler_module, "handle", None)
        if handler is None or not callable(handler):
            raise PluginImportError(
                f"Plugin '{manifest.name}' missing callable 'handle' function"
            )

        return PluginDefinition(
            name=manifest.name,
            version=manifest.version,
            handles_event=manifest.handles_event,
            root=plugin_dir,
            spec=spec,
            manifest=manifest,
            module=handler_module,
            handler=handler,
        )

    def _iter_plugin_dirs(self) -> Iterator[Path]:
        if not self.plugin_root.exists():
            return
        for path in sorted(self.plugin_root.iterdir()):
            if path.is_dir():
                yield path

    def _validate_structure(self, plugin_dir: Path) -> None:
        missing = [name for name in self.required_files if not (plugin_dir / name).exists()]
        if missing:
            raise PluginValidationError(
                f"Plugin '{plugin_dir.name}' missing required files: {', '.join(sorted(missing))}"
            )

    def _import_handler(self, handler_path: Path, plugin_name: str) -> ModuleType:
        spec = importlib.util.spec_from_file_location(f"acms_plugin_{plugin_name}", handler_path)
        if spec is None or spec.loader is None:  # pragma: no cover - importlib defensive
            raise PluginImportError(f"Unable to create module spec for {handler_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


__all__ = [
    "PluginLoader",
    "PluginDefinition",
    "PluginManifest",
    "PluginSpec",
    "PluginError",
    "PluginValidationError",
    "PluginImportError",
    "DEFAULT_REQUIRED_FILES",
]
