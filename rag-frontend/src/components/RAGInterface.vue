<template>
  <div class="container">
    <!-- 左侧输入面板 -->
    <div class="input-panel">
      <div class="header">
        <h1>🔍 RAG知识库系统</h1>
        <p>智能问答与思考过程可视化</p>
      </div>

      <div class="question-input">
        <label for="question">请输入您的问题：</label>
        <textarea v-model="questionInput" id="question" class="question-textarea"
          placeholder="例如：中芯国际在晶圆制造行业中的地位如何？其服务范围和全球布局是怎样的？" />
      </div>

      <button class="submit-btn" @click="submitQuestion" :disabled="isLoading">
        <span v-if="!isLoading">🔮 开始分析</span>
        <span v-else>⏳ 处理中...</span>
      </button>

      <!-- 简单的状态显示 -->
      <div v-if="statusMsg" class="status-msg" :class="statusType">
        {{ statusMsg }}
      </div>

      <div class="examples">
        <h3>💡 示例问题：</h3>
        <ul>
          <li>• 中芯国际在晶圆制造行业中的地位如何？其服务范围和全球布局是怎样的？</li>
          <li>• 中芯国际的营收和利润情况近期有何变化？影响因素是什么？</li>
          <li>• 芯国际的收入结构有何变化？尤其是在中国大陆和北美市场的表现如何？</li>
        </ul>
      </div>
    </div>

    <!-- 右侧显示面板 -->
    <div class="display-panel">
      <div class="process-container">
        <h2 class="process-title">
          思考过程可视化
          <span v-if="currentQuestion" class="question-preview"> - "{{ truncateText(currentQuestion, 30)
          }}"</span>
        </h2>

        <div class="process-steps">
          <!-- 步骤列表 -->
          <div v-for="(step, index) in processSteps" :key="index" class="step" :class="step.type">

            <!-- 1. 接收问题 -->
            <div v-if="step.type === 'input'" class="step-content input-info">
              <div class="step-header">
                <div class="step-title">📥 接收问题</div>
                <div class="step-time">{{ step.time || '' }}</div>
              </div>
              <div class="step-desc">{{ step.data || '' }}</div>
            </div>

            <!-- 2. 检索阶段 -->
            <div v-if="step.type === 'retrieval'" class="step-content retrieval-info">
              <div class="step-header">
                <div class="step-title">🔍 检索阶段</div>
                <div class="step-time">{{ step.time || '' }}</div>
              </div>
              <div class="step-desc">
                <div v-for="(line, idx) in step.data" :key="idx">{{ line }}</div>
              </div>
            </div>

            <!-- 3. 重排阶段 -->
            <div v-if="step.type === 'rerank'" class="step-content process-info">
              <div class="step-header">
                <div class="step-title">🧠 LLM重排阶段</div>
                <div class="step-time">{{ step.time || '' }}</div>
              </div>
              <div class="step-desc">
                <!-- <div v-for="(item, idx) in step.data" :key="idx">重排项目 {{ item }}</div> -->
              </div>
            </div>

            <!-- 4. 参考文档 -->
            <div v-if="step.type === 'rerank'" class="step-content documents-info">
              <div class="step-header">
                <div class="step-title">📄 参考文档</div>
              </div>
              <div class="step-desc">
                <div v-for="(doc, docIdx) in step.data" :key="docIdx" class="document-item">
                  <div class="doc-header">
                    <div class="doc-source">📂 {{ doc.file_origin }} <span class="page-source">
                        📄: P{{ doc.page_range ? (doc.page_range.length > 1
                          ? doc.page_range[0] + '-' + doc.page_range[1] : doc.page_range[0]) : 'N/A' }}
                      </span></div>
                    <div class="doc-relevance">相关度: {{ (doc.relevance_score * 100).toFixed(0) }}%
                    </div>
                  </div>
                  <div class="doc-content">{{ truncateText(doc.text, 100) }}</div>
                  <div class="doc-details">
                    <div class="detail-item">
                      <span class="detail-label">向量分数（{{ doc?.vector_score?.toFixed(3) || 0 }}）</span>
                      <span class="detail-label">BM25分数（{{ doc?.bm25_score?.toFixed(3) || 0 }}）</span>
                      <span class="detail-label">融合分数（{{ doc?.final_score?.toFixed(3) || 0 }}）</span>
                    </div>
                    <div class="detail-item">
                      <span class="detail-label">相似度原因:</span>
                      <span class="detail-value">{{ doc.reasoning }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 最终答案显示 -->
          <div v-if="finalAnswer" class="answer-info">
            <div class="step-header">
              <div class="step-title">💡 最终答案</div>
            </div>
            <div class="step-desc">{{ finalAnswer }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  data() {
    return {
      questionInput: '中芯国际在晶圆制造行业中的地位如何？其服务范围和全球布局是怎样的？',
      currentQuestion: '',
      processSteps: [],
      referenceDocuments: [],
      finalAnswer: '',
      isLoading: false,
      statusMsg: '',
      statusType: 'info'
    };
  },
  computed: {
    formattedAnswer() {
      if (!this.finalAnswer) return [];
      return this.finalAnswer.split('\n').filter(line => line.trim() !== '');
    }
  },
  methods: {
    truncateText(text, length) {
      if (!text) return '';
      return text.length > length ? text.substring(0, length) + '...' : text;
    },

    showMsg(msg, type = 'info') {
      this.statusMsg = msg;
      this.statusType = type;
      setTimeout(() => {
        this.statusMsg = '';
      }, 3000);
    },

    async submitQuestion() {
      if (!this.questionInput.trim()) {
        this.showMsg('请输入问题', 'error');
        return;
      }

      this.isLoading = true;
      this.currentQuestion = this.questionInput;
      this.processSteps = [];
      this.referenceDocuments = [];
      this.finalAnswer = '';
      this.showMsg('开始分析...', 'info');

      try {
        const response = await fetch('http://127.0.0.1:8000/query', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            question: this.questionInput
          })
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop();

          for (const line of lines) {
            if (line.trim().startsWith('data:')) {
              try {
                const jsonStr = line.replace('data:', '').trim();
                if (!jsonStr) continue;
                const data = JSON.parse(jsonStr);

                // --- 数据处理逻辑 ---
                switch (data.type) {
                  case 'input':
                    this.processSteps.push({
                      ...data.content
                    });
                    break;
                  case 'retrieval':
                    this.processSteps.push({
                      ...data.content
                    });
                    break;
                  case 'rerank':
                    this.processSteps.push({
                      ...data.content
                    });
                    break;
                  case 'documents':
                    this.processSteps.push({
                      type: 'documents',
                      data: data.content
                    });
                    break;
                  case 'answer':
                    this.finalAnswer += data.data;
                    break;
                  case 'done':
                    this.isLoading = false;
                    this.showMsg('分析完成', 'success');
                    break;
                }
              } catch (e) {
                console.warn('解析出错', e);
              }
            }
          }
        }

      } catch (error) {
        console.error('请求失败:', error);
        this.showMsg('后端连接失败', 'error');
        this.isLoading = false;
      }
    }
  }
};
</script>

