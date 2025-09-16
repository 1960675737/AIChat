import os
from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context

# 可选：OpenAI 集成（如果你使用其它大模型，请替换本段调用）
try:
    from openai import OpenAI
    _openai_available = True
except Exception:
    _openai_available = False

app = Flask(__name__, static_url_path="/static", static_folder="static")

API_KEY = "sk-d9179d39f4eb465b93c2e2f0de50f947"

# 当应用运行后：
# 访问 http://localhost:5000/ 时，Flask 会执行 index() 函数。
# 函数从 static 文件夹中读取 index.html 文件，并返回给浏览器。
# 浏览器渲染 index.html，展示网站首页。
@app.route("/", methods=["GET"])
def index():
    # 提供静态首页
    return send_from_directory(app.static_folder, "index.html")

def call_llm(message: str, history=None, deep_think: bool = False) -> str:
    """
    调用大模型并返回回复文本。
    - 优先读取环境变量中的 Key（DEEPSEEK_API_KEY 或 OPENAI_API_KEY）
    - deep_think=True 时切换到可推理模型
    - 若无可用 Key 或未安装 openai 库，则返回演示模式回复。
    """
    history = history or []

    if API_KEY and _openai_available:
        client = OpenAI(api_key=API_KEY, base_url="https://api.deepseek.com")

        # 将历史消息拼接为 chat messages。history 期望为 [{role, content}, ...]
        messages = [{"role": "system", "content": "You are a helpful assistant."}]
        # 将最近若干条历史拼接；可做长度/Token控制
        for m in history[-10:-1]:
            role = m.get("role")
            content = m.get("content")
            if role in ("user", "assistant") and isinstance(content, str):
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": message})
        print("Messages for LLM:", messages)

        # 根据 deep_think 切换模型：普通对话 deepseek-chat，深度思考 deepseek-reasoner
        model = "deepseek-reasoner" if deep_think else "deepseek-chat"

        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7
        )
        reply = completion.choices[0].message.content.strip()
        return reply

    # 演示模式：未配置 Key 或 openai 库不可用
    return f"(演示模式{'-深度思考' if deep_think else ''}) 你说：{message}"


def call_llm_stream(message: str, history=None, deep_think: bool = False):
    """返回一个逐步产出内容的生成器，用于流式输出。"""
    history = history or []
    # api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")

    if API_KEY and _openai_available:
        client = OpenAI(api_key=API_KEY, base_url="https://api.deepseek.com")

        messages = [{"role": "system", "content": "You are a helpful assistant."}]
        for m in history[-10:-1]:
            role = m.get("role")
            content = m.get("content")
            if role in ("user", "assistant") and isinstance(content, str):
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": message})

        model = "deepseek-reasoner" if deep_think else "deepseek-chat"
        try:
            stream = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.7,
                stream=True,
            )
            for chunk in stream:  # chunk是一个对象类型
                try:
                    choice = chunk.choices[0] if getattr(chunk, "choices", None) else None
                    delta = getattr(choice, "delta", None) if choice else None
                    content = None
                    if delta is not None:
                        # 兼容对象或字典
                        content = getattr(delta, "content", None)  # 处理对象类型
                        if content is None and isinstance(delta, dict):  # 处理字典类型
                            content = delta.get("content")
                    if content:
                        # 当提取到有效 content 时，通过 yield content 产出该文本块（暂停函数执行，将内容返回给调用方）。
                        # 下一次迭代时，函数从上次 yield 的位置继续执行，处理下一个 chunk。
                        yield content
                except Exception:
                    continue
        except Exception as e:
            yield f"[stream-error]{str(e)}"
        return

    # 演示模式：逐块返回
    demo = f"(演示模式{'-深度思考' if deep_think else ''}) 你说：{message}"
    for ch in demo:
        yield ch


# 前端通过/api/chat 发起post请求
# chat() 函数处理前端发起的请求。 首先，它从请求中提取用户消息和对话历史；然后调用大模型获取返回结果；最后将结果以 JSON 格式返回给前端。
@app.post("/api/chat")
def chat():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    history = data.get("history") or []
    deep_think = bool(data.get("deep_think"))

    if not message:
        return jsonify({"error": "message 不能为空"}), 400

    try:
        reply = call_llm(message, history=history, deep_think=deep_think)
        model = "deepseek-reasoner" if deep_think else "deepseek-chat"
        return jsonify({"reply": reply, "model": model})
    except Exception as e:
        # 生产中建议更细致的错误上报/监控
        return jsonify({"error": "LLM 调用失败", "detail": str(e)}), 500


"""
    整体执行流程：
    1. 前端发送请求到 /api/chat_stream 接口。
    2. 后端执行 chat_stream() 函数，调用 call_llm_stream() 生成器。
    3. call_llm_stream() 向 LLM 接口请求流式数据，通过 yield 逐块返回内容。
    4. chat_stream() 中的 generate() 生成器接收这些块，再通过 yield 传递给前端。
    5. 前端逐块接收数据，实现 “边接收边显示” 的效果。
"""
@app.post("/api/chat_stream")
def chat_stream():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    history = data.get("history") or []
    deep_think = bool(data.get("deep_think"))

    if not message:
        return Response("message 不能为空", status=400, mimetype="text/plain; charset=utf-8")

    def generate():
        for chunk in call_llm_stream(message, history=history, deep_think=deep_think):
            # 直接把文本块写给客户端
            yield chunk

    return Response(stream_with_context(generate()), mimetype="text/plain; charset=utf-8")

if __name__ == "__main__":
    # PORT 可通过环境变量覆盖，默认 5000
    port = int(os.getenv("PORT", "3000"))
    app.run(host="0.0.0.0", port=port, debug=True)
