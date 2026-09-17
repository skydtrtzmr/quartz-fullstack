#!/usr/bin/env python3
"""
垃圾焚烧发电厂（WTE）员工培训知识库 · 测试数据生成脚本

在 input/{domain}/ 下生成五类主体：设备 / 缺陷单 / 经验案例 / 培训课程 / 员工。
用于验证 Quartz 以下功能：

  - 页嵌入 ![[page]]          缺陷单 → 设备卡片；课程 → 案例教材
  - 小节嵌入 ![[page#小节]]   经验案例 → 缺陷单的"缺陷描述"
  - Callouts                  warning / note / tip / summary / info
  - GFM 表格                  员工/设备的指标区与近期记录表
  - frontmatter wikilink 关系字段（关联设备/处理人/讲师 等）
  - frontmatter 数值指标字段（已处理缺陷/参与案例/主讲课程 等）
  - aliases 别名与重定向（设备编号 M-2026-xxxxx）
  - H2/H3 标题层级（使 ToC 有内容）
  - 按"专业"大区聚合的图谱（regionRules: field 专业）

用法：
    python scripts/generate_train_md.py --domain wte-train --clean

生成后构建（在 client 目录）：
    node ./quartz/bootstrap-cli.mjs build -d ../input/wte-train -o ../output/wte-train \
        --settings ../settings/wte-train --sqlite
"""

import os
import random
import argparse
import shutil
import json
from datetime import datetime, timedelta
from collections import defaultdict

# ============ 域模型配置 ============

FOLDER_CONFIGS = [
    {"name": "设备", "prefix": "equip", "count": 120},
    {"name": "缺陷单", "prefix": "defect", "count": 500},
    {"name": "经验案例", "prefix": "case", "count": 200},
    {"name": "培训课程", "prefix": "course", "count": 80},
    {"name": "员工", "prefix": "staff", "count": 60},
]

# 大区维度：6 个专业（设备/缺陷单/案例/课程/员工 全部带此字段）
PROFESSIONS = ["锅炉", "汽机", "电气", "仪控", "环保", "机械"]

# 设备类别 → (所属系统, 专业)
EQUIP_TYPE_MAP = {
    "焚烧炉":     ("焚烧系统", "锅炉"),
    "余热锅炉":   ("热力系统", "锅炉"),
    "汽轮机":     ("热力系统", "汽机"),
    "发电机":     ("热力系统", "电气"),
    "烟气净化":   ("环保系统", "环保"),
    "渗滤液处理": ("环保系统", "环保"),
    "吊车":       ("焚烧系统", "机械"),
    "电气设备":   ("公用系统", "电气"),
    "仪控系统":   ("公用系统", "仪控"),
}
# 设备类别出现权重（合计 = 设备数）
EQUIP_TYPE_WEIGHTS = {
    "焚烧炉": 18, "余热锅炉": 14, "汽轮机": 12, "发电机": 12,
    "烟气净化": 16, "渗滤液处理": 12, "吊车": 10, "电气设备": 14, "仪控系统": 12,
}

# 各主体枚举值池
TYPE_POOLS = {
    "设备":   list(EQUIP_TYPE_MAP.keys()),
    "缺陷单": ["机械故障", "电气故障", "仪控故障", "泄漏", "磨损", "腐蚀", "堵塞", "振动异常"],
    "经验案例": ["消缺经验", "事故复盘", "操作要点", "维护保养", "异常处置"],
    "培训课程": ["新员工入职", "在岗提升", "转岗培训", "专项取证"],
    "员工":   ["运行值班员", "检修工", "技术员", "班组长", "专工", "培训师"],
}

STATUS_POOLS = {
    "设备":   ["运行中", "检修中", "备用", "技改中"],
    "缺陷单": [],  # 与处理人联动，单独生成
    "经验案例": ["教学中", "已归档", "评审中"],
    "培训课程": ["报名中", "进行中", "已结课"],
    "员工":   ["在职", "借调", "休假"],
}

SEVERITY_POOL = ["轻微", "一般", "严重", "紧急"]

DEPT_POOL = ["运行部", "检修部", "技术部", "安环部", "培训中心"]

TAGS_POOLS = {
    "设备":   ["关键设备", "高温部件", "旋转机械", "受压部件", "进口设备", "国产设备", "技改完成", "A修"],
    "缺陷单": ["重复缺陷", "夜间发生", "高温季节", "停机处理", "带病运行", "外委处理", "自主处理", "联锁触发"],
    "经验案例": ["经典案例", "教学用例", "新人必读", "考核要点", "应急演练", "班组共创"],
    "培训课程": ["必修课", "选修课", "取证课", "实操课", "理论课"],
    "员工":   ["高级技师", "内训师", "青年骨干", "多面手", "安全标兵", "值班骨干"],
}

