import json
from typing import Any

import httpx

from .config_service import load_config


def _chat(messages: list[dict[str, str]], timeout: float = 18.0) -> str:
    config = load_config()
    if not config["enabled"]:
        raise RuntimeError("API 尚未启用")
    if not config["base_url"] or not config["api_key"] or not config["model"]:
        raise RuntimeError("请完整填写 API Base URL、API Key 和模型名称")
    url = f"{config['base_url'].rstrip('/')}/chat/completions"
    response = httpx.post(
        url,
        headers={"Authorization": f"Bearer {config['api_key']}"},
        json={
            "model": config["model"],
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 900,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def test_connection() -> str:
    return _chat(
        [
            {"role": "system", "content": "你是数据分析助手。"},
            {"role": "user", "content": "只回复：连接成功"},
        ],
        timeout=12.0,
    )


def generate_report_insights(summary: dict[str, Any]) -> str | None:
    try:
        content = _chat(
            [
                {
                    "role": "system",
                    "content": (
                        "你是严谨的数据分析师。根据统计摘要写出 3 到 5 条中文洞察。"
                        "不得捏造数据，不要使用 Markdown 标题，每条以短横线开头。"
                    ),
                },
                {
                    "role": "user",
                    "content": "统计摘要如下：\n" + json.dumps(summary, ensure_ascii=False),
                },
            ]
        )
        return content
    except Exception:
        return None
