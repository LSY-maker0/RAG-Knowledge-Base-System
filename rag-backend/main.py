"""
main - fastapi 入口文件

Author: lsy
Date: 2026/1/22
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json
import asyncio
from src.retrieval import HybridRetriever
from pathlib import Path

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源（生产环境建议写死具体前端地址，如 ["http://localhost:5173"]）
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有 HTTP 方法
    allow_headers=["*"],  # 允许所有请求头
)

# 1. 定义请求体的数据模型
class QuestionRequest(BaseModel):
    question: str

def retrieval_chunks(question):
    retrieval = HybridRetriever(vector_index_path=Path('data/stock_data/databases/vector_dbs/all_reports.faiss'),metadata_path=Path('data/stock_data/databases/vector_dbs/all_metadata.json'))
    relevant_chunks = retrieval.hybrid_retriever_chunks(question=question, llm_reranking_sample_size=20)
    print(relevant_chunks)
    return relevant_chunks

# 2. 模拟一个流式生成数据的函数 (你可以把这里替换成真实的 LLM 调用)
async def generate_rag_response(question: str):
    """
    适配 RAGInterface.vue 的后端流式生成函数
    """

    # --- 步骤 1: 接收问题 ---
    yield {
        "type": "input",
        "content": {
            "type": "input",
            "title": "📥 接收问题",
            "data": f"收到用户问题: {question}",
            "time": "T+0.00s"
        }
    }

    # --- 步骤 2: 检索 ---
    relevant_chunks = retrieval_chunks(question=question)

    yield {
        "type": "retrieval",
        "content": {
            "type": "retrieval",
            "title": "🔍 检索阶段",
            "data": ["正在连接 Elasticsearch...", "执行语义向量检索..."],
            "description": "正在从知识库检索相关文档...",
            "time": "T+0.50s"
        }
    }

    # --- 发送参考文档 ---
    yield {
        "type": "rerank",
        "content": {
            "type": "rerank",
            "title":'🧠 LLM重排阶段',
            "data": relevant_chunks,
            "time": "T+0.50s"
        }
    }

    # --- 步骤 3: 生成答案 (打字机效果) ---
    # TODO: 这里替换成真实的 LLM 调用
    answer_text = "中芯国际在晶圆制造行业中具有显著的地位，是世界领先的集成电路晶圆代工企业之一。"


    for char in answer_text:
        await asyncio.sleep(0.05)
        yield {
            "type": "answer",
            "data": char
        }

    # --- 结束 ---
    yield {
        "type": "done",
        "timing": "总耗时: 3.0 秒"
    }


# 辅助函数：将字典转换为 SSE 格式 (data: {...}\n\n)
async def event_generator(question: str):
    """生成 SSE 格式的流数据"""
    async for chunk in generate_rag_response(question):
        json_str = json.dumps(chunk, ensure_ascii=False)
        # 标准 SSE 格式
        yield f"data: {json_str}\n\n"


# 3. 定义接口
@app.post("/query")
async def chat_endpoint(request: QuestionRequest):
    """
    流式聊天接口 - 边生成边传输
    """
    return StreamingResponse(
        event_generator(request.question),  # 传入用户的问题
        media_type="text/event-stream"  # 指定媒体类型为 SSE
    )


# 运行服务器
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
