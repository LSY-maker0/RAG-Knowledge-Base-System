# RAG-Knowledge-Base-System

基于RAG（检索增强生成）技术的企业知识库智能问答系统

## 项目简介
开发了一套完整的RAG（检索增强生成）问答系统，能够处理企业年报等复杂PDF文档，实现智能问答功能。系统采用混合检索策略和LLM重排机制，显著提升了问答准确性和相关性。

## 功能特性
- PDF文档智能解析和内容分块
- 混合检索（向量检索 + BM25检索）
- LLM驱动的重排机制
- 结构化答案输出
- 中文文档优化处理

## 技术栈
- Python
- FAISS向量数据库
- DashScope大模型API
- BM25检索算法
- jieba中文分词

## 项目结构

```
RAG-lab/
├── data/
│   ├── stock_data/
│   │   ├── debug_data/           # PDF源文件
│   │   └── databases/            # 数据库文件
│   │       ├── chunked_reports/  # 分块后的报告JSON文件
│   │       └── vector_dbs/       # 向量数据库文件(.faiss)
├── src/
│   ├── pipeline.py              # 主流程调度器 - 项目入口点
│   ├── ingestion.py             # 向量数据入库 - 创建FAISS向量库
│   ├── text_splitter.py         # 文档分块器 - PDF解析和文本分割
│   ├── retrieval.py             # 检索器 - 向量检索、BM25检索、混合检索
│   ├── reranking.py             # 重排器 - LLM重排相关性打分
│   ├── questions_processing.py  # 问题处理器 - 整合检索和生成流程
│   ├── api_requests.py          # API处理器 - 调用大模型接口
│   └── prompts.py               # 提示词模板 - 定义各种prompt模板
└── venv/                        # Python虚拟环境
```

## 核心模块说明

### 1. Pipeline (pipeline.py)
- **功能**: 项目主流程调度，包含文档分块、向量库创建和问答处理三大步骤
- **核心方法**:
  - `chunk_reports()`: PDF文档分割处理
  - `create_vector_dbs()`: 创建向量数据库
  - `answer_single_question()`: 单问题处理与回答

### 2. Ingestion (ingestion.py)
- **功能**: 文档数据提取与向量数据库构建
- **核心技术**: 使用DashScope文本嵌入模型和FAISS向量存储
- **处理流程**: 文本列表 → 嵌入向量 → 归一化 → FAISS索引构建

### 3. Text Splitter (text_splitter.py)
- **功能**: PDF文档解析和内容分块处理
- **支持格式**: PDF到Markdown转换，支持页码追踪

### 4. Retrieval (retrieval.py)
- **功能**: 混合检索系统
- **包含三类检索器**:
  - `VectorRetriever`: 基于FAISS的向量相似度检索
  - `BM25Retriever`: 基于jieba分词的关键词匹配检索
  - `HybridRetriever`: 融合向量和BM25的混合检索

### 5. Re-ranking (reranking.py)
- **功能**: 对检索结果进行LLM重排
- **核心技术**: 大语言模型相关性打分和多线程批量处理

### 6. Question Processing (questions_processing.py)
- **功能**: 问题处理与答案生成
- **流程**: 问题 → 检索 → 格式化上下文 → LLM回答生成

### 7. API Requests (api_requests.py)
- **功能**: 大模型API调用封装
- **支持平台**: 主要集成DashScope（通义千问系列）

### 8. Prompts (prompts.py)
- **功能**: 定义各类提示词模板和数据结构
- **特点**: 包含结构化输出Schema（Pydantic）和多种评估prompt