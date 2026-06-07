#!/usr/bin/env python3
"""投资实体识别脚本"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path


ALLOWED_TEXT_FIELDS = {'text', 'content', 'title', 'summary', 'description'}


def load_stock_codes(ref_path):
    """加载股票代码映射表"""
    with open(ref_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def normalize_generated_at() -> str:
    """返回 ISO 8601 格式时间戳，含时区、不含微秒。"""
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def extract_text_sources(data, allowed_fields=None):
    """从 data 中提取文本内容和来源标识。

    Args:
        data: JSON 解析后的 Python 对象。
        allowed_fields: 允许提取的字段名集合。

    Returns:
        list[(source_id, combined_text)] — 每个数据源一条记录，同源文本合并。
    """
    if allowed_fields is None:
        allowed_fields = ALLOWED_TEXT_FIELDS
    source_texts = {}

    def recurse(obj, current_source=""):
        if isinstance(obj, str):
            return
        elif isinstance(obj, dict):
            source = obj.get('source', current_source)
            # 检查是否包含 posts （多源输入）
            if 'posts' in obj:
                for post in obj['posts']:
                    recurse(post, post.get('source', source))
                return
            for key, val in obj.items():
                if isinstance(val, str) and key in allowed_fields:
                    source_texts.setdefault(source, "")
                    source_texts[source] += val + " "
                elif isinstance(val, (dict, list)):
                    recurse(val, source)
        elif isinstance(obj, list):
            for item in obj:
                recurse(item, current_source)

    recurse(data)
    return [(s, t.strip()) for s, t in source_texts.items()]


def extract_entities(text, ref_data, source=""):
    """从文本中提取实体，支持 per-source tracking。

    Args:
        text: 待分析的文本字符串。
        ref_data: 参考数据字典（含 stocks / industries / concepts）。
        source: 来源标识字符串。

    Returns:
        list[dict] — 每个实体包含 symbol/name/type/market/confidence/mentions/sources。
    """
    # 先统计提及次数（不分大小写）
    mentions = {}
    stock_match_info = {}
    industry_match_info = {}
    concept_match_info = {}

    # ---- 统计股票提及 ----
    for code, info in ref_data['stocks'].items():
        name = info['name']
        aliases = info.get('aliases', [])
        all_names = [name, code] + aliases
        text_lower = text.lower()
        total = 0
        for alias in all_names:
            alias_lower = alias.lower()
            count = text_lower.count(alias_lower)
            total += count
        if total > 0:
            mentions[code] = total
            stock_match_info[code] = info

    # ---- 统计行业提及 ----
    for name, info in ref_data['industries'].items():
        aliases = info.get('aliases', [])
        all_names = [name] + aliases
        total = 0
        for alias in all_names:
            count = text.count(alias)
            total += count
        if total > 0:
            mentions[name] = total
            industry_match_info[name] = info

    # ---- 统计概念提及 ----
    for name, info in ref_data['concepts'].items():
        aliases = info.get('aliases', [])
        all_names = [name] + aliases
        total = 0
        for alias in all_names:
            count = text.count(alias)
            total += count
        if total > 0:
            mentions[name] = total
            concept_match_info[name] = info

    # ---- 构建实体列表 ----
    entities = []

    for code, info in stock_match_info.items():
        cnt = mentions[code]
        confidence = _count_to_confidence(cnt)
        entities.append({
            'name': info['name'],
            'symbol': code,
            'type': 'stock',
            'market': info.get('market', 'a'),
            'confidence': confidence,
            'mentions': cnt,
            'sources': [source] if source else [],
        })

    for name, info in industry_match_info.items():
        cnt = mentions[name]
        confidence = _count_to_confidence(cnt)
        entities.append({
            'name': name,
            'symbol': info['code'],
            'type': 'sector',
            'market': 'a',
            'confidence': confidence,
            'mentions': cnt,
            'sources': [source] if source else [],
        })

    for name, info in concept_match_info.items():
        cnt = mentions[name]
        confidence = _count_to_confidence(cnt)
        entities.append({
            'name': name,
            'symbol': info['code'],
            'type': 'concept',
            'market': 'a',
            'confidence': confidence,
            'mentions': cnt,
            'sources': [source] if source else [],
        })

    return entities


def _count_to_confidence(count: int) -> str:
    """将提及次数映射为置信度枚举值。"""
    if count >= 3:
        return "high"
    elif count == 2:
        return "medium"
    else:
        return "low"


def merge_entities(entity_lists):
    """合并多个来源的实体列表，对相同实体去重并合并 sources。

    Args:
        entity_lists: 多个实体列表的拼接（允许重复）。

    Returns:
        去重后的实体列表，相同 symbol+type 的实体合并 mentions 与 sources。
    """
    merged = {}
    for ent in entity_lists:
        key = (ent['symbol'], ent['type'])
        if key not in merged:
            merged[key] = ent
        else:
            existing = merged[key]
            existing['mentions'] += ent['mentions']
            # 合并 sources
            add_sources = [s for s in ent.get('sources', [])
                           if s and s not in existing.get('sources', [])]
            existing['sources'].extend(add_sources)
            # 更新 confidence（取最高）
            rank = {"high": 3, "medium": 2, "low": 1}
            if rank.get(ent['confidence'], 0) > rank.get(existing['confidence'], 0):
                existing['confidence'] = ent['confidence']
    return list(merged.values())


def build_result(entities, errors, source_commands):
    """构建标准输出结构。

    Args:
        entities: 实体列表。
        errors: 错误信息列表。
        source_commands: 触发命令列表。

    Returns:
        符合 schema 的完整输出字典。
    """
    succeeded = len(entities)
    failed = len(errors)

    if failed > 0 and succeeded == 0:
        status = "failed"
    elif succeeded > 0 and failed == 0:
        status = "complete"
    else:
        status = "partial"

    return {
        "schema_version": "1.0",
        "generated_at": normalize_generated_at(),
        "status": status,
        "source": {
            "skill": "extract-investment-entities",
            "commands": source_commands,
        },
        "coverage": {
            "requested": succeeded + failed,
            "succeeded": succeeded,
            "failed": failed,
        },
        "errors": errors,
        "data": {
            "entities": entities,
        },
    }


def process_json_input(json_str, ref_data):
    """处理 JSON 字符串输入，捕获解析异常返回结构化失败。"""
    try:
        data = json.loads(json_str)
    except (json.JSONDecodeError, ValueError) as e:
        return build_result([], [f"Invalid JSON input: {e}"], [])

    sources = extract_text_sources(data)
    all_entities = []
    for src, text in sources:
        entities = extract_entities(text, ref_data, src)
        all_entities.extend(entities)
    merged = merge_entities(all_entities)
    return build_result(merged, [], [])


def main():
    if len(sys.argv) < 3:
        print("Usage: extract_entities.py <input> <output_file>")
        print("  input: 文本内容或JSON文件路径")
        print("  output_file: 输出文件路径")
        sys.exit(1)

    input_arg = sys.argv[1]
    output_file = sys.argv[2]

    # 加载参考数据
    script_dir = Path(__file__).parent
    ref_path = script_dir.parent / 'references' / 'stock-codes.json'
    ref_data = load_stock_codes(ref_path)

    # 判断输入类型
    entities = []
    source_commands = [os.path.basename(input_arg)]
    if input_arg.endswith('.json'):
        try:
            with open(input_arg, 'r', encoding='utf-8') as f:
                raw = f.read()
        except (OSError, IOError) as e:
            output = build_result([], [f"Cannot read input file: {e}"], source_commands)
            _write_output(output, output_file)
            return

        output = process_json_input(raw, ref_data)
        _write_output(output, output_file)
        return
    else:
        # 纯文本输入
        entities = extract_entities(input_arg, ref_data)
        output = build_result(entities, [] if entities else ["No entities found"], source_commands)

    _write_output(output, output_file)
    print(f"Extracted {len(entities)} entities to {output_file}")


def _write_output(output, output_file):
    """写入输出文件。"""
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()