# 字段缺失率（测试聚合"有则有效无则跳过"）
MISSING_RATE = {
    "type": 0.10,
    "priority": 0.20,
    "status": 0.15,
    "tags": 0.25,
    "severity": 0.10,
    "关联设备": 0.05,   # 缺陷单 → 设备（核心关系，极少缺失）
    "处理人": 0.15,    # 缺陷单 → 员工（未处理/挂起时缺失）
    "关联缺陷单": 0.40,  # 案例的缺陷来源
}

# 日期范围
DATE_START = datetime(2023, 1, 1)
DATE_END = datetime(2026, 9, 1)

# 员工姓名池
SURNAMES = ["王", "李", "张", "刘", "陈", "杨", "赵", "周", "吴", "徐", "孙", "马", "朱", "胡", "郭", "何", "林", "高", "罗", "郑"]
GIVEN_NAMES = [
    "伟", "芳", "娜", "敏", "静", "磊", "军", "洋", "勇", "杰", "涛", "明", "超",
    "秀英", "霞", "平", "刚", "建国", "桂兰", "志强", "文博", "海燕", "春生", "秋实", "国栋",
]

# ============ 正文素材池（WTE 语境） ============

EQUIP_INFO_POOL = [
    "该设备为垃圾焚烧发电线上的重要组成部件，长期处于高温高负荷工况下运行。",
    "设备台账、检修记录与备件清单均纳入本知识库统一管理。",
    "日常点检由当班运行人员执行，检修维护按专业分工归口管理。",
    "设备安装于主厂房内，周围配套消防、通风与监测设施完备。",
    "本页面同时作为设备知识卡，被相关缺陷单与培训材料引用。",
    "设备投运以来整体运行平稳，历次检修记录均已归档。",
]

EQUIP_PARAM_POOL = [
    "额定处理量、主蒸汽温度与压力等关键参数均在 DCS 系统中实时采集。",
    "关键测点包括轴承温度、振动幅值、润滑油压与电机电流等。",
    "设备铭牌参数与设计值一致，未发生超限运行情况。",
    "运行参数的历史趋势曲线可在值班室查询，用于辅助缺陷判断。",
    "联锁保护定值每季度校验一次，最近一次校验结果合格。",
]

EQUIP_RUN_POOL = [
    "启动前应确认润滑油系统、冷却水系统均投入正常。",
    "运行中每小时抄表一次，重点关注振动与温度的异常变化趋势。",
    "负荷调整应平稳进行，避免急剧变化造成热应力集中。",
    "异常工况下应优先执行运行规程中的应急处置条款，并同步上报值长。",
    "交接班时应对设备运行状态进行当面确认并履行签字手续。",
]

EQUIP_MAINT_POOL = [
    "按检修周期执行定期维护，A 修间隔以运行小时数为准。",
    "易损件应保持安全库存，更换后须在台账中登记寿命记录。",
    "检修作业严格执行工作票制度，作业前完成风险辨识与安全交底。",
    "检修完成后须进行试运行验收，合格后方可移交运行。",
    "年度检修计划与本设备相关的项目已全部列入检修大纲。",
]

DEFECT_DESC_POOL = [
    "运行人员在例行巡检中发现该设备运行参数异常，随即上报缺陷并录入系统。",
    "中控室 DCS 报警提示相关测点数值越限，值班人员到现场核实后确认缺陷成立。",
    "检修班组在定期维护过程中发现部件存在异常磨损，按流程上报缺陷。",
    "缺陷发现于夜班时段，值班人员先行执行运行规程中的应急措施，防止缺陷扩大。",
    "设备异响伴随振动升高，现场测量确认超过规程允许值。",
    "该缺陷与此前同类设备上发生的问题相似，具有典型性。",
]

DEFECT_WARN_POOL = [
    "处理该缺陷前须严格执行两票三制，确认相关系统已隔离并挂牌。",
    "进入炉膛或受限空间作业前，必须先通风检测并办理受限空间作业许可。",
    "涉及高温部件的作业应等待设备冷却至规程允许温度后方可进行。",
    "电气作业前必须验电、放电并挂接地线，作业全程设专人监护。",
    "吊装作业须检查吊具完好性，划定警戒区域并设专人指挥。",
]

DEFECT_PROCESS_POOL = [
    "检修人员到场后首先复核缺陷现象，结合历史缺陷记录判断故障原因。",
    "经与厂家技术支持沟通，确认故障原因为部件老化，决定整体更换处理。",
    "处理过程中同步检查了同类部件的运行状况，未发现类似隐患。",
    "更换备件后进行单机试运行，各项参数恢复正常范围。",
    "缺陷处理期间运行方式调整为备用设备带负荷，未影响生活垃圾日处理量。",
    "处理后连续跟踪 24 小时，运行参数稳定，确认缺陷消除。",
]

DEFECT_RESULT_POOL = [
    "缺陷消除后设备恢复正常运行，运行人员连续跟踪确认无异常。",
    "本次消缺共耗时 6 小时，未发生不安全事件，作业过程符合规程要求。",
    "缺陷已闭环，相关经验已整理为教学案例纳入培训体系。",
    "针对该缺陷提出的反措建议已列入设备治理计划。",
]

