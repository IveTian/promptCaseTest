#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import time
import datetime
import xml.dom.minidom
import xml.etree.ElementTree as ET
from pathlib import Path
import asyncio
import argparse
import sys
import glob
from typing import Dict, List, Any, Optional, Tuple

# 添加第三方依赖库
try:
    from openai import OpenAI, AsyncOpenAI
    import anthropic
    from pick import pick
    from tqdm import tqdm
except ImportError:
    print("请安装必要的依赖库:")
    print("pip install openai anthropic pick tqdm")
    sys.exit(1)

# 自定义类型
TestCase = Dict[str, Any]
PromptConfig = Dict[str, Any]
TestResult = Dict[str, Any]

# 定义日志颜色和格式
class LogColor:
    # 字体颜色
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    # 效果
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    # 恢复默认设置
    RESET = '\033[0m'

def log_info(message: str):
    """打印信息日志"""
    print(f"{LogColor.BOLD}{LogColor.GREEN}[INFO]{LogColor.RESET} {message}")

def log_warning(message: str):
    """打印警告日志"""
    print(f"{LogColor.BOLD}{LogColor.YELLOW}[WARN]{LogColor.RESET} {message}")

def log_error(message: str):
    """打印错误日志"""
    print(f"{LogColor.BOLD}{LogColor.RED}[ERR]{LogColor.RESET} {message}")

def log_debug(message: str):
    """打印调试日志"""
    print(f"{LogColor.BOLD}{LogColor.BLUE}[DEBUG]{LogColor.RESET} {message}")

def log_ai_output(message: str):
    """打印AI输出日志"""
    print(f"{LogColor.BOLD}{LogColor.MAGENTA}[AI]{LogColor.RESET} {message}")

def log_system(message: str):
    """打印系统日志"""
    print(f"{LogColor.BOLD}{LogColor.CYAN}[SYS]{LogColor.RESET} {message}")

