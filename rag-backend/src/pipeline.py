"""
pipeline - 系统主流程调度，pdf解析，分块，向量化，问题处理等

Author: lsy
Date: 2026/1/7
"""
import time
from importlib.metadata import metadata

from pyprojroot import here
from src.text_splitter import TextSplitter
from pathlib import Path
from src.ingestion import VectorDBIngestor
from src.questions_processing import QuestionsProcessor

class Pipeline:
    def __init__(self):
        pass

    def chunk_reports(self):
        """将pdf解析后的报告进行分块处理，存储页码以及后面向量化"""
        text_splitter = TextSplitter()
        print('开始分割文档...')
        all_report_dir = Path('../data/stock_data/debug_data')
        output_dir = Path('../data/stock_data/databases/chunked_reports')
        text_splitter.split_all_reports(
            all_report_dir=all_report_dir,
            output_dir=output_dir,
        )

    def create_vector_dbs(self):
        """从分块报告创建向量数据库"""
        input_dir = Path('../data/stock_data/databases/chunked_reports')
        output_dir = Path('../data/stock_data/databases/vector_dbs')

        # ingestor 提取器
        vdb_ingestor = VectorDBIngestor()
        vdb_ingestor.process_reports(input_dir=input_dir, output_dir=output_dir)
        print(f'向量数据库已经创建到{output_dir}中')

    def answer_single_question(self,question:str,kind:str="summary"):
        """
        单条问题即时推理
        kind问题类型：'fact','reasoning','compare','summary','greeting','other'
        事实，原因，对比，总结，闲聊，其他（无关的）
        """
        t0=time.time()
        processor = QuestionsProcessor(
            llm_ranking=False,
            api_provider="dashscope",
            answering_model="qwen-turbo",
            vector_index_path=Path("../data/stock_data/databases/vector_dbs/all_reports.faiss"),
            metadata_path=Path("../data/stock_data/databases/vector_dbs/all_metadata.json")
        )
        answer = processor.process_single_question(question,kind=kind)
        t1=time.time()
        print(f"\n{'=' * 20} 最终回答【总耗时: {t1 - t0:.2f} 秒】 {'=' * 20}")
        print(answer['final_answer'])
        print(f"{'=' * 20} 流程结束 {'=' * 20}")

if __name__ == '__main__':
    root_path=here()/"data"/"stock_data"
    # 初始化主流程，使用推荐的配置
    # print(root_path)
    pipeline = Pipeline()

    # 1. 解析pdf，并转化为markdown,json

    # 2. 分块，输出到 database/chunked_reports/对应文件名.json
    # pipeline.chunk_reports()

    # 3. 从分块报告中创建向量数据库，输出到 database/vector_dbs/对应文件名.faiss
    # pipeline.create_vector_dbs()

    # 4. 处理问题并生成答案
    pipeline.answer_single_question('中芯国际在晶圆制造行业中的地位如何？其服务范围和全球布局是怎样的？',kind="summary")

