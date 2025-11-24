import feedparser
import requests
import google.generativeai as genai
import datetime
import os
import sys

# ================= 配置区域 =================
# 从环境变量中读取 Key，更安全
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN")

if not GEMINI_API_KEY:
    print("错误：未检测到 GEMINI_API_KEY 环境变量，请检查 GitHub Secrets 设置。")
    sys.exit(1)

# 3. 你想要关注的 RSS 源 (可自由修改)
RSS_FEEDS = [
    "https://openai.com/blog/rss.xml",
    "https://huggingface.co/blog/feed.xml",
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.theverge.com/rss/artificial-intelligence/index.xml" 
]
# ===========================================

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash-exp') 

def fetch_rss_data(feeds):
    print("正在抓取新闻...")
    combined_content = ""
    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)
            feed_title = feed.feed.get('title', 'Unknown Source')
            for entry in feed.entries[:3]:
                title = entry.title
                link = entry.link
                summary = getattr(entry, 'summary', getattr(entry, 'description', 'No summary'))
                combined_content += f"Source: {feed_title}\nTitle: {title}\nLink: {link}\nSummary: {summary[:200]}...\n\n"
        except Exception as e:
            print(f"Error parsing {feed_url}: {e}")
    return combined_content

def summarize_with_gemini(content):
    print("正在让 Gemini 总结...")
    if not content: return "今日暂无更新。"
    today = datetime.date.today().strftime("%Y-%m-%d")
    
    prompt = f"""
    你是一个专业的科技主编。请根据以下抓取到的 RSS AI新闻内容，为我生成一份“今日AI早报 ({today})”。
    要求：
    1. 语言风格：中文，简洁、专业但易懂。
    2. 筛选：只挑选最重要的 5-7 条新闻。
    3. 格式：开头包含 📅 **AI早报 | {today}**，每条新闻用Emoji列表，结尾给出一句简短点评。
    4. 不要使用Markdown代码块。
    数据：{content}
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Gemini 总结失败: {e}"

def push_to_wechat(content):
    if not PUSHPLUS_TOKEN:
        print("未设置推送Token，跳过推送")
        return
    url = "http://www.pushplus.plus/send"
    today = datetime.date.today().strftime("%Y-%m-%d")
    data = {"token": PUSHPLUS_TOKEN, "title": f"AI早报 | {today}", "content": content, "template": "markdown"}
    requests.post(url, json=data)

if __name__ == "__main__":
    raw_news = fetch_rss_data(RSS_FEEDS)
    if len(raw_news) > 50: 
        summary_report = summarize_with_gemini(raw_news)
        print(summary_report)
        push_to_wechat(summary_report)
    else:
        print("未抓取到足够的新闻数据。")
