import feedparser
import requests
import google.generativeai as genai
import datetime
import os
import sys
import re

# ================= 配置区域 =================

# 1. 【直接填入】你的 Gemini API Key
GEMINI_API_KEY = "AIzaSyCns0KEA_JkwD5NBvr7-E9iCoKGsUe1SZc"

# 2. PushPlus Token (从 Secrets 读取)
PUSHPLUS_TOKEN = os.environ.get("PUSHPLUS_TOKEN")

# 3. 群组编码 (没有就留空 "")
PUSHPLUS_TOPIC = "family_news" 

# 4. 【关键升级】使用“热度筛选”后的 RSS 源
# 这里特意选用了 Hacker News (AI分类, 且点赞数>50) 的源，确保是热门文章
RSS_FEEDS = [
    # Hacker News 上包含 'AI' 或 'GPT' 且分数大于50的热门讨论
    "https://hnrss.org/newest?q=AI+OR+GPT+OR+LLM&points=50",
    # HuggingFace 每日精选
    "https://huggingface.co/blog/feed.xml",
    # OpenAI 官方 (必看)
    "https://openai.com/blog/rss.xml",
    # The Verge AI 版块
    "https://www.theverge.com/rss/artificial-intelligence/index.xml"
]
# ===========================================

print(f"DEBUG: 正在初始化...")

genai.configure(api_key=GEMINI_API_KEY)

def get_best_model():
    """自动寻找可用的模型"""
    try:
        valid_models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                valid_models.append(m.name)
        
        # 优先用 Flash (快/免费)，其次用 Pro
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
    """尝试从 RSS 条目中提取图片链接"""
    # 1. 尝试 media_content (常见于标准 RSS)
    if 'media_content' in entry:
        for media in entry.media_content:
            if 'image' in media.get('medium', '') or 'image' in media.get('type', ''):
                return media['url']
    
    # 2. 尝试 media_thumbnail
    if 'media_thumbnail' in entry:
        return entry.media_thumbnail[0]['url']
        
    # 3. 尝试 enclosure (常见的播客或图片附件)
    if 'enclosures' in entry:
        for enclosure in entry.enclosures:
            if 'image' in enclosure.get('type', ''):
                return enclosure['href']
                
    # 4. 如果都没有，尝试从 description 的 HTML 里用正则找 <img src="...">
    description = getattr(entry, 'summary', getattr(entry, 'description', ''))
    img_match = re.search(r'<img[^>]+src=["\'](.*?)["\']', description)
    if img_match:
        return img_match.group(1)
        
    return "" # 没找到图片

def fetch_rss_data(feeds):
    print("📡 正在抓取热门新闻...")
    combined_content = ""
    article_count = 0
    
    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)
            feed_title = feed.feed.get('title', 'Unknown Source')
            print(f"   -> 源: {feed_title}")
            
            # 每个源只取前 2 条 (因为我们有很多源，避免太长)
            for entry in feed.entries[:2]: 
                title = entry.title
                link = entry.link
                # 提取图片
                img_url = extract_image(entry)
                
                # 清理 summary 中的 HTML 标签，只保留文字给 Gemini 看（节省 Token）
                raw_summary = getattr(entry, 'summary', getattr(entry, 'description', 'No summary'))
                clean_summary = re.sub('<[^<]+?>', '', raw_summary)[:300] # 只取前300字
                
                # 拼接数据给 Gemini，注意这里我们把 image_url 也放进去了
                combined_content += f"""
                ---
                【来源】{feed_title}
                【标题】{title}
                【链接】{link}
                【图片链接】{img_url}
                【摘要】{clean_summary}
                ---
                """
                article_count += 1
                
        except Exception as e:
            print(f"⚠️ 解析错误 {feed_url}: {e}")
            
    return combined_content

def get_gemini_response(content):
    model_name = get_best_model()
    if not model_name: return "❌ 错误：没找到可用模型。"

    print(f"🤖 使用模型: {model_name} 进行图文排版...")
    
    today = datetime.date.today().strftime("%Y-%m-%d")
    
    # 核心 Prompt：教 Gemini 怎么排版图片
    prompt = f"""
    你是一个专业的科技主编。请根据以下抓取到的热门 AI 新闻，生成一份“图文早报”。
    日期：{today}
    
    【重要排版要求】：
    1. 请从我提供的内容中挑选 **最热门、最有价值的 5-6 条** 新闻。
    2. **必须输出 Markdown 格式**。
    3. **如果有【图片链接】且不为空**，请在每条新闻的开头使用 Markdown 图片语法显示图片：`![封面](图片链接)`。
       注意：如果【图片链接】为空，就不要显示图片，只显示文字。
    4. 每条新闻的格式如下：
       
       ![封面](图片链接) 
       ### 标题 (加粗)
       > 来源媒体 | 📅 日期
       
       这里写一句话的中文通俗总结，要吸引人，像公众号爆款文章的摘要。
       [🔗 点击阅读原文](链接)
       
       ---
       
    5. 结尾给一句简短的行业趋势点评。

    【原始数据】：
    {content}
    """
    
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"❌ Gemini 生成失败: {e}"

def push_to_wechat(content):
    if not PUSHPLUS_TOKEN: 
        print("⚠️ 未设置 Token，跳过推送")
        return
    print("🚀 正在推送图文消息...")
    url = "http://www.pushplus.plus/send"
    today = datetime.date.today().strftime("%Y-%m-%d")
    data = {
        "token": PUSHPLUS_TOKEN,
        "title": f"AI图文早报 | {today}",
        "content": content,
        "template": "markdown" # 必须是 markdown 才能显示图片
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
        print("⚠️ 内容太少，无法生成。")
    else:
        report = get_gemini_response(news_content)
        # 打印预览
        print(report[:200] + "...")
        push_to_wechat(report)
