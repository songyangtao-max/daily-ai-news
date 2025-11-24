import feedparser
import requests
import google.generativeai as genai
import datetime
import os
import sys
import time

# ================= 配置区域 =================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN")
# 填入你的群组编码，如果发给自己就留空 ""
PUSHPLUS_TOPIC = "" 

# RSS 源列表
RSS_FEEDS = [
    "https://openai.com/blog/rss.xml",
    "https://huggingface.co/blog/feed.xml",
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.theverge.com/rss/artificial-intelligence/index.xml" 
]
# ===========================================

if not GEMINI_API_KEY:
    print("❌ 错误：未检测到 GEMINI_API_KEY")
    sys.exit(1)

genai.configure(api_key=GEMINI_API_KEY)

def get_gemini_response(prompt):
    """智能尝试不同的模型，防止报错"""
    # 优先列表：先试 1.5 Flash (快且免费额度高)，不行再试老款 Pro
    models_to_try = [
        'gemini-1.5-flash', 
        'gemini-1.5-pro',
        'gemini-pro'
    ]
    
    for model_name in models_to_try:
        try:
            print(f"🤖 正在尝试使用模型: {model_name} ...")
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"⚠️ 模型 {model_name} 失败: {e}")
            print("🔄 正在自动切换到下一个备用模型...")
            time.sleep(2) # 歇两秒再试
            continue
            
    return "❌ 所有模型都尝试失败，请检查 API Key 或网络状态。"

def fetch_rss_data(feeds):
    print("📡 正在抓取新闻...")
    combined_content = ""
    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)
            feed_title = feed.feed.get('title', 'Unknown Source')
            print(f"   -> 已抓取: {feed_title}")
            for entry in feed.entries[:2]: 
                title = entry.title
                link = entry.link
                summary = getattr(entry, 'summary', getattr(entry, 'description', 'No summary'))
                combined_content += f"Source: {feed_title}\nTitle: {title}\nLink: {link}\nSummary: {summary[:200]}...\n\n"
        except Exception as e:
            print(f"⚠️ 解析错误 {feed_url}: {e}")
    return combined_content

def push_to_wechat(content):
    if not PUSHPLUS_TOKEN:
        print("⚠️ 未设置 PUSHPLUS_TOKEN，跳过推送")
        return

    print("🚀 正在推送到微信...")
    url = "http://www.pushplus.plus/send"
    today = datetime.date.today().strftime("%Y-%m-%d")
    
    data = {
        "token": PUSHPLUS_TOKEN,
        "title": f"AI早报 | {today}",
        "content": content,
        "template": "markdown"
    }
    if PUSHPLUS_TOPIC:
        data["topic"] = PUSHPLUS_TOPIC
    
    try:
        requests.post(url, json=data)
        print("✅ 推送请求已发送")
    except Exception as e:
        print(f"❌ 推送失败: {e}")

if __name__ == "__main__":
    news_content = fetch_rss_data(RSS_FEEDS)
    if len(news_content) > 50:
        print("\n" + "="*30)
        
        # 构建 Prompt
        today = datetime.date.today().strftime("%Y-%m-%d")
        prompt = f"""
        你是一个科技主编。请根据以下RSS抓取的AI新闻，为家人朋友生成一份简报。
        日期：{today}
        要求：
        1. 用中文，通俗易懂，像发朋友圈一样。
        2. 只选最重要的 5 条。
        3. 每条格式：emoji 标题 (来源) \n 一句话总结...
        4. 结尾给一句简短的个人见解/辣评。
        5. 不要使用Markdown代码块。
        内容：{news_content}
        """
        
        # 调用智能生成函数
        report = get_gemini_response(prompt)
        print(report)
        print("="*30 + "\n")
        
        if "❌" not in report:
            push_to_wechat(report)
    else:
        print("⚠️ 未抓取到足够数据。")
