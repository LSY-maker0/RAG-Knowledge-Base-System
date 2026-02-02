"""
retrieval - 检索器，检索出对应问题的块

Author: lsy
Date: 2026/1/7
"""
import os
import time
from typing import List,Dict
from pathlib import Path
import json
import faiss
import dashscope
import numpy as np
import glob
from rank_bm25 import BM25Okapi
import jieba
from src.reranking import LLMReranker

class BM25Retriever:
    def __init__(self, metadata_path: Path):
        """
        初始化 BM25 检索器
        :param metadata_path: 存放分块 json 文件的目录路径
        """
        self.documents = []
        self.corpus_tokens = []
        self.bm25 = None

        print(f"[BM25] 正在从 {metadata_path} 加载文档并构建索引...")
        self._load_and_index(metadata_path)

    def _load_and_index(self, metadata_path:Path):
        with open(metadata_path,'r',encoding='utf-8') as f:
            chunks = json.load(f)
            for chunk in chunks:
                self.documents.append(chunk)

        # 2. 分词 - 使用jieba将中文文本切成词语列表（构建索引的关键）
        self.corpus_tokens = [list(jieba.cut(doc['text'])) for doc in self.documents]

        # 3. 初始化 BM25 模型
        self.bm25 = BM25Okapi(self.corpus_tokens)

    @staticmethod
    def normalize_scores(scores):
        """Min-Max 归一化到 [0, 1]"""
        scores = np.array(scores)
        min_score = scores.min()
        max_score = scores.max()

        # 避免除以 0
        if max_score == min_score:
            return np.zeros_like(scores)

        return (scores - min_score) / (max_score - min_score)

    def retrieve(self, question:str,top_n:int=20):
        """检索相关文档"""
        question_tokens = list(jieba.cut(question)) # 问题分词
        raw_scores = self.bm25.get_scores(question_tokens) # 获取文档得分（返回的是文档在列表中的索引）
        normalized_scores = self.normalize_scores(raw_scores) # 归一化
        top_n_indices = normalized_scores.argsort()[-top_n:][::-1] # 倒序取前k个
        # 组装结果
        results = []
        for index in top_n_indices:
            doc = self.documents[index].copy()
            # 将BM25分数添加到文档中（分数越大越好）
            doc['bm25_score'] = float(normalized_scores[index])
            results.append(doc)
        return results

class VectorRetriever:
    def __init__(self,vector_index_path:Path, metadata_path:Path,embedding_provider:str="dashscope"):
        """
        :param vector_index_path: FAISS向量索引文件路径
        :param metadata_path: 文档元数据文件路径
        """
        self.vector_index_path=vector_index_path
        self.metadata_path=metadata_path
        self.embedding_provider=embedding_provider
        self._set_up_llm() # 设置大模型提供商

        # 定义实例变量但不赋值，用于后续缓存
        self._index = None
        self._metadata_list = None
        self.load()

    def load(self):
        """显式加载资源，也可以在首次搜索时自动触发"""
        if self._index is None:
            self._load_index()
        if self._metadata_list is None:
            self._load_metadata()
        return self

    def _load_index(self):
        """加载 FAISS 索引"""
        if not self.vector_index_path.exists():
            raise FileNotFoundError(f"向量索引文件不存在: {self.vector_index_path}")

        # faiss.read_index 是读取磁盘上预训练好的索引的标准方法
        self._index = faiss.read_index(str(self.vector_index_path))

    def _load_metadata(self):
        """
        加载元数据
        假设元数据是用 pickle 存储的 List[Dict] 或 DataFrame
        """
        if not self.metadata_path.exists():
            raise FileNotFoundError(f"元数据文件不存在: {self.metadata_path}")

        with open(self.metadata_path, 'rb') as f:
            self._metadata_list = json.load(f)

    def _set_up_llm(self):
        if self.embedding_provider=="dashscope":
            dashscope.api_key=os.getenv('DASHSCOPE_API_KEY')

    def _get_embedding(self,text:str):
        resp = dashscope.TextEmbedding.call(
            model='text-embedding-v1',
            input=[text],
        )
        embedding = resp.output['embeddings'][0]['embedding']  # List[float]
        vec = np.array(embedding, dtype='float32')
        # L2 归一化
        # 这一步让向量长度变为 1，以便与库里同样归一化的向量进行余弦相似度计算
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec

    def get_relevant_chunks(self, question:str, top_n:int = 20) -> List[Dict]:
        # 检索出与问题相关的块，返回全部块

        # 获取query的embedding，支持dashscope
        embedding_question = self._get_embedding(question)
        # print(embedding_question,len(embedding_question),f'{question}的向量表表示')
        embedding_array = embedding_question.reshape(1, -1) # 变为二维
        k = min(top_n, self._index.ntotal)
        # print(self._metadata_list,'元数据')
        distances, indices = self._index.search(x=embedding_array,k=k)

        retrieval_results = []
        # print('distances:',distances)
        # print('indices:',indices)
        for distance, index in zip(distances[0], indices[0]):
            distance = float(distance)
            chunk=self._metadata_list[index]

            result = {
                "vector_score": distance,
                "page_range": chunk["page_range"],
                "file_origin": chunk["file_origin"],
                "text": chunk["text"],
            }
            retrieval_results.append(result)
        return retrieval_results

