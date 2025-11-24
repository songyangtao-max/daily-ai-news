import feedparser
import requests
import google.generativeai as genai
import datetime
import os
import sys
import time

# ================= 配置区域 =================

# 1. 【直接填入】你的 Gemini API Key
GEMINI_API_KEY = "AIzaSyCns0KEA_JkwD5NBvr7-E9iCoKGsUe1SZc"

# 2. PushPlus Token (如果你之前设置了Secrets，这里不用动；如果没设置，也可以直接填在这里)
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN")

# 3. 群组编码 (没有就留空 "")
PUSHPLUS_TOPIC = "" 

# RSS 源列表
RSS_FEEDS = [
    "https://openai.com/blog/rss.xml",
    "https://huggingface.co/blog/feed.xml",
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.theverge.com/rss/artificial-intelligence/index.xml" 
]
# ===========================================

print(f"DEBUG: 正在使用硬编码的 API Key...")

genai.configure(api_key=GEMINI_API_KEY)

def get_best_model():
    """自动寻找可用的模型"""
    print("🔍 正在向 Google 查询当前可用模型列表...")
    try:
        valid_models = []
        # 获取所有支持生成的模型
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                valid_models.append(m.name)
        
        print(f"✅ Google 返回了这些可用模型: {valid_models}")
        
        # 智能筛选：优先用 Flash (快/免费)，其次用 Pro
        for m in valid_models:
            if 'gemini-1.5-flash' in m: return m
        for m in valid_models:
            if 'gemini-1.5-pro' in m: return m
        for m in valid_models:
            if 'gemini-pro' in m: return m
            
        if valid_models:
            return valid_models[0]
            
    except Exception as e:
        print(f"❌ 查询模型列表失败: {e}")
        return None

    return None

def get_gemini_response(prompt):
    # 1. 动态获取模型名字
    model_name = get_best_model()
    
    if not model_name:
        return "❌ 致命错误：Key 是对的，但没找到可用模型，或者是网络问题。"

    print(f"🤖 决定使用模型: 【{model_name}】")
    
    # 2. 调用模型
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"❌ 模型调用报错: {e}"

def fetch_rss_data(feeds):
    print("📡 正在抓取新闻...")
    combined_content = ""
    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)
            feed_title = feed.feed.get('title', 'Unknown Source')
            for entry in feed.entries[:2]: 
                summary = getattr(entry, 'summary', getattr(entry, 'description', 'No summary'))
                combined_content += f"Source: {feed_title}\nTitle: {entry.title}\nSummary: {summary[:200]}...\n\n"
        except Exception as e:
            print(f"⚠️ 解析错误 {feed_url}: {e}")
    return combined_content

def push_to_wechat(content):
    if not PUSHPLUS_TOKEN: 
        print("⚠️ 未检测到 PUSHPLUS_TOKEN，跳过推送")
        return
    print("🚀 正在推送...")
    url = "http://www.pushplus.plus/send"
    today = datetime.date.today().strftime("%Y-%m-%d")
    data = {
        "token": PUSHPLUS_TOKEN,
        "title": f"AI早报 | {today}",
        "content": content,
        "template": "markdown"
    }
    if PUSHPLUS_TOPIC: data["topic"] = PUSHPLUS_TOPIC
    
    try:
        resp = requests.post(url, json=data)
        print(f"✅ 推送响应: {resp.text}")
    except Exception as e:
        print(f"❌ 推送失败: {e}")

if __name__ == "__main__":
    news_content = fetch_rss_data(RSS_FEEDS)
    if len(news_content) < 10: news_content = "今日无更新。"
    
    today = datetime.date.today().strftime("%Y-%m-%d")
    prompt = f"""
    你是一个科技主编。请根据以下RSS抓取的AI新闻，生成简报。日期：{today}
    要求：中文，通俗，只选5条，emoji标题，不要Markdown代码块。
    内容：{news_content}
    """
    
    report = get_gemini_response(prompt)
    print("📝 最终内容预览:", report[:100])
    
    push_to_wechat(report)
