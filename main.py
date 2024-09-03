# _*_ coding: utf-8 _*_

import os
import json
import logging
from datetime import datetime
import feedparser
import markdown
from ollama import Client, ResponseError
from collections import deque

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load configuration
with open('config.json', 'r') as config_file:
    config = json.load(config_file)

# Initialize Ollama client
ollama_client = Client(host=f"http://{config['ollama_ip']}:{config['ollama_port']}")

def read_feed_urls(file_path):
    """Read feed URLs from a file."""
    with open(file_path, 'r') as file:
        return [line.strip() for line in file if line.strip() and not line.startswith('#')]

def write_feed_urls(file_path, urls):
    """Write feed URLs to a file."""
    with open(file_path, 'w') as file:
        for url in urls:
            file.write(f"{url}\n")

def load_processed_articles(file_path, article_limit):
    """Load the list of processed article links."""
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            recent_articles = deque(file, article_limit)
        return set(article.strip() for article in recent_articles)
    return set()

def save_processed_article(article_link, file_path):
    """Save a processed article link to the file."""
    with open(file_path, 'a') as file:
        file.write(f"{article_link}\n")

def fetch_valid_articles(url, article_limit, processed_articles):
    """Fetch and validate new articles from an RSS feed."""
    feed = feedparser.parse(url)
    valid_articles = []
    
    for entry in feed.entries[:article_limit]:
        article_link = entry.get('link', 'No_URL_available')
        if article_link and article_link not in processed_articles:
            content = (entry.get('summary') or
                       entry.get('description') or
                       entry.get('content', [{}])[0].get('value', '') or
                       entry.get('title', ''))

            if content.strip():  # Check if there's any non-whitespace content
                valid_articles.append({
                    'title': entry.get('title', 'Untitled'),
                    'link': article_link,
                    'content': content
                })
    return valid_articles if valid_articles else None

def ensure_model_available(model):
    """Ensure the specified model is available, attempting to pull if not."""
    try:
        ollama_client.chat(model=model, messages=[{"role": "user", "content": "Test"}])
    except ResponseError as e:
        if e.status_code == 404:
            logging.warning(f"Model '{model}' not found. Attempting to pull...")
            try:
                ollama_client.pull(model)
                logging.info(f"Successfully pulled model '{model}'")
            except Exception as pull_error:
                logging.error(f"Failed to pull model '{model}': {str(pull_error)}")
                raise
        else:
            logging.error(f"Unexpected error when checking model availability: {str(e)}")
            raise

def summarize_article(article):
    """Summarize an article using Ollama."""
    user_prompt = f"""# INSTRUCTION
    
    Respond with a summary of the key message of this article:

    # ARTICLE
    
    {article['content']}

    # RULES

    - DO NOT INCLUDE ANYTHING OTHER THAN THE SUMMARY IN YOUR RESPONSE
    - DO NOT ADD ANY TEXT BEFORE OR AFTER THE SUMMARY
    - For long content, provide a summary of the article in less than 500 words.
    - For short content, use the original content as a summary.
    - Beside summary in English, also provide a title and a summary in Simplified Chinese.
    
    # EXAMPLE OUTPUT:
    **Translated article title in Simplified Chinese**
        - Content of the summary in English.
        - Content of the summary in Simplified Chinese.
    """

    try:
        response = ollama_client.chat(model=config['ollama_model'], messages=[
            {
                'role': 'user',
                'content': user_prompt,
            }
        ])
        summary = response['message']['content']
        # Remove any empty lines and ensure proper formatting
        return '\n'.join(line.strip() for line in summary.split('\n') if line.strip())
    except ResponseError as e:
        logging.error(f"Ollama API error: {str(e)}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error during summarization: {str(e)}")
        return None

def main():
    feeds_file = config['feeds_file']
    invalid_feeds_file = config['invalid_feeds_file']
    processed_articles_file = config['processed_articles_file']
    output_folder = os.path.expanduser(config['output_folder'])
    article_limit = config['article_limit']

    os.makedirs(output_folder, exist_ok=True)

    try:
        ensure_model_available(config['ollama_model'])
    except Exception:
        logging.error("Failed to ensure model availability. Exiting.")
        return

    feeds = read_feed_urls(feeds_file)
    invalid_feeds = []
    summaries = []
    processed_articles = load_processed_articles(processed_articles_file, article_limit)

    for feed_url in feeds:
        logging.info(f"Processing feed: {feed_url}")
        articles = fetch_valid_articles(feed_url, article_limit, processed_articles)

        if articles:
            for index, article in enumerate(articles, 1):
                logging.info(f"Processing article: {index}/{len(articles)}")
                summary = summarize_article(article)
                if summary:
                    summaries.append(f"## {article['title']}\n\n{summary}\n\n[Article Link]({article['link']})\n\n")
                    save_processed_article(article['link'], processed_articles_file)
                else:
                    logging.warning(f"Failed to summarize article: {article['title']}")
        else:
            logging.warning(f"No valid content found for feed: {feed_url}")
            invalid_feeds.append(feed_url)

    # Update feeds files
    # write_feed_urls(feeds_file, [f for f in feeds if f not in invalid_feeds])
    write_feed_urls(invalid_feeds_file, invalid_feeds)

    # Get current date and format it
    current_date = datetime.now()
    formatted_date = current_date.strftime("%A, %B %d, %Y")
    file_date = current_date.strftime('%Y-%m-%d')
    
    # Write summaries to markdown file
    markdown_file = os.path.join(output_folder, f"{file_date}_feed-summaries.md")
    with open(markdown_file, 'w', encoding="utf-8", errors='replace') as file:
        file.write(f"# Feeds for {formatted_date}\n\n")
        for summary in summaries:
            file.write(summary)

    # Write summaries to html file
    html_summaries = markdown.markdown("\n".join(summaries))
    html_file = os.path.join(output_folder, f"{file_date}_feed-summaries.html")
    with open(html_file, 'w', encoding="utf-8", errors='replace') as file:
        file.write(f"<h1>Feeds for {formatted_date}\n\n</h1>")
        for summary in html_summaries:
            file.write(summary)

    logging.info(f"Summaries written to {os.path.basename(markdown_file)} and {os.path.basename(html_file)}")
    if invalid_feeds:
        logging.info(f"Removed {len(invalid_feeds)} feed(s) due to lack of content")

if __name__ == "__main__":
    main()