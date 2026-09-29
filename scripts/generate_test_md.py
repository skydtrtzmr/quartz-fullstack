#!/usr/bin/env python3
"""
批量生成测试 Markdown 文件（含 Obsidian 风格 wikilink 引用关系）

用途：在 input/{domain}/ 下生成测试文件，覆盖排序、聚合、反向链接、图谱等功能验证。

域配置按 **v5 规则** 写入 settings/{domain}/quartz.config.yaml：
整棵继承 server/config.json 的 template_file，只改写 pageTitle / baseUrl /
configuration.aggregation / note-properties-pro 的属性链 / graph-pro 的
globalGraph.{folders,coreNodeLimit}（见 scripts/v5_domain_config.py）。
**不再**写 v4 的 quartz.config.json + quartz.layout.json。

两个 profile（v4 概念在 v5 里的对应写法）：
    region  大区模式：多个文件夹当首屏大区（globalGraph.folders = [项目, 组织]），
                     目录字段链配得比较全 → 维度页/聚合分组更丰富
    core    硬上限模式：单一大区（folders = [项目]）+ coreNodeLimit 收紧到 30，
                     字段链精简

用法：
    python scripts/generate_test_md.py --domain demo-region --profile region --clean
    python scripts/generate_test_md.py --domain demo-core --profile core --clean

生成后构建（域配置改动过必须 --reset 全量重建）：
    cd quartz5
    npm run quartz -- build -d ../input/demo-region -o ../output/demo-region \\
        --settings ../settings/demo-region --sqlite --cacheDir ../cache/demo-region --reset

可选参数：
    --clean       清空目标目录后重新生成（只清本域）
    --clean-all   清理 input/ output/ settings/ 下所有其它域（递归删除，慎用）
    --charts N    额外生成 N 个 echarts 图表样例（<domain>/图表/）
"""

import os
import random
import argparse
import shutil
import json
from datetime import datetime, timedelta

from v5_domain_config import build_command as build_v5_command
from v5_domain_config import write_domain_config as write_v5_domain_config

# ============ 配置 ============

# 数量分布：组织 < 人员 < 项目 < 任务 < 问答
FOLDER_CONFIGS = [
    {"name": "组织", "prefix": "org",   "count": 40},
    {"name": "人员", "prefix": "person","count": 200},
    {"name": "项目", "prefix": "proj",  "count": 60},
    {"name": "任务", "prefix": "task",  "count": 700},
    {"name": "问答", "prefix": "qa",    "count": 1000},
]

# 人员姓名与文件编号分开生成，便于验证按 frontmatter 字段排序。
PERSON_SURNAMES = [
    "王", "李", "张", "刘", "陈", "杨", "赵", "黄", "周", "吴",
    "徐", "孙", "胡", "朱", "高", "林", "何", "郭", "马", "罗",
]
PERSON_GIVEN_NAMES = [
    "伟", "芳", "娜", "敏", "静", "丽", "强", "磊", "军", "洋",
    "勇", "艳", "杰", "娟", "涛", "明", "超", "秀英", "建华", "晓丽",
]

# 字段缺失率（用于测试聚合"有则有效无则跳过"）
MISSING_RATE = {
    "type": 0.10,
    "priority": 0.20,
    "status": 0.15,
    "tags": 0.25,
    "category": 0.30,
    "阶段": 0.20,            # 项目/任务/组织的生命周期阶段
    "级别": 0.15,            # 高/中/低 优先级分级
    "organization": 0.05,   # 人员所属组织（极少缺失）
    "project": 0.10,        # 任务所属项目
    "owner": 0.15,          # 项目负责人
    "related": 0.40,        # 问答关联对象
}

# 各分类的枚举值池
TYPE_POOLS = {
    "组织": ["部门", "小组", "虚拟团队", "委员会", "专项组"],
    "人员": ["工程师", "产品经理", "设计师", "运营", "测试", "架构师"],
    "项目": ["产品研发", "基础设施建设", "市场推广", "运营支撑", "技术预研"],
    "任务": ["开发", "测试", "文档", "评审", "调研", "部署"],
    "问答": ["技术问题", "业务问题", "流程问题", "使用问题", "方案咨询"],
}

