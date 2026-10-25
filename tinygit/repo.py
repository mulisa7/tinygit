import os
import zlib
from pathlib import Path

from .objects import hash_object, parse_commit, parse_tree

DIRNAME = ".tinygit"
SKIP = {DIRNAME, ".git"}
# not called "index": git would try to parse that name as its binary index
INDEX = "tinyindex"


class RepoError(Exception):
    pass


class Repo:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.gitdir = self.root / DIRNAME

    # -- setup --------------------------------------------------------------
    @classmethod
    def init(cls, path="."):
        repo = cls(path)
        if repo.gitdir.exists():
            raise RepoError(f"already a repository: {repo.gitdir}")
        for sub in ("objects", "refs/heads"):
            (repo.gitdir / sub).mkdir(parents=True)
        (repo.gitdir / "HEAD").write_text("ref: refs/heads/main\n", newline="\n")
        return repo

    @classmethod
    def find(cls, start="."):
        p = Path(start).resolve()
        for d in [p, *p.parents]:
            if (d / DIRNAME).is_dir():
                return cls(d)
        raise RepoError("not a tinygit repository (run `tinygit init`)")

    # -- objects ------------------------------------------------------------
    def write_object(self, kind: str, data: bytes) -> str:
        sha = hash_object(data, kind)
        path = self.gitdir / "objects" / sha[:2] / sha[2:]
        if not path.exists():
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(zlib.compress(f"{kind} {len(data)}".encode() + b"\0" + data))
        return sha

    def resolve(self, prefix: str) -> str:
        if len(prefix) == 40:
            return prefix
        if len(prefix) < 4:
            raise RepoError(f"'{prefix}' is too short to be a commit id")
        folder = self.gitdir / "objects" / prefix[:2]
        found = [prefix[:2] + f.name for f in folder.glob(prefix[2:] + "*")] if folder.is_dir() else []
        if not found:
            raise RepoError(f"no object matches '{prefix}'")
        if len(found) > 1:
            raise RepoError(f"'{prefix}' is ambiguous")
        return found[0]

    def read_object(self, sha: str):
        sha = self.resolve(sha)
        path = self.gitdir / "objects" / sha[:2] / sha[2:]
        if not path.exists():
            raise RepoError(f"missing object {sha}")
        raw = zlib.decompress(path.read_bytes())
        header, _, body = raw.partition(b"\0")
        kind, size = header.decode().split(" ")
        if int(size) != len(body):
            raise RepoError(f"corrupt object {sha}")
        return kind, body

    def commit_info(self, sha: str) -> dict:
        kind, body = self.read_object(sha)
        if kind != "commit":
            raise RepoError(f"{sha[:7]} is a {kind}, not a commit")
        return parse_commit(body)

    def tree_files(self, tree_sha: str, prefix="") -> dict:
        """Flatten a tree into {path: (mode, sha)}."""
        files = {}
        for mode, name, sha in parse_tree(self.read_object(tree_sha)[1]):
            path = prefix + name
            if mode == "40000":
                files.update(self.tree_files(sha, path + "/"))
            else:
                files[path] = (mode, sha)
        return files

    # -- refs ---------------------------------------------------------------
    def head_ref(self):
        """Branch name HEAD points at, or None if detached."""
        text = (self.gitdir / "HEAD").read_text().strip()
        return text[len("ref: refs/heads/"):] if text.startswith("ref: ") else None

    def head_commit(self):
        branch = self.head_ref()
        if branch:
            p = self.gitdir / "refs" / "heads" / branch
            return p.read_text().strip() if p.exists() else None
        return (self.gitdir / "HEAD").read_text().strip()

    def set_head_commit(self, sha: str):
        branch = self.head_ref()
        if branch:
            self.set_branch(branch, sha)
        else:
            (self.gitdir / "HEAD").write_text(sha + "\n", newline="\n")

    def set_branch(self, name: str, sha: str):
        p = self.gitdir / "refs" / "heads" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(sha + "\n", newline="\n")

    def branches(self) -> dict:
        base = self.gitdir / "refs" / "heads"
        return {p.relative_to(base).as_posix(): p.read_text().strip() for p in sorted(base.rglob("*")) if p.is_file()}

    # -- index --------------------------------------------------------------
    # Plain text, one "mode sha path" line per file. Real git uses a binary
    # index; this keeps the file readable. It's the one part git can't read.
    def load_index(self) -> dict:
        p = self.gitdir / INDEX
        if not p.exists():
            return {}
        entries = {}
        for line in p.read_text().splitlines():
            mode, sha, path = line.split(" ", 2)
            entries[path] = (mode, sha)
        return entries

    def save_index(self, entries: dict):
        lines = [f"{m} {s} {path}" for path, (m, s) in sorted(entries.items())]
        (self.gitdir / INDEX).write_text("\n".join(lines) + ("\n" if lines else ""), newline="\n")

    # -- working tree -------------------------------------------------------
    def work_files(self) -> list:
        out = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if d not in SKIP]
            for f in filenames:
                out.append((Path(dirpath) / f).relative_to(self.root).as_posix())
        return sorted(out)

    def file_mode(self, rel: str) -> str:
        return "100755" if os.stat(self.root / rel).st_mode & 0o100 else "100644"
