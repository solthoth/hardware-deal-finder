from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]


def test_dockerfile_is_locked_and_runs_as_non_root() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text()
    assert "uv sync --locked --no-dev" in dockerfile
    assert "USER 65532:65532" in dockerfile
    assert 'ENTRYPOINT ["dealfinder"]' in dockerfile
    assert "/state/dealfinder.db" in dockerfile


def test_kubernetes_cronjob_prevents_overlap_and_mounts_state() -> None:
    documents = list(
        yaml.safe_load_all((ROOT / "deploy/kubernetes/cronjob.yaml").read_text())
    )
    cronjob = next(document for document in documents if document["kind"] == "CronJob")
    assert cronjob["spec"]["concurrencyPolicy"] == "Forbid"
    pod_spec = cronjob["spec"]["jobTemplate"]["spec"]["template"]["spec"]
    assert pod_spec["securityContext"]["runAsNonRoot"] is True
    container = pod_spec["containers"][0]
    assert container["securityContext"]["readOnlyRootFilesystem"] is True
    assert "/state" in {mount["mountPath"] for mount in container["volumeMounts"]}


def test_ci_runs_all_quality_gates_and_container_build() -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yaml").read_text())
    steps = workflow["jobs"]["quality"]["steps"]
    commands = "\n".join(str(step.get("run", "")) for step in steps)
    assert "ruff check ." in commands
    assert "mypy src" in commands
    assert "pytest" in commands
    assert "docker build" in commands
