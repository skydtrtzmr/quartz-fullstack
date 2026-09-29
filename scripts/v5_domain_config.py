#!/usr/bin/env python3
"""v5 业务域配置写入工具：settings/{domain}/quartz.config.yaml。

v5 每个业务域**只有一份** YAML（`server/v5config.go` 的 `V5ConfigFileName`），分三段：
`configuration:` / `plugins:` / `layout:`。域配置 = 整棵继承 `server/config.json` 的
`template_file`，只改写少数几个字段（与 Go 端 `WriteDomainFromTemplate` 同一思路）。

为什么不用 PyYAML 往返：
    Go 端用 `yaml.Node` 做**节点级**读写，注释、YAML 锚点（`&graph-pro-options` /
    `*graph-pro-options`）、键序、plugins 清单全部原样保留；PyYAML 往返会把注释与锚点
    全部吃掉。所以这里改成「按行定位 + 局部替换」，只动下面几个键，其余逐字节继承模板：

    · configuration.pageTitle                              显示名
    · configuration.baseUrl                                {host}/{domain}（必须与产物目录名一致）
    · configuration.aggregation                            整块替换
    · plugins[note-properties-pro].options.properties      整块替换（属性显示链）
    · plugins[graph-pro].options.globalGraph.folders       单行替换（首屏大区 / 核心节点白名单）
    · plugins[graph-pro].options.globalGraph.coreNodeLimit 单行替换（核心节点硬上限）

v4 → v5 字段对应（v4 的 quartz.config.json / quartz.layout.json 已废弃）：
    graph.regionRules       → 首屏大区「恒为文件夹」，由 globalGraph.folders 指定
    graph.coreNodeFilter    → 同上（folders 命中者即核心节点），该键已删除
    graph.aggregation       → configuration.aggregation
    backlinks.aggregation   → configuration.aggregation（全站一份，不再按组件各配一份）
    graph.precomputeLocal / localDepth → graph-pro 插件 options.graph（模板里已是 true / 1）

模板形状变化时会**直接报错**（V5ConfigError），不静默写出坏配置。
"""

from __future__ import annotations

import json
import os

# v5 域配置文件名（与 server/v5config.go 保持一致）
V5_CONFIG_FILE = "quartz.config.yaml"

_CONFIG_JSON = ("server", "config.json")
_TEMPLATE_FALLBACK = ("quartz5", "quartz.config.yaml")


class V5ConfigError(RuntimeError):
    """模板结构与 v5 配置约定不符。"""


# ============ 模板定位 ============


def resolve_template_path(project_root: str) -> str:
    """建域模板：优先 server/config.json 的 template_file，回退 quartz5/quartz.config.yaml。"""
    cfg_path = os.path.join(project_root, *_CONFIG_JSON)
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, encoding="utf-8") as f:
                template_file = json.load(f).get("template_file")
        except (OSError, ValueError):
            template_file = None
        if template_file:
            # config.json 里通常写绝对路径（跟机器绑定），相对路径也一并兼容
            candidate = template_file if os.path.isabs(template_file) else os.path.join(
                project_root, template_file)
            if os.path.exists(candidate):
                return candidate

    fallback = os.path.join(project_root, *_TEMPLATE_FALLBACK)
    if not os.path.exists(fallback):
        raise V5ConfigError(
            f"找不到 v5 建域模板：server/config.json 的 template_file 无效，且 {fallback} 不存在")
    return fallback


def resolve_host(project_root: str) -> str:
    """baseUrl 的 host 部分：server/config.json 的 base_url（去掉协议前缀与尾斜杠）。

    域规则（见 QUARTZ5-COMMANDS.md §七）：baseUrl = `{host}/{domain}`，不带协议和端口，
    且路径段必须与产物目录名（= 域名）一致，否则 body[data-basepath] 错位。
    """
    host = None
    cfg_path = os.path.join(project_root, *_CONFIG_JSON)
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, encoding="utf-8") as f:
                host = json.load(f).get("base_url")
        except (OSError, ValueError):
            host = None
    host = (host or "localhost").strip().rstrip("/")
    for scheme in ("https://", "http://"):
        if host.startswith(scheme):
            host = host[len(scheme):]
    return host


