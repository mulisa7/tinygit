"""Git object formats: blob, tree, commit. Same bytes real git writes."""
import hashlib
import time
from datetime import datetime


def hash_object(data: bytes, kind: str) -> str:
    header = f"{kind} {len(data)}".encode() + b"\0"
    return hashlib.sha1(header + data).hexdigest()


def serialize_tree(entries) -> bytes:
    """entries: (mode, name, hex_sha). Git sorts as if directory names ended in '/'."""
    def key(e):
        mode, name, _ = e
        return name + "/" if mode == "40000" else name

    out = b""
    for mode, name, sha in sorted(entries, key=key):
        out += f"{mode} {name}".encode() + b"\0" + bytes.fromhex(sha)
    return out


def parse_tree(data: bytes):
    entries, i = [], 0
    while i < len(data):
        sp = data.index(b" ", i)
        nul = data.index(b"\0", sp)
        mode = data[i:sp].decode()
        name = data[sp + 1:nul].decode()
        sha = data[nul + 1:nul + 21].hex()
        entries.append((mode, name, sha))
        i = nul + 21
    return entries


def signature(name: str, email: str, when: float = None) -> str:
    when = time.time() if when is None else when
    off = datetime.fromtimestamp(when).astimezone().utcoffset()
    mins = int(off.total_seconds() // 60)
    sign = "+" if mins >= 0 else "-"
    tz = f"{sign}{abs(mins) // 60:02d}{abs(mins) % 60:02d}"
    return f"{name} <{email}> {int(when)} {tz}"


def make_commit(tree: str, parent, author: str, message: str) -> bytes:
    lines = [f"tree {tree}"]
    if parent:
        lines.append(f"parent {parent}")
    lines += [f"author {author}", f"committer {author}", "", message.rstrip("\n"), ""]
    return "\n".join(lines).encode()


def parse_commit(data: bytes) -> dict:
    head, _, message = data.decode().partition("\n\n")
    info = {"parents": []}
    for line in head.split("\n"):
        key, _, value = line.partition(" ")
        if key == "parent":
            info["parents"].append(value)
        else:
            info[key] = value
    info["message"] = message.rstrip("\n")
    return info
