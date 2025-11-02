"""
OpenTelemetry Integration
Version: 1.0.0
Date: 2025-11-02
Owner: Platform.Engineering
Distributed tracing setup
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, MutableMapping, Optional
import threading

__all__ = [
    "TracingConfig",
    "configure_tracing",
    "get_tracer",
    "shutdown_tracing",
]

_PROVIDER_LOCK = threading.Lock()
_CONFIGURED = False


@dataclass(frozen=True)
class TracingConfig:
    """Configuration container for OpenTelemetry tracing."""

    service_name: str
    jaeger_host: str = "localhost"
    jaeger_port: int = 6831
    sample_ratio: float = 1.0
    environment: str = "local"
    console_exporter: bool = False
    enabled: bool = True
    resource_attributes: Mapping[str, str] | None = field(default=None)

    def attributes(self) -> Dict[str, str]:
        """Return merged resource attributes for the tracer provider."""

        defaults: Dict[str, str] = {
            "service.name": self.service_name,
            "service.namespace": "acms",
            "deployment.environment": self.environment,
        }
        if self.resource_attributes:
            defaults.update(dict(self.resource_attributes))
        return defaults


def _import_opentelemetry() -> MutableMapping[str, Any]:
    """Dynamically import OpenTelemetry components when available."""

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.jaeger.thrift import JaegerExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,
            ConsoleSpanExporter,
            SimpleSpanProcessor,
        )
        from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
    except ImportError as exc:  # pragma: no cover - runtime guard
        raise RuntimeError(
            "OpenTelemetry packages are required to configure tracing. "
            "Install the 'opentelemetry-sdk' and 'opentelemetry-exporter-jaeger' "
            "distributions to enable observability."
        ) from exc

    return {
        "trace": trace,
        "JaegerExporter": JaegerExporter,
        "Resource": Resource,
        "TracerProvider": TracerProvider,
        "BatchSpanProcessor": BatchSpanProcessor,
        "ConsoleSpanExporter": ConsoleSpanExporter,
        "SimpleSpanProcessor": SimpleSpanProcessor,
        "ParentBased": ParentBased,
        "TraceIdRatioBased": TraceIdRatioBased,
    }


def configure_tracing(config: TracingConfig) -> Any:
    """Configure OpenTelemetry tracing based on the provided configuration."""

    if not config.enabled:
        return get_tracer(config.service_name)

    imports = _import_opentelemetry()
    trace = imports["trace"]

    global _CONFIGURED
    with _PROVIDER_LOCK:
        if _CONFIGURED:
            return trace.get_tracer(config.service_name)

        sampler_ratio = max(0.0, min(1.0, config.sample_ratio))
        sampler = imports["ParentBased"](imports["TraceIdRatioBased"](sampler_ratio))

        resource = imports["Resource"].create(config.attributes())
        provider = imports["TracerProvider"](resource=resource, sampler=sampler)
        trace.set_tracer_provider(provider)

        jaeger_exporter = imports["JaegerExporter"](
            agent_host_name=config.jaeger_host,
            agent_port=config.jaeger_port,
        )
        provider.add_span_processor(imports["BatchSpanProcessor"](jaeger_exporter))

        if config.console_exporter:
            provider.add_span_processor(
                imports["SimpleSpanProcessor"](imports["ConsoleSpanExporter"]())
            )

        _CONFIGURED = True
        return trace.get_tracer(config.service_name)


def get_tracer(service_name: Optional[str] = None) -> Any:
    """Return a tracer for the requested service."""

    imports = _import_opentelemetry()
    trace = imports["trace"]
    effective_service = service_name or "acms"
    return trace.get_tracer(effective_service)


def shutdown_tracing() -> None:
    """Flush and shutdown the active tracer provider if configured."""

    imports = _import_opentelemetry()
    trace = imports["trace"]
    provider = trace.get_tracer_provider()
    shutdown = getattr(provider, "shutdown", None)
    if callable(shutdown):
        shutdown()
