"""
BDD Step Definitions
Version: 1.0.0
Date: 2025-11-02
"""
from __future__ import annotations

import importlib
import time
from typing import Any

from behave import given, then, when


def _load_deduplicator() -> Any:
    """Dynamically load the deduplicator plugin implementation."""
    module = importlib.import_module("plugins.deduplicator.deduplicator")
    return getattr(module, "detect_duplicate")


@given('a new file "{filename}" with content "{content}"')
def step_new_file(context, filename: str, content: str) -> None:
    context.dedup_payload = {
        "file_path": filename,
        "file_hash": str(hash(content)),
        "trace_id": "bdd-trace-001",
    }
    context.deduplicator = _load_deduplicator()


@given('an existing file "{filename}" with hash "{file_hash}"')
def step_existing_file(context, filename: str, file_hash: str) -> None:
    context.existing_file = {
        "file_path": filename,
        "file_hash": file_hash,
        "trace_id": "bdd-trace-existing",
    }
    context.deduplicator = _load_deduplicator()
    context.deduplicator(context.existing_file)


@given('a new file "{filename}" with the same hash "{file_hash}"')
def step_new_duplicate_file(context, filename: str, file_hash: str) -> None:
    context.dedup_payload = {
        "file_path": filename,
        "file_hash": file_hash,
        "trace_id": "bdd-trace-duplicate",
    }


@given("a file that takes 60 seconds to process")
def step_slow_file(context) -> None:
    context.dedup_payload = {
        "file_path": "slow-file.bin",
        "file_hash": "slow-hash",
        "trace_id": "bdd-trace-slow",
        "simulate_delay_seconds": 60,
    }
    context.deduplicator = _load_deduplicator()


@given("the plugin timeout is set to 30 seconds")
def step_timeout_configuration(context) -> None:
    context.timeout_seconds = 30


@when("I run the deduplicator plugin")
def step_run_deduplicator(context) -> None:
    detect_duplicate = context.deduplicator
    payload = context.dedup_payload
    if getattr(context, "timeout_seconds", None):
        start = time.monotonic()
        result = detect_duplicate(payload)
        elapsed = time.monotonic() - start
        context.result = result
        context.elapsed = elapsed
    else:
        context.result = detect_duplicate(payload)


@when('I run the deduplicator plugin on "{filename}"')
def step_run_deduplicator_on_file(context, filename: str) -> None:
    payload = dict(context.dedup_payload)
    payload["file_path"] = filename
    context.result = context.deduplicator(payload)


@then("the file should not be marked as duplicate")
def step_assert_not_duplicate(context) -> None:
    assert context.result["is_duplicate"] is False


@then("the file should be allowed to proceed")
def step_assert_allowed(context) -> None:
    assert context.result.get("recommended_action") in {None, "allow", "proceed"}


@then("the file should be marked as duplicate")
def step_assert_duplicate(context) -> None:
    assert context.result["is_duplicate"] is True


@then('the recommended action should be "{action}"')
def step_assert_recommendation(context, action: str) -> None:
    assert context.result.get("recommended_action") == action


@then('the duplicate_of field should be "{filename}"')
def step_assert_duplicate_of(context, filename: str) -> None:
    assert context.result.get("duplicate_of") == filename


@then("the plugin should timeout gracefully")
def step_assert_timeout_behavior(context) -> None:
    assert context.result["status"] in {"timeout", "error"}
    if hasattr(context, "elapsed"):
        assert context.elapsed >= context.timeout_seconds


@then("return an error status")
def step_assert_error_status(context) -> None:
    assert context.result["status"] in {"error", "timeout"}
