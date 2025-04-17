#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import datetime
import xml.dom.minidom
import xml.etree.ElementTree as ET
import html
from typing import Dict, List, Any
import time
from pathlib import Path

from logger import log_info
from utils import TestResult

def save_results_as_xml(all_results: Dict[str, List[TestResult]], output_dir: str):
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
    file_path = os.path.join(output_dir, f"test_results_{timestamp}.xml")
    
    # 保存文件
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(pretty_xml)
        
    log_info(f"测试结果已保存到: {file_path}")
    return file_path

def save_results_as_html(test_results: Dict[str, Dict[str, List[TestResult]]], output_dir: str, filename_prefix: str = "test_results") -> str:
    """保存测试结果为HTML格式的报告
    
    参数:
    - test_results: 测试结果字典，键为轮次，值为提示词-测试结果列表的字典
    - output_dir: 输出目录
    - filename_prefix: 文件名前缀，默认为"test_results"
    
    返回:
    - 保存的HTML文件路径
    """
    # 创建输出目录（如果不存在）
    Path(output_dir).mkdir(exist_ok=True)
    
    # 生成文件名，使用时间戳确保唯一性
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    html_filename = f"{filename_prefix}_{timestamp}.html"
    html_path = os.path.join(output_dir, html_filename)
    
    # 测试时间
    test_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 计算统计数据
    total_rounds = len(test_results)
    total_prompts = set()
    total_cases = 0
    total_tokens = 0
    total_time = 0
    
    for round_name, round_results in test_results.items():
        for prompt_name, results in round_results.items():
            total_prompts.add(prompt_name)
            total_cases += len(results)
            for result in results:
                total_time += result["elapsed_time"]
                
                # 计算token总数，注意处理不同模型的token格式
                if "total_tokens" in result["tokens"]:
                    total_tokens += result["tokens"]["total_tokens"]
                elif "input_tokens" in result["tokens"] and "output_tokens" in result["tokens"]:
                    total_tokens += result["tokens"]["input_tokens"] + result["tokens"]["output_tokens"]
    
    avg_response_time = total_time / total_cases if total_cases > 0 else 0
    
    # HTML头部
    html_content = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI提示词测试报告 - {test_time}</title>
    <style>
        :root {{
            --bp-blue-1: #DEEBFF;
            --bp-blue-2: #B3D4FF;
            --bp-blue-3: #8BBDFC;
            --bp-blue-4: #549BFF;
            --bp-blue-5: #2D7FF9;
            --bp-blue-6: #106AED;
            --bp-blue-7: #0053D9;
            --bp-blue-8: #003EBE;
            --bp-blue-9: #002B84;
            
            --bp-gray-1: #F5F8FA;
            --bp-gray-2: #EBF1F5;
            --bp-gray-3: #DCE4EB;
            --bp-gray-4: #CED6DE;
            --bp-gray-5: #BFCAD4;
            --bp-gray-6: #8C9DAD;
            --bp-gray-7: #5C7080;
            --bp-gray-8: #394B59;
            --bp-gray-9: #1C2B35;
            
            --bp-green-1: #D6FCE8;
            --bp-green-2: #A8F6D2;
            --bp-green-3: #7AEFBB;
            --bp-green-4: #4DE3A3;
            --bp-green-5: #1FCF8B;
            --bp-green-6: #14BE81;
            --bp-green-7: #0DA976;
            --bp-green-8: #07936A;
            --bp-green-9: #057A5B;
            
            --bp-red-1: #FFE0E0;
            --bp-red-2: #FFC2C2;
            --bp-red-3: #FFA4A4;
            --bp-red-4: #FF8585;
            --bp-red-5: #FF6767;
            --bp-red-6: #F54E4E;
            --bp-red-7: #EB3636;
            --bp-red-8: #DB2020;
            --bp-red-9: #C81010;
            
            --shadow-sm: 0 1px 2px 0 rgba(31, 35, 41, 0.08);
            --shadow-md: 0 3px 6px 0 rgba(31, 35, 41, 0.12);
            --shadow-lg: 0 8px 16px 0 rgba(31, 35, 41, 0.16);
            
            --font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            --radius: 4px;
        }}
        
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        
        body {{
            font-family: var(--font-family);
            background-color: var(--bp-gray-1);
            color: var(--bp-gray-9);
            line-height: 1.5;
            font-size: 14px;
        }}
        
        a {{
            color: var(--bp-blue-6);
            text-decoration: none;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--bp-gray-3);
        }}
        
        .title {{
            font-size: 24px;
            font-weight: 600;
            color: var(--bp-gray-9);
        }}
        
        .subtitle {{
            font-size: 14px;
            color: var(--bp-gray-7);
            margin-top: 4px;
        }}
        
        .stats-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}
        
        .stat-card {{
            background-color: white;
            border-radius: var(--radius);
            padding: 16px;
            box-shadow: var(--shadow-sm);
        }}
        
        .stat-card-title {{
            font-size: 13px;
            color: var(--bp-gray-7);
            margin-bottom: 8px;
        }}
        
        .stat-card-value {{
            font-size: 24px;
            font-weight: 600;
            color: var(--bp-gray-9);
        }}
        
        .stat-card-unit {{
            font-size: 12px;
            color: var(--bp-gray-6);
            margin-left: 4px;
        }}
        
        .tabs {{
            display: flex;
            border-bottom: 1px solid var(--bp-gray-3);
            margin-bottom: 24px;
            overflow-x: auto;
            white-space: nowrap;
            -webkit-overflow-scrolling: touch;
        }}
        
        .tab {{
            padding: 12px 16px;
            cursor: pointer;
            border-bottom: 2px solid transparent;
            font-weight: 500;
            color: var(--bp-gray-7);
            transition: all 0.2s;
        }}
        
        .tab.active {{
            color: var(--bp-blue-6);
            border-bottom-color: var(--bp-blue-6);
        }}
        
        .tab:hover {{
            color: var(--bp-blue-5);
        }}
        
        .tab-content {{
            display: none;
        }}
        
        .tab-content.active {{
            display: block;
        }}
        
        .nested-tab-content {{
            display: none;
        }}
        
        .nested-tab-content.active {{
            display: block;
        }}
        
        .round-tabs {{
            display: flex;
            margin-bottom: 16px;
            border-bottom: 1px solid var(--bp-gray-3);
        }}
        
        .round-tab {{
            padding: 8px 16px;
            cursor: pointer;
            border-bottom: 2px solid transparent;
            font-weight: 500;
            color: var(--bp-gray-7);
            font-size: 13px;
            transition: all 0.2s;
        }}
        
        .round-tab.active {{
            color: var(--bp-green-7);
            border-bottom-color: var(--bp-green-7);
        }}
        
        .round-tab:hover {{
            color: var(--bp-green-6);
        }}
        
        .prompt-section {{
            margin-bottom: 32px;
        }}
        
        .prompt-title {{
            font-size: 18px;
            font-weight: 600;
            color: var(--bp-gray-9);
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        
        .prompt-badge {{
            font-size: 12px;
            font-weight: normal;
            color: var(--bp-gray-7);
            background-color: var(--bp-gray-2);
            padding: 4px 8px;
            border-radius: 12px;
        }}
        
        .cases {{
            display: flex;
            flex-direction: column;
            gap: 16px;
        }}
        
        .case-card {{
            background-color: white;
            border-radius: var(--radius);
            overflow: hidden;
            box-shadow: var(--shadow-sm);
            transition: all 0.2s;
        }}
        
        .case-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 16px;
            background-color: var(--bp-gray-2);
            cursor: pointer;
            user-select: none;
        }}
        
        .case-title {{
            font-weight: 500;
            color: var(--bp-gray-9);
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .case-id {{
            font-size: 12px;
            color: var(--bp-gray-6);
        }}
        
        .case-metrics {{
            display: flex;
            gap: 16px;
            font-size: 12px;
            color: var(--bp-gray-7);
        }}
        
        .case-metric-value {{
            font-weight: 600;
            color: var(--bp-gray-8);
        }}
        
        .case-content {{
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.3s ease-out;
        }}
        
        .case-content.expanded {{
            max-height: 2000px;
        }}
        
        .case-section {{
            padding: 16px;
            border-bottom: 1px solid var(--bp-gray-2);
        }}
        
        .case-section:last-child {{
            border-bottom: none;
        }}
        
        .case-section-title {{
            font-size: 13px;
            font-weight: 600;
            color: var(--bp-gray-8);
            margin-bottom: 8px;
        }}
        
        .case-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
        }}
        
        @media (max-width: 768px) {{
            .case-grid {{
                grid-template-columns: 1fr;
            }}
        }}
        
        .code-block {{
            background-color: var(--bp-gray-1);
            padding: 12px;
            border-radius: 4px;
            font-family: monospace;
            white-space: pre-wrap;
            word-break: break-word;
            font-size: 12px;
            max-height: 300px;
            overflow-y: auto;
        }}
        
        .token-list {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }}
        
        .token-item {{
            background-color: var(--bp-gray-2);
            border-radius: 4px;
            padding: 4px 8px;
            font-size: 12px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
        }}
        
        .token-name {{
            color: var(--bp-gray-8);
        }}
        
        .token-value {{
            font-weight: 600;
            color: var(--bp-gray-9);
        }}
        
        .args-table {{
            width: 100%;
            border-collapse: collapse;
        }}
        
        .args-table th, .args-table td {{
            padding: 8px;
            text-align: left;
            border-bottom: 1px solid var(--bp-gray-3);
        }}
        
        .args-table th {{
            font-weight: 600;
            color: var(--bp-gray-8);
            background-color: var(--bp-gray-2);
        }}
        
        .case-expand-icon {{
            margin-left: auto;
            display: inline-block;
            width: 16px;
            height: 16px;
            text-align: center;
            line-height: 16px;
            transform: rotate(-90deg);
        }}
        
        .footer {{
            margin-top: 40px;
            padding-top: 16px;
            border-top: 1px solid var(--bp-gray-3);
            font-size: 12px;
            color: var(--bp-gray-6);
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1 class="title">AI提示词测试报告</h1>
                <div class="subtitle">测试时间: {test_time}</div>
            </div>
        </div>
        
        <div class="stats-cards">
            <div class="stat-card">
                <div class="stat-card-title">提示词数量</div>
                <div class="stat-card-value">{len(total_prompts)}</div>
            </div>
            
            <div class="stat-card">
                <div class="stat-card-title">测试用例总数</div>
                <div class="stat-card-value">{total_cases}</div>
            </div>
            
            <div class="stat-card">
                <div class="stat-card-title">平均响应时间</div>
                <div class="stat-card-value">{avg_response_time:.2f}<span class="stat-card-unit">秒</span></div>
            </div>
            
            <div class="stat-card">
                <div class="stat-card-title">总Token消耗</div>
                <div class="stat-card-value">{total_tokens:,}<span class="stat-card-unit">tokens</span></div>
            </div>
        </div>
        <div class="tab-content active" id="results">
            <div class="round-tabs">
'''
    
    # 添加轮次标签
    round_names = list(test_results.keys())
    for i, round_name in enumerate(round_names):
        is_active = "active" if i == 0 else ""
        html_content += f'''
                <div class="round-tab {is_active}" data-round="{i}">{round_name}</div>'''
    
    html_content += '''
            </div>
'''
    
    # 添加每个轮次的测试结果
    for i, (round_name, round_results) in enumerate(test_results.items()):
        is_active = "active" if i == 0 else ""
        html_content += f'''
            <div class="nested-tab-content {is_active}" id="round-{i}">
'''
        
        # 添加每个提示词的测试结果
        for prompt_name, results in round_results.items():
            # 确定模型和提供商
            model = results[0]["model"] if results else ""
            vendor = results[0]["vendor"] if results else ""
            
            html_content += f'''
                <div class="prompt-section">
                    <h2 class="prompt-title">
                        {html.escape(prompt_name)}
                        <span class="prompt-badge">{html.escape(vendor)} - {html.escape(model)}</span>
                    </h2>
                    
                    <div class="cases">
'''
            
            for idx, result in enumerate(results):
                # 格式化token信息
                token_html = '<div class="token-list">'
                for token_key, token_value in result["tokens"].items():
                    token_html += f'''
                        <div class="token-item">
                            <span class="token-name">{html.escape(token_key)}</span>
                            <span class="token-value">{token_value:,}</span>
                        </div>'''
                token_html += '</div>'
                
                # 格式化参数信息
                args_html = ''
                if result["case_args"]:
                    args_html = '''
                        <div class="case-section">
                            <div class="case-section-title">参数</div>
                            <table class="args-table">
                                <tr>
                                    <th>参数名</th>
                                    <th>值</th>
                                </tr>'''
                    
                    for arg_key, arg_value in result["case_args"].items():
                        args_html += f'''
                                <tr>
                                    <td>{html.escape(arg_key)}</td>
                                    <td>{html.escape(str(arg_value))}</td>
                                </tr>'''
                    
                    args_html += '''
                            </table>
                        </div>'''
                
                html_content += f'''
                        <div class="case-card">
                            <div class="case-header" onclick="toggleCase(this)">
                                <div class="case-title">
                                    {html.escape(result["case_name"])}
                                    <span class="case-id">#{result["case_id"]}</span>
                                </div>
                                <div class="case-metrics">
                                    <div class="case-metric">
                                        响应时间: <span class="case-metric-value">{result["elapsed_time"]:.2f}秒</span>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="case-content">
                                <div class="case-section">
                                    <div class="case-section-title">用例描述</div>
                                    <div>{html.escape(result["case_description"] or "无描述")}</div>
                                </div>
                                
                                {args_html}
                                
                                <div class="case-grid">
                                    <div class="case-section">
                                        <div class="case-section-title">用户输入</div>
                                        <div class="code-block">{html.escape(result["case_content"])}</div>
                                    </div>
                                    
                                    <div class="case-section">
                                        <div class="case-section-title">AI输出</div>
                                        <div class="code-block">{html.escape(result["output_content"])}</div>
                                    </div>
                                </div>
                                
                                <div class="case-section">
                                    <div class="case-section-title">提示词</div>
                                    <div class="code-block">{html.escape(result["processed_prompt"])}</div>
                                </div>
                                
                                <div class="case-section">
                                    <div class="case-section-title">Token使用情况</div>
                                    {token_html}
                                </div>
                            </div>
                        </div>
'''
            
            html_content += '''
                    </div>
                </div>
'''
        
        html_content += '''
            </div>
'''
    
    # HTML尾部
    html_content += '''
        </div>
        
        <div class="footer">
            <p>由AI提示词测试工具生成 - © 2024</p>
        </div>
    </div>
    
    <script>
        function toggleCase(element) {
            const caseContent = element.nextElementSibling;
            caseContent.classList.toggle('expanded');
        }
        
        function switchTab(event) {
            // 获取所有tab和tab内容
            const tabs = document.querySelectorAll('.tab');
            const tabContents = document.querySelectorAll('.tab-content');
            
            // 移除所有active类
            tabs.forEach(tab => tab.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));
            
            // 获取点击的tab的data-tab属性
            const tabId = event.target.getAttribute('data-tab');
            
            // 添加active类到点击的tab和对应的内容
            event.target.classList.add('active');
            document.getElementById(tabId).classList.add('active');
        }
        
        function switchRoundTab(event) {
            // 获取所有轮次tab和轮次内容
            const roundTabs = document.querySelectorAll('.round-tab');
            const roundContents = document.querySelectorAll('.nested-tab-content');
            
            // 移除所有active类
            roundTabs.forEach(tab => tab.classList.remove('active'));
            roundContents.forEach(content => content.classList.remove('active'));
            
            // 获取点击的轮次tab的data-round属性
            const roundIndex = event.target.getAttribute('data-round');
            
            // 添加active类到点击的轮次tab和对应的内容
            event.target.classList.add('active');
            document.getElementById(`round-${roundIndex}`).classList.add('active');
        }
        
        // 为所有tab添加点击事件
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', switchTab);
        });
        
        // 为所有轮次tab添加点击事件
        document.querySelectorAll('.round-tab').forEach(tab => {
            tab.addEventListener('click', switchRoundTab);
        });
    </script>
</body>
</html>
'''
    
    # 保存文件
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    log_info(f"测试结果已保存到: {html_path}")
    return html_path 