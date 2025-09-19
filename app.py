import os
import sqlite3
import json
import uuid
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context, g
# g 是一个特殊的全局对象（由 Flask 框架提供），用于在一次请求的生命周期内存储和共享数据。

# 可选：OpenAI 集成（如果你使用其它大模型，请替换本段调用）
try:
    from openai import OpenAI
    _openai_available = True
except Exception:
    _openai_available = False

app = Flask(__name__, static_url_path="/static", static_folder="static")

# 数据库配置
DATABASE = 'chat.db'

def get_db():
    """获取数据库连接"""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row  # 使查询结果可以像字典一样访问
    return db

@app.teardown_appcontext
def close_connection(exception):
    """请求结束时关闭数据库连接"""
    print("请求已结束，关闭数据库连接")
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# 确保数据库已初始化
try:
    import init_db
    init_db.init_database()
except Exception as e:
    print(f"数据库初始化警告: {e}")

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


# ===== 会话管理 API =====

@app.post("/api/sessions")
def create_session():
    """创建新会话"""
    data = request.get_json(silent=True) or {}
    title = data.get("title", "新会话").strip()
    deep_think = bool(data.get("deep_think", False))
    
    session_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    
    db = get_db()
    db.execute(
        "INSERT INTO sessions (id, title, deep_think, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (session_id, title, int(deep_think), now, now)
    )
    db.commit()
    
    return jsonify({
        "id": session_id,
        "title": title,
        "deep_think": deep_think,
        "created_at": now,
        "updated_at": now
    })


@app.get("/api/sessions")
def list_sessions():
    """获取会话列表"""
    db = get_db()
    cursor = db.execute(
        "SELECT id, title, deep_think, created_at, updated_at FROM sessions ORDER BY updated_at DESC LIMIT 100"
    )
    sessions = []
    for row in cursor.fetchall():
        sessions.append({
            "id": row["id"],
            "title": row["title"],
            "deep_think": bool(row["deep_think"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        })
    return jsonify({"sessions": sessions})


@app.get("/api/sessions/<session_id>")
def get_session(session_id):
    """获取单个会话信息"""
    db = get_db()
    # 使用 ? 防止注入风险
    # 原理：将 SQL 语句的结构与用户输入的参数严格分离，数据库会将参数视为 “纯数据” 而非 SQL 代码的一部分。举例，即使参数中出现 OR '1'='1'，也只会作为纯数据替换？的占位，不会有逻辑执行
    cursor = db.execute(
        "SELECT id, title, deep_think, created_at, updated_at FROM sessions WHERE id = ?",
        (session_id,)
    )
    row = cursor.fetchone()
    if not row:
        return jsonify({"error": "会话不存在"}), 404
    
    return jsonify({
        "id": row["id"],
        "title": row["title"],
        "deep_think": bool(row["deep_think"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"]
    })


@app.patch("/api/sessions/<session_id>")
def update_session(session_id):
    """更新会话（标题或深度思考模式）"""
    data = request.get_json(silent=True) or {}
    db = get_db()
    
    # 检查会话是否存在
    cursor = db.execute("SELECT id FROM sessions WHERE id = ?", (session_id,))
    if not cursor.fetchone():
        return jsonify({"error": "会话不存在"}), 404
    
    # 构建更新语句
    updates = []
    params = []
    
    if "title" in data:
        updates.append("title = ?")
        params.append(data["title"])
    
    if "deep_think" in data:
        updates.append("deep_think = ?")
        params.append(int(bool(data["deep_think"])))
    
    if updates:
        updates.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        params.append(session_id)
        
        query = f"UPDATE sessions SET {', '.join(updates)} WHERE id = ?"
        db.execute(query, params)
        db.commit()
    
    return jsonify({"success": True})


@app.delete("/api/sessions/<session_id>")
def delete_session(session_id):
    """删除会话"""
    db = get_db()
    db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    db.commit()
    return jsonify({"success": True})


@app.get("/api/sessions/<session_id>/messages")
def get_messages(session_id):
    """获取会话的消息历史"""
    db = get_db()
    cursor = db.execute(
        "SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY created_at",
        (session_id,)
    )
    messages = []
    for row in cursor.fetchall():
        messages.append({
            "role": row["role"],
            "content": row["content"],
            "created_at": row["created_at"]
        })
    return jsonify({"messages": messages})


@app.post("/api/chat_stream_v2")
def chat_stream_v2():
    """带会话管理的流式聊天接口"""
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id")
    message = (data.get("message") or "").strip()
    
    if not session_id:
        return Response("session_id 不能为空", status=400, mimetype="text/plain; charset=utf-8")
    
    if not message:
        return Response("message 不能为空", status=400, mimetype="text/plain; charset=utf-8")
    
    db = get_db()
    
    # 获取会话信息
    cursor = db.execute(
        "SELECT id, title, deep_think FROM sessions WHERE id = ?",
        (session_id,)
    )
    session = cursor.fetchone()
    if not session:
        return Response("会话不存在", status=404, mimetype="text/plain; charset=utf-8")
    
    deep_think = bool(session["deep_think"])
    
    # 获取历史消息
    cursor = db.execute(
        "SELECT role, content FROM messages WHERE session_id = ? ORDER BY created_at",
        (session_id,)
    )
    history = []
    for row in cursor.fetchall():
        history.append({"role": row["role"], "content": row["content"]})
    
    # 保存用户消息
    now = datetime.now().isoformat()
    db.execute(
        "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        (session_id, "user", message, now)
    )
    
    # 如果是第一条消息且标题是"新会话"，自动更新标题
    if session["title"] == "新会话" and len(history) == 0:
        new_title = message[:50] + ("..." if len(message) > 50 else "")
        db.execute(
            "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
            (new_title, now, session_id)
        )
    else:
        db.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (now, session_id)
        )
    
    db.commit()
    
    def generate():
        accumulated = ""
        try:
            for chunk in call_llm_stream(message, history=history, deep_think=deep_think):
                accumulated += chunk
                yield chunk
        except GeneratorExit:
            # 客户端断开连接，仍尝试保存已生成的内容
            pass
        except Exception as _stream_err:
            # 流式调用异常时，仍保存已生成的部分
            print("[warn] stream error:", _stream_err)
        finally:
            # 流结束后（或异常/断连）保存助手回复
            if accumulated:
                try:
                    # 为避免请求上下文结束导致的已关闭连接，这里使用一次性新连接
                    conn = sqlite3.connect(DATABASE)
                    now2 = datetime.now().isoformat()
                    conn.execute(
                        "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                        (session_id, "assistant", accumulated, now2)
                    )
                    # 同步更新会话时间，方便列表排序/显示
                    conn.execute(
                        "UPDATE sessions SET updated_at = ? WHERE id = ?",
                        (now2, session_id)
                    )
                    conn.commit()
                except Exception as _e:
                    # 记录到标准输出，避免中断流
                    print("[warn] failed to persist assistant reply in stream finalizer:", _e)
                finally:
                    try:
                        conn.close()
                    except Exception:
                        pass

    return Response(stream_with_context(generate()), mimetype="text/plain; charset=utf-8")


if __name__ == "__main__":
    # PORT 可通过环境变量覆盖，默认 5000
    port = int(os.getenv("PORT", "3000"))
    app.run(host="0.0.0.0", port=port, debug=True)