CASE_BG_POOL = [
    "本案例来自该缺陷的处置实践，经班组复盘整理形成教学材料。",
    "案例所述场景在日常运行中具有较高发生频率，适合作为培训素材。",
    "本案例已在多期培训班中作为研讨素材使用，反馈良好。",
    "案例内容经过脱敏处理，仅保留技术细节与处置逻辑。",
    "本案例同时关联相关设备与缺陷单，便于学员追溯完整过程。",
]

CASE_EXP_POOL = [
    "处置过程表明，准确的参数趋势判断比单点报警更可靠，应养成看曲线的习惯。",
    "备用设备切换前务必确认联锁条件满足，防止扩大停机范围。",
    "同类故障的快速定位依赖于对设备结构和工作原理的熟悉程度。",
    "与厂家技术支持的沟通应提前准备好运行数据截图，可显著缩短诊断时间。",
    "检修作业中的风险辨识环节不可省略，本案例中的隔离措施是安全完成作业的关键。",
    "缺陷闭环后的跟踪观察期建议不少于 24 小时，避免重复缺陷。",
]

CASE_TIP_POOL = [
    "判断同类故障时，应优先核对运行趋势曲线，而非单点报警值。",
    "处置前先确认备件库存，可避免中途停工等待。",
    "夜间处置必须保证照明与监护到位，宁可放慢节奏也不冒险作业。",
    "处置完成后及时更新设备台账，为后续分析积累数据。",
]

CASE_SUMMARY_POOL = [
    "本次处置总体及时有效，暴露的短板已列入班组培训计划。",
    "该案例验证了规程中的处置流程切实可行，建议纳入新员工必修内容。",
    "复盘认为信息传递环节存在延迟，已优化值班汇报路径。",
    "本案例的经验要点已同步更新至相关专业课程。",
]

COURSE_GOAL_POOL = [
    "本课程面向本专业在岗员工，目标是掌握典型缺陷的识别与处置流程。",
    "课程以真实案例为主线，强化安全意识与标准化作业习惯。",
    "完成本课程后，学员应能独立完成本专业设备的日常点检与常见缺陷判断。",
    "课程结合仿真操作与现场教学，注重理论与实操的衔接。",
    "课程内容覆盖设备结构、运行要点、典型缺陷与应急处置四个模块。",
]

COURSE_ASSESS_POOL = [
    "考核采取理论笔试与现场实操相结合的方式，两科均需 80 分以上。",
    "结业考核包含案例分析与模拟处置两个环节，不合格者安排补训。",
    "取证类课程按监管部门要求执行闭卷考试，成绩归档备查。",
    "考核重点为安全规程的掌握程度与应急处置的规范性。",
]

STAFF_PROFILE_POOL = [
    "该员工为本专业骨干，多次参与重大缺陷处置与技术改造项目。",
    "日常工作中注重经验沉淀，参与整理多篇教学案例。",
    "作为班组培训联系人，协助组织月度技术问答与安全学习。",
    "具备跨专业协同处置能力，多次在联合消缺中承担关键角色。",
    "积极带教新员工，是新员工入职培训的结对导师。",
]

LOREM_GENERIC = [
    "本页面为自动化生成的测试内容，结构与字段设计用于功能验证。",
    "批量生成的大量文档可用于验证构建性能与图谱渲染效果。",
    "排序功能支持自然排序、字典序、日期与数值等多种方式。",
    "聚合功能支持按文件夹、字段和日期等多种维度进行分组。",
    "反向链接自动收集引用当前文档的其他文档。",
    "图谱可视化展示文档间的关联关系与专业大区分区。",
]

# ============ 通用工具 ============


def random_date() -> str:
    delta = DATE_END - DATE_START
    d = DATE_START + timedelta(days=random.randint(0, delta.days))
    return d.strftime("%Y-%m-%d")


def maybe(value, missing_rate: float):
    if random.random() < missing_rate:
        return None
    return value


def pick_tags(folder_name: str):
    pool = TAGS_POOLS[folder_name]
    tags = random.sample(pool, random.randint(1, min(3, len(pool))))
    return tags


def sample_weighted(weighted: dict, k: int) -> list:
    """按权重有放回展开后取样"""
    items = []
    for v, w in weighted.items():
        items.extend([v] * w)
    random.shuffle(items)
    return items[:k]


def build_fm(pairs) -> str:
    """pairs: [(key, value)]，value 为 None 跳过；str/int/list"""
    lines = ["---"]
    for k, v in pairs:
        if v is None:
            continue
        if k == "date":
            # YAML 裸标量 → js-yaml 解析为 Date 对象，保证日期排序/聚合兼容
            lines.append(f"date: {v}")
        elif isinstance(v, list):
            lines.append(f"{k}: [" + ", ".join(f'"{x}"' for x in v) + "]")
        elif isinstance(v, int):
            lines.append(f"{k}: {v}")
        else:
            lines.append(f'{k}: "{v}"')
    lines.append("---")
    return "\n".join(lines)


