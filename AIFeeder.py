import json
import os
import sys
import logging
from logging import StreamHandler, FileHandler
from filelock import FileLock
import feedparser
from ollama import Client, ResponseError
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

class RSSSummary:
    def __init__(self, config_path):
        # 初始化日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                FileHandler("feedreader.log", encoding='utf-8'),
                StreamHandler(sys.stdout)
            ]
        )
        try:
            self.config = self._load_config(config_path)
            self.feeds = self._load_feeds(self.config['feeds_source_file'])
            self.processed_articles = self._load_processed(self.config['processed_articles_file'])
            self.articles_per_feed = self.config['articles_per_feed']
            self.ollama_config = self.config['ollama']
            
            self.ollama_client = Client(f"http://{self.ollama_config['ip']}:{self.ollama_config['port']}")
            self.ollama_model = self.ollama_config['model']
            self._check_model_accessible()
            logging.info("初始化成功。")
        except Exception as e:
            logging.error(f"初始化失败: {e}")
            raise

    def _load_config(self, config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logging.info("成功加载配置文件。")
            return config
        except Exception as e:
            logging.error(f"加载配置文件失败: {e}")
            raise

    def _load_feeds(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                feeds = [
                    line.strip() for line in f
                    if line.strip() and not line.strip().startswith('#')
                ]
            logging.info(f"成功加载了 {len(feeds)} 个源。")
            return feeds
        except Exception as e:
            logging.error(f"加载源失败: {e}")
            raise

    def _load_processed(self, path):
        try:
            if os.path.exists(path):
                with FileLock(f"{path}.lock"):
                    with open(path, 'r', encoding='utf-8') as f:
                        processed = set(json.load(f))
                logging.info(f"已加载 {len(processed)} 篇已处理文章。")
                return processed
            logging.info(f"已处理文章文件 {path} 未找到，初始化为空集。")
            return set()
        except Exception as e:
            logging.error(f"加载已处理文章失败: {e}")
            return set()

    def _check_model_accessible(self):
        try:
            self.ollama_client.chat(model=self.ollama_model, messages=[{"role": "user", "content": "Test"}])
            logging.info(f"模型 '{self.ollama_model}' 可访问。")
        except ResponseError as e:
            if e.status_code == 404:
                logging.warning(f"未找到模型 '{self.ollama_model}'。尝试拉取模型...")
                try:
                    self.ollama_client.pull(self.ollama_model)
                    logging.info(f"成功拉取模型 '{self.ollama_model}'。")
                    self.ollama_client.chat(model=self.ollama_model, messages=[{"role": "user", "content": "Test"}])
                    logging.info(f"模型 '{self.ollama_model}' 已成功拉取并可访问。")
                except Exception as pull_error:
                    logging.error(f"拉取模型 '{self.ollama_model}' 失败: {str(pull_error)}")
                    raise
            else:
                logging.error(f"检查模型可用性时发生意外错误: {str(e)}")
                raise

    def fetch_article_abstract(self, url):
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Connection": "keep-alive",
                "Referer": "https://www.google.com/"
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            abstract_sources = [
                ('abstract', lambda s: s.find('abstract')),
                ('div.abstract', lambda s: s.find('div', class_='abstract')),
                ('div#abstract', lambda s: s.find('div', id='abstract')),
                ('section', lambda s: s.find('section', {'aria-labelledby': 'abstract'})),
                ('p', lambda s: next((p for p in s.find_all('p') if 'abstract' in p.get_text().lower()), None)),
                ('regex', lambda s: re.search(r'Abstract\s*[:\-]\s*(.*?)\s*(Introduction|1\.)', str(s), re.DOTALL | re.IGNORECASE)),
                ('meta_description', lambda s: s.find('meta', attrs={'name': 'description'})),
                ('og_description', lambda s: s.find('meta', attrs={'property': 'og:description'}))
            ]

            for source_name, finder in abstract_sources:
                result = finder(soup)
                if result:
                    if source_name == 'regex':
                        return result.group(1).strip()
                    elif source_name in ['meta_description', 'og_description']:
                        return result.get('content', '').strip()
                    else:
                        return result.get_text(strip=True)

            logging.warning(f"未找到摘要: {url}")
            return None
        except requests.exceptions.RequestException as e:
            logging.warning(f"获取文章失败 ({url}): {e}")
            return None
        except Exception as e:
            logging.warning(f"提取摘要错误 ({url}): {e}")
            return None

    def summarize_article(self, content):
        PROMPT = (
            "请阅读以下文章内容，并提供一个简洁、清晰的总结，覆盖主要观点和关键信息。"
            "总结应易于理解，并保持客观性。"
        )
        try:
            messages = [
                {"role": "user", "content": f"{PROMPT}\n\n文章内容:\n{content}"}
            ]
            response = self.ollama_client.chat(
                model=self.ollama_model,
                messages=messages
            )
            summary = response['message']['content']
            if summary:
                logging.info("成功生成摘要。")
                return summary
            else:
                logging.warning("摘要为空。")
                return "摘要生成失败。"
        except ResponseError as e:
            logging.error(f"Ollama API 请求失败: {e}")
            return "摘要生成失败。"
        except Exception as e:
            logging.error(f"使用 Ollama 生成摘要时出错: {e}")
            return "摘要生成失败。"
        
    def _save_processed(self, current_processed):
        try:
            with FileLock(f"{self.config['processed_articles_file']}.lock"):
                with open(self.config['processed_articles_file'], 'w', encoding='utf-8') as f:
                    json.dump(list(current_processed), f, ensure_ascii=False, indent=4)
            logging.info("已保存此次处理的文章。")
        except Exception as e:
            logging.error(f"保存已处理文章失败: {e}")

    def _generate_report(self, summaries):
        try:
            report_dir = self.config['report_directory']
            if not os.path.exists(report_dir):
                os.makedirs(report_dir)
                logging.info(f"创建输出目录: {report_dir}")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_path = os.path.join(report_dir, f'report_{timestamp}.html')
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write("<html><head><meta charset='UTF-8'><title>总结报告</title></head><body>")
                f.write("<h1>总结报告</h1>")
                for summary in summaries:
                    f.write(f"<h2><a href='{summary['link']}'>{summary['title']}</a></h2>")
                    f.write(f"<p>{summary['summary']}</p>")
                f.write("</body></html>")
            logging.info(f"报告已生成于 {report_path}")
        except Exception as e:
            logging.error(f"生成报告失败: {e}")

    def _process_feed(self, feed_url):
        feed_summaries = []
        try:
            feed = feedparser.parse(feed_url)
            if feed.bozo:
                logging.warning(f"解析源失败: {feed_url}")
                return feed_summaries
            for entry in feed.entries[:self.articles_per_feed]:
                article_id = entry.get('id') or entry.get('link')
                if article_id and article_id not in self.processed_articles:
                    abstract = self.fetch_article_abstract(article_id)
                    content = abstract or entry.get('summary', '') or entry.get('description', '') or \
                              (entry.get('content', [{}])[0].get('value', '') if entry.get('content') else '') or entry.get('title', '')
                    
                    if not content:
                        logging.warning(f"文章内容为空: {article_id}")
                        continue

                    summary = self.summarize_article(content)
                    if summary != "摘要生成失败。":
                        feed_summaries.append({
                            "title": entry.get('title', '无标题'),
                            "link": entry.get('link', ''),
                            "summary": summary
                        })
                    else:
                        logging.warning(f"摘要生成失败: {article_id}")
        except Exception as e:
            logging.error(f"处理源 {feed_url} 时出错: {e}")
        return feed_summaries

    def process_feeds(self):
        all_summaries = []
        current_processed = set()
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_feed = {executor.submit(self._process_feed, feed_url): feed_url for feed_url in self.feeds}
            for future in as_completed(future_to_feed):
                feed_url = future_to_feed[future]
                try:
                    summaries = future.result()
                    all_summaries.extend(summaries)
                    current_processed.update(summary['link'] for summary in summaries)
                except Exception as e:
                    logging.error(f"处理源 {feed_url} 时出错: {e}")

        if all_summaries:
            self._save_processed(current_processed)
            self._generate_report(all_summaries)
        else:
            logging.warning("未生成任何摘要，未生成报告。")

if __name__ == "__main__":
    rss_summary = RSSSummary('settings.json')
    rss_summary.process_feeds()