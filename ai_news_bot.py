import feedparser
import requests
import google.generativeai as genai
import datetime
import os
import sys
import re
import random

# ================= 🔴 必须修改区域 🔴 =================

# 1. 你的 PushPlus Token (必须填！否则发不出去)
# 请保留双引号，把中间的中文替换成你的 Token
PUSHPLUS_TOKEN = "332ed63d748f4c6fb2989b2cebc9d959" 

# 2. 你的 Gemini API Key (保持不动)
GEMINI_API_KEY = "AIzaSyCns0KEA_JkwD5NBvr7-E9iCoKGsUe1SZc"

# 3. 【强制修改】群组编码留空，先确保你自己能收到！
PUSHPLUS_TOPIC = "" 

# =======================================================

# RSS 源 (保留 Hacker News 热榜，确保内容质量)
RSS_FEEDS = [
    "https://hnrss.org/newest?q=AI+OR+GPT+OR+LLM&points=50", 
    "https://huggingface.co/blog/feed.xml",
    "https://openai.com/blog/rss.xml",
    "https://www.theverge.com/rss/artificial-intelligence/index.xml"
]

# 高颜值备用图库
DEFAULT_IMAGES = [
    "https://images.unsplash.com/photo-1677442136019-21780ecad995?w=800&q=80", 
    "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?w=800&q=80",
    "https://images.unsplash.com/photo-1625314897458-9cbb7e2d93e3?w=800&q=80",
    "https://images.unsplash.com/photo-1555255707-c07966088b7b?w=800&q=80",
    "https://images.unsplash.com/photo-1617791160505-6f00504e3519?w=800&q=80",
    "https://images.unsplash.com/photo-1620641788421-7a1c342ea42e?w=800&q=80",
]

print(f"DEBUG: 系统初始化...")
print(f"DEBUG: 检查 Token... {'✅ 已填入' if '这里填' not in PUSHPLUS_TOKEN and len(PUSHPLUS_TOKEN)>5 else '❌ 未填入 (请修改第17行)'}")

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

def extract_image(entry):
    """提取图片"""
    img_url = ""
    if 'media_content' in entry:
        for media in entry.media_content:
            if 'image' in media.get('medium', '') or 'image' in media.get('type', ''):
                img_url = media['url']
                break
    if not img_url and 'media_thumbnail' in entry:
        img_url = entry.media_thumbnail[0]['url']
    if not img_url and 'enclosures' in entry:
        for enclosure in entry.enclosures:
            if 'image' in enclosure.get('type', ''):
                img_url = enclosure['href']
                break
    if not img_url:
        description = getattr(entry, 'summary', getattr(entry, 'description', ''))
        img_match = re.search(r'<img[^>]+src=["\'](.*?)["\']', description)
        if img_match:
            img_url = img_match.group(1)
    # 如果没图或图链接无效，随机选一张
    if not img_url or "http" not in img_url:
        img_url = random.choice(DEFAULT_IMAGES)
    return img_url

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
                img_url = extract_image(entry)
                raw_summary = getattr(entry, 'summary', getattr(entry, 'description', 'No summary'))
                clean_summary = re.sub('<[^<]+?>', '', raw_summary)[:300]
                # 构造数据
                combined_content += f"""
                <NEWS_ITEM>
                TITLE: {title}
                SOURCE: {feed_title}
                LINK: {link}
                IMAGE: {img_url}
                SUMMARY: {clean_summary}
                </NEWS_ITEM>
                """
        except Exception as e:
            print(f"⚠️ 解析错误 {feed_url}: {e}")
    return combined_content

def get_gemini_response(content):
    model_name = get_best_model()
    if not model_name: return "❌ 错误：没找到可用模型。"

    print(f"🤖 使用模型: {model_name} 生成 HTML...")
    today = datetime.date.today().strftime("%Y-%m-%d")
    
    prompt = f"""
    你是一个高级前端工程师。请根据以下新闻数据，生成一份**HTML格式**的早报。
    【数据源】：
    {content}
    【要求】：
    1. 挑选 5 条最重要的新闻。
    2. **直接输出 HTML 代码**，不要包含 ```html 标记。
    3. 使用高颜值 CSS 卡片样式。
    【HTML 模板结构】：
    <div style="max-width: 600px; margin: 0 auto; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f5f5f5; padding: 15px; border-radius: 10px;">
        <div style="text-align: center; margin-bottom: 20px;">
            <h1 style="color: #333; font-size: 24px; margin: 0;">📅 AI 每日精选</h1>
            <p style="color: #666; font-size: 14px; margin: 5px 0;">{today} | 由 Gemini 整理</p>
        </div>
        <!-- 循环生成卡片 -->
        <div style="background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.05); margin-bottom: 20px;">
            <a href="{{链接}}" style="text-decoration: none; color: inherit; display: block;">
                <div style="height: 160px; overflow: hidden; background-color: #eee;">
                    <img src="{{图片链接}}" style="width: 100%; height: 100%; object-fit: cover;" alt="cover">
                </div>
                <div style="padding: 15px;">
                    <h3 style="margin: 0 0 8px 0; font-size: 18px; color: #222; line-height: 1.4; font-weight: 700;">{{标题}}</h3>
                    <div style="font-size: 12px; color: #999; margin-bottom: 10px;">{{来源}}</div>
                    <p style="margin: 0; font-size: 14px; color: #555; line-height: 1.6; text-align: justify;">{{一句话总结}}</p>
                </div>
            </a>
        </div>
        <div style="text-align: center; color: #aaa; font-size: 12px; margin-top: 20px;">
            <p>🤖 本内容由 AI 自动生成</p>
        </div>
    </div>
    """
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        text = response.text
        text = text.replace("```html", "").replace("```", "")
        return text
    except Exception as e:
        return f"<h3>Gemini 生成失败</h3><p>{e}</p>"

def push_to_wechat(content):
    if not PUSHPLUS_TOKEN or "这里填" in PUSHPLUS_TOKEN: 
        print("❌ 严重错误：Token 未填写！请修改代码第 17 行！")
        return
        
    print(f"🚀 正在强制推送 (一对一通道)...")
    url = "[http://www.pushplus.plus/send](http://www.pushplus.plus/send)"
    today = datetime.date.today().strftime("%Y-%m-%d")
    data = {
        "token": PUSHPLUS_TOKEN,
        "title": f"AI图文早报 | {today}",
        "content": content,
        "template": "html"
    }
    # 强制不使用 Topic，确保送达
    # if PUSHPLUS_TOPIC: data["topic"] = PUSHPLUS_TOPIC 
    
    try:
        resp = requests.post(url, json=data)
        print(f"✅ PushPlus 响应: {resp.text}") 
    except Exception as e:
        print(f"❌ 推送失败: {e}")

if __name__ == "__main__":
    news_content = fetch_rss_data(RSS_FEEDS)
    if len(news_content) < 10:
        print("⚠️ 内容太少，但我们还是尝试生成...")
    
    html_report = get_gemini_response(news_content)
    # 打印前200字符方便调试
    print(f"DEBUG: 生成内容预览: {html_report[:100]}...")
    push_to_wechat(html_report)
