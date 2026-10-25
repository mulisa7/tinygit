import shutil
import subprocess

import pytest

from tinygit import commands
from tinygit.cli import main
from tinygit.objects import hash_object, parse_tree, serialize_tree
from tinygit.repo import Repo, RepoError

HAVE_GIT = shutil.which("git") is not None


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TINYGIT_NAME", "Test User")
    monkeypatch.setenv("TINYGIT_EMAIL", "test@example.com")
    return Repo.init(".")


def write(repo, rel, text):
    p = repo.root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def save(repo, msg, *paths):
    commands.add(repo, list(paths) or ["."])
    return commands.commit(repo, msg)


def test_blob_hash_matches_real_git():
    # `printf 'hello\n' | git hash-object --stdin`
    assert hash_object(b"hello\n", "blob") == "ce013625030ba8dba906f756967f9e9ca394464a"


def test_tree_roundtrip_and_sort_order():
    sha = "ab" * 20
    entries = [("100644", "b.txt", sha), ("40000", "a", sha), ("100644", "a.txt", sha)]
    parsed = parse_tree(serialize_tree(entries))
    # git sorts the directory "a" as "a/", so it lands after "a.txt"
    assert [e[1] for e in parsed] == ["a.txt", "a", "b.txt"]


def test_commit_and_log(repo):
    write(repo, "a.txt", "one\n")
    first = save(repo, "first")
    write(repo, "a.txt", "two\n")
    second = save(repo, "second")
    history = [sha for sha, _ in commands.log(repo)]
    assert history == [second, first]
    assert repo.commit_info(second)["parents"] == [first]


def test_nothing_to_commit(repo):
    write(repo, "a.txt", "one\n")
    save(repo, "first")
    with pytest.raises(RepoError):
        commands.commit(repo, "again")


def test_status_buckets(repo):
    write(repo, "kept.txt", "k\n")
    write(repo, "changed.txt", "v1\n")
    save(repo, "base")
    write(repo, "changed.txt", "v2\n")
    write(repo, "new.txt", "n\n")
    st = commands.status(repo)
    assert st["unstaged"] == {"changed.txt": "modified"}
    assert st["untracked"] == ["new.txt"]
    commands.add(repo, ["new.txt"])
    assert commands.status(repo)["staged"] == {"new.txt": "new file"}


def test_deleted_file_can_be_staged(repo):
    write(repo, "a.txt", "x\n")
    write(repo, "b.txt", "y\n")
    save(repo, "base")
    (repo.root / "a.txt").unlink()
    commands.add(repo, ["a.txt"])
    assert commands.status(repo)["staged"] == {"a.txt": "deleted"}


def test_branch_and_checkout_restore_files(repo):
    write(repo, "a.txt", "main version\n")
    write(repo, "sub/deep.txt", "deep\n")
    save(repo, "on main")
    commands.create_branch(repo, "feature")
    commands.checkout(repo, "feature")
    write(repo, "a.txt", "feature version\n")
    write(repo, "only_feature.txt", "f\n")
    save(repo, "on feature")

    commands.checkout(repo, "main")
    assert (repo.root / "a.txt").read_text() == "main version\n"
    assert not (repo.root / "only_feature.txt").exists()

    commands.checkout(repo, "feature")
    assert (repo.root / "a.txt").read_text() == "feature version\n"
    assert (repo.root / "sub" / "deep.txt").read_text() == "deep\n"


def test_checkout_refuses_with_uncommitted_changes(repo):
    write(repo, "a.txt", "v1\n")
    save(repo, "base")
    commands.create_branch(repo, "other")
    write(repo, "a.txt", "dirty\n")
    with pytest.raises(RepoError):
        commands.checkout(repo, "other")
    assert (repo.root / "a.txt").read_text() == "dirty\n"


def test_checkout_by_sha_detaches_head(repo):
    write(repo, "a.txt", "v1\n")
    first = save(repo, "one")
    write(repo, "a.txt", "v2\n")
    save(repo, "two")
    commands.checkout(repo, first[:8])
    assert repo.head_ref() is None
    assert (repo.root / "a.txt").read_text() == "v1\n"


def test_cli_end_to_end(repo, capsys):
    write(repo, "a.txt", "hi\n")
    assert main(["add", "a.txt"]) == 0
    assert main(["commit", "-m", "hello"]) == 0
    assert main(["log", "--oneline"]) == 0
    out = capsys.readouterr().out
    assert "hello" in out
    assert main(["commit", "-m", "again"]) == 1


@pytest.mark.skipif(not HAVE_GIT, reason="git not installed")
def test_real_git_accepts_our_repository(repo):
    write(repo, "a.txt", "one\n")
    write(repo, "src/lib/mod.py", "print('hi')\n")
    save(repo, "first commit")
    write(repo, "a.txt", "two\n")
    save(repo, "second commit")

    def git(*args):
        return subprocess.run(["git", "--git-dir", str(repo.gitdir), *args], capture_output=True, text=True, check=True).stdout

    git("fsck", "--strict")
    assert git("log", "--format=%s").split("\n")[:2] == ["second commit", "first commit"]
    assert git("show", "HEAD:src/lib/mod.py") == "print('hi')\n"
    assert git("log", "-1", "--format=%an <%ae>").strip() == "Test User <test@example.com>"