STATUS_POOLS = {
    "组织": ["活跃", "休眠", "已解散", "筹备中", "重组中"],
    "人员": ["在职", "离职", "实习", "外包", "借调"],
    "项目": ["规划中", "进行中", "已完成", "已暂停", "已取消"],
    "任务": ["待处理", "进行中", "已完成", "已取消", "阻塞中"],
    "问答": ["待回复", "已回复", "已解决", "已关闭", "待补充"],
}

CATEGORY_POOLS = {
    "组织": ["一级部门", "二级部门", "项目组", "职能组", "临时组"],
    "人员": ["研发部", "产品部", "设计部", "运营部", "测试部", "管理部"],
    "项目": ["技术", "业务", "管理", "战略"],
    "任务": ["紧急", "普通", "低优先级", "例行"],
    "问答": ["前端", "后端", "运维", "产品", "数据", "算法"],
}

# 阶段：实体在其生命周期中的阶段（用于二级动态分类演示）
PHASE_POOLS = {
    "组织": ["筹备", "扩张", "稳定", "收缩", "重组"],
    "人员": ["入职", "转正", "晋升", "轮岗", "离职"],
    "项目": ["立项", "计划", "执行", "收尾", "验收"],
    "任务": ["待办", "进行", "联调", "测试", "发布"],
    "问答": ["提问", "排查", "验证", "归档", "关闭"],
}

# 级别：粗粒度的优先级分级（高/中/低），作为第三分类轴演示
LEVEL_POOLS = {
    "组织": ["高", "中", "低"],
    "人员": ["高", "中", "低"],
    "项目": ["高", "中", "低"],
    "任务": ["高", "中", "低"],
    "问答": ["高", "中", "低"],
}

TAGS_POOLS = {
    "组织": ["核心部门", "支持部门", "创新单元", "成本中心", "利润中心", "矩阵", "扁平"],
    "人员": ["专家", "骨干", "新人", "导师", "远程", "全职", "兼职", "Leader"],
    "项目": ["核心", "关键路径", "跨部门", "长期", "短期", "高风险", "高投入", "ROI"],
    "任务": ["前端", "后端", "数据库", "API", "UI", "安全", "性能", "兼容"],
    "问答": ["Bug", "最佳实践", "架构", "排障", "配置", "权限", "迁移", "优化"],
}

