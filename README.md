# AI提示词测试工具

这个工具用于测试和评估AI提示词的效果，支持OpenAI和Anthropic的API。

## 项目结构

- `runTest.py`: 主程序入口
- `tester.py`: 测试核心类
- `api_clients.py`: API调用模块
- `utils.py`: 辅助函数模块
- `formatters.py`: 结果格式化模块
- `logger.py`: 日志模块
- `prompts.json`: 提示词配置文件
- `cases/`: 测试用例目录
- `testLog/`: 测试结果输出目录

## 设置

1. 复制配置文件模板：
```bash
cp .aitest_config.template.json .aitest_config.json
```

2. 编辑配置文件，添加您的API密钥：
```bash
# 使用您喜欢的编辑器打开配置文件
nano .aitest_config.json
```

3. 安装依赖：
```bash
pip install -r requirements.txt
```

4. 运行测试：
```bash
python runTest.py
```

## 命令行参数

```
usage: runTest.py [-h] [--config CONFIG] [--prompts PROMPTS]
                 [--cases-dir CASES_DIR] [--output-dir OUTPUT_DIR]

AI提示词测试工具

optional arguments:
  -h, --help           显示帮助信息并退出
  --config CONFIG      配置文件路径 (默认: .aitest_config.json)
  --prompts PROMPTS    提示词配置文件路径 (默认: prompts.json)
  --cases-dir CASES_DIR
                       测试用例目录 (默认: cases)
  --output-dir OUTPUT_DIR
                       输出目录 (默认: testLog)
```

## 注意事项

- `.aitest_config.json` 文件包含API密钥，已被添加到 .gitignore 中，不会被提交到仓库
- 测试结果保存在 `testLog/` 目录中
- 测试用例在 `cases/` 目录中定义 