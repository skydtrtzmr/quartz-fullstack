#!/usr/bin/env python3
"""
生成多层嵌套目录的测试 Markdown 内容。

只写 input/{domain}/，不写任何业务域配置文件；配置应通过产品 API 产生，
避免手写 YAML 与产品写入路径分叉。

用法：
    python scripts/generate_nested_md.py --domain nest-full --size full --clean
    python scripts/generate_nested_md.py --domain nest-small --size small --clean

可选参数：
    --clean      只清空 input/{domain} 后重新生成（不会删其它域）
    --seed       随机种子，默认 42，保证可复现
"""

import os
import json
import random
import argparse
import shutil
from datetime import datetime, timedelta

# ============ 可复现随机 ============

# 固定种子，保证同样参数生成同样内容，便于回归。
# 运行时可 --seed 覆盖，用于验证随机敏感性。
DEFAULT_SEED = 42

# ============ 规模配置 ============
#
# 目录树是同一套，只有每个叶目录的文件数不同。
# small 约 30~40 个文件，用于快速回归；
# full 约 300~400 个文件，用于主用例。

SIZE_CONFIG = {
    "small": {
        "leaf_counts": {
            "组织/总部": 5,
            "组织/子公司": 3,
            "组织/build": 2,
            "人员/技术部": 5,
            "人员/产品部": 3,
            "人员/status": 2,
            "项目/核心项目/2024": 3,
            "项目/核心项目/2025": 2,
            "项目/支撑项目": 3,
            "任务/在办 任务": 5,
            "任务/归档任务": 3,
            "任务/logs": 2,
        },
        # 附件 md 与 echarts 图表数量
        "attachments": 4,
        "charts": 3,
    },
    "full": {
        "leaf_counts": {
            "组织/总部": 45,
            "组织/子公司": 30,
            "组织/build": 15,
            "人员/技术部": 50,
            "人员/产品部": 30,
            "人员/status": 15,
            "项目/核心项目/2024": 35,
            "项目/核心项目/2025": 25,
            "项目/支撑项目": 40,
            "任务/在办 任务": 55,
            "任务/归档任务": 35,
            "任务/logs": 15,
        },
        "attachments": 10,
        "charts": 6,
    },
}

# 目录树（叶目录必须在上面的 leaf_counts 里出现）
FOLDER_TREE = [
    {
        "name": "组织",
        "children": [
            {"name": "总部", "children": []},
            {"name": "子公司", "children": []},
            {"name": "build", "children": []},   # 边界：与接口后缀同名
        ],
    },
    {
        "name": "人员",
        "children": [
            {"name": "技术部", "children": []},
            {"name": "产品部", "children": []},
            {"name": "status", "children": []}, # 边界
        ],
    },
    {
        "name": "项目",
        "children": [
            {
                "name": "核心项目",
                "children": [
                    {"name": "2024", "children": []},
                    {"name": "2025", "children": []},
                ],
            },
            {"name": "支撑项目", "children": []},
        ],
    },
    {
        "name": "任务",
        "children": [
            {"name": "在办 任务", "children": []},  # 边界：含空格，需 slug 归一化
            {"name": "归档任务", "children": []},
            {"name": "logs", "children": []},      # 边界
        ],
    },
]

# 字段缺失率：验证聚合「有则有效无则跳过」
MISSING_RATE = {
    "type": 0.10,
    "status": 0.15,
    "category": 0.30,
    "阶段": 0.20,
    "级别": 0.15,
    "priority": 0.25,
    "tags": 0.25,
    "organization": 0.05,
    "owner": 0.15,
    "project": 0.10,
}

