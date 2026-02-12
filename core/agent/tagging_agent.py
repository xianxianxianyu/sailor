from __future__ import annotations

import json
import logging

from core.agent.base import LLMClient
from core.storage.tag_repository import TagRepository

logger = logging.getLogger(__name__)

TAGGING_SYSTEM = """你是一个智能标签分类助手。根据用户已有的标签偏好和文章内容，为文章分配合适的标签。

规则：
1. 优先使用用户已有的标签（provided in existing_tags）
2. 如果文章内容不匹配任何已有标签，可以建议1-2个新标签
3. 每篇文章分配1-4个标签
4. 标签使用英文，简洁明了，如 "LLM", "DevOps", "Security", "Frontend"
5. 输出严格 JSON（不要包含 markdown 代码块标记）

输出格式：
{
  "tags": [
    {"name": "TagName", "is_new": false},
    {"name": "NewTag", "is_new": true}
  ]
}"""


class TaggingAgent:
    def __init__(self, llm: LLMClient, tag_repo: TagRepository) -> None:
        self.llm = llm
        self.tag_repo = tag_repo

    def auto_tag(self, title: str, text: str) -> list[dict]:
        """对文章进行智能打标，返回 [{"name": ..., "is_new": bool}]"""
        existing_tags = self.tag_repo.list_tags()
        tag_names = [t.name for t in existing_tags]

        truncated = text[:2000] if len(text) > 2000 else text
        user_content = f"""已有标签: {json.dumps(tag_names, ensure_ascii=False)}

文章标题: {title}
文章内容: {truncated}

请为这篇文章分配标签。"""

        messages = [
            {"role": "system", "content": TAGGING_SYSTEM},
            {"role": "user", "content": user_content},
        ]

        try:
            resp = self.llm.chat(messages, max_tokens=500)
            result = json.loads(resp.content)
            return result.get("tags", [])
        except Exception:
            logger.warning("LLM tagging failed for: %s", title, exc_info=True)
            return []

    def tag_resource(self, resource_id: str, title: str, text: str) -> list[str]:
        """打标并持久化，返回最终 tag 名称列表"""
        tag_suggestions = self.auto_tag(title, text)
        applied = []

        for suggestion in tag_suggestions:
            name = suggestion.get("name", "").strip()
            if not name:
                continue
            tag = self.tag_repo.create_tag(name)
            self.tag_repo.tag_resource(resource_id, tag.tag_id, source="llm")
            self.tag_repo.increment_weight(tag.tag_id)
            applied.append(name)

        return applied