class HybridRetriever:
    def __init__(self,vector_index_path:Path, metadata_path:Path):
        self.vector_retriever = VectorRetriever(vector_index_path,metadata_path)
        self.bm25_retriever = BM25Retriever(metadata_path)
        self.reranker=LLMReranker()

    @staticmethod
    def _merge_hybrid_results(vector_results, bm25_results, x=0.6):
        """
        融合向量检索和BM25检索的结果
        :param vector_results: 向量检索的结果
        :param bm25_results: BM25检索的结果
        :param x: 向量占比的权重
        :return: 融合后的结果
        """

        bm25_by_id = {}
        for res in bm25_results:
            chunk_id = res['text'][:50]
            bm25_by_id[chunk_id] = res

        # 建立映射（用text内容作为id进行去重和叠加）
        merged_map = {}

        for i, res in enumerate(vector_results):
            chunk_id = res['text'][:50]
            vector_score = float(res.get('vector_score', 0.0))

            bm25_res = bm25_by_id.get(chunk_id)
            bm25_score = float(bm25_res.get('bm25_score')) if bm25_res and bm25_res.get(
                'bm25_score') is not None else 0.0

            # 基于向量结果为主构造条目
            merged_item = dict(res)
            if bm25_res is not None and bm25_res.get('bm25_score') is not None:
                merged_item['bm25_score'] = bm25_res['bm25_score']

            final_score = x * vector_score + (1-x) * bm25_score
            merged_item['final_score'] = final_score

            merged_map[chunk_id] = merged_item

        final_list = [item for item in merged_map.values()]
        # 把总分写回到字典里
        for i, item in enumerate(merged_map.values()):
            final_list[i]['final_score'] = item['final_score']
        final_list.sort(key=lambda x: x['final_score'], reverse=True)
        return final_list

    def __format_retrieval_results(self, retrieval_results) -> str:
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

    def hybrid_retriever_chunks(
            self,
            question:str,
            llm_reranking_sample_size:int=8,
            rerank_batch_size:int=4,
            top_n:int=8,
            llm_weight:float=0.6,
    ) -> List[Dict]:
        """
        使用混合检索方法进行检索和重排
        :param question: 检索的查询语句
        :param llm_reranking_sample_size: 首轮向量检索返回的候选数量

        :param top_n: 最终返回的重排结果数量
        :param llm_weight: LLM分数权重
        :return: 经过重排后的文档字典列表，包含分数
        """
        t0 = time.time()
        print(f"[阶段 1/3] 混合检索中...")
        vector_results = self.vector_retriever.get_relevant_chunks(question,top_n=llm_reranking_sample_size)
        print(f"  -> 向量检索到 {len(vector_results)} 个片段")
        bm25_results = self.bm25_retriever.retrieve(question,top_n=llm_reranking_sample_size)
        print(f"  -> BM25检索到 {len(bm25_results)} 个片段")
        x = llm_weight # (向量检索的占比)
        hybrid_results = self._merge_hybrid_results(vector_results,bm25_results,x)
        hybrid_results_format=self.__format_retrieval_results(hybrid_results)
        # print(hybrid_results_format)
        print(f"  -> 融合合并出 {len(hybrid_results)} 个相关片段")
        t1 = time.time()
        print(f'[HybridRetriever] 混合检索完成，【耗时： {t1-t0:.2f} 秒】')

        t2 = time.time()
        print(f"\n[阶段 2/3] LLM 重排中...")
        print(f"  -> 准备对 {len(hybrid_results)} 个候选块进行重排，批次大小: {rerank_batch_size}")
        reranked_results=self.reranker.rerank_chunks(
            question=question,
            retrieved_chunks=hybrid_results,
            top_n=top_n,
            rerank_batch_size=rerank_batch_size,
        )
        t3 = time.time()
        print(f"  -> 重排完成，最终选取 Top {len(reranked_results)} 个块")
        print(f'[rerank] LLM重排完成，【耗时： {t3 - t2:.2f} 秒】')
        return reranked_results