# 每个顶级分类的枚举值池
VALUE_POOLS = {
    "组织": {
        "type": ["部门", "小组", "虚拟团队", "委员会", "专项组"],
        "status": ["活跃", "休眠", "已解散", "筹备中", "重组中"],
        "category": ["一级部门", "二级部门", "项目组", "职能组", "临时组"],
        "阶段": ["筹备", "扩张", "稳定", "收缩", "重组"],
        "级别": ["高", "中", "低"],
        "tags": ["核心部门", "支持部门", "创新单元", "成本中心", "利润中心", "矩阵", "扁平"],
    },
    "人员": {
        "type": ["工程师", "产品经理", "设计师", "运营", "测试", "架构师"],
        "status": ["在职", "离职", "实习", "外包", "借调"],
        "category": ["研发部", "产品部", "设计部", "运营部", "测试部", "管理部"],
        "阶段": ["入职", "转正", "晋升", "轮岗", "离职"],
        "级别": ["高", "中", "低"],
        "tags": ["专家", "骨干", "新人", "导师", "远程", "全职", "兼职", "Leader"],
    },
    "项目": {
        "type": ["产品研发", "基础设施建设", "市场推广", "运营支撑", "技术预研"],
        "status": ["规划中", "进行中", "已完成", "已暂停", "已取消"],
        "category": ["技术", "业务", "管理", "战略"],
        "阶段": ["立项", "计划", "执行", "收尾", "验收"],
        "级别": ["高", "中", "低"],
        "tags": ["核心", "关键路径", "跨部门", "长期", "短期", "高风险", "高投入", "ROI"],
    },
    "任务": {
        "type": ["开发", "测试", "文档", "评审", "调研", "部署"],
        "status": ["待处理", "进行中", "已完成", "已取消", "阻塞中"],
        "category": ["紧急", "普通", "低优先级", "例行"],
        "阶段": ["待办", "进行", "联调", "测试", "发布"],
        "级别": ["高", "中", "低"],
        "tags": ["前端", "后端", "数据库", "API", "UI", "安全", "性能", "兼容"],
    },
}

# ============ 附件与 echarts 图表 ============
#
# 附件页：每个域一个 附件/ 目录，里面是「解析后的附件文本」md；
# frontmatter 的 `附件下载` 字段带指向公共 assets 目录的实际下载链接
# （服务端 attachments 服务把 input/assets 暴露为 /assets/...）。
# 其它目录的文件会以 wikilink 引用附件 md（引用附件 md 本身，不是下载链接）。

# 公共 assets 目录里实际存在的文件（见 input/assets/）
ASSET_FILES = [
    "DCOM配置手册.pdf",
    "U3报表取数公式说明.pdf",
    "20251224东莞水务会议纪要.docx",
]

ATTACHMENT_POOLS = {
    "type": ["会议纪要", "方案文档", "操作手册", "报表说明"],
    "status": ["已归档", "待归档"],
    "category": ["会议", "方案", "手册", "报表"],
    "阶段": ["收集", "整理", "归档"],
    "级别": ["高", "中", "低"],
    "tags": ["附件", "素材", "下载"],
}

CHART_POOLS = {
    "type": ["柱状图", "折线图", "饼图", "仪表盘"],
    "status": ["草稿", "已验证", "已发布"],
    "category": ["趋势", "占比", "分布", "监控"],
    "阶段": ["样例", "验收", "归档"],
    "级别": ["高", "中", "低"],
    "tags": ["echarts", "图表", "可视化"],
}

# 供 echarts-pro 渲染：正文里的 ```echarts 围栏块内容是合法 ECharts option JSON
ECHARTS_SPECS = [
    ("折线图", {
        "title": {"text": "月度任务完成量趋势"},
        "tooltip": {"trigger": "axis"},
        "xAxis": {"type": "category", "data": ["1月", "2月", "3月", "4月", "5月", "6月"]},
        "yAxis": {"type": "value"},
        "series": [{"type": "line", "smooth": True, "data": [820, 932, 901, 1290, 1330, 1450]}],
    }),
    ("柱状图", {
        "title": {"text": "各类型任务数量"},
        "tooltip": {"trigger": "axis"},
        "xAxis": {"type": "category", "data": ["开发", "测试", "文档", "评审", "调研", "部署"]},
        "yAxis": {"type": "value"},
        "series": [{"type": "bar", "data": [120, 200, 150, 80, 70, 110]}],
    }),
    ("饼图", {
        "title": {"text": "问题类型占比"},
        "tooltip": {"trigger": "item"},
        "legend": {"orient": "vertical", "left": "left"},
        "series": [{
            "type": "pie",
            "radius": "55%",
            "data": [
                {"name": "技术问题", "value": 1048},
                {"name": "业务问题", "value": 735},
                {"name": "流程问题", "value": 580},
                {"name": "使用问题", "value": 484},
                {"name": "方案咨询", "value": 300},
            ],
        }],
    }),
    ("仪表盘", {
        "title": {"text": "整体完成度"},
        "tooltip": {"formatter": "{a} <br/>{b} : {c}%"},
        "series": [{
            "type": "gauge",
            "progress": {"show": True},
            "detail": {"valueAnimation": True, "formatter": "{value}%"},
            "data": [{"value": 72, "name": "完成度"}],
        }],
    }),
]

