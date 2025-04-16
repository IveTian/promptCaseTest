#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import argparse
import sys

try:
    from openai import OpenAI, AsyncOpenAI
    import anthropic
    from pick import pick
    from tqdm import tqdm
except ImportError:
    print("请安装必要的依赖库:")
    print("pip install openai anthropic pick tqdm")
    sys.exit(1)

from tester import AIPromptTester

async def main():
    """主程序入口"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='AI提示词测试工具')
    parser.add_argument('--config', type=str, help='配置文件路径', default='.aitest_config.json')
    parser.add_argument('--prompts', type=str, help='提示词配置文件路径', default='prompts.json')
    parser.add_argument('--cases-dir', type=str, help='测试用例目录', default='cases')
    parser.add_argument('--output-dir', type=str, help='输出目录', default='testLog')
    
    args = parser.parse_args()
    
    # 创建测试器实例
    tester = AIPromptTester()
    
    # 更新配置
    if args.config:
        tester.config_file = args.config
    if args.prompts:
        tester.prompts_file = args.prompts
    if args.cases_dir:
        tester.cases_dir = args.cases_dir
    if args.output_dir:
        tester.output_dir = args.output_dir
        
    # 运行测试
    await tester.run()

if __name__ == "__main__":
    asyncio.run(main()) 