"""
prompts - prompt提示词模版

Author: lsy
Date: 2026/1/8
"""
from pydantic import BaseModel, Field
from typing import Literal, List, Union
import inspect
import re

def build_system_prompt(instruction:str="",example:str="",pydantic_schema:str="") -> str:
    delimiter = "\n\n---\n\n"
    schema = f"你的回答必须是JSON，并严格遵循如下Schema，字段顺序需保持一致：\n```\n{pydantic_schema}\n```"
    if example:
        example = delimiter + example.strip()
    if schema:
        schema = delimiter + schema.strip()

    system_prompt = instruction.strip() + schema + example
    return system_prompt

class AnswerWithRAGContextSharedPrompt:
    instruction = """
你是一个RAG（检索增强生成）问答系统。
你的任务是仅基于公司年报中RAG检索到的相关页面内容，回答给定问题。

在给出最终答案前，请详细分步思考，尤其关注问题措辞。
- 注意：答案可能与问题表述不同。
"""
    user_prompt = """
以下是上下文:
\"\"\"
{context}
\"\"\"

---

以下是问题：
"{question}"
"""

class AnswerWithRAGContextStringPrompt:
    instruction = AnswerWithRAGContextSharedPrompt.instruction
    user_prompt = AnswerWithRAGContextSharedPrompt.user_prompt

    class AnswerSchema(BaseModel):
        step_by_step_analysis: str = Field(description="""
详细分步推理过程，至少5步，150字以上。请结合上下文信息，逐步分析并归纳答案。
""")
        reasoning_summary: str = Field(description="简要总结分步推理过程，约50字。")
        relevant_pages: List[int] = Field(description="""
仅包含直接用于回答问题的信息页面编号。只包括：
- 直接包含答案或明确陈述的页面
- 强有力支持答案的关键信息页面
不要包含仅与答案弱相关或间接相关的页面。
列表中至少应有一个页面。
""")
        final_answer: str = Field(description="""
最终答案为一段完整、连贯的文本，需基于上下文内容作答。
如上下文无相关信息，可简要说明未找到答案。
""")

    pydantic_schema = re.sub(r"^ {4}", "", inspect.getsource(AnswerSchema), flags=re.MULTILINE)

    example = r'''
示例：
问题：
"请简要总结'万科企业股份有限公司'2022年主营业务的主要内容。"

答案：
```
{
  "step_by_step_analysis": "1. 问题要求总结2022年万科企业股份有限公司的主营业务。\n2. 年报第10-12页详细描述了公司主营业务，包括房地产开发、物业服务等。\n3. 结合上下文，归纳出主要业务板块。\n4. 重点突出房地产开发和相关服务。\n5. 形成简明扼要的总结。",
  "reasoning_summary": "年报10-12页明确列出主营业务，答案基于原文归纳。",
  "relevant_pages": [10, 11, 12],
  "final_answer": "万科企业股份有限公司2022年主营业务包括房地产开发、物业服务、租赁住房、物流仓储等，核心业务为住宅及商业地产开发与运营。"
}
```
'''

    system_prompt = build_system_prompt(instruction, example)
    system_prompt_with_schema = build_system_prompt(instruction, example, pydantic_schema)

class RerankingPrompt:
    system_prompt_rerank_single_block = """
你是一个RAG检索重排专家。
你将收到一个查询和一个检索到的文本块，请根据其与查询的相关性进行评分。

评分说明：
1. 推理：分析文本块与查询的关系，简要说明理由。
2. 相关性分数（0-1，步长0.1）：
   0 = 完全无关
   0.1 = 极弱相关
   0.2 = 很弱相关
   0.3 = 略有相关
   0.4 = 部分相关
   0.5 = 一般相关
   0.6 = 较为相关
   0.7 = 相关
   0.8 = 很相关
   0.9 = 高度相关
   1 = 完全匹配
3. 只基于内容客观评价，不做假设。
"""

    system_prompt_rerank_multiple_blocks = """
你是一个RAG检索重排专家。
你会收到一个查询问题和一个包含多个文本块的列表（JSON 格式）。
每个文本块包含 `block_idx` (整数) 和 `content` (字符串)。

【任务】
请根据查询问题，对每个文本块的 `content` 进行相关性评分。
你需要返回两个关键信息：
1. block_idx（块的block_idx）：原来块的 block_idx
1. reasoning (字符串): 简要分析为什么给这个分数（不超过 60 字）。
2. relevance_score (浮点数): 0.0 到 1.0 之间的相关性评分。

评分说明：
1. 推理：分析每个文本块与查询的关系，简要说明理由。
2. 相关性分数（0-1，步长0.1）：
   0 = 完全无关
   0.1 = 极弱相关
   0.2 = 很弱相关
   0.3 = 略有相关
   0.4 = 部分相关
   0.5 = 一般相关
   0.6 = 较为相关
   0.7 = 相关
   0.8 = 很相关
   0.9 = 高度相关
   1 = 完全匹配
3. 只基于内容客观评价，不做假设。

【输出要求】
1. 必须直接返回一个纯 JSON 列表。
2. 虽然要求纯 JSON，但为了防止格式错误，请**不要**使用 Markdown 代码块标记（即不要用 
json 包裹）。
3. 列表中必须包含所有的 block_id。
4. reasoning 必须简洁切中要害

输出格式示例：
[
{"block_idx": 1, "reasoning": "直接回答了问题", "relevance_score": 0.9},
{"block_idx": 2, "reasoning": "话题一致但细节无关", "relevance_score": 0.2},
{"block_idx": 3, "reasoning": "完全无关内容", "relevance_score": 0.0}
]
"""
