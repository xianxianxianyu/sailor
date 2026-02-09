from __future__ import annotations

ARTICLE_ANALYSIS_SYSTEM = """你是一个专业的技术文章分析助手。对给定文章输出严格 JSON（不要包含 markdown 代码块标记）：
{
  "summary": "200字以内中文摘要，概括文章核心观点和关键信息",
  "topics": ["Topic1", "Topic2"],
  "scores": {"depth": 1-10, "utility": 1-10, "novelty": 1-10},
  "kb_recommendations": [{"kb_id": "...", "confidence": 0.0-1.0, "reason": "推荐理由"}],
  "insights": {
    "core_arguments": ["核心论点1", "核心论点2"],
    "tech_points": ["技术要点1", "技术要点2"],
    "practices": ["实践建议1", "实践建议2"]
  }
}

评分标准：
- depth（深度）：技术分析的深入程度，1=浅显科普，10=深入底层原理
- utility（实用性）：对读者的实际帮助，1=纯理论，10=可直接应用
- novelty（新颖性）：观点或技术的新颖程度，1=常见知识，10=前沿突破

注意：
- topics 使用英文标签，如 "LLM", "DevOps", "Security" 等
- kb_recommendations 从提供的知识库列表中选择最匹配的
- 所有文本内容使用中文
- 只输出 JSON，不要有其他内容"""


KB_CLUSTER_SYSTEM = """你是一个专业的知识库分析助手。根据提供的文章摘要列表，进行主题聚类分析。
输出严格 JSON（不要包含 markdown 代码块标记）。所有文本内容使用中文。"""

KB_CLUSTER_PROMPT = """对以下知识库中的文章进行主题聚类分析，输出 JSON：
{
  "clusters": [{"theme": "主题名", "description": "主题描述", "resource_ids": ["id1", "id2"], "trend": "rising|stable|declining"}],
  "hot_topics": ["热门话题1", "热门话题2"],
  "emerging_trends": ["新兴趋势1", "新兴趋势2"]
}"""

KB_ASSOCIATION_SYSTEM = """你是一个专业的知识库分析助手。根据提供的文章摘要列表，分析文章间的关联关系。
输出严格 JSON（不要包含 markdown 代码块标记）。所有文本内容使用中文。"""

KB_ASSOCIATION_PROMPT = """分析以下文章之间的关联关系，输出 JSON：
{
  "associations": [{"resource_id_a": "id1", "resource_id_b": "id2", "relation": "关联描述", "strength": 0.85}],
  "reading_paths": [{"name": "路径名", "description": "路径描述", "resource_ids": ["id1", "id2", "id3"]}]
}"""

KB_SUMMARY_SYSTEM = """你是一个专业的知识库分析助手。根据提供的文章摘要列表，生成知识总结报告。
输出严格 JSON（不要包含 markdown 代码块标记）。所有文本内容使用中文。"""

KB_SUMMARY_PROMPT = """对以下知识库内容生成总结报告，输出 JSON：
{
  "executive_summary": "整体概述（200字以内）",
  "key_themes": [{"theme": "主题名", "summary": "主题总结", "key_resources": ["id1", "id2"]}],
  "knowledge_gaps": ["知识空白1", "知识空白2"],
  "recommendations": ["建议1", "建议2"]
}"""


def build_article_prompt(title: str, text: str, kb_list: list[dict]) -> list[dict]:
    """构建文章分析的消息列表。"""
    # 截断正文到 3000 字符控制 token 成本
    truncated_text = text[:3000] if len(text) > 3000 else text

    kb_info = "\n".join(
        f"- {kb['kb_id']}: {kb['name']} ({kb.get('description', '')})"
        for kb in kb_list
    )

    user_content = f"""请分析以下文章：

标题：{title}

正文：
{truncated_text}

可选知识库：
{kb_info}"""

    return [
        {"role": "system", "content": ARTICLE_ANALYSIS_SYSTEM},
        {"role": "user", "content": user_content},
    ]


def build_kb_analysis_prompt(
    report_type: str,
    articles: list[dict],
) -> list[dict]:
    """构建 KB 分析的消息列表。"""
    articles_text = "\n\n".join(
        f"[{a['resource_id']}] {a['title']}\n摘要: {a.get('summary', '无')}\n主题: {', '.join(a.get('topics', []))}"
        for a in articles
    )

    if report_type == "cluster":
        system = KB_CLUSTER_SYSTEM
        prompt = KB_CLUSTER_PROMPT
    elif report_type == "association":
        system = KB_ASSOCIATION_SYSTEM
        prompt = KB_ASSOCIATION_PROMPT
    else:
        system = KB_SUMMARY_SYSTEM
        prompt = KB_SUMMARY_PROMPT

    user_content = f"""{prompt}

文章列表：
{articles_text}"""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]