class AIPromptTester:
    def __init__(self):
        self.openai_key = os.environ.get("OPENAI_API_KEY", "")
        self.anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self.prompts_file = "prompts.json"
        self.cases_dir = "cases"
        self.output_dir = "testLog"
        self.config_file = ".aitest_config.json"
        self.prompts: List[PromptConfig] = []
        self.cases_map: Dict[str, List[TestCase]] = {}
        self.openai_client = None
        self.async_openai_client = None
        self.anthropic_client = None
        
    def _load_api_keys_from_config(self):
        """从配置文件加载API密钥"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.openai_key = config.get("openai_key", "")
                    self.anthropic_key = config.get("anthropic_key", "")
                    return True
            except Exception as e:
                log_error(f"加载配置文件失败: {str(e)}")
        return False
        
    def _save_api_keys_to_config(self):
        """保存API密钥到配置文件"""
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
        self.openai_client = OpenAI(api_key=self.openai_key)
        self.async_openai_client = AsyncOpenAI(api_key=self.openai_key)
        self.anthropic_client = anthropic.Anthropic(api_key=self.anthropic_key)
        
        # 创建输出目录
        Path(self.output_dir).mkdir(exist_ok=True)
        
    def load_configs(self):
        """加载提示词配置和测试用例"""
        try:
            # 加载提示词配置
            with open(self.prompts_file, 'r', encoding='utf-8') as f:
                prompts_data = json.load(f)
                self.prompts = prompts_data.get("prompts", [])
            
            # 加载所有测试用例
            case_files = glob.glob(f"{self.cases_dir}/*.json")
            for case_file in case_files:
                try:
                    with open(case_file, 'r', encoding='utf-8') as f:
                        case_data = json.load(f)
                        case_name = case_data.get("caseName", "")
                        if case_name:
                            self.cases_map[case_name] = case_data.get("cases", [])
                except Exception as e:
                    log_error(f"加载测试用例文件 {case_file} 失败: {str(e)}")
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
    
    async def call_openai_api(self, prompt_config: PromptConfig, case: TestCase) -> Tuple[str, float, Dict[str, Any], str]:
        """调用OpenAI API并返回结果、耗时、token使用情况和处理后的提示词"""
        start_time = time.time()
        try:
            # 处理提示词中的变量替换
            processed_prompt = self._process_prompt(prompt_config, case)
            
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
            processed_prompt = self._process_prompt(prompt_config, case)
            
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
    
    def _process_prompt(self, prompt_config: PromptConfig, case: TestCase) -> str:
        """处理提示词中的变量替换，从测试用例的args字段获取参数值"""
        prompt = prompt_config["prompt"]
        
        # 查找所有{{parameter}}模式的参数
        import re
        params = re.findall(r'{{(\w+)}}', prompt)
        
        if params:
            log_debug(f"在提示词中检测到以下参数: {', '.join(params)}")
            
            # 检查是否有args字段
            if "args" in case and isinstance(case["args"], dict):
                args = case["args"]
                
                # 记录参数替换情况
                replaced_params = []
                missing_params = []
                
                # 替换所有找到的参数
                for param in params:
                    placeholder = f"{{{{{param}}}}}"
                    if param in args:
                        value = args[param]
                        prompt = prompt.replace(placeholder, str(value))
                        replaced_params.append(f"{param}={value}")
                        log_debug(f"替换参数: {placeholder} -> {value}")
                    else:
                        missing_params.append(param)
                
                # 记录参数替换结果
                if replaced_params:
                    log_info(f"参数替换: {', '.join(replaced_params)}")
                
                # 警告缺失的参数
                if missing_params:
                    log_warning(f"测试用例缺少以下参数: {', '.join(missing_params)}")
            
            # 兼容旧代码中特殊处理translate的targetLanguage参数
            elif prompt_config["name"] == "translate" and "targetLanguage" in case:
                # 如果找到了language参数并且有targetLanguage字段，进行替换
                if "language" in params:
                    prompt = prompt.replace("{{language}}", case["targetLanguage"])
                    log_info(f"使用旧格式替换参数: {{language}} -> {case['targetLanguage']}")
                else:
                    log_warning(f"提示词需要language参数，但在提示词模板中未找到 {{{{language}}}} 占位符")
            else:
                log_warning(f"提示词需要参数 {', '.join(params)}，但测试用例中没有提供args字段")
        
        return prompt
    
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
            
            # 根据vendor选择API
            if prompt_config["vendor"].lower() == "openai":
                content, elapsed_time, tokens, processed_prompt = await self.call_openai_api(prompt_config, case)
            elif prompt_config["vendor"].lower() == "anthropic":
                content, elapsed_time, tokens, processed_prompt = await self.call_anthropic_api(prompt_config, case)
            else:
                log_error(f"不支持的提供商: {prompt_config['vendor']}")
                continue
            
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
            
        return results
    
    async def run_all_tests(self, selected_prompts: List[str]) -> Dict[str, List[TestResult]]:
        """运行所有选中的测试"""
        all_results = {}
        
        for prompt_name in selected_prompts:
            results = await self.run_test(prompt_name)
            if results:
                all_results[prompt_name] = results
                
        return all_results
    
    def save_results_as_xml(self, all_results: Dict[str, List[TestResult]]):
        """将测试结果保存为XML文件"""
        # 创建XML根元素
        root = ET.Element("TestResults")
        
        # 添加测试时间
        test_time = ET.SubElement(root, "TestTime")
        test_time.text = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 添加每个提示词的测试结果
        for prompt_name, results in all_results.items():
            prompt_elem = ET.SubElement(root, "PromptTest")
            prompt_elem.set("name", prompt_name)
            
            for result in results:
                case_elem = ET.SubElement(prompt_elem, "Case")
                case_elem.set("id", result["case_id"])
                case_elem.set("name", result["case_name"])
                
                # 添加用例描述
                if result.get("case_description"):
                    description = ET.SubElement(case_elem, "Description")
                    description.text = result["case_description"]
                
                # 添加提示词信息
                prompt_info = ET.SubElement(case_elem, "PromptInfo")
                model = ET.SubElement(prompt_info, "Model")
                model.text = result["model"]
                vendor = ET.SubElement(prompt_info, "Vendor")
                vendor.text = result["vendor"]
                
                # 添加原始提示词和处理后的提示词
                original_prompt = ET.SubElement(prompt_info, "OriginalPrompt")
                original_prompt.text = result["prompt_text"]
                processed_prompt = ET.SubElement(prompt_info, "ProcessedPrompt")
                processed_prompt.text = result.get("processed_prompt", result["prompt_text"])
                
                # 添加用例参数
                if result.get("case_args"):
                    args_elem = ET.SubElement(case_elem, "Args")
                    for key, value in result["case_args"].items():
                        arg_elem = ET.SubElement(args_elem, key)
                        arg_elem.text = str(value)
                
                # 添加用例内容
                case_content = ET.SubElement(case_elem, "CaseContent")
                case_content.text = result["case_content"]
                
                # 添加输出内容
                output = ET.SubElement(case_elem, "Output")
                output.text = result["output_content"]
                
                # 添加性能指标
                metrics = ET.SubElement(case_elem, "Metrics")
                elapsed_time = ET.SubElement(metrics, "ElapsedTime")
                elapsed_time.text = str(result["elapsed_time"])
                
                tokens = ET.SubElement(metrics, "Tokens")
                for key, value in result["tokens"].items():
                    token_elem = ET.SubElement(tokens, key)
                    token_elem.text = str(value)
        
        # 美化XML
        xml_str = ET.tostring(root, encoding="utf-8")
        dom = xml.dom.minidom.parseString(xml_str)
        pretty_xml = dom.toprettyxml(indent="  ")
        
        # 生成带时间戳的文件名
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = os.path.join(self.output_dir, f"test_results_{timestamp}.xml")
        
        # 保存文件
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(pretty_xml)
            
        log_info(f"测试结果已保存到: {file_path}")
    
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
            self.save_results_as_xml(all_results)
            
            log_system("测试完成！")
        except Exception as e:
            log_error(f"测试过程中发生错误: {str(e)}")
            raise

async def main():
    tester = AIPromptTester()
    await tester.run()

if __name__ == "__main__":
    asyncio.run(main())