def para(pool, k=None) -> str:
    k = k or random.randint(2, 3)
    return "\n\n".join(random.sample(pool, min(k, len(pool))))


def stem_of(rec) -> str:
    return rec["stem"]


def d_alias(rec) -> str:
    """缺陷单的短别名，如 D-00123"""
    return f"D-{rec['num']:05d}"


def generate_unique_names(count: int) -> list:
    names = set()
    while len(names) < count:
        names.add(random.choice(SURNAMES) + random.choice(GIVEN_NAMES))
    return list(names)


# ============ 阶段一：主体与关系分配 ============


def build_records():
    random.seed(20260916)  # 固定种子，结果可复现

    # ---- 设备 ----
    equip_types = sample_weighted(EQUIP_TYPE_WEIGHTS, FOLDER_CONFIGS[0]["count"])
    equips = []
    for i, cfg in enumerate(FOLDER_CONFIGS):
        if cfg["name"] != "设备":
            continue
        for n in range(1, cfg["count"] + 1):
            etype = equip_types[n - 1]
            system, prof = EQUIP_TYPE_MAP[etype]
            equips.append({
                "num": n, "stem": f"equip-{n:05d}", "title": f"设备-{n:05d}",
                "etype": etype, "system": system, "prof": prof,
                "alias_code": f"M-2026-{n:05d}",
                "alias_colloq": f"{random.randint(1, 3)}#{etype}",
                "date": random_date(),
            })

    # ---- 员工 ----
    staff_names = generate_unique_names(FOLDER_CONFIGS[4]["count"])
    staffs = []
    for n in range(1, FOLDER_CONFIGS[4]["count"] + 1):
        prof = PROFESSIONS[(n - 1) % len(PROFESSIONS)]  # 均匀分布到 6 个专业
        staffs.append({
            "num": n, "stem": f"staff-{n:05d}", "title": staff_names[n - 1],
            "job": random.choice(TYPE_POOLS["员工"]), "prof": prof,
            "dept": random.choice(DEPT_POOL), "date": random_date(),
        })
    staff_by_prof = defaultdict(list)
    for s in staffs:
        staff_by_prof[s["prof"]].append(s)

    # ---- 缺陷单 ----
    defects = []
    for n in range(1, FOLDER_CONFIGS[1]["count"] + 1):
        equip = maybe(random.choice(equips), MISSING_RATE["关联设备"])
        prof = equip["prof"] if equip else random.choice(PROFESSIONS)
        # 处理人按专业对口分配
        handler = None
        if random.random() > MISSING_RATE["处理人"]:
            candidates = staff_by_prof.get(prof) or staffs
            handler = random.choice(candidates)
        if handler:
            status = random.choices(["已消缺", "已验证", "处理中", "挂起"], weights=[55, 25, 15, 5])[0]
        else:
            status = random.choices(["待处理", "处理中"], weights=[70, 30])[0]
        defects.append({
            "num": n, "stem": f"defect-{n:05d}", "title": f"缺陷-{n:05d}",
            "dtype": random.choice(TYPE_POOLS["缺陷单"]),
            "severity": maybe(random.choice(SEVERITY_POOL), MISSING_RATE["severity"]),
            "status": status, "prof": prof,
            "equip": equip, "handler": handler, "date": random_date(),
        })

    # ---- 经验案例 ----
    cases = []
    for n in range(1, FOLDER_CONFIGS[2]["count"] + 1):
        defect = None
        if random.random() > MISSING_RATE["关联缺陷单"]:
            defect = random.choice([d for d in defects if d["equip"]])
        if defect:
            equip = defect["equip"] if random.random() > 0.2 else random.choice(equips)
            prof = defect["prof"]
        else:
            equip = random.choice(equips)
            prof = equip["prof"]
        # 参与员工：优先继承缺陷处理人
        participants = []
        if defect and defect["handler"] and random.random() < 0.5:
            participants.append(defect["handler"])
        elif random.random() < 0.3:
            candidates = staff_by_prof.get(prof) or staffs
            participants.append(random.choice(candidates))
        cases.append({
            "num": n, "stem": f"case-{n:05d}", "title": f"案例-{n:05d}",
            "ctype": random.choice(TYPE_POOLS["经验案例"]),
            "status": maybe(random.choice(STATUS_POOLS["经验案例"]), MISSING_RATE["status"]),
            "prof": prof, "defect": defect, "equip": equip,
            "participants": participants, "date": random_date(),
        })

    case_by_prof = defaultdict(list)
    for c in cases:
        case_by_prof[c["prof"]].append(c)

    # ---- 培训课程 ----
    courses = []
    for n in range(1, FOLDER_CONFIGS[3]["count"] + 1):
        prof = PROFESSIONS[(n - 1) % len(PROFESSIONS)]
        # 讲师按专业对口
        lecturer = random.choice(staff_by_prof.get(prof) or staffs)
        # 关联案例 2-5 个，优先同专业，不足则从全池补
        k = random.randint(2, 5)
        pool = case_by_prof.get(prof)[:]
        if len(pool) < k:
            extra = random.sample(cases, min(k - len(pool), len(cases)))
            pool.extend(e for e in extra if e not in pool)
        course_cases = random.sample(pool, min(k, len(pool)))
        courses.append({
            "num": n, "stem": f"course-{n:05d}", "title": f"课程-{n:05d}",
            "ctype": random.choice(TYPE_POOLS["培训课程"]),
            "status": maybe(random.choice(STATUS_POOLS["培训课程"]), MISSING_RATE["status"]),
            "prof": prof, "hours": random.choice([2, 4, 8, 12, 16, 24]),
            "lecturer": lecturer, "cases": course_cases, "date": random_date(),
        })

    return equips, staffs, defects, cases, courses


