"""Tests for EvalOps CI deployment."""

from pathlib import Path

import pytest
from git import Repo

from evalops.commands.deploy import deploy
from evalops.bootstrap import bootstrap
from evalops.utils.git_platform.platform_types import PlatformType


@pytest.fixture
def github_repo(tmp_path, monkeypatch):
    """Create a minimal GitHub repository."""
    repo = Repo.init(tmp_path)
    repo.create_remote("origin", "https://github.com/test/repo.git")

    # Initial commit (required for branch operations)
    readme = tmp_path / "README.md"
    readme.write_text("# Test Repo\n")
    repo.index.add(["README.md"])
    repo.index.commit("Initial commit")

    monkeypatch.chdir(tmp_path)
    yield repo


@pytest.fixture
def gitlab_repo(tmp_path, monkeypatch):
    """Create a minimal GitLab repository."""
    repo = Repo.init(tmp_path)
    repo.create_remote("origin", "https://gitlab.com/test/repo.git")

    readme = tmp_path / "README.md"
    readme.write_text("# Test Repo\n")
    repo.index.add(["README.md"])
    repo.index.commit("Initial commit")

    monkeypatch.chdir(tmp_path)
    yield repo


def test_deploy_github_creates_workflow_files(github_repo, monkeypatch):
    """Deploying to GitHub creates expected workflow files."""
    bootstrap()
    monkeypatch.setattr("builtins.input", lambda _: "")
    monkeypatch.setattr("evalops.commands.deploy.identify_git_platform", lambda _: PlatformType.GITHUB)

    deploy(commit=False, model="gemma-4-31b-it")

    workflow = Path(".github/workflows/evalops-code-review.yml")
    assert workflow.exists()

    content = workflow.read_text(encoding="utf-8")
    assert "GOOGLE_API_KEY" in content
    assert "evalops" in content.lower()


def test_deploy_gitlab_creates_workflow_files(gitlab_repo, monkeypatch):
    """Deploying to GitLab creates expected workflow files."""
    bootstrap()
    monkeypatch.setattr("builtins.input", lambda _: "")
    monkeypatch.setattr("evalops.commands.deploy.identify_git_platform", lambda _: PlatformType.GITLAB)

    deploy(commit=False, model="gemma-4-31b-it")

    workflow = Path(".gitlab/ci/evalops-code-review.yml")
    gitlab_ci = Path(".gitlab-ci.yml")

    assert workflow.exists()
    assert gitlab_ci.exists()

    content = workflow.read_text(encoding="utf-8")
    assert "GOOGLE_API_KEY" in content
    assert "GITLAB_ACCESS_TOKEN" in content


def test_deploy_does_not_overwrite_existing(github_repo, monkeypatch):
    """Deploying fails if workflow already exists (without --rewrite)."""
    bootstrap()
    monkeypatch.setattr("builtins.input", lambda _: "")

    # First deploy
    deploy(commit=False, model="gemma-4-31b-it")

    # Second deploy should fail
    result = deploy(commit=False, rewrite=False)

    assert result is False


def test_deploy_rewrite_overwrites_existing(github_repo, monkeypatch):
    """Deploying with --rewrite replaces existing workflow."""
    bootstrap()
    monkeypatch.setattr("builtins.input", lambda _: "")

    deploy(commit=False, model="gemma-4-31b-it")
    deploy(commit=False, rewrite=True, model="gemma-4-31b-it")

    workflow = Path(".github/workflows/evalops-code-review.yml")
    content = workflow.read_text(encoding="utf-8")

    assert "GOOGLE_API_KEY" in content
    assert "gemma-4-31b-it" in content
