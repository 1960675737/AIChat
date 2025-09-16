import os
from flask import Flask, request, jsonify, send_from_directory

# 可选：OpenAI 集成（如果你使用其它大模型，请替换本段调用）
try:
    from openai import OpenAI
    _openai_available = True
except Exception:
    _openai_available = False

app = Flask(__name__, static_url_path="/static", static_folder="static")


# 当应用运行后：
# 访问 http://localhost:5000/ 时，Flask 会执行 index() 函数。
# 函数从 static 文件夹中读取 index.html 文件，并返回给浏览器。
# 浏览器渲染 index.html，展示网站首页。
@app.route("/", methods=["GET"])
def index():
    # 提供静态首页
    return send_from_directory(app.static_folder, "index.html")

def call_llm(message: str, history=None) -> str:
    """
    调用大模型并返回回复文本。
    - 优先使用 OPENAI_API_KEY 调用 OpenAI。
    - 如果没有配置 Key 或未安装 openai 库，则返回演示模式回复。
    """
    history = history or []
    api_key = "sk-d9179d39f4eb465b93c2e2f0de50f947"
    # api_key = os.getenv("OPENAI_API_KEY")

    if api_key and _openai_available:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

        # 将历史消息拼接为 chat messages。history 期望为 [{role, content}, ...]
        messages = [{"role": "system", "content": "You are a helpful assistant."}]
        # 仅示例：将最近若干条历史拼接；生产中可做长度/Token控制
        for m in history[-10:-1]:
            role = m.get("role")
            content = m.get("content")
            if role in ("user", "assistant") and isinstance(content, str):
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": message})
        print("Messages for LLM:", messages)

        # 调用 Chat Completions（你也可以选择其它模型）
        completion = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            temperature=0.7
        )
        reply = completion.choices[0].message.content.strip()
        return reply

    # 演示模式：未配置 OpenAI 时的占位逻辑
    return f"(演示模式) 你说：{message}"


# 前端通过/api/chat 发起post请求
# chat() 函数处理前端发起的请求。 首先，它从请求中提取用户消息和对话历史；然后调用大模型获取返回结果；最后将结果以 JSON 格式返回给前端。
@app.post("/api/chat")
def chat():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    history = data.get("history") or []

    if not message:
        return jsonify({"error": "message 不能为空"}), 400

    try:
        reply = call_llm(message, history=history)
        return jsonify({"reply": reply})
    except Exception as e:
        # 生产中建议更细致的错误上报/监控
        return jsonify({"error": "LLM 调用失败", "detail": str(e)}), 500

if __name__ == "__main__":
    # PORT 可通过环境变量覆盖，默认 5000
    port = int(os.getenv("PORT", "3000"))
    app.run(host="0.0.0.0", port=port, debug=True)