# ============ 行级定位工具 ============


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _key_of(line: str) -> str | None:
    """返回该行的键名（`key:` 形式）；空行 / 注释行 / 列表项 / 非键行返回 None。"""
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or stripped.startswith("-"):
        return None
    if ":" not in stripped:
        return None
    return stripped.split(":", 1)[0].strip() or None


def _find_key(lines: list[str], key: str, indent: int,
              start: int = 0, end: int | None = None) -> int | None:
    """在 [start, end) 里找缩进恰好为 indent 且键为 key 的行号。"""
    end = len(lines) if end is None else end
    for i in range(start, end):
        if _indent(lines[i]) == indent and _key_of(lines[i]) == key:
            return i
    return None


def _block_end(lines: list[str], start: int, indent: int) -> int:
    """块首行 start（缩进 indent）的区间右界：第一条「缩进 <= indent 的真实行」。

    注意：**不能**把 `- ` 列表项当作块结束符 —— `ignorePatterns:` 这类 key 的子项
    缩进更深（`    - private`），把它们误判成结束会让 configuration 段提前收尾。
    """
    i = start + 1
    while i < len(lines):
        line = lines[i]
        if line.strip() and not line.lstrip().startswith("#"):
            if _indent(line) <= indent:
                break
        i += 1
    return i


def _section_range(lines: list[str], name: str) -> tuple[int, int]:
    """顶层段（configuration / plugins / layout）的行区间。"""
    for i, line in enumerate(lines):
        if _indent(line) == 0 and _key_of(line) == name:
            return i, _block_end(lines, i, 0)
    raise V5ConfigError(f"模板缺少顶层段 `{name}:`")


def _plugin_items(lines: list[str]) -> list[tuple[int, int]]:
    """plugins: 段里每个条目的行区间；条目首行是 `  - `。"""
    starts = [i for i, line in enumerate(lines) if line.startswith("  - ")]
    return [(s, starts[k + 1] if k + 1 < len(starts) else len(lines))
            for k, s in enumerate(starts)]


def _key_value(line: str) -> tuple[str, str] | None:
    """把 `  - source: x` / `    name: x` 解析成 (key, value)；注释行/非键行返回 None。"""
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or ":" not in stripped:
        return None
    if stripped.startswith("- "):
        stripped = stripped[2:].strip()
    key, _, value = stripped.partition(":")
    return key.strip(), value.strip()


def _find_plugin_item(lines: list[str], name: str) -> tuple[int, int]:
    """按插件名定位 plugins 条目：只看 `source:` / `name:` 的值。

    不能直接全文匹配 —— 条目区间是按 `  - ` 行切分的，两个条目之间的**注释块**会落在
    前一个条目的区间里（模板里大量「本地 graph-pro（fork ...）」这类说明），全文匹配会命中错。
    """
    for start, end in _plugin_items(lines):
        for i in range(start, end):
            kv = _key_value(lines[i])
            if kv and kv[0] in ("source", "name") and name in kv[1]:
                return start, end
    raise V5ConfigError(f"模板 plugins: 里找不到插件 `{name}`（按 source / name 匹配）")


def _split_comment(line: str) -> str:
    """取出行尾注释（含前导空格），用于改写标量时保留注释。"""
    idx = line.find(" #")
    return line[idx:] if idx != -1 else ""


# ============ YAML 值渲染 ============


def _scalar(value) -> str:
    """YAML 标量：安全时用 plain 风格，否则回退到双引号（JSON 字符串即合法 YAML）。"""
    text = str(value)
    if not text or text != text.strip() or any(ch in text for ch in ':#,[]{}"\'&*!?|>%@`'):
        return json.dumps(text, ensure_ascii=False)
    return text


