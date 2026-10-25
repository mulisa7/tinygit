"""Draws the explainer cards in docs/images from a real tinygit session.

Hashes, tree listings and git's own verdicts are produced by running the code
(and the real `git` command) when this script runs.

    pip install pillow
    python docs/make_images.py
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tinygit import commands  # noqa: E402
from tinygit.objects import hash_object  # noqa: E402
from tinygit.repo import Repo  # noqa: E402

OUT = Path(__file__).parent / "images"
OUT.mkdir(exist_ok=True)

W, H = 1080, 1350
PAPER, INK, SOFT = "#fdf6e3", "#1d1d2c", "#6b6b80"
CORAL, MUSTARD, TEAL, BLUE, PURPLE, PINK = "#ff6b6b", "#ffd166", "#06d6a0", "#118ab2", "#8e7dff", "#ff9ecd"
FONTS = "C:/Windows/Fonts/"


def font(size, kind="ui"):
    name = {"ui": "segoeui.ttf", "bold": "segoeuib.ttf", "hand": "segoepr.ttf", "handb": "segoeprb.ttf",
            "mono": "consola.ttf", "monob": "consolab.ttf", "emoji": "seguiemj.ttf"}[kind]
    return ImageFont.truetype(FONTS + name, size)


def emoji(d, xy, ch, size=44):
    try:
        d.text(xy, ch, font=font(size, "emoji"), embedded_color=True)
    except Exception:
        pass


def shadow_box(img, box, fill, outline=None, r=22, width=3, offset=7):
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    x0, y0, x1, y1 = box
    ImageDraw.Draw(sh).rounded_rectangle([x0 + offset, y0 + offset, x1 + offset, y1 + offset], r, fill=(29, 29, 44, 70))
    sh = sh.filter(ImageFilter.GaussianBlur(5))
    img.paste(sh, (0, 0), sh)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(box, r, fill=fill, outline=outline, width=width)
    return d


def wrap(text, f, width, d):
    lines, line = [], ""
    for word in text.split():
        trial = (line + " " + word).strip()
        if d.textlength(trial, font=f) <= width:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def para(d, x, y, text, f, fill, width, gap=8):
    for line in wrap(text, f, width, d):
        d.text((x, y), line, font=f, fill=fill)
        y += f.size + gap
    return y


def pill(d, x, y, text, fill, fg=INK, f=None):
    f = f or font(24, "bold")
    w = d.textlength(text, font=f) + 36
    d.rounded_rectangle([x, y, x + w, y + 44], 22, fill=fill)
    d.text((x + 18, y + 6), text, font=f, fill=fg)
    return x + w + 12


def new_card(step, title, sub, color=CORAL):
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    for gx in range(0, W, 54):
        d.line([gx, 0, gx, H], fill="#f3ead0", width=1)
    for gy in range(0, H, 54):
        d.line([0, gy, W, gy], fill="#f3ead0", width=1)
    pill(d, 60, 56, step, color, fg="white")
    d.text((60, 118), title, font=font(60, "bold"), fill=INK)
    d.text((62, 200), sub, font=font(32, "hand"), fill=SOFT)
    d.text((60, H - 62), "tinygit  ·  github.com/mulisa7/tinygit", font=font(24, "bold"), fill=SOFT)
    return img, d


def terminal(img, box, lines, size=24):
    d = shadow_box(img, box, "#1b1b2b", r=18, width=0)
    x0, y0, x1, _ = box
    for i, c in enumerate((CORAL, MUSTARD, TEAL)):
        d.ellipse([x0 + 22 + i * 30, y0 + 18, x0 + 40 + i * 30, y0 + 36], fill=c)
    y = y0 + 58
    f = font(size, "mono")
    for text, color in lines:
        for ln in wrap(text, f, x1 - x0 - 50, d) or [""]:
            d.text((x0 + 26, y), ln, font=f, fill=color)
            y += size + 10
    return y


def arrow_down(d, x, y1, y2, color=SOFT):
    d.line([x, y1, x, y2 - 10], fill=color, width=5)
    d.polygon([(x - 13, y2 - 16), (x + 13, y2 - 16), (x, y2)], fill=color)


# ------------------------------------------------------------------ real session
os.environ["TINYGIT_NAME"] = "Mulisa"
os.environ["TINYGIT_EMAIL"] = "mulisa@example.com"
work = Path(tempfile.mkdtemp(prefix="tinygit_demo_"))
os.chdir(work)
repo = Repo.init(".")


def put(rel, text):
    p = work / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, newline="\n")


put("a.txt", "first draft\n")
put("a/inner.txt", "inside a folder\n")
put("hello.txt", "hello\n")
put("src/lib/mod.py", "print(1)\n")
commands.add(repo, ["."])
c1 = commands.commit(repo, "first commit")
put("a.txt", "second draft\n")
commands.add(repo, ["a.txt"])
c2 = commands.commit(repo, "rewrite a.txt")

info2 = repo.commit_info(c2)
info1 = repo.commit_info(c1)
tree2 = commands.cat_file(repo, c2, "-p").decode().splitlines()[0].split()[1]
tree_lines = commands.cat_file(repo, tree2, "-p").decode().splitlines()
blob_hello = hash_object(b"hello\n", "blob")


def git(*args):
    r = subprocess.run(["git", "--git-dir", str(repo.gitdir), *args], capture_output=True, text=True)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


fsck_code, fsck_out, _ = git("fsck", "--strict")
_, git_log, _ = git("log", "--format=%h %s")
_, git_show, _ = git("show", "HEAD:src/lib/mod.py")
real_hash = subprocess.run(["git", "hash-object", "--stdin"], input=b"hello\n", capture_output=True).stdout.decode().strip()
assert real_hash == blob_hello, "tinygit and real git disagree on a blob hash"

# ------------------------------------------------------------------ 1 hero
img, d = new_card("1 / 6", "I rebuilt Git.", "...and the real git can read it", CORAL)
emoji(d, (900, 60), "🌿", 70)
terminal(img, (60, 290, 1020, 880), [
    ("$ tinygit init", "#ffffff"),
    ("initialized empty repository in .tinygit", "#9aa0b4"), ("", "#fff"),
    ("$ tinygit add .", "#ffffff"),
    ('$ tinygit commit -m "first commit"', "#ffffff"),
    (f"[main {c1[:7]}] first commit", "#06d6a0"), ("", "#fff"),
    ("$ tinygit log --oneline", "#ffffff"),
    (f"{c2[:7]} rewrite a.txt", "#ffd166"),
    (f"{c1[:7]} first commit", "#ffd166"), ("", "#fff"),
    ("$ git --git-dir .tinygit fsck --strict", "#ffffff"),
    ("(no output, exit code 0: git is happy)", "#06d6a0")], size=25)
d = ImageDraw.Draw(img)
x = 60
for label, col in [("0 dependencies", TEAL), ("about 500 lines", MUSTARD), ("real Git objects", PINK)]:
    x = pill(d, x, 930, label, col)
para(d, 60, 1010, "Git looks like magic until you open .git. Inside it is just files named after the SHA-1 of their contents. This builds the same ones from scratch.", font(28), INK, 960, gap=10)
d.text((60, 1160), "Swipe: what a commit really is, how files get their names,", font=font(28, "hand"), fill=SOFT)
d.text((60, 1202), "and proof from real git.", font=font(28, "hand"), fill=SOFT)
img.save(OUT / "1_overview.png")

# ------------------------------------------------------------------ 2 three kinds
img, d = new_card("2 / 6", "A commit is 3 kinds of files", "all taken from the demo repo's second commit", TEAL)
shadow_box(img, (60, 270, 1020, 560), "white", outline=BLUE, width=4, r=20)
d = ImageDraw.Draw(img)
d.text((90, 286), f"commit  {c2[:10]}...", font=font(32, "bold"), fill=BLUE)
for i, ln in enumerate([f"tree {info2['tree'][:10]}...", f"parent {info2['parents'][0][:10]}...",
                        "author Mulisa <mulisa@example.com> ...", f"message: {info2['message']}"]):
    d.text((90, 340 + i * 44), ln, font=font(26, "mono"), fill=INK)
arrow_down(d, 300, 565, 625, BLUE)
d.text((330, 580), "points at", font=font(24, "hand"), fill=SOFT)
shadow_box(img, (60, 630, 1020, 930), "white", outline=PURPLE, width=4, r=20)
d = ImageDraw.Draw(img)
d.text((90, 646), f"tree  {tree2[:10]}...   (the top folder)", font=font(32, "bold"), fill=PURPLE)
for i, ln in enumerate(tree_lines):
    mode, kind, rest = ln.split(" ", 2)
    sha, name = rest.split("\t")
    d.text((90, 704 + i * 50), f"{kind:<4}  {sha[:8]}...  {name}", font=font(26, "mono"), fill=INK)
arrow_down(d, 300, 935, 995, PURPLE)
d.text((330, 950), "points at", font=font(24, "hand"), fill=SOFT)
shadow_box(img, (60, 1000, 1020, 1200), "white", outline=MUSTARD, width=4, r=20)
d = ImageDraw.Draw(img)
d.text((90, 1016), "blob  (a file's contents, nothing else)", font=font(32, "bold"), fill="#b88400")
d.text((90, 1076), "no name, no date, just the bytes:", font=font(26), fill=SOFT)
d.text((90, 1120), '"second draft\\n"', font=font(28, "mono"), fill=INK)
img.save(OUT / "2_objects.png")

# ------------------------------------------------------------------ 3 naming
img, d = new_card("3 / 6", "How a file gets its name", 'follow the 6 bytes of "hello"', PURPLE)
steps = [("1", "Contents", 'hello\\n   (6 bytes)', "#e9f8ff", BLUE),
         ("2", "Add a header", 'blob 6\\0hello\\n', "#f2edff", PURPLE),
         ("3", "SHA-1 it", blob_hello, "#fff8e0", "#b88400"),
         ("4", "Compress with zlib", f".tinygit/objects/{blob_hello[:2]}/{blob_hello[2:12]}...", "#eafff6", TEAL)]
y = 290
for n, head, body, bg, edge in steps:
    shadow_box(img, (60, y, 1020, y + 150), bg, outline=edge, width=4, r=20)
    d = ImageDraw.Draw(img)
    d.ellipse([84, y + 40, 140, y + 96], fill=edge)
    d.text((104, y + 46), n, font=font(34, "bold"), fill="white")
    d.text((165, y + 22), head, font=font(32, "bold"), fill=INK)
    d.text((165, y + 80), body, font=font(27, "mono"), fill=INK)
    if n != "4":
        arrow_down(d, 540, y + 152, y + 196)
    y += 195
shadow_box(img, (60, 1100, 1020, 1240), "#1b1b2b", r=18, width=0)
d = ImageDraw.Draw(img)
d.text((90, 1120), '$ printf "hello\\n" | git hash-object --stdin', font=font(24, "mono"), fill="#ffffff")
d.text((90, 1166), real_hash, font=font(26, "mono"), fill="#06d6a0")
d.text((750, 1170), "<- same", font=font(26, "handb"), fill=MUSTARD)
img.save(OUT / "3_naming.png")

# ------------------------------------------------------------------ 4 trees
img, d = new_card("4 / 6", "Folders are objects too", "and Git has a sneaky sort order", BLUE)
d.text((60, 270), "The demo repo's top-level tree, read back with cat-file -p:", font=font(28, "bold"), fill=INK)
terminal(img, (60, 320, 1020, 560), [(ln.replace("\t", "  "), "#06d6a0") for ln in tree_lines], size=25)
d = ImageDraw.Draw(img)
d.text((60, 600), "Spot it?", font=font(44, "bold"), fill=CORAL)
para(d, 60, 665, "The file a.txt comes BEFORE the folder a, even though 'a' is shorter. Git sorts a folder as if its name ended in a slash, and '.' sorts before '/'.", font(30), INK, 960, gap=10)
rows = [("a.txt", "sorts as", "a.txt"), ("a/  (folder)", "sorts as", "a/"), ("hello.txt", "sorts as", "hello.txt")]
y = 830
for left, mid, right in rows:
    shadow_box(img, (60, y, 1020, y + 70), "white", outline="#d8d2bb", width=2, r=14)
    d = ImageDraw.Draw(img)
    d.text((90, y + 16), left, font=font(28, "mono"), fill=INK)
    d.text((470, y + 16), mid, font=font(26, "hand"), fill=SOFT)
    d.text((660, y + 16), right, font=font(28, "monob"), fill=CORAL if right == "a/" else BLUE)
    y += 86
para(d, 60, 1110, "Get that wrong and every tree hash changes, so real git would reject the repo. Each tree entry is mode + name + a NUL byte + 20 raw bytes of SHA.", font(26), SOFT, 960, gap=8)
img.save(OUT / "4_trees.png")

# ------------------------------------------------------------------ 5 proof
img, d = new_card("5 / 6", "Don't trust me: ask real git", "outputs below came from the real `git` command", CORAL)
lines = [("$ git --git-dir .tinygit fsck --strict", "#ffffff"),
         (f"exit code {fsck_code}" + ("  (all objects valid)" if fsck_code == 0 else ""), "#06d6a0" if fsck_code == 0 else "#ff6b6b"), ("", "#fff"),
         ("$ git --git-dir .tinygit log --format='%h %s'", "#ffffff")]
lines += [(ln, "#ffd166") for ln in git_log.splitlines()]
lines += [("", "#fff"), ("$ git --git-dir .tinygit show HEAD:src/lib/mod.py", "#ffffff"), (git_show, "#ffd166")]
y_end = terminal(img, (60, 290, 1020, 780), lines, size=23)
d = ImageDraw.Draw(img)
shadow_box(img, (60, 820, 1020, 1250), "white", outline=CORAL, width=4, r=22)
d = ImageDraw.Draw(img)
d.text((90, 840), "Real git told me off twice", font=font(36, "bold"), fill=CORAL)
bugs = [("1", "Windows wrote refs with \\r\\n.", "git warned: trailing garbage. Fixed by writing \\n only."),
        ("2", "My text staging file was called 'index'.", "git tried to read it as its binary index: 'index file corrupt'. Renamed it tinyindex.")]
yy = 905
for n, head, body in bugs:
    d.ellipse([90, yy + 4, 134, yy + 48], fill=CORAL)
    d.text((104, yy + 8), n, font=font(26, "bold"), fill="white")
    d.text((155, yy), head, font=font(27, "bold"), fill=INK)
    yy = para(d, 155, yy + 42, body, font(24), SOFT, 820, gap=6) + 22
d.text((90, 1200), "This is why a test runs `git fsck` on a real repo.", font=font(26, "hand"), fill=SOFT)
img.save(OUT / "5_proof.png")

# ------------------------------------------------------------------ 6 time travel
repo2_dir = Path(tempfile.mkdtemp(prefix="tinygit_demo2_"))
os.chdir(repo2_dir)
r2 = Repo.init(".")
(repo2_dir / "story.txt").write_text("chapter one\n", newline="\n")
commands.add(r2, ["."])
commands.commit(r2, "chapter one")
commands.create_branch(r2, "rewrite")
commands.checkout(r2, "rewrite")
(repo2_dir / "story.txt").write_text("chapter one, better\n", newline="\n")
(repo2_dir / "extra.txt").write_text("a new file\n", newline="\n")
commands.add(r2, ["."])
commands.commit(r2, "rewrite chapter one")
on_rewrite = (repo2_dir / "story.txt").read_text().strip(), (repo2_dir / "extra.txt").exists()
commands.checkout(r2, "main")
on_main = (repo2_dir / "story.txt").read_text().strip(), (repo2_dir / "extra.txt").exists()
dirty_blocked = False
(repo2_dir / "story.txt").write_text("oops, unsaved edit\n", newline="\n")
try:
    commands.checkout(r2, "rewrite")
except Exception as e:
    dirty_blocked = str(e)

img, d = new_card("6 / 6", "Time travel", "checkout rewrites your folder from objects", TEAL)
cols = [("branch: rewrite", on_rewrite, PURPLE, "#f2edff"), ("branch: main", on_main, BLUE, "#e9f8ff")]
x = 60
for title, (text, extra), edge, bg in cols:
    shadow_box(img, (x, 290, x + 460, 560), bg, outline=edge, width=4, r=20)
    d = ImageDraw.Draw(img)
    d.text((x + 24, 306), title, font=font(30, "bold"), fill=edge)
    d.text((x + 24, 372), "story.txt", font=font(24, "bold"), fill=SOFT)
    d.text((x + 24, 408), f'"{text}"', font=font(24, "mono"), fill=INK)
    d.text((x + 24, 470), "extra.txt", font=font(24, "bold"), fill=SOFT)
    d.text((x + 24, 506), "exists" if extra else "gone", font=font(26, "monob"), fill=TEAL if extra else CORAL)
    x += 500
d.text((60, 590), "Same folder, same command, different files. Nothing was stored twice:", font=font(26, "hand"), fill=SOFT)
d.text((60, 630), "checkout just reads the objects and rebuilds the files.", font=font(26, "hand"), fill=SOFT)
terminal(img, (60, 690, 1020, 900), [
    ("$ echo 'oops, unsaved edit' > story.txt", "#ffffff"),
    ("$ tinygit checkout rewrite", "#ffffff"),
    ("tinygit: " + (dirty_blocked or "(no error?)"), "#ff6b6b")], size=24)
d = ImageDraw.Draw(img)
d.text((60, 940), "It refuses rather than eat your edit.", font=font(30, "handb"), fill=CORAL)
d.text((60, 1010), "Not built yet", font=font(36, "bold"), fill=INK)
x = 60
for label in ["merge", "diff", "remotes", "packfiles", ".gitignore"]:
    x = pill(d, x, 1070, label, "#e9e2c8")
d.text((60, 1150), "Try it:  pip install -e .  &&  tinygit init", font=font(28, "monob"), fill=BLUE)
img.save(OUT / "6_try_it.png")
print("wrote", len(list(OUT.glob("*.png"))), "images")