# ============ 阶段二：指标统计 ============


def build_stats(equips, staffs, defects, cases, courses):
    # 员工指标
    staff_defects = defaultdict(list)      # stem -> [defect]
    for d in defects:
        if d["handler"]:
            staff_defects[d["handler"]["stem"]].append(d)
    staff_cases = defaultdict(list)        # stem -> [case]
    for c in cases:
        for p in c["participants"]:
            staff_cases[p["stem"]].append(c)
    staff_courses = defaultdict(list)      # stem -> [course]
    for co in courses:
        staff_courses[co["lecturer"]["stem"]].append(co)

    # 设备指标
    equip_defects = defaultdict(list)     # stem -> [defect]
    for d in defects:
        if d["equip"]:
            equip_defects[d["equip"]["stem"]].append(d)
    equip_cases = defaultdict(list)       # stem -> [case]
    for c in cases:
        if c["equip"]:
            equip_cases[c["equip"]["stem"]].append(c)

    return {
        "staff_defects": staff_defects,
        "staff_cases": staff_cases,
        "staff_courses": staff_courses,
        "equip_defects": equip_defects,
        "equip_cases": equip_cases,
    }


def recent_defects(defects, k=5):
    return sorted(defects, key=lambda d: d["date"], reverse=True)[:k]


def staff_name_map(staffs):
    return {s["stem"]: s["title"] for s in staffs}


# ============ 阶段三：页面构建 ============


def equipment_md(rec, stats, staff_titles) -> str:
    ds = stats["equip_defects"].get(rec["stem"], [])
    cs = stats["equip_cases"].get(rec["stem"], [])
    open_cnt = len([d for d in ds if d["status"] in ("待处理", "处理中", "挂起")])

    fm = build_fm([
        ("title", rec["title"]),
        ("date", rec["date"]),
        ("type", maybe(rec["etype"], MISSING_RATE["type"])),
        ("status", maybe(random.choice(STATUS_POOLS["设备"]), MISSING_RATE["status"])),
        ("系统", rec["system"]),
        ("专业", rec["prof"]),
        ("aliases", [rec["alias_code"], rec["alias_colloq"]]),
        ("priority", maybe(random.randint(1, 100), MISSING_RATE["priority"])),
        ("tags", maybe(pick_tags("设备"), MISSING_RATE["tags"])),
        ("累计缺陷", len(ds)),
        ("关联案例", len(cs)),
    ])

    body = f"""# {rec['title']}

## 基本信息

> [!info] 设备信息
> - 设备类别：{rec['etype']}
> - 所属系统：{rec['system']}
> - 专业：{rec['prof']}
> - 设备编号：{rec['alias_code']}

{para(EQUIP_INFO_POOL)}

## 关键参数

{para(EQUIP_PARAM_POOL)}

## 运行要点

{para(EQUIP_RUN_POOL)}

## 维护要点

{para(EQUIP_MAINT_POOL)}

## 运行指标

累计缺陷 **{len(ds)}** 单 · 未消缺 **{open_cnt}** 单 · 关联案例 **{len(cs)}** 篇
"""
    if ds:
        body += "\n## 近期缺陷记录\n\n"
        body += "| 缺陷单 | 日期 | 严重度 | 处理人 |\n|--------|------|--------|--------|\n"
        for d in recent_defects(ds):
            h = f"[[{d['handler']['stem']}\\|{staff_titles[d['handler']['stem']]}]]" if d["handler"] else "—"
            body += f"| [[{d['stem']}\\|{d_alias(d)}]] | {d['date']} | {d['severity'] or '—'} | {h} |\n"
    return fm + "\n\n" + body


