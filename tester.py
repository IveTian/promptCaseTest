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
        # 控制并行执行的参数
        self.max_prompt_concurrency = 5  # 最大提示词并发数
        self.max_case_concurrency = 3    # 每个提示词的最大测试用例并发数
        # 进度跟踪
        self.total_cases = 0
        self.completed_cases = 0
        self._progress_lock = None  # 将在run()方法中初始化
        # 显示选项
        self.show_preview = False
        self.preview_length = 100
        self.quiet_mode = False
        
    def _load_api_keys_from_config(self):
        """从配置文件加载API密钥和并发设置"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    import json
                    config = json.load(f)
                    self.openai_key = config.get("openai_key", "")
                    self.anthropic_key = config.get("anthropic_key", "")
                    # 加载并发设置
                    self.max_prompt_concurrency = config.get("max_prompt_concurrency", 5)
                    self.max_case_concurrency = config.get("max_case_concurrency", 3)
                    return True
            except Exception as e:
                log_error(f"加载配置文件失败: {str(e)}")
        return False
        
    def _save_api_keys_to_config(self):
        """保存API密钥和并发设置到配置文件"""
        import json
        config = {
            "openai_key": self.openai_key,
            "anthropic_key": self.anthropic_key,
            "max_prompt_concurrency": self.max_prompt_concurrency,
            "max_case_concurrency": self.max_case_concurrency
        }
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
            # 设置文件权限为仅当前用户可读写
            os.chmod(self.config_file, 0o600)
            log_info("配置已保存到本地配置文件")
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
        """并行运行单个提示词的所有测试用例"""
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
        
        if not self.quiet_mode:
            log_system(f"开始测试提示词: {prompt_name}")
            log_debug(f"提供商: {prompt_config['vendor']}, 模型: {prompt_config['model']}")
        
        # 检查提示词中的参数
        import re
        params = re.findall(r'{{(\w+)}}', prompt_config["prompt"])
        if params and not self.quiet_mode:
            log_debug(f"提示词中包含以下参数: {', '.join(params)}")
            
        if not self.quiet_mode:
            log_debug(f"测试用例数量: {len(cases)}")
        
        # 创建每个测试用例的任务
        async def run_single_case(case):
            case_id = case['id']
            case_name = case['name']
            
            if not self.quiet_mode:
                log_info(f"[{prompt_name}] 开始测试用例: {case_name} (ID: {case_id})")
            
            # 显示参数信息
            args_dict = {}
            if "args" in case and isinstance(case["args"], dict):
                args_dict = case["args"]
                if not self.quiet_mode:
                    args_str = ", ".join([f"{k}={v}" for k, v in case["args"].items()])
                    log_debug(f"用例参数: {args_str}")
            elif "targetLanguage" in case:
                args_dict = {"language": case["targetLanguage"]}
                if not self.quiet_mode:
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
                    "case_id": case_id,
                    "case_name": case_name,
                    "case_description": case.get("description", ""),
                    "case_content": case["content"],
                    "case_args": args_dict,
                    "output_content": content,
                    "elapsed_time": elapsed_time,
                    "tokens": tokens
                }
                
                # 更新总体进度
                await self._update_progress()
                
                # 在控制台输出测试结果摘要
                if not self.quiet_mode:
                    log_info(f"[{prompt_name}] 测试用例 {case_name} 完成，耗时: {elapsed_time:.2f}秒")
                    
                    # 显示简短的输出预览
                    if self.show_preview:
                        preview = content[:self.preview_length] + ("..." if len(content) > self.preview_length else "")
                        log_info(f"[{prompt_name}] 输出预览: {preview}")
                    
                    # 格式化输出token使用情况
                    token_info = ", ".join([f"{k}: {v}" for k, v in tokens.items()])
                    log_debug(f"Token使用: {token_info}")
                    
                    # 分隔线
                    print(f"{LogColor.BOLD}{LogColor.CYAN}[{prompt_name}-{case_id}] 测试完成 {'=' * 20}{LogColor.RESET}")
                
                return result
                
            except Exception as e:
                # 更新总体进度
                await self._update_progress()
                
                if not self.quiet_mode:
                    log_error(f"[{prompt_name}] 测试用例 {case_name} 执行失败: {str(e)}")
                
                # 记录错误结果
                result = {
                    "prompt_name": prompt_name,
                    "prompt_text": prompt_config["prompt"],
                    "processed_prompt": prompt_config["prompt"],
                    "model": prompt_config["model"],
                    "vendor": prompt_config["vendor"],
                    "case_id": case_id,
                    "case_name": case_name,
                    "case_description": case.get("description", ""),
                    "case_content": case["content"],
                    "case_args": args_dict,
                    "output_content": f"错误: {str(e)}",
                    "elapsed_time": 0.0,
                    "tokens": {"error": str(e)}
                }
                return result
        
        # 并行执行所有测试用例，但限制并发数
        if not self.quiet_mode:
            log_system(f"为 {prompt_name} 并行执行 {len(cases)} 个测试用例 (最大并发数: {self.max_case_concurrency})...")
        
        semaphore = asyncio.Semaphore(self.max_case_concurrency)
        
        async def run_with_semaphore(case):
            async with semaphore:
                return await run_single_case(case)
        
        case_tasks = [run_with_semaphore(case) for case in cases]
        results = await asyncio.gather(*case_tasks)
            
        return results
    
    async def run_all_tests(self, selected_prompts: List[str]) -> Dict[str, List[TestResult]]:
        """并行运行所有选中的测试，但限制并发数量"""
        all_results = {}
        
        # 计算总测试用例数量
        self.total_cases = sum(len(self.cases_map.get(prompt_name, [])) for prompt_name in selected_prompts)
        log_system(f"总共将执行 {self.total_cases} 个测试用例")
        
        # 创建信号量控制提示词并发数
        prompt_semaphore = asyncio.Semaphore(self.max_prompt_concurrency)
        
        async def run_prompt_with_semaphore(prompt_name):
            async with prompt_semaphore:
                return prompt_name, await self.run_test(prompt_name)
        
        # 创建所有测试的任务列表
        tasks = [run_prompt_with_semaphore(prompt_name) for prompt_name in selected_prompts]
        
        # 并行执行所有测试任务
        if not self.quiet_mode:
            log_system(f"正在并行执行 {len(tasks)} 个提示词测试 (最大并发数: {self.max_prompt_concurrency})...")
        
        results = await asyncio.gather(*tasks)
        
        # 将结果整理到字典中
        for prompt_name, prompt_results in results:
            if prompt_results:
                all_results[prompt_name] = prompt_results
                
        return all_results
    
    async def _update_progress(self):
        """更新并显示总体进度"""
        async with self._progress_lock:
            self.completed_cases += 1
            progress = (self.completed_cases / self.total_cases) * 100
            progress_bar = "█" * int(progress / 2) + "░" * (50 - int(progress / 2))
            print(f"\r{LogColor.BOLD}{LogColor.GREEN}进度 [{self.completed_cases}/{self.total_cases}] {progress:.1f}% |{progress_bar}|{LogColor.RESET}", end="", flush=True)
            if self.completed_cases == self.total_cases:
                print(f"\n{LogColor.BOLD}{LogColor.GREEN}所有测试用例已完成!{LogColor.RESET}")  # 完成后换行
    
    async def run(self):
        """主运行函数"""
        try:
            log_system("正在初始化测试环境...")
            self.setup()
            
            log_system("正在加载配置文件...")
            self.load_configs()
            
            log_system("请选择要运行的测试...")
            selected_prompts = self.select_tests()
            
            # 初始化进度跟踪
            self.completed_cases = 0
            self._progress_lock = asyncio.Lock()
            
            log_system(f"将运行以下测试: {', '.join(selected_prompts)}")
            all_results = await self.run_all_tests(selected_prompts)
            
            log_system("所有测试已完成，正在保存结果...")
            save_results_as_html(all_results, self.output_dir)
            
            log_system("测试完成！")
        except Exception as e:
            log_error(f"测试过程中发生错误: {str(e)}")
            raise 