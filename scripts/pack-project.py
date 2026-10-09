#!/usr/bin/env python3
"""
打包 quartz5 生产部署包（zip）。

包含四块内容 + 一键部署入口脚本：
  - quartz5/        基座源码
      · 全局剔除 node_modules；排除上游 .github 与仓库自身的 .git（生产不需要）
      · .quartz/plugins/<社区插件>/ ：保留 .git（浅克隆，离线复用必需）+ dist；
                                     剔除 node_modules 及 src/、test/、*.map 等开发产物
      · .quartz/plugins/<本地插件>/ ：跳过（开发机上是指向 plugins-local 的链接，生产由部署脚本重建）
  - plugins-local/  本地插件 dist + package.json（剔除 node_modules、.git
                    及 src/、test/、构建配置、*.map 等开发产物）
  - server/         仅部署所需的最小集合（白名单）：*.exe + 401.html + config_example.json
                    （不含源码/日志；运行所需的 input、settings、output、cache 目录需另行准备内容）
  - 内容目录骨架    input/、output/、settings/、cache/ 四目录：仅纳入占位 .gitkeep
                    （保证解压后目录存在；四目录内的实际内容不打包）
  - scripts/deploy.ps1、scripts/setup-local-plugins.mjs（一键部署所需）

打包前校验（缺失只告警、不中断）：
  - 每个 plugins-local/<name> 必须有 dist/
  - 每个社区插件 quartz5/.quartz/plugins/<name> 必须有 dist/ 与 .git/
  - server/ 至少有一个 *.exe，且存在 401.html、config_example.json

输出：quartz-deploy-<timestamp>.zip（zip 内统一前缀 quartz-fullstack/）

用法：python scripts/pack-project.py
"""

import os
import zipfile
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

QUARTZ5_DIR = PROJECT_ROOT / "quartz5"
PLUGINS_LOCAL_DIR = PROJECT_ROOT / "plugins-local"
PLUGINS_CACHE_DIR = QUARTZ5_DIR / ".quartz" / "plugins"
SERVER_DIR = PROJECT_ROOT / "server"

# 除四大块外，额外定向纳入的部署脚本（一键部署必需）
EXTRA_FILES = [
    "scripts/deploy.ps1",
    "scripts/setup-local-plugins.mjs",
]

# 四个必须的内容目录：只纳入其占位 .gitkeep（内容不打包）
CONTENT_DIRS = ["input", "output", "settings", "cache"]

# server/ 只纳入部署所需的最小集合（白名单）
SERVER_KEEP_NAMES = {"401.html", "config_example.json"}
SERVER_KEEP_SUFFIXES = (".exe",)

# 任意层级都剔除的目录名
#   .github = 上游仓库 CI/Issue 模板，构建与运行均不读取
PRUNE_DIR_NAMES = {"node_modules", ".github"}
# 剔除的文件名（submodule 的 .git 是指针文件）与后缀
PRUNE_FILE_NAMES = {".git"}
PRUNE_FILE_SUFFIXES = (".log", ".stackdump")

# 插件开发产物（本地插件与社区插件在生产均不构建、只运行其 dist，
# 故源码 / 测试 / 构建配置 / 源码映射等一律剔除，不影响构建与运行）。
DEV_PRUNE_DIR_NAMES = {"src", "test", "tests", "__tests__", "coverage", ".github", ".vscode"}
DEV_FILE_PREFIXES = (
    "tsconfig",
    "tsup.config.",
    "vitest.config.",
    "jest.config.",
    "vite.config.",
    "rollup.config.",
    "esbuild.config.",
    ".eslintrc",
    ".eslintignore",
    ".prettierrc",
    ".editorconfig",
    ".gitignore",
    ".npmignore",
)
DEV_FILE_SUFFIXES = (".map",)

ZIP_PREFIX = "quartz-fullstack/"
TIMESTAMP = datetime.now().strftime("%Y%m%d-%H%M%S")
OUT_FILE = PROJECT_ROOT / f"quartz-deploy-{TIMESTAMP}.zip"