<style scoped>
.container {
  display: flex;
  height: 100vh;
  background-color: #f5f7fa;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
}

/* 左侧输入面板 */
.input-panel {
  width: 40%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 30px;
  display: flex;
  flex-direction: column;
  box-shadow: 2px 0 10px rgba(0, 0, 0, 0.1);
}

.header {
  text-align: center;
  margin-bottom: 30px;
}

.header h1 {
  font-size: 24px;
  margin-bottom: 10px;
  font-weight: 700;
}

.header p {
  opacity: 0.9;
  font-size: 14px;
}

.question-input {
  margin-bottom: 20px;
}

.question-input label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
}

.question-textarea {
  width: 100%;
  height: 120px;
  padding: 15px;
  border: none;
  border-radius: 8px;
  resize: vertical;
  font-size: 14px;
  line-height: 1.4;
  background: rgba(255, 255, 255, 0.95);
  color: #333;
  box-sizing: border-box;
  transition: box-shadow 0.2s;
}

.question-textarea:focus {
  outline: none;
  box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.5);
}

.submit-btn {
  background: white;
  color: #667eea;
  border: none;
  padding: 12px 20px;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 600;
  transition: transform 0.2s;
  margin-bottom: 20px;
}

.submit-btn:hover:not(:disabled) {
  transform: translateY(-2px);
}

