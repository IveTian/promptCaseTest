#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from pick import pick
from tqdm import tqdm
import time
import threading
import sys

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
        self.max_round_concurrency = 1   # 最大轮次并发数
        # 进度跟踪
        self.total_cases = 0
        self.completed_cases = 0
        self._progress_lock = None  # 将在run()方法中初始化
        # 显示选项
        self.show_preview = False
        self.preview_length = 100
        self.quiet_mode = False
        # 加载动画控制
        self._loading_stop = None
        self._loading_thread = None
        # 进度条锁
        self._console_lock = asyncio.Lock()
        # 防抖动更新变量
        self._last_console_update = 0
        self._console_update_interval = 0.2  # 控制台更新最小间隔(秒)
        # 进度保存
        self._round_progress = {}
        self._prompt_progress = {}
        self._case_progress = {}
        
    def _start_loading_animation(self, message):
        """启动加载动画"""
        self._loading_stop = threading.Event()
        self._loading_thread = threading.Thread(target=self._loading_animation, args=(message,))
        self._loading_thread.daemon = True
        self._loading_thread.start()
        
    def _stop_loading_animation(self, success=True):
        """停止加载动画"""
        if self._loading_stop and not self._loading_stop.is_set():
            self._loading_stop.set()
            if self._loading_thread:
                self._loading_thread.join()
            # 清除当前行
            sys.stdout.write("\r" + " " * 100)
            sys.stdout.write("\r")
            sys.stdout.flush()
            
    def _loading_animation(self, message):
        """显示加载动画"""
        spinner = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        i = 0
        last_update = 0
        while not self._loading_stop.is_set():
            i = (i + 1) % len(spinner)
            # 使用\r回车不换行来覆盖当前行，不清屏
            sys.stdout.write(f"\r{LogColor.BOLD}{LogColor.CYAN}{spinner[i]}{LogColor.RESET} {message}")
            sys.stdout.flush()
            time.sleep(0.03)  # 进一步加快动画速度，从0.05改为0.03
        
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
    
    async def run_test(self, prompt_name: str, round_num: int) -> List[TestResult]:
        """并行运行单个提示词的所有测试用例
        
        参数:
        - prompt_name: 提示词名称
        - round_num: 测试轮次
        """
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
            
        # 初始化当前提示词的进度
        total_prompt_cases = len(cases)
        
        # 存储提示词进度
        async with self._console_lock:
            key = f"round_{round_num}_{prompt_name}"
            self._prompt_progress[key] = {"total": total_prompt_cases, "completed": 0}
            await self._update_console_output(round_num)
        
        # 创建每个测试用例的任务
        async def run_single_case(case_idx: int, case: dict):
            case_id = case['id']
            case_name = case['name']
            
            # 获取参数信息
            args_dict = {}
            if "args" in case and isinstance(case["args"], dict):
                args_dict = case["args"]
            elif "targetLanguage" in case:
                args_dict = {"language": case["targetLanguage"]}
            
            # 状态列表用于动态显示执行进度
            status_list = ["等待中", "开始调用", "调用中", "响应中", "处理数据", "完成"]
            key = f"round_{round_num}_{prompt_name}_{case_idx}"
            
            # 更新案例状态 - 开始执行（使用更简单的锁机制）
            async with self._console_lock:
                self._case_progress[key] = {
                    "status": status_list[1],  # 开始调用
                    "case_name": case_name,
                    "vendor": prompt_config['vendor'],
                    "model": prompt_config['model'],
                    "index": case_idx + 1,
                    "total": total_prompt_cases
                }
            # 尝试更新控制台输出，如果时间允许
            await self._update_console_output(round_num)
            
            try:
                # 更新状态 - 调用中（无需获取锁，直接更新状态）
                self._case_progress[key]["status"] = status_list[2]
                # 尝试更新控制台输出，如果时间允许
                await self._update_console_output(round_num)
                
                # 调用API
                content, elapsed_time, tokens, processed_prompt = await self.api_client_manager.call_api(
                    prompt_config, case
                )
                
                # 更新状态 - 处理数据（无需获取锁，直接更新状态）
                self._case_progress[key]["status"] = status_list[4]
                # 尝试更新控制台输出，如果时间允许
                await self._update_console_output(round_num)
                
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
                
                # 更新提示词进度和案例状态（这里需要锁以保证计数正确）
                async with self._console_lock:
                    # 更新提示词进度 - 修复KeyError
                    prompt_key = f"round_{round_num}_{prompt_name}"
                    if prompt_key in self._prompt_progress:
                        self._prompt_progress[prompt_key]["completed"] += 1
                    # 更新案例状态 - 完成
                    self._case_progress[key]["status"] = status_list[5]
                    # 更新全局进度
                    self.completed_cases += 1
                # 尝试更新控制台输出，如果时间允许
                await self._update_console_output(round_num)
                
                return result
                
            except Exception as e:
                # 更新进度和案例状态（这里需要锁以保证计数正确）
                async with self._console_lock:
                    # 更新提示词进度 - 修复KeyError
                    prompt_key = f"round_{round_num}_{prompt_name}"
                    if prompt_key in self._prompt_progress:
                        self._prompt_progress[prompt_key]["completed"] += 1
                    # 更新案例状态 - 错误
                    self._case_progress[key]["status"] = "错误"
                    # 更新全局进度
                    self.completed_cases += 1
                # 尝试更新控制台输出，如果时间允许
                await self._update_console_output(round_num)
                
                # 记录错误结果
                log_error(f"用例 {case_name} 执行失败: {str(e)}")
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
        semaphore = asyncio.Semaphore(self.max_case_concurrency)
        
        async def run_with_semaphore(case_idx: int, case: dict):
            async with semaphore:
                return await run_single_case(case_idx, case)
        
        # 创建所有测试用例的任务
        case_tasks = [run_with_semaphore(i, case) for i, case in enumerate(cases)]
        results = await asyncio.gather(*case_tasks)
            
        return results
    
    async def run_all_tests(self, selected_prompts: List[str], round_num: int) -> Dict[str, List[TestResult]]:
        """并行运行所有选中的测试，但限制并发数量
        
        参数:
        - selected_prompts: 选中的提示词
        - round_num: 测试轮次
        """
        all_results = {}
        
        # 计算轮次内的测试用例数量
        round_total_cases = sum(len(self.cases_map.get(prompt_name, [])) for prompt_name in selected_prompts)
        
        if round_total_cases == 0:
            log_warning("未找到任何测试用例")
            return all_results
        
        # 初始化轮次进度
        async with self._console_lock:
            self._round_progress[round_num] = {"total": round_total_cases, "completed": 0}
        # 尝试更新控制台输出，如果时间允许
        await self._update_console_output(round_num)
        
        # 创建信号量控制提示词并发数
        prompt_semaphore = asyncio.Semaphore(self.max_prompt_concurrency)
        
        async def run_prompt_with_semaphore(prompt_name):
            async with prompt_semaphore:
                results = await self.run_test(prompt_name, round_num)
                # 更新轮次进度 - 只更新计数器，而不强制更新控制台
                async with self._console_lock:
                    # 安全地更新轮次进度，检查键是否存在
                    if round_num in self._round_progress:
                        self._round_progress[round_num]["completed"] += len(results)
                # 尝试更新控制台输出，如果时间允许
                await self._update_console_output(round_num)
                return prompt_name, results
        
        # 创建所有测试的任务列表
        tasks = [run_prompt_with_semaphore(prompt_name) for prompt_name in selected_prompts]
        
        # 并行执行所有测试任务
        results = await asyncio.gather(*tasks)
        
        # 将结果整理到字典中
        for prompt_name, prompt_results in results:
            if prompt_results:
                all_results[prompt_name] = prompt_results
                
        return all_results
    
    async def run_round(self, selected_prompts: List[str], round_num: int) -> Dict[str, List[TestResult]]:
        """运行单轮测试
        
        参数:
        - selected_prompts: 选中的提示词
        - round_num: 测试轮次
        """
        return await self.run_all_tests(selected_prompts, round_num)
    
    async def run(self):
        """主运行函数"""
        try:
            self._start_loading_animation("正在初始化测试环境")
            self.setup()
            self._stop_loading_animation()
            
            # 获取当前spinner字符
            spinner_chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
            spinner_idx = int(time.time() * 10) % len(spinner_chars)
            spinner_char = spinner_chars[spinner_idx]
            
            log_info(f"✓ 测试环境初始化完成")
            
            self._start_loading_animation("正在加载配置文件")
            self.load_configs()
            self._stop_loading_animation()
            
            # 更新spinner字符
            spinner_idx = int(time.time() * 10) % len(spinner_chars)
            spinner_char = spinner_chars[spinner_idx]
            
            log_info(f"✓ 配置文件加载完成")
            
            # 更新spinner字符
            spinner_idx = int(time.time() * 10) % len(spinner_chars)
            spinner_char = spinner_chars[spinner_idx]
            
            log_info(f"请选择要运行的测试...")
            selected_prompts = self.select_tests()
            
            # 询问用户输入测试轮次
            test_rounds = 1
            try:
                rounds_input = input(f"{LogColor.BOLD}{LogColor.CYAN}?{LogColor.RESET} 请输入测试轮次 (默认1): ")
                if rounds_input.strip():
                    test_rounds = max(1, int(rounds_input))
            except ValueError:
                log_warning("输入的轮次无效，将使用默认值1")
                test_rounds = 1
                
            # 询问用户输入轮次并发数
            try:
                concurrency_input = input(f"{LogColor.BOLD}{LogColor.CYAN}?{LogColor.RESET} 请输入轮次并发数 (默认1): ")
                if concurrency_input.strip():
                    self.max_round_concurrency = max(1, min(test_rounds, int(concurrency_input)))
            except ValueError:
                log_warning("输入的并发数无效，将使用默认值1")
                self.max_round_concurrency = 1
            
            # 更新spinner字符
            spinner_idx = int(time.time() * 10) % len(spinner_chars)
            spinner_char = spinner_chars[spinner_idx]
                
            log_info(f"将执行 {test_rounds} 轮测试，轮次并发数: {self.max_round_concurrency}")
            
            # 初始化进度锁
            self._progress_lock = asyncio.Lock()
            
            # 计算总测试用例数量 = 轮次 * 每轮的测试用例数
            cases_per_round = sum(len(self.cases_map.get(prompt_name, [])) for prompt_name in selected_prompts)
            self.total_cases = test_rounds * cases_per_round
            self.completed_cases = 0
            
            # 存储多轮测试结果
            all_rounds_results = {}
            
            # 创建轮次信号量
            round_semaphore = asyncio.Semaphore(self.max_round_concurrency)
            
            async def run_round_with_semaphore(round_num):
                async with round_semaphore:
                    return round_num, await self.run_round(selected_prompts, round_num)
            
            # 创建所有轮次的任务
            round_tasks = [run_round_with_semaphore(i+1) for i in range(test_rounds)]
            
            # 并行执行所有轮次
            round_results = await asyncio.gather(*round_tasks)
            
            # 整理结果
            for round_num, results in round_results:
                all_rounds_results[f"第{round_num}轮"] = results
            
            # 清屏，准备显示保存信息
            os.system('cls' if os.name == 'nt' else 'clear')
            
            self._start_loading_animation("正在保存测试结果")
            # 使用修改后的格式保存结果
            html_file_path = save_results_as_html(all_rounds_results, self.output_dir)
            self._stop_loading_animation()
            
            # 更新spinner字符
            spinner_idx = int(time.time() * 10) % len(spinner_chars)
            spinner_char = spinner_chars[spinner_idx]
            
            log_info(f"✓ 测试完成! 结果已保存到: {os.path.basename(html_file_path)}")
            
            # 询问用户是否打开生成的HTML报告
            import platform
            
            # 根据操作系统设置打开HTML文件的命令
            open_command = None
            if platform.system() == 'Darwin':  # macOS
                open_command = 'open'
            elif platform.system() == 'Windows':
                open_command = 'start'
            elif platform.system() == 'Linux':
                open_command = 'xdg-open'
            
            # 只有在支持的系统上询问
            if open_command:
                # 询问用户是否打开文件
                print(f"{LogColor.BOLD}{LogColor.CYAN}?{LogColor.RESET} 是否打开测试报告？(Y/n)", end='', flush=True)
                
                # 获取用户输入，不需要按Enter确认
                import termios
                import tty
                
                fd = sys.stdin.fileno()
                old_settings = termios.tcgetattr(fd)
                try:
                    tty.setraw(fd)
                    answer = sys.stdin.read(1).lower()
                finally:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                
                # 默认为"是"，或者用户输入Y/y
                if answer == 'y' or answer == '\r' or answer == '\n' or answer == '':
                    print(f"\r{LogColor.BOLD}{LogColor.GREEN}✓{LogColor.RESET} 正在打开测试报告...")
                    os.system(f'{open_command} "{html_file_path}"')
                else:
                    print(f"\r{LogColor.BOLD}{LogColor.YELLOW}i{LogColor.RESET} 您选择不打开报告。报告保存在: {html_file_path}")
                
        except KeyboardInterrupt:
            # 处理Ctrl+C中断
            # 确保停止所有加载动画
            if self._loading_stop and not self._loading_stop.is_set():
                self._stop_loading_animation(success=False)
                
            # 清屏并打印友好的退出消息
            os.system('cls' if os.name == 'nt' else 'clear')
            print("\n")
            log_warning("测试被用户中断。")
            
            # 如果有部分结果，询问是否保存
            if hasattr(self, 'completed_cases') and self.completed_cases > 0:
                try:
                    print(f"{LogColor.BOLD}{LogColor.CYAN}?{LogColor.RESET} 是否保存已完成的测试结果？(Y/n)", end='', flush=True)
                    
                    # 获取用户输入
                    import termios
                    import tty
                    
                    fd = sys.stdin.fileno()
                    old_settings = termios.tcgetattr(fd)
                    try:
                        tty.setraw(fd)
                        answer = sys.stdin.read(1).lower()
                    finally:
                        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                    
                    if answer == 'y' or answer == '\r' or answer == '\n' or answer == '':
                        # 保存部分结果
                        print("\r", end="", flush=True)
                        log_info("正在保存已完成的测试结果...")
                        
                        # 收集已完成的测试结果
                        partial_results = {}
                        # 这里可以根据需要收集相关数据保存
                        # 为简化处理，我们创建一个最基础的结果记录
                        partial_results["部分测试结果"] = {
                            "info": {
                                "completed": self.completed_cases,
                                "total": self.total_cases,
                                "interrupted_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                                "note": "此结果不完整，测试被用户中断"
                            }
                        }
                        
                        # 保存为HTML
                        html_file_path = save_results_as_html(partial_results, self.output_dir, 
                                                             filename_prefix="interrupted_test")
                        log_info(f"部分测试结果已保存至: {os.path.basename(html_file_path)}")
                    else:
                        print("\r", end="", flush=True)
                        log_info("未保存测试结果。")
                
                except Exception as e:
                    log_error(f"保存部分结果时出错: {str(e)}")
            
            print("\n")
            log_info("测试工具已退出。")
            sys.exit(0)
            
        except Exception as e:
            if self._loading_stop and not self._loading_stop.is_set():
                self._stop_loading_animation(success=False)
            log_error(f"测试过程中发生错误: {str(e)}")
            raise 

    async def _update_console_output(self, current_round: int = None):
        """更新控制台输出，显示所有进度信息
        
        参数:
        - current_round: 当前执行轮次，用于高亮显示
        """
        # 检查是否应该更新显示（防抖动）
        current_time = time.time()
        if current_time - self._last_console_update < self._console_update_interval:
            # 如果距离上次更新时间太短，则跳过本次更新
            return
            
        # 更新最后刷新时间
        self._last_console_update = current_time
        
        # 使用局部清屏方法替代全屏清除，提高性能
        # 首先计算需要输出的行数
        lines_count = 1  # 全局进度条
        lines_count += 1  # 空行
        for round_num in self._round_progress:
            lines_count += 1  # 轮次进度条
            # 每个轮次的提示词数量
            prompt_count = sum(1 for k in self._prompt_progress if k.startswith(f"round_{round_num}_"))
            lines_count += prompt_count
            # 每个提示词的测试用例数量
            for key in self._prompt_progress:
                if key.startswith(f"round_{round_num}_"):
                    prompt_name = key.split('_', 2)[2]
                    case_count = sum(1 for k in self._case_progress if k.startswith(f"round_{round_num}_{prompt_name}_"))
                    lines_count += case_count
        
        # 回到控制台顶部（如果有必要）并清除之前的输出
        sys.stdout.write(f"\033[{lines_count}A\033[J" if lines_count > 1 else "\r\033[J")
        
        # 动态加载动画字符 - 增加频率修饰因子，使刷新更快
        spinner_chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        spinner_idx = int(time.time() * 20) % len(spinner_chars)  # 增加频率，从15改为20
        spinner_char = spinner_chars[spinner_idx]
        
        # 显示全局进度
        progress = (self.completed_cases / self.total_cases) * 100 if self.total_cases > 0 else 0
        bar_length = 30
        filled_length = int(bar_length * self.completed_cases // max(1, self.total_cases))
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        status = f"[{self.completed_cases}/{self.total_cases}]"
        
        print(f"{LogColor.BOLD}{LogColor.CYAN}{spinner_char}{LogColor.RESET} 执行测试 {status} {progress:.1f}% |{bar}|")
        print()
        
        # 显示每个轮次的进度
        for round_num, round_data in sorted(self._round_progress.items()):
            progress = (round_data["completed"] / round_data["total"]) * 100 if round_data["total"] > 0 else 0
            bar_length = 30
            filled_length = int(bar_length * round_data["completed"] // max(1, round_data["total"]))
            bar = '█' * filled_length + '░' * (bar_length - filled_length)
            
            # 高亮当前轮次
            prefix = LogColor.BOLD + LogColor.CYAN if round_num == current_round else ""
            suffix = LogColor.RESET if round_num == current_round else ""
            
            # 对每个轮次使用不同的spinner（微小时差）让动画看起来更流畅
            round_spinner_idx = (spinner_idx + round_num) % len(spinner_chars)
            round_spinner_char = spinner_chars[round_spinner_idx]
            
            # 使用动态spinner
            print(f"{prefix}{round_spinner_char}{suffix} 执行第{round_num}轮 {progress:.1f}% |{bar}|")
            
            # 显示轮次中每个提示词的进度
            for key, prompt_data in self._prompt_progress.items():
                if key.startswith(f"round_{round_num}_"):
                    prompt_name = key.split('_', 2)[2]
                    prompt_progress = (prompt_data["completed"] / prompt_data["total"]) * 100 if prompt_data["total"] > 0 else 0
                    prompt_bar_length = 30
                    prompt_filled_length = int(prompt_bar_length * prompt_data["completed"] // max(1, prompt_data["total"]))
                    prompt_bar = '█' * prompt_filled_length + '░' * (prompt_bar_length - prompt_filled_length)
                    
                    # 每个提示词使用略微不同的spinner，营造更流畅的动画效果
                    prompt_spinner_idx = (spinner_idx + hash(prompt_name) % 5) % len(spinner_chars)
                    prompt_spinner_char = spinner_chars[prompt_spinner_idx]
                    
                    # 使用动态spinner
                    print(f"  {prefix}{prompt_spinner_char}{suffix} 执行 {prompt_name} 的测试用例 {prompt_progress:.1f}% |{prompt_bar}|")
                    
                    # 显示正在执行的测试用例
                    for case_key, case_data in self._case_progress.items():
                        if case_key.startswith(f"round_{round_num}_{prompt_name}_"):
                            # 每个用例使用略微不同的spinner，增强视觉动态效果
                            case_idx = case_data["index"]
                            case_spinner_idx = (spinner_idx + case_idx) % len(spinner_chars)
                            case_spinner_char = spinner_chars[case_spinner_idx]
                            
                            # 使用动态spinner
                            print(f"    {prefix}{case_spinner_char}{suffix} 执行测试 [{case_data['index']}/{case_data['total']}] [{prompt_name}] {case_data['status']} {case_data['vendor']} API ({case_data['model']}) 处理用例 {case_data['case_name']}...")
        
        # 保持光标在底部
        print() 