def is_dev_file(name):
    """插件目录下与构建/运行无关的开发产物（可安全剔除）。"""
    return name.endswith(DEV_FILE_SUFFIXES) or name.startswith(DEV_FILE_PREFIXES)


def in_community_plugin(dirpath):
    """dirpath 是否位于 .quartz/plugins/<name>/ 之下（社区插件目录内）。"""
    try:
        rel = dirpath.relative_to(PLUGINS_CACHE_DIR)
    except ValueError:
        return False
    return len(rel.parts) >= 1


def local_plugin_names():
    """plugins-local 下含 package.json 的目录名（= 本地插件名集合）。"""
    names = set()
    if PLUGINS_LOCAL_DIR.is_dir():
        for entry in PLUGINS_LOCAL_DIR.iterdir():
            if entry.is_dir() and (entry / "package.json").is_file():
                names.add(entry.name)
    return names


def community_plugin_dirs(local_names):
    """quartz5/.quartz/plugins 下的社区插件目录（排除本地插件名与链接型目录）。"""
    result = []
    if PLUGINS_CACHE_DIR.is_dir():
        for entry in sorted(PLUGINS_CACHE_DIR.iterdir()):
            if not entry.is_dir():
                continue
            if entry.name in local_names:  # 本地插件条目：不进包，生产重建
                continue
            if entry.is_symlink():  # 兜底：跳过任何链接型目录
                continue
            result.append(entry)
    return result


def walk_files(root, keep_dot_git, local_names, slim_local=False, slim_community=False):
    """遍历 root，按规则产出文件路径。

    keep_dot_git     : 仅保留「社区插件自身」的 .git（.quartz/plugins/<name>/.git）；
                       排除 quartz5/.git 等其它 .git。
    slim_local       : 对 plugins-local 全量剔除开发产物。
    slim_community   : 仅对 .quartz/plugins/<name>/ 之下剔除开发产物（不动基座源码）。
    任意层级剔除 node_modules 与 .github；跳过链接型目录与「本地插件名」命名的条目。
    """
    for dirpath, dirnames, filenames in os.walk(root):
        here = Path(dirpath)
        slim_here = slim_local or (slim_community and in_community_plugin(here))

        kept = []
        for dn in dirnames:
            full = here / dn
            if dn in PRUNE_DIR_NAMES:
                continue
            if slim_here and dn in DEV_PRUNE_DIR_NAMES:
                continue
            if dn == ".git":
                # 只保留社区插件自身的 .git（离线复用必需）；quartz5/.git 等排除
                if not (keep_dot_git and here.parent == PLUGINS_CACHE_DIR):
                    continue
            # 本地插件在 .quartz/plugins 下的条目（开发机是 junction）按名跳过
            if here == PLUGINS_CACHE_DIR and dn in local_names:
                continue
            if full.is_symlink():  # 兜底：任何链接型目录一律跳过
                continue
            kept.append(dn)
        dirnames[:] = kept

        for fn in filenames:
            if fn in PRUNE_FILE_NAMES:
                continue
            if fn.endswith(PRUNE_FILE_SUFFIXES):
                continue
            if slim_here and is_dev_file(fn):
                continue
            yield here / fn


def collect_server():
    """server/ 仅纳入白名单文件：*.exe + 401.html + config_example.json。"""
    files = []
    if not SERVER_DIR.is_dir():
        return files
    for dirpath, dirnames, filenames in os.walk(SERVER_DIR):
        dirnames[:] = [
            d
            for d in dirnames
            if d not in PRUNE_DIR_NAMES and not (Path(dirpath) / d).is_symlink()
        ]
        for fn in filenames:
            if fn in SERVER_KEEP_NAMES or fn.endswith(SERVER_KEEP_SUFFIXES):
                p = Path(dirpath) / fn
                files.append((p, p.relative_to(PROJECT_ROOT)))
    return files


