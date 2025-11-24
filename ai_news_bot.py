import feedparser
import requests
import google.generativeai as genai
import datetime
import os
import sys
import re
import random

# ================= 配置区域 =================

# 1. API Key
GEMINI_API_KEY = "AIzaSyCns0KEA_JkwD5NBvr7-E9iCoKGsUe1SZc"

# 2. PushPlus Token
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN")

# 3. 群组编码 (没有就留空 "")
PUSHPLUS_TOPIC = "family_news" 

# 4. RSS 源 (保留了热度筛选)
RSS_FEEDS = [
    "https://hnrss.org/newest?q=AI+OR+GPT+OR+LLM&points=50", # HN 热榜
    "https://huggingface.co/blog/feed.xml",
    "https://openai.com/blog/rss.xml",
    "https://www.theverge.com/rss/artificial-intelligence/index.xml"
]

# 5. 【新增】高颜值备用图库 (当文章没图时，随机从这里选一张)
DEFAULT_IMAGES = [
    "https://images.unsplash.com/photo-1677442136019-21780ecad995?w=800&q=80", # AI芯片
    "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?w=800&q=80", # 抽象AI
    "https://images.unsplash.com/photo-1625314897458-9cbb7e2d93e3?w=800&q=80", # 神经网络
    "https://images.unsplash.com/photo-1676299081847-824d16b71d08?w=800&q=80", # 机器人手
    "https://images.unsplash.com/photo-1555255707-c07966088b7b?w=800&q=80", # 科技代码
    "https://images.unsplash.com/photo-1617791160505-6f00504e3519?w=800&q=80", # 赛博朋克
]
# ===========================================

print(f"DEBUG: 系统初始化...")
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
    """提取图片，如果没有就随机返回一张备用图"""
    img_url = ""
    # 1. 尝试 media_content
    if 'media_content' in entry:
        for media in entry.media_content:
            if 'image' in media.get('medium', '') or 'image' in media.get('type', ''):
                img_url = media['url']
                break
    
    # 2. 尝试 media_thumbnail
    if not img_url and 'media_thumbnail' in entry:
        img_url = entry.media_thumbnail[0]['url']
        
    # 3. 尝试 enclosure
    if not img_url and 'enclosures' in entry:
        for enclosure in entry.enclosures:
            if 'image' in enclosure.get('type', ''):
                img_url = enclosure['href']
                break
                
    # 4. 正则匹配 HTML
    if not img_url:
        description = getattr(entry, 'summary', getattr(entry, 'description', ''))
        img_match = re.search(r'<img[^>]+src=["\'](.*?)["\']', description)
        if img_match:
            img_url = img_match.group(1)
    
    # 【关键】如果还是没图，随机选一张备用图！
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
                img_url = extract_image(entry) # 这里现在一定会有图
                
                raw_summary = getattr(entry, 'summary', getattr(entry, 'description', 'No summary'))
                clean_summary = re.sub('<[^<]+?>', '', raw_summary)[:300]
                
                # 构造 JSON 风格的数据给 Gemini，方便它理解结构
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
    
    # 核心 Prompt：要求直接输出 HTML 卡片代码
    prompt = f"""
    你是一个高级前端工程师兼科技主编。请根据以下新闻数据，生成一份**HTML格式**的早报。
    
    【数据源】：
    {content}

    【要求】：
    1. 挑选 5 条最重要的新闻。
    2. **直接输出 HTML 代码**，不要包含 ```html 标记，也不要 markdown。
    3. 使用我指定的 CSS 样式，确保在微信里显示美观。
    
    【HTML 模板结构（请严格模仿）】：
    
    <div style="max-width: 600px; margin: 0 auto; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f5f5f5; padding: 15px; border-radius: 10px;">
        
        <!-- 头部 -->
        <div style="text-align: center; margin-bottom: 20px;">
            <h1 style="color: #333; font-size: 24px; margin: 0;">📅 AI 每日精选</h1>
            <p style="color: #666; font-size: 14px; margin: 5px 0;">{today} | 由 Gemini 整理</p>
        </div>

        <!-- 循环生成新闻卡片 -->
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
        <!-- 卡片结束 -->

        <!-- 底部 -->
        <div style="text-align: center; color: #aaa; font-size: 12px; margin-top: 20px;">
            <p>🤖 本内容由 AI 自动生成，仅供参考</p>
        </div>
    </div>
    """
    
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        text = response.text
        # 清理可能存在的 markdown 标记
        text = text.replace("```html", "").replace("```", "")
        return text
    except Exception as e:
        return f"<h3>Gemini 生成失败</h3><p>{e}</p>"

def push_to_wechat(content):
    if not PUSHPLUS_TOKEN: return
    print("🚀 正在推送 HTML 消息...")
    url = "[http://www.pushplus.plus/send](http://www.pushplus.plus/send)"
    today = datetime.date.today().strftime("%Y-%m-%d")
    data = {
        "token": PUSHPLUS_TOKEN,
        "title": f"AI早报 | {today}",
        "content": content,
        "template": "html"  # 【关键】这里改成了 html 模式
    }
    if PUSHPLUS_TOPIC: data["topic"] = PUSHPLUS_TOPIC
    
    try:
        requests.post(url, json=data)
        print("✅ 推送完成！")
    except Exception as e:
        print(f"❌ 推送失败: {e}")

if __name__ == "__main__":
    news_content = fetch_rss_data(RSS_FEEDS)
    if len(news_content) < 10:
        print("⚠️ 内容太少")
    else:
        html_report = get_gemini_response(news_content)
        push_to_wechat(html_report)