.submit-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.examples {
  margin-top: auto;
}

.examples h3 {
  font-size: 16px;
  margin-bottom: 10px;
}

.examples ul {
  list-style: none;
  padding-left: 0;
}

.examples li {
  padding: 5px 0;
  font-size: 13px;
  opacity: 0.9;
}

/* 右侧显示面板 */
.display-panel {
  width: 60%;
  padding: 30px;
  overflow-y: auto;
  background: white;
}

.process-container {
  max-width: 800px;
  margin: 0 auto;
}

.process-title {
  font-size: 22px;
  color: #333;
  margin-bottom: 20px;
  text-align: center;
}

.question-preview {
  font-weight: normal;
  font-size: 14px;
  opacity: 0.8;
}

.process-steps {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.step {
  background: white;
  /* padding: 20px; */
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
  transition: all 0.3s ease;
}

.step-content {
  display: flex;
  flex-direction: column;
  padding: 15px;
}

.step-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.step-title {
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.step-time {
  font-size: 12px;
  color: #666;
  background: #f0f0f0;
  padding: 4px 8px;
  border-radius: 12px;
}

.step-desc {
  color: #555;
  line-height: 1.6;
}

/* 不同步骤的样式 - 根据你的要求设置不同颜色 */
.input-info {
  background: #f0f9ff;
  /* 浅蓝色背景 */
  border-left: 4px solid #50b4f1;
  /* 蓝色左边框 */
  border-radius: 10px;
}

.retrieval-info {
  background: #f4f2f4;
  /* 浅蓝色背景 */
  border-left: 4px solid #beacc5;
  /* 蓝色左边框 */
  border-radius: 10px;
}

.process-info {
  background: #f0f9f0;
  /* 浅绿色背景 */
  border-left: 4px solid #5cb85c;
  /* 绿色左边框 */
  border-radius: 10px;
}

.documents-info {
  background: #f0f9f0;
  /* 浅绿色背景 */
  border-left: 4px solid #5cb85c;
  /* 绿色左边框 */
  border-radius: 10px;
}

.answer-info {
  background: #fff7e6;
  /* 浅橙色背景 */
  border-left: 4px solid #fa8c16;
  /* 橙色左边框 */
}

/* 最终答案 */
.answer-info {
  background: #fff7e6;
  border-left: 4px solid #fa8c16;
  padding: 10px;
  border-radius: 10px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
}

/* 文档项样式 */
.document-item {
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 12px;
  margin: 8px 0;
}

.doc-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.doc-source {
  font-weight: 600;
  color: #333;
  font-size: 14px;
}

.page-source {
  margin-left: 10px;
  font-weight: 600;
  color: #333;
  font-size: 14px;
}

.doc-relevance {
  background: #ff6b6b;
  font-weight: 600;
  color: white;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
}

.doc-content {
  font-size: 13px;
  color: #666;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
  margin-bottom: 8px;
}

/* 文档详情样式 */
.doc-details {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid #eee;
}

.detail-item {
  font-size: 12px;
  color: #666;
  margin-bottom: 4px;
}

.detail-label {
  font-weight: 600;
  color: #333;
  margin-right: 10px;
}

.detail-value {
  color: #666;
}

.loading {
  display: inline-block;
  width: 20px;
  height: 20px;
  border: 3px solid #f3f3f3;
  border-top: 3px solid #667eea;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-right: 8px;
}

@keyframes spin {
  0% {
    transform: rotate(0deg);
  }

  100% {
    transform: rotate(360deg);
  }
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  font-size: 14px;
}

.final-answer-content {
  margin: 10px 0;
}
</style>
