# RAG-Knowledge-Base-System

<div align="center">
<br>
<h3>基于RAG（检索增强生成）构建的垂直领域知识库系统</h3>
</div>

## ✨ 项目简介

本项目是一个基于RAG（检索增强生成） 构建的垂直领域知识库系统，专注于解决复杂 PDF 财报（含表格、跨页排版）的解析与精准问答问题，实现了从文档解析、知识入库、混合检索到流式响应的全流程闭环。

核心亮点：
*   🧠 **精准解析**：针对财报表格跨页问题，设计基于块结构的解析策略，有效保留数据完整性。
*   ⚡  **极致体验**：基于 SSE 实现流式输出，前端实时渲染"思考"过程，告别长耗时等待。
*   🎯 **混合检索**：结合 BM25 关键词检索与向量语义检索，显著提升专业术语的召回准确率。

## 🖥️ 效果展示

### 视频：
https://github.com/user-attachments/assets/62c43f30-a94e-46ca-9ed1-b8a93e03e4bb

### 图片：
<div align="center">
  <img width="80%" alt="文档解析过程" src="https://github.com/user-attachments/assets/c17a4cd7-8139-4299-bde3-c2d546056c32" />
  
  <br><br>
  
  <img width="45%" alt="检索出的块预览" src="https://github.com/user-attachments/assets/94f5c89d-96db-47f4-b69b-d33bd298b4eb" />
  <img width="45%" alt="RAG问答结果" src="https://github.com/user-attachments/assets/d05478d4-be07-4098-b6c1-6fc4d1dceeb5" />
</div>

## 🛠️ 技术栈

| 类别           | 技术组件                     |
| -------------- | ---------------------------- |
| **前端框架**   | Vue3                         |
| **后端语言**   | Python                       |
| **向量数据库** | FAISS                        |
| **大模型服务** | DashScope (通义千问系列)     |
| **检索算法**   | 向量相似度 + BM25 + 混合检索 |
| **中文处理**   | jieba分词                    |
| **API框架**    | FastAPI                      |