# ============ 图表样例（任务 1：图表代码块渲染）============
# 围栏块语言标记必须是 `echarts`，块内容必须是**合法 JSON 对象**（ECharts option 原样透传）；
# 渲染由本地插件 `plugins-local/echarts-pro` 负责（height / styleMode 由该插件 YAML options 控制）。
# 这里覆盖几种常见图表类型，轮流分配给生成的图表文件。
CHART_SPECS = [
    ("折线图", {
        "title": {"text": "月度任务完成量趋势"},
        "tooltip": {"trigger": "axis"},
        "xAxis": {"type": "category", "data": ["1月", "2月", "3月", "4月", "5月", "6月"]},
        "yAxis": {"type": "value"},
        "series": [{"type": "line", "smooth": True, "data": [820, 932, 901, 1290, 1330, 1450]}],
    }),
    ("面积折线图", {
        "title": {"text": "项目投入与产出"},
        "tooltip": {"trigger": "axis"},
        "legend": {"data": ["投入", "产出"]},
        "xAxis": {"type": "category", "boundaryGap": False, "data": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]},
        "yAxis": {"type": "value"},
        "series": [
            {"name": "投入", "type": "line", "stack": "总量", "areaStyle": {}, "data": [120, 132, 101, 134, 90, 230, 210]},
            {"name": "产出", "type": "line", "stack": "总量", "areaStyle": {}, "data": [220, 182, 191, 234, 290, 330, 310]},
        ],
    }),
    ("柱状图", {
        "title": {"text": "各类型任务数量"},
        "tooltip": {"trigger": "axis"},
        "xAxis": {"type": "category", "data": ["开发", "测试", "文档", "评审", "调研", "部署"]},
        "yAxis": {"type": "value"},
        "series": [{"type": "bar", "data": [120, 200, 150, 80, 70, 110]}],
    }),
    ("堆叠柱状图", {
        "title": {"text": "各阶段任务状态分布"},
        "tooltip": {"trigger": "axis"},
        "legend": {},
        "xAxis": {"type": "category", "data": ["待办", "进行", "联调", "测试", "发布"]},
        "yAxis": {"type": "value"},
        "series": [
            {"name": "已完成", "type": "bar", "stack": "total", "data": [320, 302, 301, 334, 390]},
            {"name": "进行中", "type": "bar", "stack": "total", "data": [120, 132, 101, 134, 90]},
            {"name": "阻塞中", "type": "bar", "stack": "total", "data": [220, 182, 191, 234, 290]},
        ],
    }),
    ("横向条形图", {
        "title": {"text": "各部门人员规模"},
        "tooltip": {"trigger": "axis"},
        "xAxis": {"type": "value"},
        "yAxis": {"type": "category", "data": ["研发部", "产品部", "设计部", "运营部", "测试部"]},
        "series": [{"type": "bar", "data": [42, 18, 12, 25, 15]}],
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
    ("环形图", {
        "title": {"text": "任务优先级分布"},
        "tooltip": {"trigger": "item"},
        "legend": {"bottom": 0},
        "series": [{
            "type": "pie",
            "radius": ["40%", "65%"],
            "avoidLabelOverlap": True,
            "label": {"show": False},
            "data": [
                {"name": "高", "value": 335},
                {"name": "中", "value": 480},
                {"name": "低", "value": 210},
            ],
        }],
    }),
    ("散点图", {
        "title": {"text": "工时与产出关系"},
        "tooltip": {"trigger": "item"},
        "xAxis": {"type": "value", "name": "工时"},
        "yAxis": {"type": "value", "name": "产出"},
        "series": [{
            "type": "scatter",
            "symbolSize": 12,
            "data": [[10.0, 8.04], [8.07, 6.95], [13.0, 7.58], [9.05, 8.81], [11.0, 8.33], [14.0, 7.66], [13.4, 6.81], [10.0, 6.33], [14.0, 8.96]],
        }],
    }),
    ("雷达图", {
        "title": {"text": "项目多维评估"},
        "tooltip": {},
        "legend": {"data": ["项目A", "项目B"]},
        "radar": {
            "indicator": [
                {"name": "进度", "max": 100},
                {"name": "质量", "max": 100},
                {"name": "成本", "max": 100},
                {"name": "风险", "max": 100},
                {"name": "协作", "max": 100},
            ],
        },
        "series": [{
            "type": "radar",
            "data": [
                {"value": [85, 90, 70, 60, 88], "name": "项目A"},
                {"value": [70, 82, 88, 75, 66], "name": "项目B"},
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

# 图表样例目录的分类池（与其它目录同构，便于一并参与聚合 / 排序 / 图谱验证）
TYPE_POOLS["图表"] = ["柱状图", "折线图", "饼图", "散点图", "雷达图"]
STATUS_POOLS["图表"] = ["草稿", "已验证", "已发布"]
CATEGORY_POOLS["图表"] = ["趋势", "占比", "分布", "对比", "监控"]
PHASE_POOLS["图表"] = ["样例", "验收", "归档"]
LEVEL_POOLS["图表"] = ["高", "中", "低"]
TAGS_POOLS["图表"] = ["echarts", "图表", "可视化", "样式"]

# 日期范围
DATE_START = datetime(2020, 1, 1)
DATE_END = datetime(2025, 12, 31)

# 正文模板段落
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

# ============ v5 域配置（settings/{domain}/quartz.config.yaml）============
#
# v5 只认一份 YAML（configuration / plugins / layout 三段）；脚本不再写 v4 的
# quartz.config.json + quartz.layout.json（服务端不读，写了只会污染 settings/）。
#
# v4 → v5 字段对应：
#   graph.regionRules       → 首屏大区「恒为文件夹」，由 globalGraph.folders 指定
#                             （旧写法 regionRules: [{type: field, field: type}] 已无对应键，
#                               字段维度改由 configuration.aggregation 承担）
#   graph.coreNodeFilter    → globalGraph.folders（values 直接变成 folders 列表），该键已删除
#   graph.coreNodeLimit     → globalGraph.coreNodeLimit
#   graph.aggregation       → configuration.aggregation
#   backlinks.aggregation   → configuration.aggregation（全站一份，不再按组件各配一份）
#   graph.precomputeLocal / localDepth → graph-pro 插件 options.graph（模板里已是 true / 1）
#
# 文件夹排序可通过 _folder 接口写入域 YAML 的 sort.field；此处不预设排序字段。

# 属性面板显示链的公共部分（note-properties-pro.options.properties，与聚合链同构）
_PROPERTIES_DEFAULT = ["date", "type", "status", "priority", "category", "tags"]

DOMAIN_PROFILES = {
    # 大区模式：多个文件夹当首屏大区，目录字段链配全 → 维度页 / 聚合分组更丰富
    "region": {
        "aggregation": {
            "folder_depth": 1,
            "default": ["type", "status", "category"],
            "folders": {
                "组织": ["type", "阶段"],
                "人员": ["category", "type", "级别"],
                "项目": ["阶段", "type", "status", "负责人"],
                "任务": ["status", "阶段", "级别"],
                "问答": ["category", "status"],
            },
        },
        "properties": {
            "folder_depth": 1,
            "default": _PROPERTIES_DEFAULT,
            "folders": {
                "组织": ["type", "阶段", "tags"],
                "人员": ["姓名", "category", "type", "级别", "组织", "tags"],
                "项目": ["阶段", "type", "status", "负责人", "tags"],
                "任务": ["status", "阶段", "级别", "项目", "tags"],
                "问答": ["category", "status", "项目", "任务", "tags"],
            },
        },
        "graph_folders": ["项目", "组织"],
        "graph_core_node_limit": 50,
    },
    # 硬上限模式：单一大区 + coreNodeLimit 收紧，字段链精简
    "core": {
        "aggregation": {
            "folder_depth": 1,
            "default": ["status"],
            "folders": {
                "项目": ["阶段", "status", "负责人"],
                "任务": ["status", "项目"],
            },
        },
        "properties": {
            "folder_depth": 1,
            "default": _PROPERTIES_DEFAULT,
            "folders": {
                "项目": ["阶段", "status", "负责人", "tags"],
                "任务": ["status", "级别", "项目", "tags"],
                "人员": ["姓名", "category", "type", "级别", "组织", "tags"],
            },
        },
        "graph_folders": ["项目"],
        "graph_core_node_limit": 30,
    },
}


def random_date() -> str:
    delta = DATE_END - DATE_START
    random_days = random.randint(0, delta.days)
    d = DATE_START + timedelta(days=random_days)
    return d.strftime("%Y-%m-%d")


def maybe(value, missing_rate: float):
    if random.random() < missing_rate:
        return None
    return value


def generate_person_names(count: int) -> list[str]:
    names = [surname + given for surname in PERSON_SURNAMES for given in PERSON_GIVEN_NAMES]
    if count > len(names):
        raise ValueError(f"人员数量 {count} 超过可生成的不重复姓名数量 {len(names)}")
    return random.sample(names, count)


def build_frontmatter_lines(title: str, folder_name: str, extra_fields: dict) -> list:
    lines = ["---", f'title: "{title}"']

    # date: 所有文件都有
    lines.append(f"date: {random_date()}")

    # type
    val = maybe(random.choice(TYPE_POOLS[folder_name]), MISSING_RATE["type"])
    if val:
        lines.append(f'type: "{val}"')

    # priority: 用于 numeric 排序（1-100）
    val = maybe(random.randint(1, 100), MISSING_RATE["priority"])
    if val is not None:
        lines.append(f"priority: {val}")

    # status
    val = maybe(random.choice(STATUS_POOLS[folder_name]), MISSING_RATE["status"])
    if val:
        lines.append(f'status: "{val}"')

    # category
    val = maybe(random.choice(CATEGORY_POOLS[folder_name]), MISSING_RATE["category"])
    if val:
        lines.append(f'category: "{val}"')

    # 阶段（生命周期阶段）
    val = maybe(random.choice(PHASE_POOLS[folder_name]), MISSING_RATE["阶段"])
    if val:
        lines.append(f'阶段: "{val}"')

    # 级别（优先级分级）
    val = maybe(random.choice(LEVEL_POOLS[folder_name]), MISSING_RATE["级别"])
    if val:
        lines.append(f'级别: "{val}"')

    # tags
    val = maybe(None, MISSING_RATE["tags"])
    if val is not None:
        tag_count = random.randint(1, 3)
        tags = random.sample(TAGS_POOLS[folder_name], min(tag_count, len(TAGS_POOLS[folder_name])))
        if len(tags) == 1:
            lines.append(f'tags: ["{tags[0]}"]')
        else:
            lines.append(f'tags: ["' + '", "'.join(tags) + '"]')

    # extra_fields（引用关系字段，值使用 [[wikilink]] 格式）
    for k, v in extra_fields.items():
        if v is not None and not isinstance(v, list):
            lines.append(f'{k}: "[[{v}]]"')

    lines.append("---")
    return lines


def build_content(title: str, body_links: list[str]) -> str:
    paragraphs = random.sample(LOREM_SENTENCES, k=random.randint(2, 4))
    body = "\n\n".join(paragraphs)

    # 正文中添加 wikilink 引用段落（用于多值关联等不适合 frontmatter 单值的情况）
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


def generate_index_md(folder_path: str, folder_name: str):
    filepath = os.path.join(folder_path, "index.md")
    content = f"---\ntitle: \"{folder_name}\"\n---\n\n# {folder_name}\n\n该目录下包含大量测试文件，用于验证排序、聚合、反向链接与图谱功能。\n"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [index] {filepath}")


def generate_chart_files(target_dir: str, domain: str, count: int):
    """生成图表样例文件（`<domain>/图表/chart-NNN.md`），覆盖 CHART_SPECS 里的常见图表类型。

    每个文件的 frontmatter 与其它目录同构（分类维度齐全，能被聚合/排序/图谱测到），
    正文里是一个语言标记为 `echarts` 的围栏块，内容是 ECharts option 的 JSON 对象。
    """
    folder = "图表"
    folder_path = os.path.join(target_dir, folder)
    os.makedirs(folder_path, exist_ok=True)
    generate_index_md(folder_path, folder)

    for i in range(count):
        name, option = CHART_SPECS[i % len(CHART_SPECS)]
        file_num = i + 1
        title = f"{folder}-{file_num:03d}"
        filename = f"chart-{file_num:03d}.md"
        frontmatter = build_frontmatter_lines(title, folder, {})
        block = json.dumps(option, ensure_ascii=False, indent=2)
        body = (
            f"# {title}（{name}）\n\n"
            f"本文件用于验证 Quartz 对**图表代码块**的解析与渲染：\n\n"
            f"```echarts\n{block}\n```\n\n"
            f"代码块之外的内容与其它测试文件一致，便于一并参与聚合 / 排序 / 图谱验证"
            f"（参见 [[{folder}/]]）。\n"
        )
        with open(os.path.join(folder_path, filename), "w", encoding="utf-8") as f:
            f.write("\n".join(frontmatter))
            f.write("\n\n")
            f.write(body)
    print(f"  [done] {folder}: {count} 个图表样例（{len(CHART_SPECS)} 种类型轮流）")


def generate_root_index_md(target_dir: str, domain: str):
    """生成根目录的 index.md（Quartz 首页入口）"""
    filepath = os.path.join(target_dir, "index.md")
    
    # 计算统计
    total = sum(cfg["count"] for cfg in FOLDER_CONFIGS)
    
    # 文件数量分布表格
    folder_stats_lines = []
    for cfg in FOLDER_CONFIGS:
        folder_name = cfg["name"]
        count = cfg["count"]
        pct = (count / total * 100) if total > 0 else 0
        bar_len = int(pct / 5)  # 每5%一个字符
        bar = "█" * bar_len + "░" * (20 - bar_len)
        folder_stats_lines.append(f"| {folder_name} | {count:>6} | {pct:>5.1f}% | `{bar}` |")
    
    # 文件树（使用配置的 count 来生成）
    tree_lines = []
    for cfg in FOLDER_CONFIGS:
        folder_name = cfg["name"]
        prefix = cfg["prefix"]
        count = cfg["count"]
        tree_lines.append(f"{folder_name}/")
        tree_lines.append(f"├── index.md")
        # 根据数量决定显示方式
        if count > 7:
            for i in range(1, 4):
                tree_lines.append(f"├── {prefix}-{i:05d}.md")
            tree_lines.append(f"├── ... ({count - 6} more files) ...")
            for i in range(count - 2, count + 1):
                tree_lines.append(f"└── {prefix}-{i:05d}.md")
        else:
            for i in range(1, count + 1):
                prefix_char = "└── " if i == count else "├── "
                tree_lines.append(f"{prefix_char}{prefix}-{i:05d}.md")

    content = f"""---
title: "{domain}"
---

# {domain}

## 统计概览

| 指标 | 值 |
|------|-----|
| 总文件数 | {total} |
| 分类数量 | {len(FOLDER_CONFIGS)} |

## 文件分布

| 分类 | 文件数 | 占比 | 可视化 |
|------|--------|------|--------|
{chr(10).join(folder_stats_lines)}

## 文件树

```
.
{chr(10).join(tree_lines)}
```

## 功能说明

本文档用于测试 Quartz 构建系统的以下功能：

- **排序**：支持自然排序、字典序、日期排序、数值排序
- **聚合**：支持按文件夹、字段、日期等多种维度分组
- **反向链接**：自动收集引用当前文档的其他文档
- **图谱**：可视化文档间的关联关系

---
*此文件由自动生成，请勿手动修改*
"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [index] {filepath}")


def write_domain_config(project_root: str, domain: str, profile: str) -> str:
    """按 v5 规则生成 settings/{domain}/quartz.config.yaml（整棵继承建域模板）。"""
    preset = DOMAIN_PROFILES[profile]
    path = write_v5_domain_config(
        project_root, domain,
        aggregation=preset["aggregation"],
        properties=preset["properties"],
        graph_folders=preset["graph_folders"],
        graph_core_node_limit=preset["graph_core_node_limit"],
    )
    print(f"  [config] {path}")
    return path


def clean_old_domains(project_root: str, keep_domains: set):
    """清理 input、output、settings 下的旧业务域。

    ⚠️ 递归删除、不可恢复：只由 --clean-all 这一个显式开关把关；
    删除前先把目标全量打印出来，便于在日志里留痕或及时中断。
    """
    doomed = []
    for base in ["input", "output", "settings"]:
        base_dir = os.path.join(project_root, base)
        if not os.path.exists(base_dir):
            continue
        for name in os.listdir(base_dir):
            if name in keep_domains:
                continue
            path = os.path.join(base_dir, name)
            if os.path.isdir(path):
                doomed.append((base, path))
    if doomed:
        print(f"[clean] --clean-all 将删除 {len(doomed)} 个目录"
              f"（保留：{', '.join(sorted(keep_domains))}）：")
        for base, path in doomed:
            print(f"        [{base}] {path}")
    else:
        print("[clean] 没有需要清理的旧业务域")

    for base in ["input", "output", "settings"]:
        base_dir = os.path.join(project_root, base)
        if not os.path.exists(base_dir):
            continue
        for name in os.listdir(base_dir):
            if name not in keep_domains:
                path = os.path.join(base_dir, name)
                if os.path.isdir(path):
                    try:
                        shutil.rmtree(path)
                        print(f"[clean] 删除 {path}")
                    except PermissionError:
                        print(f"[skip] 权限不足，跳过删除 {path}")


def generate_domain(project_root: str, domain: str, clean: bool):
    target_dir = os.path.join(project_root, "input", domain)

    if clean and os.path.exists(target_dir):
        shutil.rmtree(target_dir)
        print(f"[clean] 删除 {target_dir}")

    os.makedirs(target_dir, exist_ok=True)
    print(f"[target] {target_dir}")

    # ========== 生成根目录 index.md（Quartz 首页） ==========
    generate_root_index_md(target_dir, domain)

    # ========== 第一阶段：生成所有文件，记录文件名 ==========
    all_files = {}  # folder_name -> [filename, ...]
    file_records = {}  # folder_name -> [{num, filename, title}, ...]

    for cfg in FOLDER_CONFIGS:
        folder_name = cfg["name"]
        folder_path = os.path.join(target_dir, folder_name)
        os.makedirs(folder_path, exist_ok=True)
        generate_index_md(folder_path, folder_name)

        prefix = cfg["prefix"]
        count = cfg["count"]
        files = []
        records = []

        for i in range(count):
            file_num = i + 1
            filename = f"{prefix}-{file_num:05d}.md"
            title = f"{folder_name}-{file_num:05d}"
            files.append(filename)
            records.append({"num": file_num, "filename": filename, "title": title})

        all_files[folder_name] = files
        file_records[folder_name] = records
        print(f"  [prepare] {folder_name}: {count} files")

    # ========== 第二阶段：按依赖顺序生成内容（组织 → 人员 → 项目 → 任务 → 问答） ==========

    # 1. 组织（无外部依赖）
    org_records = file_records["组织"]
    org_path = os.path.join(target_dir, "组织")
    for rec in org_records:
        frontmatter = build_frontmatter_lines(rec["title"], "组织", {})
        body = build_content(rec["title"], [])
        with open(os.path.join(org_path, rec["filename"]), "w", encoding="utf-8") as f:
            f.write("\n".join(frontmatter))
            f.write("\n\n")
            f.write(body)
    print(f"  [done] 组织: {len(org_records)} files")

    # 2. 人员（依赖：所属组织）
    person_records = file_records["人员"]
    person_path = os.path.join(target_dir, "人员")
    org_filenames = all_files["组织"]
    for rec, person_name in zip(person_records, generate_person_names(len(person_records))):
        org_file = maybe(random.choice(org_filenames), MISSING_RATE["organization"])
        extra = {}
        if org_file:
            org_name = org_file.replace(".md", "")
            extra["组织"] = org_name
        frontmatter = build_frontmatter_lines(rec["title"], "人员", extra)
        frontmatter.insert(2, f'姓名: "{person_name}"')
        body = build_content(rec["title"], [])
        with open(os.path.join(person_path, rec["filename"]), "w", encoding="utf-8") as f:
            f.write("\n".join(frontmatter))
            f.write("\n\n")
            f.write(body)
    print(f"  [done] 人员: {len(person_records)} files")

    # 3. 项目（依赖：负责人/参与人员）
    proj_records = file_records["项目"]
    proj_path = os.path.join(target_dir, "项目")
    person_filenames = all_files["人员"]
    for rec in proj_records:
        owner_file = maybe(random.choice(person_filenames), MISSING_RATE["owner"])
        extra = {}
        if owner_file:
            owner_name = owner_file.replace(".md", "")
            extra["负责人"] = owner_name
        # 再随机引用 1-2 个参与人员（放入正文）
        body_links = []
        participant_count = random.randint(0, 2)
        for _ in range(participant_count):
            p = random.choice(person_filenames).replace(".md", "")
            if p not in body_links:
                body_links.append(p)
        frontmatter = build_frontmatter_lines(rec["title"], "项目", extra)
        body = build_content(rec["title"], body_links)
        with open(os.path.join(proj_path, rec["filename"]), "w", encoding="utf-8") as f:
            f.write("\n".join(frontmatter))
            f.write("\n\n")
            f.write(body)
    print(f"  [done] 项目: {len(proj_records)} files")

    # 4. 任务（依赖：所属项目）
    task_records = file_records["任务"]
    task_path = os.path.join(target_dir, "任务")
    proj_filenames = all_files["项目"]
    for rec in task_records:
        proj_file = maybe(random.choice(proj_filenames), MISSING_RATE["project"])
        extra = {}
        if proj_file:
            proj_name = proj_file.replace(".md", "")
            extra["项目"] = proj_name
        # 再随机引用 0-1 个关联人员（放入正文）
        body_links = []
        if random.random() < 0.3:
            p = random.choice(person_filenames).replace(".md", "")
            body_links.append(p)
        frontmatter = build_frontmatter_lines(rec["title"], "任务", extra)
        body = build_content(rec["title"], body_links)
        with open(os.path.join(task_path, rec["filename"]), "w", encoding="utf-8") as f:
            f.write("\n".join(frontmatter))
            f.write("\n\n")
            f.write(body)
    print(f"  [done] 任务: {len(task_records)} files")

    # 5. 问答（依赖：关联项目/任务/人员）
    qa_records = file_records["问答"]
    qa_path = os.path.join(target_dir, "问答")
    task_filenames = all_files["任务"]
    for rec in qa_records:
        extra = {}
        body_links = []

        # 关联项目
        if random.random() < 0.5:
            proj_file = random.choice(proj_filenames)
            proj_name = proj_file.replace(".md", "")
            extra["项目"] = proj_name

        # 关联任务
        if random.random() < 0.6:
            task_file = random.choice(task_filenames)
            task_name = task_file.replace(".md", "")
            extra["任务"] = task_name

        # 关联人员（提问者/回答者）
        if random.random() < 0.4:
            p = random.choice(person_filenames).replace(".md", "")
            extra["相关人员"] = p

        # 额外随机引用（放入正文，确保有足够链接密度）
        extra_refs = random.randint(0, 2)
        all_candidates = proj_filenames + task_filenames + person_filenames
        for _ in range(extra_refs):
            ref = random.choice(all_candidates).replace(".md", "")
            if ref not in body_links:
                body_links.append(ref)

        frontmatter = build_frontmatter_lines(rec["title"], "问答", extra)
        body = build_content(rec["title"], body_links)
        with open(os.path.join(qa_path, rec["filename"]), "w", encoding="utf-8") as f:
            f.write("\n".join(frontmatter))
            f.write("\n\n")
            f.write(body)
    print(f"  [done] 问答: {len(qa_records)} files")

    total = sum(cfg["count"] for cfg in FOLDER_CONFIGS)
    index_count = len(FOLDER_CONFIGS) + 1  # 各子目录 + 根目录
    print(f"[summary] 共生成 {total} 个 Markdown 文件（含 {index_count} 个 index.md: {index_count-1} 个子目录 + 1 个根目录）")
    print(f"[summary] 目标目录: {target_dir}")


def main():
    parser = argparse.ArgumentParser(description="批量生成测试 Markdown 文件")
    parser.add_argument("--domain", type=str, required=True, help="业务域名称，如 demo-region")
    parser.add_argument("--profile", type=str, choices=["region", "core"], required=True,
                        help="配置模板：region（多文件夹大区 + 完整字段链）或 core（单一大区 + 硬上限）")
    parser.add_argument("--clean", action="store_true", help="清空目标目录后重新生成")
    parser.add_argument("--clean-all", action="store_true",
                        help="清理 input/output/settings 下所有其它域（递归删除，慎用）")
    parser.add_argument("--charts", type=int, default=0,
                        help="额外生成 N 个图表样例文件（覆盖常见图表类型，放 <domain>/图表/）")
    parser.add_argument("--charts-only", action="store_true",
                        help="只生成图表样例，不重新生成其它内容与域配置文件（需配合 --charts N）")
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    target_dir = os.path.join(project_root, "input", args.domain)

    # 只补图表样例：不动既有内容与 settings（避免整域随机重生成）
    if args.charts_only:
        if args.charts <= 0:
            parser.error("--charts-only 需要同时指定 --charts N（N > 0）")
        os.makedirs(target_dir, exist_ok=True)
        print(f"[target] {target_dir}")
        generate_chart_files(target_dir, args.domain, args.charts)
        print(f"[summary] 仅生成图表样例：{args.charts} 个 → {os.path.join(target_dir, '图表')}")
        return

    # 清理所有旧业务域
    if args.clean_all:
        clean_old_domains(project_root, keep_domains={args.domain})

    # 生成 v5 域配置（settings/{domain}/quartz.config.yaml）
    write_domain_config(project_root, args.domain, args.profile)

    # 生成 Markdown 文件
    generate_domain(project_root, args.domain, args.clean)

    # 额外生成图表样例
    if args.charts > 0:
        generate_chart_files(target_dir, args.domain, args.charts)

    print(f"[next] 域配置改动过必须全量重建，命令：{build_v5_command(args.domain)} --reset")


if __name__ == "__main__":
    main()
