"""
ingestion - 提取分好块的.json文件入FAISS向量数据库

Author: lsy
Date: 2026/1/7
"""
import os
import json
import numpy as np # 科学计算和数据分析
import faiss

import dashscope
from dashscope import TextEmbedding
from typing import Dict,List
from tqdm import tqdm
from pathlib import Path


class VectorDBIngestor:
    def __init__(self):
        dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")

    def _get_embeddings(self, text_list, model:str = "text-embedding-v1") -> List[float]:
        # 获取文本或文本块的嵌入向量
        MAX_BATCH_SIZE = 25
        embeddings = []
        for i in range(0, len(text_list), MAX_BATCH_SIZE):
            batch = text_list[i:i+MAX_BATCH_SIZE]
            resp = TextEmbedding.call(
                model=TextEmbedding.Models.text_embedding_v1,
                input=batch,
            )
            batch_embeddings = [item['embedding'] for item in resp.output['embeddings']]
            embeddings.extend(batch_embeddings)
        return embeddings

    def _create_vector_db(self,embeddings:List[float]):
        """用faiss构建向量库，采用内积（余弦距离）"""
        # List 转换成 NumPy 的多维数组（Matrix）
        # FAISS是C++写的，只认float32类型的numpy数组，如果不转，FAISS 会报错或极慢
        embeddings_array = np.array(embeddings,dtype=np.float32)
        faiss.normalize_L2(embeddings_array) # 归一化
        dimension = len(embeddings_array[0]) # 获取维度
        # FAISS 索引对象，“余弦相似度”索引， "Flat" 意思是暴力穷举（精确）， "IP" 意思是 Inner Product（内积）
        index = faiss.IndexFlatIP(dimension) # 开空间
        # FAISS 就在内存中建立好了这些向量的结构，准备好被搜索了
        index.add(embeddings_array)
        return index # 调用 index.search() 去查找相似的向量

    def _extract_report_data(self,report_data:Dict):
        """提取单份报告的数据,不再直接创建 index，只负责取数据"""
        # 从源头上过滤掉空字符串，用来页码对应
        clean_chunks = [chunk for chunk in report_data['content']['chunks'] if
                        chunk.get('text') and chunk['text'].strip()]
        # 过滤空内容，超长内容截断到2048字符
        max_len = 2048
        processed_chunks = []
        for chunk in clean_chunks:
            text = chunk['text']
            if len(text) > max_len:
                text = text[:max_len]
            processed_chunks.append({
                "text": text,
                "file_origin": chunk['file_origin'],
                "page_range": chunk['page_range']
            })
        text_list = [item['text'] for item in processed_chunks]
        embeddings=self._get_embeddings(text_list)
        # print(embeddings,len(embeddings))
        return embeddings, processed_chunks

    def process_reports(self,input_dir:Path,output_dir:Path):
        """批量处理所有报告，生成并保存faiss向量数据库"""
        all_report_path=list(input_dir.glob("*.json"))
        # print(all_report_path)
        output_dir.mkdir(parents=True, exist_ok=True)

        all_embeddings = []
        all_metadata = []
        for report_path in tqdm(all_report_path,desc="处理报告入faiss向量库中"):
            # 加载报告
            with open(report_path,"r",encoding='utf-8') as f:
                report_data = json.load(f)
            embeddings, metadata = self._extract_report_data(report_data)
            all_embeddings.extend(embeddings)
            all_metadata.extend(metadata)

        index = self._create_vector_db(all_embeddings)
        # 保存 FAISS 索引文件
        faiss_file_path = output_dir / "all_reports.faiss"
        faiss.write_index(index, str(faiss_file_path))

        # 保存元数据文件 (保存对应文件和页码)
        metadata_file_path = output_dir / "all_metadata.json"
        with open(metadata_file_path, "w", encoding='utf-8') as f:
            json.dump(all_metadata, f, ensure_ascii=False, indent=2)

        print(f'报告已存入向量库中！')