def _flow(fields) -> str:
    return "[" + ", ".join(_scalar(f) for f in fields) + "]"


def _render_chain_block(key: str, indent: int, folder_depth: int, default_fields,
                        folder_fields: dict, min_group_size: int | None = None) -> list[str]:
    """渲染「目录 + 字段链」块（configuration.aggregation 与 properties 同构）。

    目录级只有两态：配了字段 / 未配置；`目录: []` 等价于未配置（构建期告警），
    所以空链直接不写，由下游逐层向父目录回退到 default。
    """
    pad = " " * indent
    inner = " " * (indent + 2)
    inner2 = " " * (indent + 4)
    inner3 = " " * (indent + 6)

    block = [f"{pad}{key}:"]
    if min_group_size is not None:
        block.append(f"{inner}minGroupSize: {min_group_size}")
    block.append(f"{inner}folderDepth: {folder_depth}")
    block.append(f"{inner}branches:")
    block.append(f"{inner2}default: {_flow(default_fields)}")
    entries = [(name, fields) for name, fields in (folder_fields or {}).items() if fields]
    if entries:
        block.append(f"{inner2}folders:")
        for name, fields in entries:
            block.append(f"{inner3}{_scalar(name)}: {_flow(fields)}")
    else:
        block.append(f"{inner2}folders: {{}}")
    return block


# ============ 各字段的替换实现 ============


def _set_scalar(lines: list[str], section: str, key: str, indent: int, value: str):
    start, end = _section_range(lines, section)
    i = _find_key(lines, key, indent, start, end)
    if i is None:
        raise V5ConfigError(f"模板 `{section}:` 段里找不到 `{key}:`（缩进 {indent}）")
    lines[i] = " " * indent + f"{key}: {value}" + _split_comment(lines[i])


def _replace_aggregation(lines: list[str], aggregation: dict):
    start, end = _section_range(lines, "configuration")
    block = _render_chain_block(
        "aggregation", 2,
        aggregation["folder_depth"],
        aggregation["default"],
        aggregation.get("folders", {}),
        aggregation.get("min_group_size", 2),
    )
    i = _find_key(lines, "aggregation", 2, start, end)
    if i is None:
        # 模板没配聚合：插到 configuration: 段首（Go 端 ensureAggregation 同思路）
        lines[start + 1:start + 1] = block
    else:
        lines[i:_block_end(lines, i, 2)] = block


def _replace_properties(lines: list[str], properties: dict):
    start, end = _find_plugin_item(lines, "note-properties-pro")
    i_include_all = _find_key(lines, "includeAll", 6, start, end)
    if i_include_all is not None and "false" not in lines[i_include_all]:
        # v5 约定：includeAll: true 与 properties 链互斥（构建期直接抛错）
        raise V5ConfigError(
            "模板 note-properties-pro 配了 includeAll: true，与 properties 链互斥；"
            "请先把模板改成 includeAll: false")

    block = _render_chain_block(
        "properties", 6,
        properties["folder_depth"],
        properties["default"],
        properties.get("folders", {}),
    )
    i = _find_key(lines, "properties", 6, start, end)
    if i is not None:
        lines[i:_block_end(lines, i, 6)] = block
        return
    i_options = _find_key(lines, "options", 4, start, end)
    if i_options is None:
        raise V5ConfigError("模板 note-properties-pro 条目缺少 `options:` 段")
    lines[i_options + 1:i_options + 1] = block


def _patch_global_graph(lines: list[str], folders=None, core_node_limit=None):
    start, end = _find_plugin_item(lines, "graph-pro")
    i_graph = _find_key(lines, "globalGraph", 6, start, end)
    if i_graph is None:
        raise V5ConfigError("模板 graph-pro 条目里找不到 `globalGraph:` 段")
    graph_end = _block_end(lines, i_graph, 6)

    if folders is not None:
        i = _find_key(lines, "folders", 8, i_graph, graph_end)
        line = " " * 8 + f"folders: {_flow(folders)}"
        if i is None:
            lines[i_graph + 1:i_graph + 1] = [line]
        else:
            lines[i] = line
        graph_end = _block_end(lines, i_graph, 6)

    if core_node_limit is not None:
        i = _find_key(lines, "coreNodeLimit", 8, i_graph, graph_end)
        line = " " * 8 + f"coreNodeLimit: {int(core_node_limit)}"
        if i is None:
            lines[i_graph + 1:i_graph + 1] = [line]
        else:
            lines[i] = line


