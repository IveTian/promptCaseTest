#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import os
import json
from typing import Dict, Any, List
import glob

from logger import log_info, log_warning, log_debug, log_error

# 自定义类型
TestCase = Dict[str, Any]
PromptConfig = Dict[str, Any]
TestResult = Dict[str, Any]

def process_prompt(prompt_config: PromptConfig, case: TestCase) -> str:
    """处理提示词中的变量替换，从测试用例的args字段获取参数值"""
    prompt = prompt_config["prompt"]
    
    # 查找所有{{parameter}}模式的参数
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

def load_prompts(prompts_file: str) -> List[PromptConfig]:
    """加载提示词配置"""
    try:
        with open(prompts_file, 'r', encoding='utf-8') as f:
            prompts_data = json.load(f)
            return prompts_data.get("prompts", [])
    except Exception as e:
        log_error(f"加载提示词配置文件失败: {str(e)}")
        return []

def load_test_cases(cases_dir: str) -> Dict[str, List[TestCase]]:
    """加载测试用例"""
    cases_map = {}
    
    case_files = glob.glob(f"{cases_dir}/*.json")
    for case_file in case_files:
        try:
            with open(case_file, 'r', encoding='utf-8') as f:
                case_data = json.load(f)
                case_name = case_data.get("caseName", "")
                if case_name:
                    cases_map[case_name] = case_data.get("cases", [])
        except Exception as e:
            log_warning(f"加载测试用例文件 {case_file} 失败: {str(e)}")
    
    return cases_map

def load_api_keys_from_config(config_file: str) -> Dict[str, str]:
    """从配置文件加载API密钥"""
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return {
                    "openai_key": config.get("openai_key", ""),
                    "anthropic_key": config.get("anthropic_key", "")
                }
        except Exception as e:
            log_warning(f"加载配置文件失败: {str(e)}")
    return {"openai_key": "", "anthropic_key": ""}

def save_api_keys_to_config(config_file: str, openai_key: str, anthropic_key: str) -> bool:
    """保存API密钥到配置文件"""
    config = {
        "openai_key": openai_key,
        "anthropic_key": anthropic_key
    }
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        # 设置文件权限为仅当前用户可读写
        os.chmod(config_file, 0o600)
        log_info("API密钥已保存到本地配置文件")
        return True
    except Exception as e:
        log_warning(f"保存配置文件失败: {str(e)}")
        return False 