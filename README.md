# AI提示词测试工具

这个工具用于测试和评估AI提示词的效果，支持OpenAI和Anthropic的API。

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

## 注意事项

- `.aitest_config.json` 文件包含API密钥，已被添加到 .gitignore 中，不会被提交到仓库
- 测试结果保存在 `testLog/` 目录中
- 测试用例在 `cases/` 目录中定义 