# 让 build_frontmatter_lines 能处理这两个分类（与 _category_for_path 配合）
VALUE_POOLS["附件"] = ATTACHMENT_POOLS
VALUE_POOLS["图表"] = CHART_POOLS

DATE_START = datetime(2020, 1, 1)
DATE_END = datetime(2025, 12, 31)

LOREM_SENTENCES = [
    "这是一个用于测试的示例段落，包含基本的文本内容。",
    "在实际业务场景中，该文档会包含更详细的描述和说明。",
    "通过批量生成大量文件，可以验证系统在大数据量下的性能和稳定性。",
    "排序功能支持自然排序、字典序、日期和数值等多种方式。",
    "聚合功能支持按文件夹、字段和日期等多种维度分组。",
    "每个文件都可以设置不同的 frontmatter 属性，以实现差异化的排序和聚合效果。",
    "系统会自动处理缺失字段的情况，确保聚合和排序的鲁棒性。",
    "构建过程采用增量更新机制，可以有效减少大规模站点的构建时间。",
    "建议在实际使用前，先用测试数据集验证配置是否符合预期。",
    "本文档由自动化脚本生成，仅用于功能测试和性能基准测试。",
]


def random_date() -> str:
    delta = DATE_END - DATE_START
    random_days = random.randint(0, delta.days)
    d = DATE_START + timedelta(days=random_days)
    return d.strftime("%Y-%m-%d")


def maybe(value, missing_rate: float):
    if random.random() < missing_rate:
        return None
    return value


def _category_for_path(path_parts: list[str]) -> str:
    """根据路径返回顶级分类，用于决定字段值池。"""
    if not path_parts:
        return "任务"
    top = path_parts[0]
    return top if top in VALUE_POOLS else "任务"


def _pick_list(pool: list[str], missing_rate: float):
    val = maybe(None, missing_rate)
    if val is None:
        return None
    count = random.randint(1, min(3, len(pool)))
    tags = random.sample(pool, count)
    return tags


def build_frontmatter_lines(title: str, category: str, extra: dict, known_refs: dict) -> list:
    """生成 frontmatter 行列表。

    known_refs: {"组织": [name, ...], "人员": [...], "项目": [...]}
    extra: 调用方强制写入的字段（如引用关系），会覆盖随机生成的同名字段。
    """
    pool = VALUE_POOLS[category]
    lines = ["---", f'title: "{title}"']

    lines.append(f"date: {random_date()}")

    def add(key: str, value):
        if value is None:
            return
        if isinstance(value, list):
            if len(value) == 1:
                lines.append(f'{key}: ["{value[0]}"]')
            else:
                lines.append(f'{key}: ["' + '", "'.join(value) + '"]')
        elif isinstance(value, int):
            lines.append(f'{key}: {value}')
        else:
            lines.append(f'{key}: "{value}"')

    add("type", maybe(random.choice(pool["type"]), MISSING_RATE["type"]))
    add("status", maybe(random.choice(pool["status"]), MISSING_RATE["status"]))
    add("category", maybe(random.choice(pool["category"]), MISSING_RATE["category"]))
    add("阶段", maybe(random.choice(pool["阶段"]), MISSING_RATE["阶段"]))
    add("级别", maybe(random.choice(pool["级别"]), MISSING_RATE["级别"]))
    add("priority", maybe(random.randint(1, 100), MISSING_RATE["priority"]))
    add("tags", _pick_list(pool["tags"], MISSING_RATE["tags"]))

    # 引用关系字段（与 generate_test_md.py 同口径：单值 wikilink）
    if category == "人员" and "组织" in known_refs and known_refs["组织"]:
        ref = maybe(random.choice(known_refs["组织"]), MISSING_RATE["organization"])
        if ref:
            add("组织", f"[[{ref}]]")
    if category == "项目" and "人员" in known_refs and known_refs["人员"]:
        ref = maybe(random.choice(known_refs["人员"]), MISSING_RATE["owner"])
        if ref:
            add("负责人", f"[[{ref}]]")
    if category == "任务" and "项目" in known_refs and known_refs["项目"]:
        ref = maybe(random.choice(known_refs["项目"]), MISSING_RATE["project"])
        if ref:
            add("项目", f"[[{ref}]]")

    for k, v in extra.items():
        # 强制字段若为空列表表示删除；否则覆盖
        if v == []:
            continue
        # 先删掉已有的同名字段，避免重复
        prefix = f'{k}: '
        lines = [ln for ln in lines if not ln.startswith(prefix)]
        add(k, v)

    lines.append("---")
    return lines


