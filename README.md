# AIFeeder

**Fetch and summarize RSS feeds using a local Ollama model.**
- Use local Ollama to analyze RSS feeds, summarize articles (in Chinese; change the `PROMPT` in AIFeeder.py to summarize in other languages).
- Only process new RSS feeds, skip already summarized articles.

## 简介
AIFeeder.py 是一个用于自动化处理 RSS 源的 Python 脚本。该脚本的主要功能包括从多个 RSS 源中获取最新的文章，提取文章摘要，使用 AI 模型（本地Ollama）生成文章摘要，并最终生成一个包含所有摘要的报告。此脚本特别适用于需要定期汇总和分析大量 RSS 文章内容的场景，如新闻聚合、研究综述或内容监控。

- 利用本地Ollama分析RSS订阅，总结文献(中文总结)。
- 仅处理新RSS订阅文章，对已总结过的文献跳过不再处理。

## 功能概述
### 配置管理：
- 加载配置文件（settings.json），其中包含 RSS 源列表、已处理文章记录、文章数量限制和 AI 模型的配置信息。
### 日志记录：
- 使用 Python 的 logging 模块记录运行时信息，包括初始化过程、错误、警告和操作成功信息。日志信息被写入 feedreader.log 文件，并实时输出到控制台。
### RSS 源处理：
- 从配置文件中加载多个 RSS 源。
- 使用 feedparser 解析 RSS 源，提取最新的文章条目。
- 控制每个 RSS 源处理的文章数量，避免处理过多文章。
### 文章摘要提取：
- 对于每篇文章，尝试从网页内容中提取摘要。使用 requests 获取文章内容，并通过 BeautifulSoup 解析 HTML。
- 使用多种方法（如查找特定标签、正则表达式匹配）来提取摘要，确保尽可能准确地获取文章的主要内容。
### 摘要生成：
- 使用 Ollama AI 模型对提取的文章内容进行摘要生成。
- 通过与 Ollama API 交互，发送文章内容并接收生成的摘要。
- 处理 API 请求中的错误和异常，确保摘要生成过程的稳定性。
### 已处理文章管理：
- 记录已处理的文章，以避免重复处理相同的内容。
- 使用文件锁（FileLock）确保多线程环境下对已处理文章记录的安全写入。
### 报告生成：
- 汇总所有生成的文章摘要，生成一个 HTML 格式的报告。
- 报告包括每篇文章的标题、链接和生成的摘要，方便用户快速浏览和参考。
### 多线程支持（尚未开发）：
- 考虑使用 ThreadPoolExecutor 来并行处理多个 RSS 源，提高处理效率，特别是在处理大量 RSS 源时。


## Installation
### Install Ollama

Following the Ollama [instruction](https://github.com/ollama/ollama?tab=readme-ov-file) to install Ollama on Windows or Linux.

### Install AIFeeder

```
git clone https://github.com/jianggl2000/AIfeeder/

cd AIfeeder

pip install -r requirements.txt
```
## Run AIFeeder

`python AIFeeder.py`

## Reference
- [Ollama](https://github.com/ollama/ollama?tab=readme-ov-file)