def defect_md(rec, stats) -> str:
    fm = build_fm([
        ("title", rec["title"]),
        ("date", rec["date"]),
        ("type", maybe(rec["dtype"], MISSING_RATE["type"])),
        ("status", rec["status"]),
        ("severity", rec["severity"]),
        ("专业", rec["prof"]),
        ("关联设备", f"[[{rec['equip']['stem']}]]" if rec["equip"] else None),
        ("处理人", f"[[{rec['handler']['stem']}]]" if rec["handler"] else None),
        ("priority", maybe(random.randint(1, 100), MISSING_RATE["priority"])),
        ("tags", maybe(pick_tags("缺陷单"), MISSING_RATE["tags"])),
    ])

    body = f"""# {rec['title']}

## 缺陷描述

{para(DEFECT_DESC_POOL)}

> [!warning] 安全注意事项
> {random.choice(DEFECT_WARN_POOL)}
"""
    if rec["equip"]:
        e = rec["equip"]
        body += f"""
## 缺陷设备

![[{e['stem']}]]

涉及设备：[[{e['stem']}|{e['title']}]]（{e['alias_code']}），所属系统：{e['system']}。
"""
    else:
        body += "\n涉及设备待确认，暂未建立关联。\n"

    body += f"""
## 处理过程

{para(DEFECT_PROCESS_POOL)}

## 处理结果

{para(DEFECT_RESULT_POOL, k=random.randint(1, 2))}

> [!note] 消缺确认
> 缺陷当前状态：{rec['status']}。
"""
    return fm + "\n\n" + body


def case_md(rec) -> str:
    fm = build_fm([
        ("title", rec["title"]),
        ("date", rec["date"]),
        ("type", maybe(rec["ctype"], MISSING_RATE["type"])),
        ("status", rec["status"]),
        ("专业", rec["prof"]),
        ("关联缺陷单", f"[[{rec['defect']['stem']}]]" if rec["defect"] else None),
        ("关联设备", f"[[{rec['equip']['stem']}]]" if rec["equip"] else None),
        ("参与员工", f"[[{rec['participants'][0]['stem']}]]" if rec["participants"] else None),
        ("priority", maybe(random.randint(1, 100), MISSING_RATE["priority"])),
        ("tags", maybe(pick_tags("经验案例"), MISSING_RATE["tags"])),
    ])

    body = f"""# {rec['title']}

## 背景说明

{para(CASE_BG_POOL)}
"""
    if rec["defect"]:
        d = rec["defect"]
        handler_line = ""
        if d["handler"]:
            handler_line = f"，处理人：[[{d['handler']['stem']}|{d['handler']['title']}]]"
        body += f"""
## 原始缺陷

![[{d['stem']}#缺陷描述]]

原始缺陷单：[[{d['stem']}|{d['title']}]]{handler_line}。
"""
    if rec["equip"]:
        e = rec["equip"]
        body += f"""
## 涉及设备

![[{e['stem']}]]

相关设备：[[{e['stem']}|{e['title']}]]（{e['alias_code']}）。
"""

    body += f"""
## 处置经验

{para(CASE_EXP_POOL)}

> [!tip] 经验要点
> {random.choice(CASE_TIP_POOL)}

## 复盘结论

{para(LOREM_GENERIC, k=1)}

> [!summary] 复盘结论
> {random.choice(CASE_SUMMARY_POOL)}
"""
    return fm + "\n\n" + body


def course_md(rec) -> str:
    cs = rec["cases"]
    equips_covered = list({c["equip"]["stem"] for c in cs if c["equip"]})
    fm = build_fm([
        ("title", rec["title"]),
        ("date", rec["date"]),
        ("type", maybe(rec["ctype"], MISSING_RATE["type"])),
        ("status", rec["status"]),
        ("专业", rec["prof"]),
        ("学时", rec["hours"]),
        ("讲师", f"[[{rec['lecturer']['stem']}]]"),
        ("priority", maybe(random.randint(1, 100), MISSING_RATE["priority"])),
        ("tags", maybe(pick_tags("培训课程"), MISSING_RATE["tags"])),
    ])

    lec = rec["lecturer"]
    body = f"""# {rec['title']}

> [!info] 课程信息
> - 培训类型：{rec['ctype']}
> - 适用专业：{rec['prof']}
> - 学时：{rec['hours']}
> - 讲师：[[{lec['stem']}|{lec['title']}]]
> - 关联案例：{len(cs)} 篇 · 覆盖设备：{len(equips_covered)} 台

## 课程目标

{para(COURSE_GOAL_POOL)}

## 课程安排

{para(LOREM_GENERIC, k=1)}

## 教学案例

![[{cs[0]['stem']}]]

"""
    more = [f"[[{c['stem']}|{c['title']}]]" for c in cs[1:]]
    if more:
        body += "更多教学案例：" + "、".join(more) + "。\n"

    body += f"""
## 考核要点

{para(COURSE_ASSESS_POOL)}
"""
    return fm + "\n\n" + body


