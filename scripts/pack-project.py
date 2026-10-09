#!/usr/bin/env python3
"""
打包 quartz5 生产部署包（zip）。

只包含两块内容 + 一键部署入口脚本：
  - quartz5/        基座源码（全局剔除 node_modules）
      · .quartz/plugins/<社区插件>/ ：保留 .git（浅克隆，离线复用必需）+ dist，剔除 node_modules
      · .quartz/plugins/<本地插件>/ ：跳过（开发机上是指向 plugins-local 的链接，生产由部署脚本重建）
  - plugins-local/  本地插件源码 + dist（剔除 node_modules 与 .git）
  - scripts/deploy.ps1、scripts/setup-local-plugins.mjs（一键部署所需）

打包前校验（缺失只告警、不中断）：
  - 每个 plugins-local/<name> 必须有 dist/
  - 每个社区插件 quartz5/.quartz/plugins/<name> 必须有 dist/ 与 .git/

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

# 除两大块外，额外定向纳入的部署脚本（一键部署必需）
EXTRA_FILES = [
    "scripts/deploy.ps1",
    "scripts/setup-local-plugins.mjs",
]

# 任意层级都剔除的目录名
PRUNE_DIR_NAMES = {"node_modules"}
# 剔除的文件名（submodule 的 .git 是指针文件）与后缀
PRUNE_FILE_NAMES = {".git"}
PRUNE_FILE_SUFFIXES = (".log", ".stackdump")

ZIP_PREFIX = "quartz-fullstack/"
TIMESTAMP = datetime.now().strftime("%Y%m%d-%H%M%S")
OUT_FILE = PROJECT_ROOT / f"quartz-deploy-{TIMESTAMP}.zip"


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


def walk_files(root, keep_dot_git, local_names):
    """遍历 root，按规则产出文件路径。

    keep_dot_git=True 时保留 .git 目录（社区插件浅克隆离线复用需要）。
    任意层级剔除 node_modules；跳过链接型目录与「本地插件名」命名的条目。
    """
    for dirpath, dirnames, filenames in os.walk(root):
        kept = []
        for dn in dirnames:
            full = Path(dirpath) / dn
            if dn in PRUNE_DIR_NAMES:
                continue
            if dn == ".git" and not keep_dot_git:
                continue
            # 本地插件在 .quartz/plugins 下的条目（开发机是 junction）按名跳过
            if Path(dirpath) == PLUGINS_CACHE_DIR and dn in local_names:
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
            yield Path(dirpath) / fn


def collect(local_names):
    files = []
    for p in walk_files(QUARTZ5_DIR, keep_dot_git=True, local_names=local_names):
        files.append((p, p.relative_to(PROJECT_ROOT)))
    for p in walk_files(PLUGINS_LOCAL_DIR, keep_dot_git=False, local_names=local_names):
        files.append((p, p.relative_to(PROJECT_ROOT)))
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
    return warns


def main():
    local_names = local_plugin_names()
    community = community_plugin_dirs(local_names)

    print(f"项目根        : {PROJECT_ROOT}")
    print(f"输出文件      : {OUT_FILE}")
    print(f"本地插件({len(local_names)})   : {', '.join(sorted(local_names)) or '(无)'}")
    print(f"社区插件({len(community)})   : {', '.join(d.name for d in community) or '(无)'}")

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
            zf.write(full, ZIP_PREFIX + rel.as_posix())

    size_mb = OUT_FILE.stat().st_size / (1024 * 1024)
    print(f"\n完成！{OUT_FILE.name}（{size_mb:.2f} MB，{total} 个文件）")


if __name__ == "__main__":
    main()
