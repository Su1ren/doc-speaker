"""
prompt_builder.py – Prompts for turning Markdown into a spoken-friendly script.
"""

from textwrap import dedent
from typing import List, Dict


def build_speech_prompt(markdown: str, locale: str = "zh") -> str:
    """Return a prompt that rewrites *markdown* into SSML ready for TTS."""
    locale_note = "使用中文输出。" if locale.lower().startswith("zh") else "Use the same language as the source."
    prompt = dedent(
        f"""
        你现在的角色是我的实习面试导师。请根据下面的 Markdown 资料生成一份口语化讲解稿，要求：
        - 语气：亲切、专业、像真人对话，避免书面语；{locale_note}
        - 结构：先给约 1 分钟的核心摘要，再分 3 个重点详细讲解，最后给出 2 个可能的面试官追问及回答思路。
        - 互动感：每个重点结束后插入一句“这一点在面试中很容易被问到，你准备好怎么回答了吗？”。
        - 表格/图表处理：不要逐行朗读数字，分析趋势、最大/最小值或异常点，并说明可能原因。
        - 节奏与 SSML：在关键概念后加入 <break time="0.5s"/>，需要强调的词语用 <emphasis level="moderate">词</emphasis>；整体包裹在 <speak>…</speak> 中。
        - 输出：直接返回可供 TTS 使用的 SSML，不要包含额外解释或 Markdown。

        资料（Markdown）：
        {markdown.strip()}
        """
    ).strip()
    return prompt


def build_chat_messages(markdown: str, locale: str = "zh") -> List[Dict[str, str]]:
    """Convenience helper for Chat Completions style APIs."""
    system = (
        "You are an interview coach who rewrites documents into friendly, spoken scripts "
        "with SSML pacing. You never read tables verbatim; you summarise insights instead."
    )
    user = build_speech_prompt(markdown, locale=locale)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
