"""
api_requests - api处理器

Author: lsy
Date: 2026/1/8
"""
import dashscope
import src.prompts as prompts
import os
import json

class APIProcessor:
    # "openai" "dashscope" "gemini"
    def __init__(self,provider:str="dashscope"):
        self.provider = provider.lower()
        if self.provider=="dashscope":
            self.processor = BaseDashscopeProcessor()


    def get_answer_from_rag_context(self, question, rag_context, kind, model, stream=False) -> dict:
        system_prompt, response_format, user_prompt = self._build_rag_context_prompts(kind)

        answer_dict = self.processor.send_message(
            model=model,
            system_prompt=system_prompt,
            human_content=user_prompt.format(context=rag_context, question=question),
            is_structured=True,
            response_format=response_format,
            stream=stream  # 传递流式参数
        )

        return answer_dict

    def _build_rag_context_prompts(self,kind):
        """根据给定的问题类型生成对应的提示词模版"""
        # use_schema_prompt = True if self.provider == "ibm" or self.provider == "gemini" else False
        if kind == "summary":
            system_prompt = prompts.AnswerWithRAGContextStringPrompt.system_prompt
            response_format = prompts.AnswerWithRAGContextStringPrompt.AnswerSchema
            user_prompt = prompts.AnswerWithRAGContextStringPrompt.user_prompt

        return system_prompt,response_format,user_prompt


# DashScope基础处理器，支持Qwen大模型对话
class BaseDashscopeProcessor:
    def __init__(self):
        # 从环境变量读取API-KEY
        dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")
        self.default_model = 'qwen-turbo-latest'

    def send_message(
            self,
            model="qwen-turbo-latest",
            temperature=0.1,
            seed=None,  # 兼容参数，暂不使用
            system_content='You are a helpful assistant.',
            human_content='Hello!',
            is_structured=False,
            response_format=None,
            stream=False,  # 新增流式参数
            **kwargs
    ):
        """
        发送消息到DashScope Qwen大模型，支持 system_content + human_content 拼接为 messages。
        支持流式输出。
        """
        if model is None:
            model = self.default_model
        # 拼接 messages
        messages = []
        if system_content:
            messages.append({"role": "system", "content": system_content})
        if human_content:
            messages.append({"role": "user", "content": human_content})
        
        if stream:
            # 流式输出模式
            responses = dashscope.Generation.call(
                model=model,
                messages=messages,
                temperature=temperature,
                result_format='message',
                stream=True,
                incremental_output=True
            )
            return responses
        else:
            # 同步输出模式
            response = dashscope.Generation.call(
                model=model,
                messages=messages,
                temperature=temperature,
                result_format='message'
            )
            # 兼容 openai/gemini 返回格式，始终返回 dict
            if hasattr(response, 'output') and hasattr(response.output, 'choices'):
                content = response.output.choices[0].message.content
            else:
                content = str(response)
            # 增加 response_data 属性，保证接口一致性
            self.response_data = {"model": model,
                                  "input_tokens": response.usage.input_tokens if hasattr(response, 'usage') and hasattr(
                                      response.usage, 'input_tokens') else None,
                                  "output_tokens": response.usage.output_tokens if hasattr(response, 'usage') and hasattr(
                                      response.usage, 'output_tokens') else None}

            # 尝试解析 content 为 JSON，如果是结构化响应
            try:
                # 先尝试移除可能的markdown代码块标记
                content_str = content.strip()
                if content_str.startswith('```') and '```' in content_str[3:]:
                    # 找到第一个 ``` 和 最后一个 ``` 之间的内容
                    first_backtick = content_str.find('```') + 3
                    next_newline = content_str.find('\n', first_backtick)
                    if next_newline > 0:
                        first_backtick = next_newline + 1
                    last_backtick = content_str.rfind('```')
                    if last_backtick > first_backtick:
                        json_str = content_str[first_backtick:last_backtick].strip()
                    else:
                        json_str = content_str
                else:
                    json_str = content_str

                # 尝试解析 JSON
                parsed_content = json.loads(json_str)
                return parsed_content
            except (json.JSONDecodeError, TypeError):
                # 如果不是有效的JSON，返回基本格式
                # print(f"Content is not valid JSON, returning basic format: {content}")
                return {"final_answer": content, "step_by_step_analysis": "", "reasoning_summary": "", "relevant_pages": []}