def staff_md(rec, stats) -> str:
    ds = stats["staff_defects"].get(rec["stem"], [])
    cs = stats["staff_cases"].get(rec["stem"], [])
    co = stats["staff_courses"].get(rec["stem"], [])

    fm = build_fm([
        ("title", rec["title"]),
        ("date", rec["date"]),
        ("type", maybe(rec["job"], MISSING_RATE["type"])),
        ("status", maybe(random.choice(STATUS_POOLS["员工"]), MISSING_RATE["status"])),
        ("专业", rec["prof"]),
        ("部门", rec["dept"]),
        ("priority", maybe(random.randint(1, 100), MISSING_RATE["priority"])),
        ("tags", maybe(pick_tags("员工"), MISSING_RATE["tags"])),
        ("已处理缺陷", len(ds)),
        ("参与案例", len(cs)),
        ("主讲课程", len(co)),
    ])

    body = f"""# {rec['title']}

> [!info] 员工信息
> - 岗位：{rec['job']}
> - 专业：{rec['prof']}
> - 部门：{rec['dept']}

{para(STAFF_PROFILE_POOL, k=random.randint(1, 2))}

## 工作指标

| 指标 | 数值 |
|------|-----|
| 已处理缺陷 | {len(ds)} |
| 参与案例 | {len(cs)} |
| 主讲课程 | {len(co)} |
"""
    if ds:
        body += "\n## 近期处理缺陷\n\n"
        body += "| 缺陷单 | 日期 | 严重度 | 状态 |\n|--------|------|--------|------|\n"
        for d in recent_defects(ds):
            body += f"| [[{d['stem']}\\|{d_alias(d)}]] | {d['date']} | {d['severity'] or '—'} | {d['status']} |\n"
    else:
        body += "\n暂无缺陷处理记录。\n"

    if co:
        links = "、".join(f"[[{c['stem']}|{c['title']}]]" for c in co)
        body += f"\n## 主讲课程\n\n{links}\n"
    if cs:
        links = "、".join(f"[[{c['stem']}|{c['title']}]]" for c in cs[:5])
        body += f"\n## 参与编写的案例\n\n{links}\n"
    return fm + "\n\n" + body


# ============ index / 配置 ============

FOLDER_DESC = {
    "设备": "全厂设备台账与知识卡片，按专业归口，是缺陷单与培训材料的引用核心。",
    "缺陷单": "设备缺陷记录，关联设备（页嵌入设备卡片）与处理人。",
    "经验案例": "缺陷处置与运维经验的教学化整理，嵌入原始缺陷单小节。",
    "培训课程": "分专业的培训课程页，嵌入教学案例作为教材。",
    "员工": "员工档案页，含工作指标与近期处理缺陷表格。",
}


def generate_index_md(folder_path, folder_name):
    filepath = os.path.join(folder_path, "index.md")
    content = (
        f"---\ntitle: \"{folder_name}\"\n---\n\n# {folder_name}\n\n"
        f"{FOLDER_DESC[folder_name]}\n"
    )
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [index] {filepath}")