def build_content(title: str, body_links: list[str]) -> str:
    paragraphs = random.sample(LOREM_SENTENCES, k=random.randint(2, 4))
    body = "\n\n".join(paragraphs)
    if body_links:
        link_sentences = []
        for link in body_links:
            templates = [
                f"相关内容请参见 [[{link}]]。",
                f"详细信息可参考 [[{link}|{link}]]。",
                f"如需了解背景，请查看 [[{link}]]。",
                f"关联文档：[[{link}|{link}]]。",
            ]
            link_sentences.append(random.choice(templates))
        body += "\n\n" + " ".join(random.sample(link_sentences, min(len(link_sentences), 3)))
    return f"# {title}\n\n{body}\n"


def generate_index_md(folder_path: str, folder_name: str, rel_path: str):
    filepath = os.path.join(folder_path, "index.md")
    content = f"""---
title: "{folder_name}"
---

# {folder_name}

路径：`{rel_path}`

该目录用于验证多层嵌套目录下的聚合、排序、图谱与属性面板。
"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [index] {filepath}")


def generate_attachment_files(target_dir: str, count: int, known_refs: dict) -> list:
    """生成 附件/ 目录与附件 md，返回 slug 列表。"""
    folder = "附件"
    folder_path = os.path.join(target_dir, folder)
    os.makedirs(folder_path, exist_ok=True)
    generate_index_md(folder_path, folder, folder)
    slugs = []
    for i in range(1, count + 1):
        slug = f"附件-{i:03d}"
        title = f"{folder}-{i:03d}"
        asset = ASSET_FILES[(i - 1) % len(ASSET_FILES)]
        download = f"[{asset}](/assets/{asset})"
        frontmatter = build_frontmatter_lines(title, folder, {"附件下载": download}, known_refs)
        body_links = known_refs.get("项目", [])[:2] if known_refs.get("项目") else []
        body = (
            f"# {title}\n\n"
            f"本文件是解析后的附件文本（测试用），实际附件放在公共 assets 目录。\n\n"
            f"## 附件下载\n\n"
            f"{download}\n\n"
        )
        if body_links:
            body += "关联项目：" + " ".join(f"[[{b}]]" for b in body_links) + "\n"
        filepath = os.path.join(folder_path, f"{slug}.md")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(frontmatter))
            f.write("\n\n")
            f.write(body)
        slugs.append(slug)
    print(f"  [done] {folder}: {count} 个附件 md")
    return slugs


def generate_chart_files(target_dir: str, count: int, known_refs: dict) -> list:
    """生成 图表/ 目录与 echarts 样例，返回 slug 列表。"""
    folder = "图表"
    folder_path = os.path.join(target_dir, folder)
    os.makedirs(folder_path, exist_ok=True)
    generate_index_md(folder_path, folder, folder)
    slugs = []
    for i in range(1, count + 1):
        name, option = ECHARTS_SPECS[(i - 1) % len(ECHARTS_SPECS)]
        slug = f"chart-{i:03d}"
        title = f"{folder}-{i:03d}"
        frontmatter = build_frontmatter_lines(title, folder, {}, known_refs)
        block = json.dumps(option, ensure_ascii=False, indent=2)
        body = (
            f"# {title}（{name}）\n\n"
            f"```echarts\n{block}\n```\n\n"
            f"该文件用于验证 `echarts-pro` 对图表代码块的解析与渲染。\n"
        )
        filepath = os.path.join(folder_path, f"{slug}.md")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(frontmatter))
            f.write("\n\n")
            f.write(body)
        slugs.append(slug)
    print(f"  [done] {folder}: {count} 个 echarts 样例")
    return slugs


def _collect_leaf_paths(node, parent_path="") -> list:
    """按目录树展开出所有叶目录的相对路径（例如 组织/总部）。"""
    current = f"{parent_path}/{node['name']}" if parent_path else node["name"]
    if not node.get("children"):
        return [current]
    leaves = []
    for child in node["children"]:
        leaves.extend(_collect_leaf_paths(child, current))
    return leaves


def _prefix_for_category(category: str) -> str:
    return {"组织": "org", "人员": "person", "项目": "proj", "任务": "task"}.get(category, "note")


def _check_unique_content_names(file_plan: list, attachment_count: int, chart_count: int):
    """内容页的文件名在整个业务域中唯一，避免 shortest 链接匹配到多个页面。"""
    filenames = [f"{slug}.md" for _, _, slug in file_plan]
    filenames.extend(f"附件-{i:03d}.md" for i in range(1, attachment_count + 1))
    filenames.extend(f"chart-{i:03d}.md" for i in range(1, chart_count + 1))
    seen = set()
    for filename in filenames:
        key = filename.casefold()
        if key in seen or key == "index.md":
            raise ValueError(f"生成计划包含重复的内容页文件名: {filename}")
        seen.add(key)


def generate_domain(project_root: str, domain: str, size: str, clean: bool, seed: int,
                    charts: int = -1, attachments: int = -1):
    random.seed(seed)

    target_dir = os.path.join(project_root, "input", domain)
    if clean and os.path.exists(target_dir):
        shutil.rmtree(target_dir)
        print(f"[clean] {target_dir}")

    os.makedirs(target_dir, exist_ok=True)
    print(f"[target] {target_dir}")

    leaf_counts = SIZE_CONFIG[size]["leaf_counts"]
    all_leaf_paths = []
    for top in FOLDER_TREE:
        all_leaf_paths.extend(_collect_leaf_paths(top))

    # 检查配置是否遗漏目录
    missing = [p for p in all_leaf_paths if p not in leaf_counts]
    if missing:
        raise ValueError(f"SIZE_CONFIG[{size!r}].leaf_counts 缺少目录: {missing}")

    # 预先生成所有文件记录，用于后续引用
    # records: {category: [slug, ...]}
    records_by_category: dict[str, list[str]] = {
        "组织": [], "人员": [], "项目": [], "任务": [], "附件": [], "图表": []
    }
    file_plan = []  # (leaf_path, seq, slug)
    # 序号按分类全局连续分配，不能每个目录从 1 重计 —— 否则跨目录出现同名文件，
    # Quartz shortest 链接解析要求同名唯一（匹配数 != 1 即解析失败 → 虚拟节点占位页）
    cat_seq: dict[str, int] = {}
    for leaf_path in all_leaf_paths:
        category = _category_for_path(leaf_path.split("/"))
        count = leaf_counts[leaf_path]
        prefix = _prefix_for_category(category)
        for _ in range(count):
            seq = cat_seq.get(category, 0) + 1
            cat_seq[category] = seq
            filename = f"{prefix}-{seq:05d}.md"
            slug = filename.replace(".md", "")
            file_plan.append((leaf_path, seq, slug))
            records_by_category[category].append(slug)

    chart_count = SIZE_CONFIG[size]["charts"] if charts < 0 else charts
    attachment_count = SIZE_CONFIG[size]["attachments"] if attachments < 0 else attachments
    _check_unique_content_names(file_plan, attachment_count, chart_count)

    # 先生成附件与图表，这样普通文件的引用有目标可指
    if attachment_count > 0:
        records_by_category["附件"] = generate_attachment_files(target_dir, attachment_count, records_by_category)
    if chart_count > 0:
        records_by_category["图表"] = generate_chart_files(target_dir, chart_count, records_by_category)

    # 生成 index.md（根目录 + 每个子目录）
    generate_root_index_md(target_dir, domain, file_plan, attachment_count, chart_count)
    for leaf_path in all_leaf_paths:
        folder_path = os.path.join(target_dir, *leaf_path.split("/"))
        os.makedirs(folder_path, exist_ok=True)
        generate_index_md(folder_path, leaf_path.split("/")[-1], leaf_path)
    # 中间目录也需要 index.md
    _ensure_intermediate_indices(target_dir, FOLDER_TREE)

    # 生成文件内容
    for leaf_path, seq, slug in file_plan:
        folder_path = os.path.join(target_dir, *leaf_path.split("/"))
        category = _category_for_path(leaf_path.split("/"))
        filename = f"{slug}.md"
        title = f"{leaf_path.replace('/', ' / ')}-{seq:05d}"

        # 正文引用：随机链到同分类或相关分类的几条
        body_links = []
        if category == "任务":
            candidates = records_by_category["项目"] + records_by_category["人员"]
        elif category == "项目":
            candidates = records_by_category["人员"] + records_by_category["任务"]
        elif category == "人员":
            candidates = records_by_category["组织"] + records_by_category["任务"]
        else:
            candidates = records_by_category["人员"] + records_by_category["项目"]
        if candidates:
            link_count = random.randint(0, min(2, len(candidates)))
            body_links = random.sample(candidates, link_count)

        # 约 20% 的文件引用一个附件 md（引用附件 md，而不是 assets 下载链接）
        extra = {}
        attachments = records_by_category.get("附件", [])
        if attachments and random.random() < 0.20:
            att = random.choice(attachments)
            if random.random() < 0.5:
                extra["相关附件"] = f"[[{att}]]"
            else:
                body_links.append(att)

        frontmatter = build_frontmatter_lines(title, category, extra, records_by_category)
        body = build_content(title, body_links)
        filepath = os.path.join(folder_path, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(frontmatter))
            f.write("\n\n")
            f.write(body)

    total_files = len(file_plan)
    total_dirs = len(all_leaf_paths)
    print(f"[summary] 共生成 {total_files} 个普通 Markdown 文件，{total_dirs} 个叶目录，"
          f"{attachment_count} 个附件 md，{chart_count} 个 echarts 样例，种子={seed}")
    print(f"[summary] 目标目录: {target_dir}")


def _ensure_intermediate_indices(target_dir: str, tree: list, parent_path=""):
    """为非叶中间目录补 index.md。"""
    for node in tree:
        current = f"{parent_path}/{node['name']}" if parent_path else node["name"]
        folder_path = os.path.join(target_dir, *current.split("/"))
        os.makedirs(folder_path, exist_ok=True)
        if not os.path.exists(os.path.join(folder_path, "index.md")):
            generate_index_md(folder_path, node["name"], current)
        if node.get("children"):
            _ensure_intermediate_indices(target_dir, node["children"], current)


def generate_root_index_md(target_dir: str, domain: str, file_plan: list,
                           attachment_count: int = 0, chart_count: int = 0):
    total = len(file_plan)
    # 按叶目录统计
    folder_counts: dict[str, int] = {}
    for leaf_path, _, _ in file_plan:
        folder_counts[leaf_path] = folder_counts.get(leaf_path, 0) + 1

    folder_lines = []
    for leaf_path, count in sorted(folder_counts.items()):
        pct = count / total * 100 if total else 0
        folder_lines.append(f"| {leaf_path} | {count} | {pct:.1f}% |")

    content = f"""---