def collect(local_names):
    files = []
    for p in walk_files(
        QUARTZ5_DIR, keep_dot_git=True, local_names=local_names, slim_community=True
    ):
        files.append((p, p.relative_to(PROJECT_ROOT)))
    for p in walk_files(
        PLUGINS_LOCAL_DIR, keep_dot_git=False, local_names=local_names, slim_local=True
    ):
        files.append((p, p.relative_to(PROJECT_ROOT)))
    files.extend(collect_server())
    # 四个必须的内容目录：纳入其占位 .gitkeep，保证解压后目录骨架存在；
    # dev 上缺失时补一个空占位（full 为 None，写包时用空内容）。
    for d in CONTENT_DIRS:
        p = PROJECT_ROOT / d / ".gitkeep"
        if p.is_file():
            files.append((p, p.relative_to(PROJECT_ROOT)))
        else:
            files.append((None, Path(d) / ".gitkeep"))
    for rel in EXTRA_FILES:
        p = PROJECT_ROOT / rel
        if p.is_file():
            files.append((p, Path(rel)))
        else:
            print(f"  ! 缺少部署脚本（应在打包前创建）：{rel}")
    return files


def precheck(local_names, community_dirs):
    warns = []
    if not QUARTZ5_DIR.is_dir():
        warns.append("缺少 quartz5/ 目录")
    if not PLUGINS_LOCAL_DIR.is_dir():
        warns.append("缺少 plugins-local/ 目录")

    for name in sorted(local_names):
        if not (PLUGINS_LOCAL_DIR / name / "dist").is_dir():
            warns.append(f"本地插件缺 dist/：plugins-local/{name}/dist（生产会静默缺该插件）")
    for d in community_dirs:
        if not (d / "dist").is_dir():
            warns.append(f"社区插件缺 dist/：.quartz/plugins/{d.name}/dist（生产会静默缺该插件）")
        if not (d / ".git").exists():
            warns.append(f"社区插件缺 .git/：.quartz/plugins/{d.name}/.git（生产会尝试 clone GitHub）")

    if not SERVER_DIR.is_dir():
        warns.append("缺少 server/ 目录（将不含服务端）")
    else:
        if not any(SERVER_DIR.rglob("*.exe")):
            warns.append("server/ 未找到 *.exe（生产无法直接启动服务端，请先 go build）")
        for f in sorted(SERVER_KEEP_NAMES):
            if not (SERVER_DIR / f).is_file():
                warns.append(f"server/{f} 缺失（部署所需）")
    return warns


def main():
    local_names = local_plugin_names()
    community = community_plugin_dirs(local_names)
    server_files = collect_server()

    print(f"项目根        : {PROJECT_ROOT}")
    print(f"输出文件      : {OUT_FILE}")
    print(f"本地插件({len(local_names)})   : {', '.join(sorted(local_names)) or '(无)'}")
    print(f"社区插件({len(community)})   : {', '.join(d.name for d in community) or '(无)'}")
    print(f"服务端文件({len(server_files)})   : {', '.join(p.name for _, p in server_files) or '(无)'}")
    print(f"内容目录占位  : {', '.join(d + '/.gitkeep' for d in CONTENT_DIRS)}")

    warns = precheck(local_names, community)
    if warns:
        print("\n[告警] 打包前校验未通过（会导致生产静默缺插件）：")
        for w in warns:
            print(f"  - {w}")
        print()
    else:
        print("\n[通过] 打包前校验通过\n")

    files = collect(local_names)
    total = len(files)
    print(f"待打包文件数  : {total}")

    if OUT_FILE.exists():
        OUT_FILE.unlink()

    with zipfile.ZipFile(OUT_FILE, "w", zipfile.ZIP_DEFLATED) as zf:
        for full, rel in files:
            arc = ZIP_PREFIX + rel.as_posix()
            if full is None:  # 合成的空占位（如缺失的 .gitkeep）
                zf.writestr(arc, "")
            else:
                zf.write(full, arc)

    size_mb = OUT_FILE.stat().st_size / (1024 * 1024)
    print(f"\n完成！{OUT_FILE.name}（{size_mb:.2f} MB，{total} 个文件）")


if __name__ == "__main__":
    main()
