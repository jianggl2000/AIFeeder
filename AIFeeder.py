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

class RSSSummary:
    PROMPT = (
        "请阅读以下文章内容，并提供一个简洁、清晰的总结，覆盖主要观点和关键信息。"
        "总结应易于理解，并保持客观性。"
        "不要在总结前面或后面添加任何与文章无关的解释，如'下面是对该文章的总结：'。"
    )

    def __init__(self, config_path):
        # Initialize logging
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
            logging.info("Initialization successful.")
        except Exception as e:
            logging.error(f"Initialization failed: {e}")
            raise

    def _load_config(self, config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logging.info("Configuration file loaded successfully.")
            return config
        except Exception as e:
            logging.error(f"Failed to load configuration file: {e}")
            raise

    def _load_feeds(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                feeds = [
                    line.strip() for line in f
                    if line.strip() and not line.strip().startswith('#')
                ]
            logging.info(f"Successfully loaded {len(feeds)} feeds.")
            return feeds
        except Exception as e:
            logging.error(f"Failed to load feeds: {e}")
            raise

    def _load_processed(self, path):
        try:
            if os.path.exists(path):
                with FileLock(f"{path}.lock"):
                    with open(path, 'r', encoding='utf-8') as f:
                        processed = set(json.load(f))
                logging.info(f"Loaded {len(processed)} processed articles.")
                return processed
            logging.info(f"Processed articles file {path} not found, initializing as empty set.")
            return set()
        except Exception as e:
            logging.error(f"Failed to load processed articles: {e}")
            return set()

    def _check_model_accessible(self):
        try:
            self.ollama_client.chat(model=self.ollama_model, messages=[{"role": "user", "content": "Test"}])
            logging.info(f"Model '{self.ollama_model}' is accessible.")
        except ResponseError as e:
            if e.status_code == 404:
                logging.warning(f"Model '{self.ollama_model}' not found. Attempting to pull the model...")
                try:
                    self.ollama_client.pull(self.ollama_model)
                    logging.info(f"Successfully pulled model '{self.ollama_model}'.")
                    self.ollama_client.chat(model=self.ollama_model, messages=[{"role": "user", "content": "Test"}])
                    logging.info(f"Model '{self.ollama_model}' has been successfully pulled and is accessible.")
                except Exception as pull_error:
                    logging.error(f"Failed to pull model '{self.ollama_model}': {str(pull_error)}")
                    raise
            else:
                logging.error(f"Unexpected error while checking model accessibility: {str(e)}")
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

            logging.warning(f"Abstract not found: {url}")
            return None
        except requests.exceptions.RequestException as e:
            logging.warning(f"Failed to fetch article ({url}): {e}")
            return None
        except Exception as e:
            logging.warning(f"Error extracting abstract ({url}): {e}")
            return None

    def summarize_article(self, content):
        try:
            messages = [
                {"role": "user", "content": f"{self.PROMPT}\n\n文章内容:\n{content}"}
            ]
            response = self.ollama_client.chat(
                model=self.ollama_model,
                messages=messages
            )
            summary = response['message']['content']
            if summary:
                logging.info("Summary generated successfully.")
                return summary
            else:
                logging.warning("Summary is empty.")
                return "Summary generation failed."
        except ResponseError as e:
            logging.error(f"Ollama API request failed: {e}")
            return "Summary generation failed."
        except Exception as e:
            logging.error(f"Error using Ollama to generate summary: {e}")
            return "Summary generation failed."
        
    def _save_processed(self, current_processed):
        lock = FileLock(f"{self.config['processed_articles_file']}.lock")
        try:
            with lock:
                with open(self.config['processed_articles_file'], 'w', encoding='utf-8') as f:
                    json.dump(list(current_processed), f, ensure_ascii=False, indent=4)
            logging.info("Processed articles have been saved.")
        except Exception as e:
            logging.error(f"Failed to save processed articles: {e}")
        finally:
            if lock.is_locked:
                lock.release()

    def _generate_report(self, summaries):
        try:
            report_dir = self.config['report_directory']
            if not os.path.exists(report_dir):
                os.makedirs(report_dir, exist_ok=True)
                logging.info(f"Created output directory: {report_dir}")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_path = os.path.join(report_dir, f'report_{timestamp}.html')
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write("<html><head><meta charset='UTF-8'><title>Summary Report</title></head><body>")
                f.write("<h1>Summary Report</h1>")
                for summary in summaries:
                    f.write(f"<h2><a href='{summary['link']}'>{summary['title']}</a></h2>")
                    f.write(f"<p>{summary['summary']}</p>")
                    f.write(f"<p>{summary['content']}</p>")
                f.write("</body></html>")
            logging.info(f"Report generated at {report_path}")
        except Exception as e:
            logging.error(f"Failed to generate report: {e}")

    def process_feeds(self):
        summaries = []
        current_processed = set()
        for feed_url in self.feeds:
            try:
                feed = feedparser.parse(feed_url)
                if feed.bozo:
                    logging.warning(f"Failed to parse feed: {feed_url}")
                    continue
                count = 0
                for entry in feed.entries:
                    if count >= self.articles_per_feed:
                        break
                    article_id = entry.get('id') or entry.get('link')
                    if article_id and article_id not in self.processed_articles:
                        # Fetch article abstract
                        abstract = self.fetch_article_abstract(article_id)
                        if not abstract:
                            # Fetch RSS article content
                            content = (entry.get('summary', '') or entry.get('description', '') or
                                       entry.get('content', [{}])[0].get('value', '') or entry.get('title', ''))
                        else:
                            content = abstract
                        if not content:
                            logging.warning(f"Article content is empty: {article_id}")
                            continue
                        summary = self.summarize_article(content)
                        if summary != "Summary generation failed.":
                            summaries.append({
                                "title": entry.get('title', 'Untitled'),
                                "link": entry.get('link', ''),
                                "summary": summary,
                                "content": content
                            })
                            current_processed.add(article_id)
                            count += 1
                        else:
                            logging.warning(f"Summary generation failed: {article_id}")
            except Exception as e:
                logging.error(f"Error processing feed {feed_url}: {e}")
        if summaries:
            self._generate_report(summaries)
            self.processed_articles.update(current_processed)
            self._save_processed(self.processed_articles)
        else:
            logging.info("No summaries generated. Skipping report generation and saving processed records.")

if __name__ == "__main__":
    rss_summary = RSSSummary('settings.json')
    rss_summary.process_feeds()
