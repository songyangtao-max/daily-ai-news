import feedparser
import requests
import google.generativeai as genai
import datetime
import os
import sys

# ================= 配置区域 =================
# 1. 从 GitHub Secrets 读取密钥 (千万不要在这里直接填密码)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN")

# 2. 【关键】如果你要发给家人群组，请在这里填入你的“群组编码”
# 如果只想发给自己，就保持为空字符串 ""
PUSHPLUS_TOPIC = "family_news"   # 例如: "family_news"

# 3. 你想要关注的 RSS 源
RSS_FEEDS = [
    "https://openai.com/blog/rss.xml",
    "https://huggingface.co/blog/feed.xml",
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.theverge.com/rss/artificial-intelligence/index.xml" 
]

# ===========================================

# 检查 Key 是否存在
if not GEMINI_API_KEY:
    print("❌ 错误：未检测到 GEMINI_API_KEY，请检查 GitHub Secrets 设置！")
    sys.exit(1)

# 初始化 Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def fetch_rss_data(feeds):
    """抓取 RSS 数据"""
    print("📡 正在抓取新闻...")
    combined_content = ""
    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)
            feed_title = feed.feed.get('title', 'Unknown Source')
            print(f"   -> 已抓取: {feed_title}")
            
            # 每个源只取最新的 2 条，避免内容太长
            for entry in feed.entries[:2]: 
                title = entry.title
                link = entry.link
                summary = getattr(entry, 'summary', getattr(entry, 'description', 'No summary'))
                combined_content += f"Source: {feed_title}\nTitle: {title}\nLink: {link}\nSummary: {summary[:200]}...\n\n"
        except Exception as e:
            print(f"⚠️ 解析错误 {feed_url}: {e}")
    return combined_content

def summarize_with_gemini(content):
    """使用 Gemini 总结"""
    print("🤖 正在让 Gemini 总结...")
    if not content: return "今日暂无更新。"
    today = datetime.date.today().strftime("%Y-%m-%d")
    
    prompt = f"""
    你是一个科技主编。请根据以下RSS抓取的AI新闻，为家人朋友生成一份简报。
    日期：{today}
    
    要求：
    1. 用中文，通俗易懂，像发朋友圈一样。
    2. 只选最重要的 5 条。
    3. 每条格式：emoji 标题 (来源) \n 一句话总结...
    4. 结尾给一句简短的个人见解/辣评。
    5. 不要使用Markdown代码块，直接输出文本。

    内容：
    {content}
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"❌ Gemini 总结失败: {e}"

def push_to_wechat(content):
    """发送到微信 (PushPlus)"""
    if not PUSHPLUS_TOKEN:
        print("⚠️ 未检测到 PUSHPLUS_TOKEN，跳过微信推送。")
        return

    print("🚀 正在推送到微信...")
    url = "http://www.pushplus.plus/send"
    today = datetime.date.today().strftime("%Y-%m-%d")
    
    # 构造发送数据
    data = {
        "token": PUSHPLUS_TOKEN,
        "title": f"AI早报 | {today}",
        "content": content,
        "template": "markdown"
    }

    # 如果设置了群组编码，就添加 topic 字段
    if PUSHPLUS_TOPIC:
        data["topic"] = PUSHPLUS_TOPIC
        print(f"   -> 目标群组: {PUSHPLUS_TOPIC}")
    else:
        print("   -> 目标: 个人 (一对一)")
    
    try:
        response = requests.post(url, json=data)
        print(f"✅ 推送结果: {response.json()}")
    except Exception as e:
        print(f"❌ 推送失败: {e}")

if __name__ == "__main__":
    # 1. 抓取
    news_content = fetch_rss_data(RSS_FEEDS)
    
    # 2. 总结与发送
    if len(news_content) > 50:
        print("\n" + "="*30)
        report = summarize_with_gemini(news_content)
        print(report) # 在 GitHub 日志中显示
        print("="*30 + "\n")
        
        # 3. 推送
        push_to_wechat(report)
    else:
        print("⚠️ 未抓取到足够数据。")
