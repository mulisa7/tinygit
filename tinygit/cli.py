import argparse
import sys

from . import commands
from .repo import Repo, RepoError


def build_parser():
    ap = argparse.ArgumentParser(prog="tinygit", description="A small Git, for learning how Git stores things.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="create a repository here")
    p = sub.add_parser("add", help="stage files or folders")
    p.add_argument("paths", nargs="+")
    p = sub.add_parser("commit", help="record the staged files")
    p.add_argument("-m", "--message", required=True)
    p = sub.add_parser("log", help="show history, newest first")
    p.add_argument("--oneline", action="store_true")
    p.add_argument("-n", type=int, help="limit the number of commits")
    sub.add_parser("status", help="show staged, unstaged and untracked files")
    p = sub.add_parser("branch", help="list branches, or create one at HEAD")
    p.add_argument("name", nargs="?")
    p = sub.add_parser("checkout", help="switch to a branch or commit")
    p.add_argument("target")
    p = sub.add_parser("cat-file", help="print an object")
    g = p.add_mutually_exclusive_group()
    g.add_argument("-t", dest="mode", action="store_const", const="-t", help="show the type")
    g.add_argument("-s", dest="mode", action="store_const", const="-s", help="show the size")
    g.add_argument("-p", dest="mode", action="store_const", const="-p", help="show the contents (default)")
    p.add_argument("sha")
    return ap


def run(args) -> int:
    if args.cmd == "init":
        repo = Repo.init(".")
        print(f"initialized empty repository in {repo.gitdir}")
        return 0

    repo = Repo.find(".")

    if args.cmd == "add":
        commands.add(repo, args.paths)
    elif args.cmd == "commit":
        sha = commands.commit(repo, args.message)
        branch = repo.head_ref() or "detached HEAD"
        print(f"[{branch} {sha[:7]}] {args.message.splitlines()[0]}")
    elif args.cmd == "log":
        for sha, info in commands.log(repo, args.n):
            if args.oneline:
                print(f"{sha[:7]} {info['message'].splitlines()[0]}")
            else:
                print(f"commit {sha}")
                print(f"Author: {info['author'].rsplit(' ', 2)[0]}")
                print(f"Date:   {commands.format_date(info['author'])}\n")
                for line in info["message"].splitlines():
                    print(f"    {line}")
                print()
    elif args.cmd == "status":
        st = commands.status(repo)
        print(f"On branch {repo.head_ref()}" if repo.head_ref() else "HEAD detached")
        for title, key in (("Staged", "staged"), ("Not staged", "unstaged")):
            if st[key]:
                print(f"\n{title}:")
                for path, what in st[key].items():
                    print(f"  {what}: {path}")
        if st["untracked"]:
            print("\nUntracked:")
            for path in st["untracked"]:
                print(f"  {path}")
        if not (st["staged"] or st["unstaged"] or st["untracked"]):
            print("nothing to commit, working tree clean")
    elif args.cmd == "branch":
        if args.name:
            commands.create_branch(repo, args.name)
        else:
            current = repo.head_ref()
            for name in repo.branches():
                print(("* " if name == current else "  ") + name)
    elif args.cmd == "checkout":
        commands.checkout(repo, args.target)
        print(f"now on {repo.head_ref() or repo.head_commit()[:7]}")
    elif args.cmd == "cat-file":
        sys.stdout.flush()
        sys.stdout.buffer.write(commands.cat_file(repo, args.sha, args.mode or "-p"))
    return 0


def main(argv=None):
    try:
        return run(build_parser().parse_args(argv))
    except RepoError as e:
        print(f"tinygit: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
