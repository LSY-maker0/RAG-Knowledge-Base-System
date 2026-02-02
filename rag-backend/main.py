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
import time

from src.api_requests import APIProcessor
from src.retrieval import HybridRetriever,BM25Retriever,VectorRetriever
from src.reranking import LLMReranker
from pathlib import Path

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源（生产环境建议写死具体前端地址，如 ["http://localhost:5173"]）
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有 HTTP 方法
    allow_headers=["*"],  # 允许所有请求头
)

vector_index_path = Path('data/stock_data/databases/vector_dbs/all_reports.faiss')
metadata_path = Path('data/stock_data/databases/vector_dbs/all_metadata.json')

# 1. 定义请求体的数据模型
class QuestionRequest(BaseModel):
    question: str

async def search_vector(question):
    vector_retriever = VectorRetriever(vector_index_path, metadata_path)
    vector_results = vector_retriever.get_relevant_chunks(question, top_n=20)
    return vector_results

async def search_bm25(question):
    bm25_retriever = BM25Retriever(metadata_path)
    bm25_results = bm25_retriever.retrieve(question, top_n=20)
    return bm25_results

def hybrid_chunks(vector_results,bm25_results):
    hybrid_retriever = HybridRetriever(vector_index_path=vector_index_path,metadata_path=metadata_path)
    hybrid_results = hybrid_retriever._merge_hybrid_results(vector_results, bm25_results, 0.6)
    return hybrid_results

def rerank_chunks(question,hybrid_results,top_n=8,rerank_batch_size=4):
    reranker = LLMReranker()
    reranked_results = reranker.rerank_chunks(
        question=question,
        retrieved_chunks=hybrid_results,
        top_n=top_n,
        rerank_batch_size=rerank_batch_size,
    )
    return reranked_results

def format_retrieval_results(retrieval_results) -> str:
    """将检索结果转化为RAG上下文字符串，优化大模型理解"""
    context_parts = []

    # 遍历检索出的每一个块
    for idx, chunk in enumerate(retrieval_results):
        # 1. 提取关键信息
        vector_score = chunk.get('vector_score', 0)
        bm25_score = chunk.get('bm25_score', 0)
        final_score = chunk.get('final_score', 0)
        file_name = chunk.get('file_origin', '未知文件')
        page_range = chunk.get('page_range', [])
        text_content = chunk.get('text', '')

        # 2. 格式化页码信息 (例如：P34-35)
        page_info = f"P{page_range[0]}" if page_range else "未知页码"
        if len(page_range) > 1:
            page_info += f"-{page_range[-1]}"

        # 3. 构建每个块的展示文本
        # 使用 >>> 符号作为视觉分隔符，帮助模型区分不同引用块
        chunk_text = f"""
[参考文档 {idx + 1}] (向量分数: {vector_score})(bm25分数: {bm25_score})(加权分数: {final_score})
📂 来源文件: {file_name}
📄 页码: {page_info}
---------------
{text_content}
"""
        context_parts.append(chunk_text)

    # 4. 拼接所有块，作为整体上下文
    rag_text = "\n".join(context_parts)
    return rag_text


# 2. 模拟一个流式生成数据的函数 (你可以把这里替换成真实的 LLM 调用)
async def generate_rag_response(question: str):
    """
    适配 RAGInterface.vue 的后端流式生成函数
    """

    t0 = time.time()
    # --- 步骤 1: 接收问题 ---
    yield {
        "type": "input",
        "content": {
            "type": "input",
            "title": "📥 接收问题",
            "data": f"收到用户问题: {question}",
        }
    }

    # --- 步骤 2: 检索 ---
    data = []
    description = []

    # 初始显示
    yield {
        "type": "retrieval",
        "content": {
            "type": "retrieval",
            "title": "🔍 检索阶段",
            "data": data,
            "description": description,
        }
    }
    t1 = time.time()
    vector_results = await search_vector(question=question)
    t2 = time.time()
    description.append('✅ 向量检索完成')
    data.append(vector_results)
    # 更新同一个卡片
    yield {
        "type": "retrieval",
        "content": {
            "type": "retrieval",
            "title": "🔍 检索阶段",
            "data": data,
            "description": description,
            "time": f"耗时 {t2-t1:.2f} s"
        }
    }
    t3 = time.time()
    bm25_results = await search_bm25(question=question)
    t4 = time.time()
    description.append('✅ BM25关键词检索完成')
    data.append(bm25_results)
    # 更新同一个卡片
    yield {
        "type": "retrieval",
        "content": {
            "type": "retrieval",
            "title": "🔍 检索阶段",
            "data": data,
            "description": description,
            "time": f"耗时 {t4-t3+t2-t1:.2f} s"
        }
    }

    t5 = time.time()
    hybrid_results = hybrid_chunks(vector_results, bm25_results)
    t6 = time.time()
    description.append('✅ 混合合并完成')
    data.append(hybrid_results)
    # 更新同一个卡片
    yield {
        "type": "retrieval",
        "content": {
            "type": "retrieval",
            "title": "🔍 检索阶段",
            "data": data,
            "description": description,
            "time": f"耗时 {t6-t5+t4-t3+t2-t1:.2f} s"
        }
    }

    t7 = time.time()
    rerank_results = rerank_chunks(question=question,hybrid_results=hybrid_results,top_n=8,rerank_batch_size=4)
    t8 = time.time()

    # --- 发送参考文档 ---
    yield {
        "type": "rerank",
        "content": {
            "type": "rerank",
            "title": '🧠 LLM重排阶段',
            "description": '✅ LLM 重排完成',
            "data": rerank_results,
            "time": f"耗时 {t8-t7:.2f} s"
        }
    }

    # --- 步骤 3: 生成答案 (打字机效果) ---
    api_processor = APIProcessor()
    rag_context = format_retrieval_results(rerank_results)
    
    # 获取真实的LLM流式响应
    responses = api_processor.get_answer_from_rag_context(
        question=question,
        rag_context=rag_context,
        kind="summary",  # 添加缺失的参数
        model='qwen-turbo-latest',  # 使用实际模型名称而不是'dashscope'
        stream=True  # 启用流式输出
    )
    
    # 处理流式响应
    full_answer = ""
    for response in responses:
        if hasattr(response, 'output') and hasattr(response.output, 'choices'):
            content = response.output.choices[0].message.content or ""
        else:
            content = ""
        
        # 将每个响应内容逐字符发送
        for char in content:
            full_answer += char
            yield {
                "type": "answer",
                "data": char
            }

    t9 = time.time()
    print("最终答案:", full_answer)

    # --- 结束 ---
    yield {
        "type": "done",
        "timing": f"总耗时 {t9 - t0:.2f} s"
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
