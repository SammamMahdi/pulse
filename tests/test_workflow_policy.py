"""Pipeline security policy, enforced as tests so a workflow edit cannot silently weaken it."""

import re
from pathlib import Path

import pytest
import yaml

WORKFLOWS = Path(__file__).resolve().parent.parent / ".github" / "workflows"
SHA_PIN = re.compile(r"^[\w.-]+/[\w.-]+(/[\w./-]+)?@[0-9a-f]{40}$")


def load(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text())


def all_steps(workflow: dict):
    for job_name, job in workflow["jobs"].items():
        for step in job.get("steps", []):
            yield job_name, step


@pytest.mark.parametrize("name", ["ci.yml", "deploy.yml"])
def test_default_token_permissions_are_read_only(name: str) -> None:
    assert load(name)["permissions"] == {"contents": "read"}


@pytest.mark.parametrize("name", ["ci.yml", "deploy.yml"])
def test_every_action_is_pinned_to_a_commit_sha(name: str) -> None:
    unpinned = [
        step["uses"]
        for _, step in all_steps(load(name))
        if "uses" in step and not SHA_PIN.match(step["uses"])
    ]
    assert unpinned == []


@pytest.mark.parametrize("name", ["ci.yml", "deploy.yml"])
def test_checkout_does_not_persist_credentials(name: str) -> None:
    for _, step in all_steps(load(name)):
        if step.get("uses", "").startswith("actions/checkout@"):
            assert step["with"]["persist-credentials"] is False


def test_only_trusted_push_events_publish_images() -> None:
    ci = load("ci.yml")
    triggers = ci.get("on", ci.get(True))  # PyYAML (YAML 1.1) reads the key `on` as boolean True
    assert triggers["push"] == {"branches": ["main"], "tags": ["v*.*.*"]}
    assert ci["jobs"]["publish"]["if"] == "github.event_name == 'push'"
    assert ci["jobs"]["publish"]["needs"] == "build"


def test_registry_write_permission_is_limited_to_publish_job() -> None:
    writers = [
        name
        for name, job in load("ci.yml")["jobs"].items()
        if job.get("permissions", {}).get("packages") == "write"
    ]
    assert writers == ["publish"]


def test_promotion_requires_an_environment_gate() -> None:
    deploy = load("deploy.yml")
    assert deploy["jobs"]["promote"]["environment"] == "${{ inputs.environment }}"
    assert deploy["jobs"]["promote"]["needs"] == "verify"
    assert deploy["concurrency"]["cancel-in-progress"] is False
