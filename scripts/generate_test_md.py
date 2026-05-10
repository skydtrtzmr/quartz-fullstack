#!/usr/bin/env python3
"""
批量生成测试 Markdown 文件

用途：在 input/testgen/ 下生成 2 万个测试文件，覆盖排序、聚合等功能验证。

执行方式：
    python scripts/generate_test_md.py

可选参数：
    --clean    清空目标目录后重新生成
"""

import os
import sys
import random
import argparse
from datetime import datetime, timedelta

# ============ 配置 ============

TARGET_DOMAIN = "testgen"
TOTAL_FILES = 20000
FOLDER_CONFIGS = [
    {
        "name": "项目",
        "prefix": "proj",
        "count": 4000,
        "types": ["产品研发", "基础设施建设", "市场推广", "运营支撑", "技术预研"],
        "statuses": ["规划中", "进行中", "已完成", "已暂停", "已取消"],
        "categories": ["技术", "业务", "管理", "战略"],
        "tags_pool": ["核心", "关键路径", "跨部门", "长期", "短期", "高风险", "高投入", "ROI"],
    },
    {
        "name": "任务",
        "prefix": "task",
        "count": 4000,
        "types": ["开发", "测试", "文档", "评审", "调研", "部署"],
        "statuses": ["待处理", "进行中", "已完成", "已取消", "阻塞中"],
        "categories": ["紧急", "普通", "低优先级", "例行"],
        "tags_pool": ["前端", "后端", "数据库", "API", "UI", "安全", "性能", "兼容"],
    },
    {
        "name": "问答",
        "prefix": "qa",
        "count": 4000,
        "types": ["技术问题", "业务问题", "流程问题", "使用问题", "方案咨询"],
        "statuses": ["待回复", "已回复", "已解决", "已关闭", "待补充"],
        "categories": ["前端", "后端", "运维", "产品", "数据", "算法"],
        "tags_pool": ["Bug", "最佳实践", "架构", "排障", "配置", "权限", "迁移", "优化"],
    },
    {
        "name": "人员",
        "prefix": "person",
        "count": 4000,
        "types": ["工程师", "产品经理", "设计师", "运营", "测试", "架构师"],
        "statuses": ["在职", "离职", "实习", "外包", "借调"],
        "categories": ["研发部", "产品部", "设计部", "运营部", "测试部", "管理部"],
        "tags_pool": ["专家", "骨干", "新人", "导师", "远程", "全职", "兼职", "Leader"],
    },
    {
        "name": "组织",
        "prefix": "org",
        "count": 4000,
        "types": ["部门", "小组", "虚拟团队", "委员会", "专项组"],
        "statuses": ["活跃", "休眠", "已解散", "筹备中", "重组中"],
        "categories": ["一级部门", "二级部门", "项目组", "职能组", "临时组"],
        "tags_pool": ["核心部门", "支持部门", "创新单元", "成本中心", "利润中心", "矩阵", "扁平"],
    },
]

# 字段缺失率（用于测试聚合"有则有效无则跳过"）
MISSING_RATE = {
    "type": 0.10,
    "priority": 0.20,
    "status": 0.15,
    "tags": 0.25,
    "category": 0.30,
}

# 日期范围
DATE_START = datetime(2020, 1, 1)
DATE_END = datetime(2025, 12, 31)

LOREM_SENTENCES = [
    "这是一个用于测试的示例段落，包含基本的文本内容。",
    "在实际业务场景中，该文档会包含更详细的描述和说明。",
    "通过批量生成大量文件，可以验证系统在大数据量下的性能和稳定性。",
    "排序功能支持自然排序、字典序、日期和数值等多种方式。",
    "聚合功能支持按文件夹、字段和日期等多种维度进行分组。",
    "每个文件都可以设置不同的 frontmatter 属性，以实现差异化的排序和聚合效果。",
    "系统会自动处理缺失字段的情况，确保聚合和排序的鲁棒性。",
    "构建过程采用增量更新机制，可以有效减少大规模站点的构建时间。",
    "建议在实际使用前，先用测试数据集验证配置是否符合预期。",
    "本文档由自动化脚本生成，仅用于功能测试和性能基准测试。",
]


def random_date() -> str:
    """生成随机日期字符串 yyyy-mm-dd"""
    delta = DATE_END - DATE_START
    random_days = random.randint(0, delta.days)
    d = DATE_START + timedelta(days=random_days)
    return d.strftime("%Y-%m-%d")


