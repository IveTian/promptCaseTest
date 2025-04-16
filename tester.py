#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional
from pick import pick
from tqdm import tqdm

from logger import log_info, log_warning, log_error, log_debug, log_system, LogColor
from utils import TestCase, PromptConfig, TestResult, load_prompts, load_test_cases, process_prompt
from api_clients import APIClientManager
from formatters import save_results_as_xml, save_results_as_html

class AIPromptTester:
    """AI提示词测试工具核心类，用于执行和管理测试流程"""
    
    def __init__(self):
        self.openai_key = os.environ.get("OPENAI_API_KEY", "")
        self.anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self.prompts_file = "prompts.json"
        self.cases_dir = "cases"
        self.output_dir = "testLog"
        self.config_file = ".aitest_config.json"
        self.prompts: List[PromptConfig] = []
        self.cases_map: Dict[str, List[TestCase]] = {}
        self.api_client_manager = None
        
    def _load_api_keys_from_config(self):
        """从配置文件加载API密钥"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    import json
                    config = json.load(f)
                    self.openai_key = config.get("openai_key", "")
                    self.anthropic_key = config.get("anthropic_key", "")
                    return True
            except Exception as e:
                log_error(f"加载配置文件失败: {str(e)}")
        return False
        
    def _save_api_keys_to_config(self):
        """保存API密钥到配置文件"""
        import json
        config = {
            "openai_key": self.openai_key,
            "anthropic_key": self.anthropic_key
        }
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
            # 设置文件权限为仅当前用户可读写
            os.chmod(self.config_file, 0o600)
            log_info("API密钥已保存到本地配置文件")
        except Exception as e:
            log_error(f"保存配置文件失败: {str(e)}")
        
    def setup(self):
        """初始化设置，包括API密钥配置和输出目录创建"""
        # 尝试从配置文件加载API密钥
        if not (self.openai_key and self.anthropic_key):
            self._load_api_keys_from_config()
        
        # 检查环境变量或请求用户输入API密钥
        if not self.openai_key:
            self.openai_key = input(f"{LogColor.BOLD}{LogColor.CYAN}[INPUT]{LogColor.RESET} 请输入OpenAI API密钥: ")
            os.environ["OPENAI_API_KEY"] = self.openai_key
        
        if not self.anthropic_key:
            self.anthropic_key = input(f"{LogColor.BOLD}{LogColor.CYAN}[INPUT]{LogColor.RESET} 请输入Anthropic API密钥: ")
            os.environ["ANTHROPIC_API_KEY"] = self.anthropic_key
        
        # 保存API密钥到配置文件
        self._save_api_keys_to_config()
        
        # 初始化API客户端
        self.api_client_manager = APIClientManager(self.openai_key, self.anthropic_key)
        self.api_client_manager.setup_clients()
        
        # 创建输出目录
        Path(self.output_dir).mkdir(exist_ok=True)
        
    def load_configs(self):
        """加载提示词配置和测试用例"""
        try:
            # 加载提示词配置
            self.prompts = load_prompts(self.prompts_file)
            
            # 加载所有测试用例
            self.cases_map = load_test_cases(self.cases_dir)
            
        except Exception as e:
            log_error(f"加载配置文件失败: {str(e)}")
            raise
        
    def select_tests(self) -> List[str]:
        """交互式选择要运行的测试"""
        prompt_names = [p["name"] for p in self.prompts]
        title = "请选择要测试的提示词 (空格选择/取消选择, 回车确认):"
        options = prompt_names + ["全部测试"]
        
        selected = pick(options, title, multiselect=True, min_selection_count=1)
        selected_options = [option[0] for option in selected]
        
        if "全部测试" in selected_options:
            return prompt_names
        else:
            return selected_options
    
    async def run_test(self, prompt_name: str) -> List[TestResult]:
        """运行单个提示词的所有测试用例"""
        results = []
        
        # 查找对应的提示词配置
        prompt_config = next((p for p in self.prompts if p["name"] == prompt_name), None)
        if not prompt_config:
            log_error(f"未找到名为 {prompt_name} 的提示词配置")
            return results
        
        # 查找对应的测试用例
        cases = self.cases_map.get(prompt_name, [])
        if not cases:
            log_error(f"未找到名为 {prompt_name} 的测试用例")
            return results
        
        log_system(f"开始测试提示词: {prompt_name}")
        log_debug(f"提供商: {prompt_config['vendor']}, 模型: {prompt_config['model']}")
        
        # 检查提示词中的参数
        import re
        params = re.findall(r'{{(\w+)}}', prompt_config["prompt"])
        if params:
            log_debug(f"提示词中包含以下参数: {', '.join(params)}")
            
        log_debug(f"测试用例数量: {len(cases)}")
        
        for case in tqdm(cases, desc=f"测试 {prompt_name}", bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt}"):
            log_info(f"测试用例: {case['name']} (ID: {case['id']})")
            log_debug(f"用例描述: {case.get('description', '无描述')}")
            log_debug(f"用例内容: {case['content']}")
            
            # 显示参数信息
            args_dict = {}
            if "args" in case and isinstance(case["args"], dict):
                args_dict = case["args"]
                args_str = ", ".join([f"{k}={v}" for k, v in case["args"].items()])
                log_debug(f"用例参数: {args_str}")
            elif "targetLanguage" in case:
                args_dict = {"language": case["targetLanguage"]}
                log_debug(f"用例参数(旧格式): targetLanguage={case['targetLanguage']}")
            
            try:
                # 调用API
                content, elapsed_time, tokens, processed_prompt = await self.api_client_manager.call_api(
                    prompt_config, case
                )
                
                # 记录结果
                result = {
                    "prompt_name": prompt_name,
                    "prompt_text": prompt_config["prompt"],
                    "processed_prompt": processed_prompt,
                    "model": prompt_config["model"],
                    "vendor": prompt_config["vendor"],
                    "case_id": case["id"],
                    "case_name": case["name"],
                    "case_description": case.get("description", ""),
                    "case_content": case["content"],
                    "case_args": args_dict,
                    "output_content": content,
                    "elapsed_time": elapsed_time,
                    "tokens": tokens
                }
                
                results.append(result)
                
                # 在控制台输出测试结果摘要
                log_info(f"测试用例 {case['name']} 完成")
                log_debug(f"耗时: {elapsed_time:.2f}秒")
                
                # 格式化输出token使用情况
                token_info = ", ".join([f"{k}: {v}" for k, v in tokens.items()])
                log_debug(f"Token使用: {token_info}")
                
                print(f"{LogColor.BOLD}{LogColor.CYAN}{'=' * 50}{LogColor.RESET}")  # 分隔线
                
            except Exception as e:
                log_error(f"测试用例 {case['name']} 执行失败: {str(e)}")
                # 记录错误结果
                result = {
                    "prompt_name": prompt_name,
                    "prompt_text": prompt_config["prompt"],
                    "processed_prompt": prompt_config["prompt"],
                    "model": prompt_config["model"],
                    "vendor": prompt_config["vendor"],
                    "case_id": case["id"],
                    "case_name": case["name"],
                    "case_description": case.get("description", ""),
                    "case_content": case["content"],
                    "case_args": args_dict,
                    "output_content": f"错误: {str(e)}",
                    "elapsed_time": 0.0,
                    "tokens": {"error": str(e)}
                }
                results.append(result)
            
        return results
    
    async def run_all_tests(self, selected_prompts: List[str]) -> Dict[str, List[TestResult]]:
        """运行所有选中的测试"""
        all_results = {}
        
        for prompt_name in selected_prompts:
            results = await self.run_test(prompt_name)
            if results:
                all_results[prompt_name] = results
                
        return all_results
    
    async def run(self):
        """主运行函数"""
        try:
            log_system("正在初始化测试环境...")
            self.setup()
            
            log_system("正在加载配置文件...")
            self.load_configs()
            
            log_system("请选择要运行的测试...")
            selected_prompts = self.select_tests()
            
            log_system(f"将运行以下测试: {', '.join(selected_prompts)}")
            all_results = await self.run_all_tests(selected_prompts)
            
            log_system("所有测试已完成，正在保存结果...")
            # self.save_results_as_xml(all_results)  # 旧方法，可选
            save_results_as_html(all_results, self.output_dir)  # 新方法
            
            log_system("测试完成！")
        except Exception as e:
            log_error(f"测试过程中发生错误: {str(e)}")
            raise 