title: "{domain}"
---

# {domain}

这是一个多层嵌套测试业务域，用于验证按文件夹聚合、属性继承、边界目录名（`build`/`status`/`logs`、含空格目录）、
echarts 图表与附件页等场景。

## 统计

| 指标 | 值 |
|------|-----|
| 普通文件数 | {total} |
| 叶目录数 | {len(folder_counts)} |
| 附件 md | {attachment_count} |
| echarts 样例 | {chart_count} |

## 叶目录分布

| 叶目录 | 文件数 | 占比 |
|--------|--------|------|
{chr(10).join(folder_lines)}

*此文件由 `scripts/generate_nested_md.py` 自动生成，请勿手动修改。*
"""
    filepath = os.path.join(target_dir, "index.md")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [index] {filepath}")


def main():
    parser = argparse.ArgumentParser(description="生成多层嵌套目录的测试 Markdown 内容")
    parser.add_argument("--domain", type=str, required=True, help="业务域名称，如 nest-full")
    parser.add_argument("--size", type=str, choices=["small", "full"], required=True,
                        help="生成规模：small 约 30~40 文件，full 约 300~400 文件")
    parser.add_argument("--clean", action="store_true",
                        help="清空 input/{domain} 后重新生成（只清本域，不会删其它域）")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED,
                        help=f"随机种子，默认 {DEFAULT_SEED}")
    parser.add_argument("--charts", type=int, default=-1,
                        help="echarts 样例数量；-1 = 按 size 默认（small 3 / full 6），0 = 不生成")
    parser.add_argument("--attachments", type=int, default=-1,
                        help="附件 md 数量；-1 = 按 size 默认（small 4 / full 10），0 = 不生成")
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)

    generate_domain(project_root, args.domain, args.size, args.clean, args.seed,
                    charts=args.charts, attachments=args.attachments)


if __name__ == "__main__":
    main()
