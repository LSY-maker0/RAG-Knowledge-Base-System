"""
questions_processing - 问题处理器

Author: lsy
Date: 2026/1/7
"""
import time
from pathlib import Path

from src.api_requests import APIProcessor
from src.retrieval import VectorRetriever
from src.retrieval import HybridRetriever

class QuestionsProcessor:
    def __init__(
        self,
        llm_ranking:bool=False,
        api_provider:str="dashscope",
        answering_model:str="qwen-turbo-lastest",
        vector_index_path:Path=None,
        metadata_path:Path=None,
    ):
        self.llm_ranking = llm_ranking
        self.api_provider = api_provider
        self.answering_model = answering_model
        self.vector_index_path = vector_index_path
        self.metadata_path = metadata_path
        self.api_processor = APIProcessor(provider=self.api_provider)

    # def __format_retrieval_results(self, retrieval_results) -> str:
    #     """将检索结果转化为RAG上下文字符串，优化大模型理解"""
    #     context_parts = []
    #
    #     # 遍历检索出的每一个块
    #     for idx, chunk in enumerate(retrieval_results):
    #         # 1. 提取关键信息
    #         vector_score = chunk.get('vector_score', 0)
    #         bm25_score = chunk.get('bm25_score', 0)
    #         final_score = chunk.get('final_score', 0)
    #         file_name = chunk.get('file_origin', '未知文件')
    #         page_range = chunk.get('page_range', [])
    #         text_content = chunk.get('text', '')
    #
    #         # 2. 格式化页码信息 (例如：P34-35)
    #         page_info = f"P{page_range[0]}" if page_range else "未知页码"
    #         if len(page_range) > 1:
    #             page_info += f"-{page_range[-1]}"
    #
    #         # 3. 构建每个块的展示文本
    #         # 使用 >>> 符号作为视觉分隔符，帮助模型区分不同引用块
    #         chunk_text = f"""
    # [参考文档 {idx + 1}] (向量分数: {vector_score})(bm25分数: {bm25_score})(加权分数: {final_score})
    # 📂 来源文件: {file_name}
    # 📄 页码: {page_info}
    # ---------------
    # {text_content}
    # """
    #         context_parts.append(chunk_text)
    #
    #     # 4. 拼接所有块，作为整体上下文
    #     rag_text = "\n".join(context_parts)
    #     return rag_text

    def __format_retrieval_results(self, retrieval_results) -> str:
        """将检索结果转化为RAG上下文字符串，优化大模型理解"""
        context_parts = []

        # 遍历检索出的每一个块
        for idx, chunk in enumerate(retrieval_results):
            # 1. 提取关键信息
            # 只保留重排后的相关性分数
            relevance_score = chunk.get('relevance_score', 0)
            reasoning = chunk.get('reasoning', '')
            file_name = chunk.get('file_origin', '未知文件')
            page_range = chunk.get('page_range', [])
            text_content = chunk.get('text', '')

            # 2. 格式化页码信息 (例如：P34-35)
            page_info = f"P{page_range[0]}" if page_range else "未知页码"
            if len(page_range) > 1:
                page_info += f"-{page_range[-1]}"

            # 3. 构建每个块的展示文本
            # 只显示重排后的分数
            chunk_text = f"""
    [参考文档 {idx + 1}] (相关度: {relevance_score:.2f})
    📂 来源文件: {file_name}
    📄 页码: {page_info}
    💡 匹配原因: {reasoning}
    ---------------
    {text_content}
    """
            context_parts.append(chunk_text)

        # 4. 拼接所有块，作为整体上下文
        rag_text = "\n".join(context_parts)
        return rag_text

    def process_single_question(self,question:str,kind:str) -> dict:
        """单条问题推理，返回结构化答案"""
        # retrieval=Hybridretrieval()
        # retrieval=VectorRetriever(vector_index_path=self.vector_index_path,metadata_path=self.metadata_path)
        print(f"{'=' * 20} 开始 RAG 流程 {'=' * 20}")
        print(f"用户问题: {question}\n")
        retrieval=HybridRetriever(vector_index_path=self.vector_index_path,metadata_path=self.metadata_path)
        relevant_chunks = retrieval.hybrid_retriever_chunks(question=question,llm_reranking_sample_size=20)

        rag_context = self.__format_retrieval_results(relevant_chunks)
        print(rag_context)
        t0=time.time()
        print(f"\n[阶段 3/3] 生成最终回答...")
        answer_dict = self.api_processor.get_answer_from_rag_context(
            question=question,
            rag_context=rag_context,
            kind=kind,
            model=self.answering_model
        )
        t1 = time.time()
        print(f"  -> 模型调用【耗时： {t1-t0:.2f} 秒】")
        return answer_dict
