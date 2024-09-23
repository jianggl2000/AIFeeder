# AIFeeder

**Fetch and summarize RSS feeds using a local Ollama model.**

- Use local Ollama to analyze RSS feeds, summarize articles, and provide summaries (in Chinese; change the `PROMPT` in AIFeeder.py to summarize in other languages).
- Only process new RSS feeds, skip already summarized articles.

- 利用本地Ollama分析RSS订阅，总结文献(中文总结)。
- 仅处理新RSS订阅文章，对已总结过的文献跳过不再处理。

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