def random_time() -> str:
    """生成随机时间后缀"""
    h = random.randint(8, 18)
    m = random.randint(0, 59)
    return f"{h:02d}:{m:02d}"


def maybe(value, missing_rate: float):
    """按缺失率决定是否返回空值"""
    if random.random() < missing_rate:
        return None
    return value


def build_frontmatter(
    title: str,
    folder_cfg: dict,
    file_idx: int,
) -> str:
    """构建 frontmatter YAML"""
    lines = ["---", f'title: "{title}"']

    # date: 所有文件都有，用于 date 排序和 date 聚合
    lines.append(f"date: {random_date()}")

    # type: 用于 field 聚合
    val = maybe(random.choice(folder_cfg["types"]), MISSING_RATE["type"])
    if val:
        lines.append(f'type: "{val}"')

    # priority: 用于 numeric 排序（1-100）
    val = maybe(random.randint(1, 100), MISSING_RATE["priority"])
    if val is not None:
        lines.append(f"priority: {val}")

    # status: 用于 field 聚合
    val = maybe(random.choice(folder_cfg["statuses"]), MISSING_RATE["status"])
    if val:
        lines.append(f'status: "{val}"')

    # category: 用于 field 聚合
    val = maybe(random.choice(folder_cfg["categories"]), MISSING_RATE["category"])
    if val:
        lines.append(f'category: "{val}"')

    # tags: 用于 field 聚合（数组）
    val = maybe(None, MISSING_RATE["tags"])
    if val is not None:
        tag_count = random.randint(1, 3)
        tags = random.sample(folder_cfg["tags_pool"], min(tag_count, len(folder_cfg["tags_pool"])))
        if len(tags) == 1:
            lines.append(f'tags: ["{tags[0]}"]')
        else:
            lines.append(f'tags: ["' + '", "'.join(tags) + '"]')

    lines.append("---")
    return "\n".join(lines)


def build_content(title: str) -> str:
    """生成正文内容"""
    paragraphs = random.sample(LOREM_SENTENCES, k=random.randint(2, 5))
    body = "\n\n".join(paragraphs)
    return f"# {title}\n\n{body}\n"


def generate_index_md(folder_path: str, folder_name: str):
    """生成文件夹的 index.md"""
    filepath = os.path.join(folder_path, "index.md")
    content = f"---\ntitle: \"{folder_name}\"\n---\n\n# {folder_name}\n\n该目录下包含大量测试文件，用于验证排序与聚合功能。\n"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [index] {filepath}")


def generate_folder(base_dir: str, cfg: dict, start_idx: int) -> int:
    """生成单个文件夹下的所有文件"""
    folder_path = os.path.join(base_dir, cfg["name"])
    os.makedirs(folder_path, exist_ok=True)

    # 生成 index.md
    generate_index_md(folder_path, cfg["name"])

    count = cfg["count"]
    prefix = cfg["prefix"]

    for i in range(count):
        file_idx = start_idx + i + 1
        file_num = i + 1
        filename = f"{prefix}-{file_num:05d}.md"
        filepath = os.path.join(folder_path, filename)

        title = f"{cfg['name']}-{file_num:05d}"
        frontmatter = build_frontmatter(title, cfg, file_idx)
        body = build_content(title)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(frontmatter)
            f.write("\n\n")
            f.write(body)

    print(f"  [done] {cfg['name']}: {count} files")
    return count


def main():
    parser = argparse.ArgumentParser(description="批量生成测试 Markdown 文件")
    parser.add_argument("--clean", action="store_true", help="清空目标目录后重新生成")
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    target_dir = os.path.join(project_root, "input", TARGET_DOMAIN)

    if args.clean and os.path.exists(target_dir):
        import shutil
        print(f"[clean] 删除 {target_dir}")
        shutil.rmtree(target_dir)

    os.makedirs(target_dir, exist_ok=True)
    print(f"[target] {target_dir}")

    total = 0
    for cfg in FOLDER_CONFIGS:
        total += generate_folder(target_dir, cfg, total)

    print(f"[summary] 共生成 {total} 个 Markdown 文件（含 {len(FOLDER_CONFIGS)} 个 index.md）")
    print(f"[summary] 目标目录: {target_dir}")


if __name__ == "__main__":
    main()
