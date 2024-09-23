# AIFeeder

Fetch and summarize RSS feeds using a local Ollama

- 利用本地Ollama分析RSS订阅，总结文献并提供中文总结（change the prompt in AIFeeder.py to summarize in English or other language）。
- 仅处理新RSS订阅，对已总结过的文献跳过不再处理。

# Installation
## Install Ollama

Following the Ollama [instruction](https://github.com/ollama/ollama?tab=readme-ov-file) to install Ollama on Windows or Linux.

## Install AIFeeder

```
git clone https://github.com/jianggl2000/AIfeeder/

cd AIfeeder

pip install -r requirements.txt
```
## Run AIFeeder

`python AIFeeder.py`

## Reference
- [Ollama](https://github.com/ollama/ollama?tab=readme-ov-file)


