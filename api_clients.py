#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
from typing import Dict, Any, Tuple, Optional

from openai import OpenAI, AsyncOpenAI
import anthropic

from logger import log_info, log_error, LogColor
from utils import PromptConfig, TestCase, process_prompt

class APIClientManager:
    """API客户端管理器，负责创建和管理API客户端实例"""
    
    def __init__(self, openai_key: str = "", anthropic_key: str = ""):
        self.openai_key = openai_key
        self.anthropic_key = anthropic_key
        self.openai_client = None
        self.async_openai_client = None
        self.anthropic_client = None
        
    def setup_clients(self):
        """初始化API客户端"""
        if self.openai_key:
            self.openai_client = OpenAI(api_key=self.openai_key)
            self.async_openai_client = AsyncOpenAI(api_key=self.openai_key)
            
        if self.anthropic_key:
            self.anthropic_client = anthropic.Anthropic(api_key=self.anthropic_key)
    
    async def call_openai_api(self, prompt_config: PromptConfig, case: TestCase) -> Tuple[str, float, Dict[str, Any], str]:
        """调用OpenAI API并返回结果、耗时、token使用情况和处理后的提示词"""
        start_time = time.time()
        try:
            # 处理提示词中的变量替换
            processed_prompt = process_prompt(prompt_config, case)
            
            # 使用异步客户端流式调用API
            log_info(f"开始调用 OpenAI API ({prompt_config['model']})...")
            print(f"{LogColor.BOLD}{LogColor.MAGENTA}[AI输出开始]{LogColor.RESET}")
            response_chunks = []
            
            stream = await self.async_openai_client.chat.completions.create(
                model=prompt_config["model"],
                messages=[
                    {"role": "system", "content": processed_prompt},
                    {"role": "user", "content": case["content"]}
                ],
                max_tokens=1000,
                stream=True
            )
            
            # 处理流式响应
            full_response = ""
            async for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    content = chunk.choices[0].delta.content or ""
                    if content:
                        print(content, end="", flush=True)
                        full_response += content
                        response_chunks.append(content)
            
            print(f"\n{LogColor.BOLD}{LogColor.MAGENTA}[AI输出结束]{LogColor.RESET}")
            
            end_time = time.time()
            elapsed_time = end_time - start_time
            
            # 获取完整响应的令牌使用情况
            response = await self.async_openai_client.chat.completions.create(
                model=prompt_config["model"],
                messages=[
                    {"role": "system", "content": processed_prompt},
                    {"role": "user", "content": case["content"]}
                ],
                max_tokens=1000
            )
            
            tokens = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
            
            return full_response, elapsed_time, tokens, processed_prompt
        except Exception as e:
            end_time = time.time()
            elapsed_time = end_time - start_time
            log_error(f"OpenAI API调用失败: {str(e)}")
            return f"错误: {str(e)}", elapsed_time, {"error": str(e)}, prompt_config["prompt"]
    
    async def call_anthropic_api(self, prompt_config: PromptConfig, case: TestCase) -> Tuple[str, float, Dict[str, Any], str]:
        """调用Anthropic API并返回结果、耗时、token使用情况和处理后的提示词"""
        start_time = time.time()
        try:
            # 处理提示词中的变量替换
            processed_prompt = process_prompt(prompt_config, case)
            
            # 流式调用API
            log_info(f"开始调用 Anthropic API ({prompt_config['model']})...")
            print(f"{LogColor.BOLD}{LogColor.MAGENTA}[AI输出开始]{LogColor.RESET}")
            
            with self.anthropic_client.messages.stream(
                model=prompt_config["model"],
                system=processed_prompt,
                messages=[
                    {"role": "user", "content": case["content"]}
                ],
                max_tokens=1000
            ) as stream:
                full_response = ""
                for text in stream.text_stream:
                    print(text, end="", flush=True)
                    full_response += text
                
                # 获取最终的完整消息
                response = stream.get_final_message()
            
            print(f"\n{LogColor.BOLD}{LogColor.MAGENTA}[AI输出结束]{LogColor.RESET}")
            
            end_time = time.time()
            elapsed_time = end_time - start_time
            
            # 获取结果
            tokens = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens
            }
            
            return full_response, elapsed_time, tokens, processed_prompt
        except Exception as e:
            end_time = time.time()
            elapsed_time = end_time - start_time
            log_error(f"Anthropic API调用失败: {str(e)}")
            return f"错误: {str(e)}", elapsed_time, {"error": str(e)}, prompt_config["prompt"]
    
    async def call_api(self, prompt_config: PromptConfig, case: TestCase) -> Tuple[str, float, Dict[str, Any], str]:
        """根据提供商选择合适的API调用方法"""
        if prompt_config["vendor"].lower() == "openai":
            if not self.async_openai_client:
                raise ValueError("OpenAI客户端未初始化")
            return await self.call_openai_api(prompt_config, case)
        elif prompt_config["vendor"].lower() == "anthropic":
            if not self.anthropic_client:
                raise ValueError("Anthropic客户端未初始化")
            return await self.call_anthropic_api(prompt_config, case)
        else:
            raise ValueError(f"不支持的提供商: {prompt_config['vendor']}") 