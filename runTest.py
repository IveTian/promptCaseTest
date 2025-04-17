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
    try:
        # 解析命令行参数
        parser = argparse.ArgumentParser(description='AI提示词测试工具')
        parser.add_argument('--config', type=str, help='配置文件路径', default='.aitest_config.json')
        parser.add_argument('--prompts', type=str, help='提示词配置文件路径', default='prompts.json')
        parser.add_argument('--cases-dir', type=str, help='测试用例目录', default='cases')
        parser.add_argument('--output-dir', type=str, help='输出目录', default='testLog')
        parser.add_argument('--prompt-concurrency', type=int, help='提示词并发执行数量', default=5)
        parser.add_argument('--case-concurrency', type=int, help='每个提示词的测试用例并发数量', default=3)
        parser.add_argument('--show-preview', action='store_true', help='显示输出预览')
        parser.add_argument('--preview-length', type=int, help='输出预览的长度', default=100)
        parser.add_argument('--quiet', action='store_true', help='静默模式，减少输出信息')
        
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
        if args.prompt_concurrency:
            tester.max_prompt_concurrency = args.prompt_concurrency
        if args.case_concurrency:
            tester.max_case_concurrency = args.case_concurrency
        
        # 设置显示选项
        tester.show_preview = args.show_preview
        tester.preview_length = args.preview_length
        tester.quiet_mode = args.quiet
            
        # 运行测试
        await tester.run()
    
    except KeyboardInterrupt:
        # 主程序已通过tester.run()方法处理了KeyboardInterrupt，这里只是为了保险
        # 确保即使在tester.run()之外的地方也能优雅退出
        print("\n用户中断，正在退出程序...")
        sys.exit(0)
    except Exception as e:
        print(f"\n程序执行出错: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # 捕获顶层键盘中断
        print("\n用户中断，正在退出程序...")
        sys.exit(0) 