def generate_root_index_md(target_dir, domain):
    filepath = os.path.join(target_dir, "index.md")
    total = sum(cfg["count"] for cfg in FOLDER_CONFIGS)

    folder_stats_lines = []
    for cfg in FOLDER_CONFIGS:
        pct = cfg["count"] / total * 100
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        folder_stats_lines.append(
            f"| {cfg['name']} | {cfg['count']:>5} | {pct:>5.1f}% | `{bar}` |")

    folder_links = "\n".join(
        f"- [[{cfg['name']}]]（{cfg['count']} 个文件）" for cfg in FOLDER_CONFIGS)

    tree_lines = []
    for cfg in FOLDER_CONFIGS:
        tree_lines.append(f"{cfg['name']}/")
        tree_lines.append("├── index.md")
        for i in range(1, 3):
            tree_lines.append(f"├── {cfg['prefix']}-{i:05d}.md")
        tree_lines.append(f"└── ... 共 {cfg['count']} 个文件")

    content = f"""---
title: "{domain}"
---

# {domain} · 垃圾焚烧发电厂培训知识库

## 统计概览

| 指标 | 值 |
|------|-----|
| 总文件数 | {total} |
| 主体类型 | {len(FOLDER_CONFIGS)} |
| 专业大区 | {len(PROFESSIONS)}（{'/'.join(PROFESSIONS)}） |

## 文件分布

| 主体 | 文件数 | 占比 | 可视化 |
|------|--------|------|--------|
{chr(10).join(folder_stats_lines)}

## 分类目录

{folder_links}

## 本域验证的功能点

- **页嵌入** `![[x]]`：缺陷单嵌入设备卡片、课程嵌入教学案例
- **小节嵌入** `![[x#小节]]`：经验案例嵌入缺陷单的"缺陷描述"
- **Callouts**：warning / note / tip / summary / info
- **GFM 表格**：员工工作指标、设备近期缺陷记录
- **frontmatter 关系字段**：关联设备 / 处理人 / 讲师 / 关联缺陷单
- **数值指标字段**：已处理缺陷 / 参与案例 / 主讲课程 / 学时
- **aliases 别名**：设备编号（M-2026-xxxxx）与口语名
- **标题层级**：H2 小节结构，右侧目录有内容
- **专业大区图谱**：regionRules 按 `专业` 字段分区，设备为核心节点

## 文件树

```
.
{chr(10).join(tree_lines)}
```

---
*此文件由脚本自动生成，请勿手动修改*
"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [index] {filepath}")


# layout 配置（profile: wte —— 大区模式变体，按"专业"分区）
LAYOUT_TEMPLATES = {
    "wte": {
        "explorer": {"sort": {"type": "natural", "order": "asc", "field": ""}},
        "folderPage": {"sort": {"type": "date", "order": "desc", "field": "date"}},
        "backlinks": {
            "hideWhenEmpty": False,
            "aggregation": [
                {"type": "folder", "depth": 1},
                {"type": "field", "field": "type"},
            ],
        },
        "graph": {
            "coreNodeFilter": [{"type": "folder", "depth": 1, "values": ["设备"]}],
            "coreNodeLimit": 60,
            "regionRules": [{"type": "field", "field": "专业"}],
            "aggregation": [
                {"type": "folder", "depth": 1},
                {"type": "field", "field": "severity"},
            ],
        },
    }
}

DEFAULT_CONFIG = {
    "pageTitle": "",
    "baseUrl": "",
    "graph": {
        "precomputeLocal": True,
        "localDepth": 1,
        "fallbackToBfs": True,
    },
}


def write_domain_config(project_root, domain):
    settings_dir = os.path.join(project_root, "settings", domain)
    os.makedirs(settings_dir, exist_ok=True)

    layout = LAYOUT_TEMPLATES["wte"]
    with open(os.path.join(settings_dir, "quartz.layout.json"), "w", encoding="utf-8") as f:
        json.dump(layout, f, ensure_ascii=False, indent=2)
    print(f"  [config] {settings_dir}\\quartz.layout.json")

    config = dict(DEFAULT_CONFIG)
    config["pageTitle"] = domain
    config["baseUrl"] = f"http://127.0.0.1:8766/{domain}"
    with open(os.path.join(settings_dir, "quartz.config.json"), "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    print(f"  [config] {settings_dir}\\quartz.config.json")


# ============ 主流程 ============


def main():
    parser = argparse.ArgumentParser(description="生成 WTE 培训知识库测试数据")
    parser.add_argument("--domain", type=str, required=True, help="业务域名称，如 wte-train")
    parser.add_argument("--clean", action="store_true", help="清空目标目录后重新生成")
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    target_dir = os.path.join(project_root, "input", args.domain)

    if args.clean and os.path.exists(target_dir):
        shutil.rmtree(target_dir)
        print(f"[clean] 删除 {target_dir}")
    os.makedirs(target_dir, exist_ok=True)
    print(f"[target] {target_dir}")

    # 配置
    write_domain_config(project_root, args.domain)

    # 根 index
    generate_root_index_md(target_dir, args.domain)

    # 目录骨架
    for cfg in FOLDER_CONFIGS:
        p = os.path.join(target_dir, cfg["name"])
        os.makedirs(p, exist_ok=True)
        generate_index_md(p, cfg["name"])

    # 阶段一：主体与关系
    equips, staffs, defects, cases, courses = build_records()
    print(f"[phase1] 设备{len(equips)} 员工{len(staffs)} 缺陷单{len(defects)} 案例{len(cases)} 课程{len(courses)}")

    # 阶段二：指标
    stats = build_stats(equips, staffs, defects, cases, courses)
    staff_titles = staff_name_map(staffs)
    print("[phase2] 指标统计完成")

    def write(folder, rec, content):
        path = os.path.join(target_dir, folder, rec["stem"] + ".md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    # 阶段三：按依赖序写页面
    for rec in equips:
        write("设备", rec, equipment_md(rec, stats, staff_titles))
    print(f"  [done] 设备: {len(equips)}")

    for rec in staffs:
        write("员工", rec, staff_md(rec, stats))
    print(f"  [done] 员工: {len(staffs)}")

    for rec in defects:
        write("缺陷单", rec, defect_md(rec, stats))
    print(f"  [done] 缺陷单: {len(defects)}")

    for rec in cases:
        write("经验案例", rec, case_md(rec))
    print(f"  [done] 经验案例: {len(cases)}")

    for rec in courses:
        write("培训课程", rec, course_md(rec))
    print(f"  [done] 培训课程: {len(courses)}")

    total = sum(cfg["count"] for cfg in FOLDER_CONFIGS)
    print(f"[summary] 共生成 {total} 个 Markdown 文件（+{len(FOLDER_CONFIGS) + 1} 个 index.md）")
    print(f"[summary] 目录: {target_dir}")
    print("[next] cd client && node ./quartz/bootstrap-cli.mjs build "
          f"-d ../input/{args.domain} -o ../output/{args.domain} "
          f"--settings ../settings/{args.domain} --sqlite")


if __name__ == "__main__":
    main()
