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
# 填入你的群组编码 (如果发给自己就留空 "")
PUSHPLUS_TOPIC = "" 

# RSS 源列表
RSS_FEEDS = [
    "https://openai.com/blog/rss.xml",
    "https://huggingface.co/blog/feed.xml",
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.theverge.com/rss/artificial-intelligence/index.xml" 
]
# ===========================================

# 检查环境
print(f"DEBUG: 检查 API Key... {'✅ 已获取' if GEMINI_API_KEY else '❌ 未获取'}")
print(f"DEBUG: 检查 PushPlus Token... {'✅ 已获取' if PUSHPLUS_TOKEN else '❌ 未获取'}")

if not GEMINI_API_KEY:
    print("❌ 致命错误：没有找到 API Key，程序无法运行。")
    sys.exit(1)

genai.configure(api_key=GEMINI_API_KEY)

def get_gemini_response(prompt):
    """智能尝试不同的模型，防止报错"""
    # 调整顺序：先试最稳的老款 Pro，再试新款 Flash
    models_to_try = [
        'gemini-pro',          # 最稳，几乎不报错
        'gemini-1.5-flash',    # 快，但偶尔 404
        'gemini-1.5-pro'       # 备用
    ]
    
    last_error = ""
    
    for model_name in models_to_try:
        try:
            print(f"🤖 正在尝试使用模型: {model_name} ...")
            model = genai.GenerativeModel(model_name)
            # 这里的 prompt 稍微简单点，减少报错概率
            response = model.generate_content(prompt)
            print(f"✅ 模型 {model_name} 调用成功！")
            return response.text
        except Exception as e:
            print(f"⚠️ 模型 {model_name} 失败: {e}")
            last_error = str(e)
            print("🔄 正在自动切换到下一个备用模型...")
            time.sleep(2) 
            continue
            
    # 如果都失败了，返回错误信息，并在微信里告诉你
    return f"❌ 所有模型都挂了。\n最后一次报错信息：{last_error}\n请检查 API Key 是否有效。"

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
        print("⚠️ 未设置 PUSHPLUS_TOKEN，无法发送。")
        return

    print("🚀 正在强行推送到微信...")
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
        response = requests.post(url, json=data)
        print(f"✅ PushPlus 响应结果: {response.text}")
    except Exception as e:
        print(f"❌ 推送彻底失败: {e}")

if __name__ == "__main__":
    news_content = fetch_rss_data(RSS_FEEDS)
    
    # 哪怕没抓到新闻，也要跑后面的逻辑，防止静默失败
    if len(news_content) < 10:
        news_content = "今日 RSS 源似乎没有更新，或者抓取失败。请检查 RSS 链接。"

    print("\n" + "="*30)
    
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
    
    # 获取结果（无论成功还是报错）
    report = get_gemini_response(prompt)
    print("📝 生成的内容摘要(前100字):", report[:100])
    print("="*30 + "\n")
    
    # 【关键修改】删除了 if 判断，无论内容是什么，都强制发送！
    push_to_wechat(report)
