"""
reranking - 重排

Author: lsy
Date: 2026/1/15
"""
import os
import re
import json
import src.prompts as prompts
from concurrent.futures import ThreadPoolExecutor

class LLMReranker:
    def __init__(self):
        self.system_prompt_rerank_multiple_blocks = prompts.RerankingPrompt.system_prompt_rerank_multiple_blocks

        import dashscope
        dashscope.api_key=os.getenv("DASHSCOPE_API_KEY")
        self.llm = dashscope

    def get_rank_for_multiple_blocks(self, question, blocks_data):
        """
        针对多个文本块，批量调用 LLM 进行相关性评分。

        Args:
            question (str): 查询问题
            blocks_data (list): 待评分的文本块列表

        Returns:
            list: [{'block_id': int, 'relevance_score': float}, ...]
        """
        blocks_json_str = json.dumps(blocks_data, ensure_ascii=False)

        user_prompt = (
            f"这是查询问题：\"{question}\"\n\n"
            "以下是检索到的文本块列表（每一块包含block_id和content属性）：\n\n"
            f"{blocks_json_str}\n\n"
        )

        messages = [
            {"role": "system", "content": self.system_prompt_rerank_multiple_blocks},
            {"role": "user", "content": user_prompt},
        ]

        # 调用 LLM
        rsp = self.llm.Generation.call(
            model="qwen-turbo",
            messages=messages,
            temperature=0,
            result_format='message'
        )

        # 检查返回格式
        if 'output' in rsp and 'choices' in rsp['output']:
            content = rsp['output']['choices'][0]['message']['content']
            # 解析并返回结构化结果
            return json.loads(content)
        else:
            raise RuntimeError(f"DashScope返回格式异常: {rsp}")

    def rerank_chunks(self, question, retrieved_chunks, top_n, rerank_batch_size):
        """
        使用多线程并行方式对多个文档进行重排。

        Args:
            question (str): 查询语句
            retrieved_chunks (list): 待重排的文档列表，每个元素是 {'text': str, 'final_score': float}
            top_n (int): 重排后返回的块个数
            rerank_batch_size (int): 每批处理的块数量

        Returns:
            list: 重排后的块列表，按相关性分数从高到低排序
        """
        if not retrieved_chunks:
            return []

        # 按批次分组
        chunk_batches = [retrieved_chunks[i:i+rerank_batch_size]
                        for i in range(0, len(retrieved_chunks), rerank_batch_size)]
        batch_counter = [0]

        # 处理每一批
        def process_chunk(batch):
            batch_counter[0] += 1
            current_batch = batch_counter[0]
            total_batches = len(chunk_batches)
            print(f"  -> 正在处理批次 {current_batch}/{total_batches} (包含 {len(batch)} 个块)...")

            blocks_data = []
            for i, chunk in enumerate(batch):
                # 建议截断文本，防止超出模型单字段长度限制
                blocks_data.append({
                    "block_idx": i,
                    "content": chunk['text']
                })
            # 调用 LLM 获取评分
            rankings = self.get_rank_for_multiple_blocks(question, blocks_data)
            # 将评分结果关联到原始 chunks
            results = []
            for rank_item in rankings:
                block_idx = rank_item['block_idx']
                results.append({
                    "text":batch[block_idx]['text'],
                    "file_origin":batch[block_idx]['file_origin'],
                    "vector_score":batch[block_idx]['vector_score'],
                    "bm25_score":batch[block_idx].get('bm25_score'), # 存在问题
                    "final_score":batch[block_idx]['final_score'],
                    "page_range":batch[block_idx]['page_range'],
                    "relevance_score": rank_item['relevance_score'],
                    "reasoning": rank_item['reasoning'],
                })

            return results

        # 使用多线程处理（max_workers=1 串行调用，避免 QPS 超限）
        with ThreadPoolExecutor(max_workers=1) as executor:
            batch_results = list(executor.map(process_chunk, chunk_batches))

        # 扁平化所有批次的结果
        all_results = []
        for batch in batch_results:
            all_results.extend(batch)

        # 按 relevance_score 从高到低排序
        if all_results:
            all_results.sort(key=lambda x: x['relevance_score'], reverse=True)

        # 返回 top_n 个结果
        return all_results[:top_n]
        print(all_results)