# ============ 对外 API ============


def patch_config_yaml(text: str, *, page_title: str | None = None, base_url: str | None = None,
                      aggregation: dict | None = None, properties: dict | None = None,
                      graph_folders=None, graph_core_node_limit=None) -> str:
    """按 v5 规则改写一份域配置文本；只有传了的字段会被动，其余（含注释/锚点）原样保留。"""
    if text.startswith("\ufeff"):
        text = text[1:]
    lines = text.split("\n")

    # 顺序敏感：每次改写都会移动行号，所以各实现都按「键名」重新定位
    if aggregation is not None:
        _replace_aggregation(lines, aggregation)
    if properties is not None:
        _replace_properties(lines, properties)
    if graph_folders is not None or graph_core_node_limit is not None:
        _patch_global_graph(lines, graph_folders, graph_core_node_limit)
    if page_title is not None:
        _set_scalar(lines, "configuration", "pageTitle", 2, _scalar(page_title))
    if base_url is not None:
        _set_scalar(lines, "configuration", "baseUrl", 2, _scalar(base_url))

    result = "\n".join(lines)
    _assert_well_formed(result)
    return result


def _assert_well_formed(text: str):
    """纯 stdlib 的结构自检：三段齐全、无 tab 缩进（YAML 不允许）、可选 PyYAML 真实解析。"""
    lines = text.split("\n")
    for name in ("configuration", "plugins", "layout"):
        _section_range(lines, name)
    for i, line in enumerate(lines, start=1):
        if "\t" in line:
            raise V5ConfigError(f"第 {i} 行含 tab 缩进，YAML 不允许")

    try:
        import yaml  # 可选依赖：装了 PyYAML 就再做一次真实解析
    except ImportError:
        return
    data = yaml.safe_load(text)
    config = (data or {}).get("configuration") or {}
    if "pageTitle" not in config or "baseUrl" not in config:
        raise V5ConfigError("改写后的配置缺少 configuration.pageTitle / baseUrl")


def write_domain_config(project_root: str, domain: str, *, aggregation: dict,
                        properties: dict | None = None, graph_folders=None,
                        graph_core_node_limit=None, page_title: str | None = None,
                        host: str | None = None) -> str:
    """从建域模板派生 settings/{domain}/quartz.config.yaml，返回写入的路径。

    page_title 缺省用域名；base_url 恒为 `{server base_url}/{domain}`（服务端建域时
    也是这套规则，手工写必须与之一致，否则下次经 API 写入会被覆盖）。
    """
    template_path = resolve_template_path(project_root)
    with open(template_path, encoding="utf-8") as f:
        template_text = f.read()

    new_text = patch_config_yaml(
        template_text,
        page_title=page_title or domain,
        base_url=f"{host or resolve_host(project_root)}/{domain}",
        aggregation=aggregation,
        properties=properties,
        graph_folders=graph_folders,
        graph_core_node_limit=graph_core_node_limit,
    )

    settings_dir = os.path.join(project_root, "settings", domain)
    os.makedirs(settings_dir, exist_ok=True)
    dest = os.path.join(settings_dir, V5_CONFIG_FILE)
    with open(dest, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_text)
    return dest


def build_command(domain: str) -> str:
    """v5 的等价手工构建命令（quartz5 目录下执行）。"""
    return (
        f"cd quartz5; npm run quartz -- build -d ../input/{domain} "
        f"-o ../output/{domain} --settings ../settings/{domain} "
        f"--sqlite --cacheDir ../cache/{domain}"
    )
