import feedparser
import requests
import google.generativeai as genai
import datetime
import os
import sys
import time

# ================= 配置区域 =================

# 1. 你的 PushPlus Token (必须填)
# 为了防止出错，这里直接填入你的 Token 字符串 (例如 "332e......")
PUSHPLUS_TOKEN = "332ed63d748f4c6fb2989b2cebc9d959" 

# 2. 你的 Gemini API Key (推荐使用 Secrets，或者临时填在这里测试)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") 
# 如果 Secrets 没配置好，也可以临时解开下面这行的注释直接填：
# GEMINI_API_KEY = "AIzaSyCns0KEA_JkwD5NBvr7-E9iCoKGsUe1SZc"

# 3. 群组编码 (发给家人填 "family_news"，发给自己留空 "")
PUSHPLUS_TOPIC = "family_news"

# 4. RSS 源 (这一版我们用回最基础的源，确保抓取稳定)
RSS_FEEDS = [
    "https://hnrss.org/newest?q=AI+OR+GPT+OR+LLM&points=50", 
    "https://huggingface.co/blog/feed.xml",
    "https://openai.com/blog/rss.xml",
    "https://www.theverge.com/rss/artificial-intelligence/index.xml"
]

# ===========================================

print(f"DEBUG: 系统初始化...")
if not GEMINI_API_KEY:
    print("❌ 致命错误：没有找到 API Key。")
    sys.exit(1)

genai.configure(api_key=GEMINI_API_KEY)

def get_best_model():
    """自动寻找可用的模型"""
    try:
        valid_models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                valid_models.append(m.name)
        
        # 优先用 Flash，其次 Pro
        for m in valid_models:
            if 'gemini-1.5-flash' in m: return m
        for m in valid_models:
            if 'gemini-1.5-pro' in m: return m
        for m in valid_models:
            if 'gemini-pro' in m: return m
        if valid_models: return valid_models[0]
    except Exception:
        return None
    return None

def fetch_rss_data(feeds):
    print("📡 正在抓取新闻...")
    combined_content = ""
    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)
            feed_title = feed.feed.get('title', 'Unknown Source')
            print(f"   -> 源: {feed_title}")
            for entry in feed.entries[:2]: 
                title = entry.title
                link = entry.link
                summary = getattr(entry, 'summary', getattr(entry, 'description', 'No summary'))
                combined_content += f"Source: {feed_title}\nTitle: {title}\nLink: {link}\nSummary: {summary[:200]}...\n\n"
        except Exception as e:
            print(f"⚠️ 解析错误 {feed_url}: {e}")
    return combined_content

def get_gemini_response(content):
    model_name = get_best_model()
    if not model_name: return "❌ 错误：没找到可用模型。"

    print(f"🤖 使用模型: {model_name} 生成文字简报...")
    today = datetime.date.today().strftime("%Y-%m-%d")
    
    # 【回归最简单的 Prompt】只要求生成 Markdown 文字
    prompt = f"""
    你是一个科技主编。请根据以下RSS抓取的AI新闻，生成一份简报。
    日期：{today}
    
    要求：
    1. 用中文，通俗易懂。
    2. 只选最重要的 5 条。
    3. 每条格式：emoji 标题 (来源) \n 一句话总结... \n [🔗链接](URL)
    4. 结尾给一句简短的个人见解/辣评。
    5. 不要使用代码块，直接输出 Markdown 文本。

    内容：
    {content}
    """
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"❌ Gemini 总结失败: {e}"

def push_to_wechat(content):
    if not PUSHPLUS_TOKEN or "这里填" in PUSHPLUS_TOKEN: 
        print("❌ 严重错误：Token 未填写！请修改代码第 15 行！")
        return

    print(f"🚀 正在推送 Markdown 消息...")
    url = "http://www.pushplus.plus/send"
    today = datetime.date.today().strftime("%Y-%m-%d")
    
    data = {
        "token": PUSHPLUS_TOKEN,
        "title": f"AI早报 | {today}",
        "content": content,
        "template": "markdown" # 回归 markdown 模式
    }
    if PUSHPLUS_TOPIC: 
        data["topic"] = PUSHPLUS_TOPIC
    
    try:
        resp = requests.post(url, json=data)
        print(f"✅ 推送响应: {resp.text}")
    except Exception as e:
        print(f"❌ 推送失败: {e}")

if __name__ == "__main__":
    news_content = fetch_rss_data(RSS_FEEDS)
    if len(news_content) < 10:
        print("⚠️ 内容太少，尝试强行生成...")
    
    report = get_gemini_response(news_content)
    print(f"DEBUG: 内容预览: {report[:100]}...")
    push_to_wechat(report)
