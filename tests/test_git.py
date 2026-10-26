import subprocess

import pytest

from away.git_context import collect_git, discover_repo, run_command

SINCE = "2000-01-01T00:00:00+00:00"


def git(path, *args):
    return subprocess.check_output(["git", "-C", str(path), "-c", "user.name=Test Developer", "-c", "user.email=test@example.invalid", *args], stderr=subprocess.STDOUT).decode().strip()


@pytest.fixture
def repository(tmp_path):
    git(tmp_path, "init", "-b", "main")
    (tmp_path / "app.txt").write_text("first\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-m", "Initial commit")
    return tmp_path


def test_staged_unstaged_untracked_read_only_and_secret_exclusion(repository):
    odd = 'line\nname "quoted".txt'
    (repository / odd).write_text("initial\n")
    (repository / ".env").write_text("PRIVATE_SECRET_SHOULD_NEVER_APPEAR\n")
    git(repository, "add", ".")
    git(repository, "commit", "-m", "Tracked files")
    (repository / "app.txt").write_text("staged\n")
    git(repository, "add", "app.txt")
    (repository / "app.txt").write_text("unstaged\n")
    (repository / odd).write_text("changed\n")
    (repository / ".env").write_text("VERY_PRIVATE_VALUE\n")
    (repository / "untracked.txt").write_text("DO_NOT_INGEST_UNTRACKED_CONTENT\n")
    before = git(repository, "status", "--porcelain=v1", "-z")
    context = collect_git(str(repository), SINCE)
    assert context["staged"] == ["app.txt"]
    assert "app.txt" in context["unstaged"] and odd in context["unstaged"]
    assert context["untracked"] == ["untracked.txt"]
    assert "+staged" in context["diff"] and "+unstaged" in context["diff"]
    assert "VERY_PRIVATE_VALUE" not in str(context)
    assert "DO_NOT_INGEST_UNTRACKED_CONTENT" not in str(context)
    assert git(repository, "status", "--porcelain=v1", "-z") == before
    assert context["head"] == git(repository, "rev-parse", "HEAD")


def test_renames_symlinks_and_literal_pathspec(repository, tmp_path):
    (repository / "old name").write_text("old\n")
    (repository / ":(glob)*").write_text("literal\n")
    git(repository, "add", ".")
    git(repository, "commit", "-m", "Files")
    git(repository, "mv", "old name", "new name")
    (repository / ":(glob)*").write_text("literal changed\n")
    outside = repository.parent / "external-private.txt"
    outside.write_text("OUTSIDE_SECRET\n")
    (repository / "link").symlink_to(outside)
    git(repository, "add", "link")
    context = collect_git(str(repository), SINCE)
    assert "new name" in context["staged"]
    assert "+literal changed" in context["diff"]
    assert "OUTSIDE_SECRET" not in str(context)
    assert "link" not in context["diff"]


def test_snapshot_base_changes_worktree_and_detached(repository):
    first = collect_git(str(repository), SINCE)
    (repository / "app.txt").write_text("next\n")
    git(repository, "add", ".")
    git(repository, "commit", "-m", "Next")
    second = collect_git(str(repository), SINCE, {"git": first})
    assert second["base_changes"] == ["app.txt"]
    worktree = repository.parent / "linked-worktree"
    git(repository, "worktree", "add", "-b", "feature", str(worktree))
    linked = discover_repo(str(worktree))
    assert linked["root"] == str(worktree)
    assert linked["branch"] == "feature"
    assert len(linked["worktrees"]) == 2
    git(repository, "checkout", "--detach")
    detached = collect_git(str(repository), SINCE)
    assert detached["branch"] is None
    assert any("Detached" in warning for warning in detached["warnings"])


def test_empty_repo_and_validation(tmp_path):
    git(tmp_path, "init", "-b", "main")
    result = collect_git(str(tmp_path), SINCE)
    assert result["head"] is None and result["commits"] == []
    assert result["remotes"] == []
    with pytest.raises(ValueError, match="ISO"):
        collect_git(str(tmp_path), "yesterday")
    with pytest.raises(ValueError, match="existing"):
        discover_repo(str(tmp_path / "missing"))


def test_subprocess_boundaries():
    import sys
    with pytest.raises(RuntimeError, match="limit"):
        run_command([sys.executable, "-c", "print('x' * 10000)"], limit=500)
    with pytest.raises(RuntimeError, match="timed out"):
        run_command([sys.executable, "-c", "import time; time.sleep(5)"], timeout=0)


def test_remote_credentials_not_returned(repository):
    git(repository, "remote", "add", "origin", "https://username:private-value@github.com/test/project.git")
    assert discover_repo(str(repository))["remotes"][0]["url"] == "https://github.com/test/project.git"


def test_diff_does_not_follow_replaced_directory_symlink(repository):
    directory = repository / "src"
    directory.mkdir()
    (directory / "config.txt").write_text("tracked value\n")
    git(repository, "add", ".")
    git(repository, "commit", "-m", "Track nested file")
    (directory / "config.txt").unlink()
    directory.rmdir()
    target = repository / "private-data"
    target.mkdir()
    (target / "config.txt").write_text("DIRECTORY_SYMLINK_SECRET\n")
    directory.symlink_to(target, target_is_directory=True)
    context = collect_git(str(repository), SINCE)
    assert "DIRECTORY_SYMLINK_SECRET" not in str(context)
