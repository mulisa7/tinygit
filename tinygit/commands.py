import os
import time
from pathlib import Path

from .objects import hash_object, make_commit, parse_tree, serialize_tree, signature
from .repo import Repo, RepoError


def _author() -> str:
    name = os.environ.get("TINYGIT_NAME") or os.environ.get("GIT_AUTHOR_NAME") or "unknown"
    email = os.environ.get("TINYGIT_EMAIL") or os.environ.get("GIT_AUTHOR_EMAIL") or "unknown@localhost"
    return signature(name, email)


def _rel(repo: Repo, path: str) -> str:
    return Path(os.path.abspath(path)).relative_to(repo.root).as_posix()


# -- add --------------------------------------------------------------------
def add(repo: Repo, paths: list) -> int:
    index = repo.load_index()
    work = set(repo.work_files())
    touched = 0
    for p in paths:
        try:
            rel = _rel(repo, p)
        except ValueError:
            raise RepoError(f"{p} is outside the repository")
        if rel == ".":
            targets = set(work) | {k for k in index}
        else:
            targets = {f for f in work if f == rel or f.startswith(rel + "/")}
            targets |= {k for k in index if k == rel or k.startswith(rel + "/")}
        if not targets:
            raise RepoError(f"pathspec '{p}' did not match any files")
        for t in targets:
            if t in work:
                data = (repo.root / t).read_bytes()
                index[t] = (repo.file_mode(t), repo.write_object("blob", data))
            else:
                index.pop(t, None)  # deleted from disk, so stage the deletion
            touched += 1
    repo.save_index(index)
    return touched


# -- commit -----------------------------------------------------------------
def write_tree(repo: Repo, entries: dict) -> str:
    files, dirs = [], {}
    for path, (mode, sha) in entries.items():
        head, _, rest = path.partition("/")
        if rest:
            dirs.setdefault(head, {})[rest] = (mode, sha)
        else:
            files.append((mode, head, sha))
    for name, sub in dirs.items():
        files.append(("40000", name, write_tree(repo, sub)))
    return repo.write_object("tree", serialize_tree(files))


def commit(repo: Repo, message: str) -> str:
    index = repo.load_index()
    if not index:
        raise RepoError("nothing to commit (the index is empty)")
    tree = write_tree(repo, index)
    parent = repo.head_commit()
    if parent and repo.commit_info(parent)["tree"] == tree:
        raise RepoError("nothing to commit, working tree matches the last commit")
    sha = repo.write_object("commit", make_commit(tree, parent, _author(), message))
    repo.set_head_commit(sha)
    return sha


# -- log --------------------------------------------------------------------
def log(repo: Repo, limit=None):
    sha, n = repo.head_commit(), 0
    while sha and (limit is None or n < limit):
        info = repo.commit_info(sha)
        yield sha, info
        sha = info["parents"][0] if info["parents"] else None
        n += 1


def format_date(author_line: str) -> str:
    parts = author_line.rsplit(" ", 2)
    ts, tz = int(parts[1]), parts[2]
    return time.strftime("%a %b %d %H:%M:%S %Y", time.localtime(ts)) + " " + tz


# -- status -----------------------------------------------------------------
def status(repo: Repo) -> dict:
    head = repo.head_commit()
    head_files = repo.tree_files(repo.commit_info(head)["tree"]) if head else {}
    index = repo.load_index()
    work = {}
    for rel in repo.work_files():
        work[rel] = hash_object((repo.root / rel).read_bytes(), "blob")

    staged = {}
    for path, (_, sha) in index.items():
        if path not in head_files:
            staged[path] = "new file"
        elif head_files[path][1] != sha:
            staged[path] = "modified"
    for path in head_files:
        if path not in index:
            staged[path] = "deleted"

    unstaged = {}
    for path, (_, sha) in index.items():
        if path not in work:
            unstaged[path] = "deleted"
        elif work[path] != sha:
            unstaged[path] = "modified"

    untracked = sorted(set(work) - set(index))
    return {"staged": dict(sorted(staged.items())), "unstaged": dict(sorted(unstaged.items())), "untracked": untracked}


# -- branch / checkout ------------------------------------------------------
def create_branch(repo: Repo, name: str):
    head = repo.head_commit()
    if not head:
        raise RepoError("make a commit before creating branches")
    if name in repo.branches():
        raise RepoError(f"branch '{name}' already exists")
    repo.set_branch(name, head)


def checkout(repo: Repo, target: str):
    st = status(repo)
    if st["staged"] or st["unstaged"]:
        raise RepoError("you have uncommitted changes; commit them first")

    branches = repo.branches()
    if target in branches:
        sha, branch = branches[target], target
    else:
        sha, branch = repo.resolve(target), None
        repo.commit_info(sha)  # make sure it is a commit

    new_files = repo.tree_files(repo.commit_info(sha)["tree"])
    old_index = repo.load_index()

    for path in new_files:
        if path not in old_index and (repo.root / path).exists():
            raise RepoError(f"untracked file '{path}' would be overwritten")

    for path in old_index:
        if path not in new_files:
            f = repo.root / path
            if f.exists():
                f.unlink()
            parent = f.parent
            while parent != repo.root and parent.is_dir() and not any(parent.iterdir()):
                parent.rmdir()
                parent = parent.parent

    for path, (mode, blob) in new_files.items():
        f = repo.root / path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(repo.read_object(blob)[1])
        if mode == "100755":
            f.chmod(f.stat().st_mode | 0o111)

    repo.save_index(new_files)
    head_file = repo.gitdir / "HEAD"
    head_file.write_text(f"ref: refs/heads/{branch}\n" if branch else sha + "\n", newline="\n")


# -- cat-file ---------------------------------------------------------------
def cat_file(repo: Repo, sha: str, mode: str) -> bytes:
    kind, body = repo.read_object(sha)
    if mode == "-t":
        return (kind + "\n").encode()
    if mode == "-s":
        return f"{len(body)}\n".encode()
    if kind == "tree":
        lines = []
        for m, name, s in parse_tree(body):
            k = "tree" if m == "40000" else "blob"
            lines.append(f"{m.rjust(6, '0')} {k} {s}\t{name}")
        return ("\n".join(lines) + "\n").encode()
    return body
