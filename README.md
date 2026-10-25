# tinygit

A small Git, written to see how Git actually stores things. It makes real Git objects (blobs, trees, commits, zlib-compressed and SHA-1 named), so the real `git` command can read a tinygit repository. About 500 lines of Python, standard library only.

The format comes from Git's own documentation ([Pro Git, "Git Internals"](https://git-scm.com/book/en/v2/Git-Internals-Git-Objects)) and the build-your-own-x style of tutorial. It is a learning project, not a replacement for Git.

## Install

```bash
pip install -e .
```

## Use

```bash
tinygit init
tinygit add .
tinygit commit -m "first commit"
tinygit log --oneline
tinygit status
tinygit branch feature
tinygit checkout feature
tinygit cat-file -p <sha>      # look inside any object
```

The repository lives in `.tinygit/` rather than `.git/` so it can't clash with a real one.

Author name and email come from `TINYGIT_NAME` and `TINYGIT_EMAIL` (or `GIT_AUTHOR_NAME` and `GIT_AUTHOR_EMAIL`).

## It really is Git

Point the real thing at a tinygit repo:

```bash
git --git-dir .tinygit fsck --strict
git --git-dir .tinygit log --format=%s
git --git-dir .tinygit show HEAD:src/lib/mod.py
```

The tests do exactly this, and also check that hashing `hello\n` gives the same blob id real Git gives (`ce013625...`).

## What's inside

| file | job |
| --- | --- |
| `objects.py` | hashing, tree and commit formats |
| `repo.py` | the `.tinygit` folder: objects, refs, the index, the working tree |
| `commands.py` | add, commit, log, status, branch, checkout, cat-file |
| `cli.py` | argument parsing |

[`docs/images`](docs/images) walks through it with cards drawn from a real run (`docs/make_images.py`).

## Limits

- The staging area is a plain text file (`.tinygit/tinyindex`), not Git's binary index. Real `git status` can't read it; everything else can.
- No merge, rebase, diff, remotes, packfiles or `.gitignore`.
- `checkout` refuses to run if you have uncommitted changes, instead of trying to carry them over.
- Paths with newlines in the name aren't supported.

## Tests

```bash
pip install pytest
python -m pytest
```
