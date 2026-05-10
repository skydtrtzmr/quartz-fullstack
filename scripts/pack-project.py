#!/usr/bin/env python3
"""
打包项目为 zip 压缩包，排除不需要的文件和目录。

排除规则：
- node_modules/
- .spec/
- input/ (保留 .gitkeep)
- output/ (保留 .gitkeep)
- settings/ (用户私有配置)
- *.log
- .git/
- client/node_modules/ (如果存在)
- server/*.exe
- bruno-api-test/ (可选)

输出：quartz-fullstack-<timestamp>.zip
"""

import os
import sys
import zipfile
from datetime import datetime
from pathlib import Path

# 项目根目录（脚本所在目录的父目录）
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent

# 输出文件路径
timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
OUT_FILE = PROJECT_ROOT / f"quartz-fullstack-{timestamp}.zip"

# 排除模式（基于 fnmatch）
EXCLUDE_PATTERNS = [
    "node_modules",
    ".spec",
    "input/*",
    "output/*",
    "settings",
    "*.log",
    ".git",
    "bruno-api-test",
    "*.exe",
]

# 保留的文件（即使匹配排除规则）
INCLUDE_PATTERNS = [
    "input/.gitkeep",
    "output/.gitkeep",
]


def matches_pattern(relative_path: str, pattern: str) -> bool:
    """检查相对路径是否匹配给定的模式。"""
    import fnmatch

    # 支持多种匹配方式
    patterns = [
        f"*/{pattern}/*",
        f"{pattern}/*",
        f"*/{pattern}",
        pattern,
    ]
    return any(fnmatch.fnmatch(relative_path, p) for p in patterns)


def should_include(relative_path: str) -> bool:
    """判断文件是否应该被打包。"""
    # 先检查保留列表
    for pattern in INCLUDE_PATTERNS:
        if relative_path == pattern:
            return True

    # 再检查排除列表
    for pattern in EXCLUDE_PATTERNS:
        if matches_pattern(relative_path, pattern):
            return False

    return True


def main():
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Output file:  {OUT_FILE}")

    # 收集所有文件
    all_files = []
    for root, dirs, files in os.walk(PROJECT_ROOT):
        # 跳过 .git 和 node_modules 以加速遍历
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules")]

        for filename in files:
            full_path = Path(root) / filename
            relative_path = full_path.relative_to(PROJECT_ROOT).as_posix()

            if should_include(relative_path):
                all_files.append((full_path, relative_path))

    print(f"Files to pack: {len(all_files)}")

    # 如果输出文件已存在，先删除
    if OUT_FILE.exists():
        OUT_FILE.unlink()

    # 创建 zip 压缩包
    with zipfile.ZipFile(OUT_FILE, "w", zipfile.ZIP_DEFLATED) as zf:
        for full_path, relative_path in all_files:
            arcname = f"quartz-fullstack/{relative_path}"
            zf.write(full_path, arcname)

    size = OUT_FILE.stat().st_size
    size_mb = size / (1024 * 1024)
    print(f"Done! {OUT_FILE} ({size_mb:.2f} MB)")


if __name__ == "__main__":
    main()
