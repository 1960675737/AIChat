const chatEl = document.getElementById("chat");
const formEl = document.getElementById("chat-form");
const inputEl = document.getElementById("msg");

/// 用 let，允许在初始化时用持久化数据覆盖
let history = [];

// 本地存储键
const STORAGE_KEY = "AIChat_history_v1";
////////////////////
const DEEPTHINK_KEY = "AIChat_deepthink_v1";
let deepThink = false;
//////////////////

// 将历史记录保存到本地存储
function saveHistory() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
  } catch {}
}

/////////////////////
function saveDeepThink() {
  try {
    localStorage.setItem(DEEPTHINK_KEY, deepThink ? "1" : "0");
  } catch {}
}

function loadDeepThink() {
  try {
    return localStorage.getItem(DEEPTHINK_KEY) === "1";
  } catch {
    return false;
  }
}
///////////////////////

// 从本地存储加载历史记录
function loadHistory() {
  try {
    const s = localStorage.getItem(STORAGE_KEY);
    if (!s) return [];
    const parsed = JSON.parse(s);
    // 只保留我们认识的结构
    return Array.isArray(parsed)
      ? parsed.filter(m => m && (m.role === "user" || m.role === "assistant") && typeof m.content === "string")
      : [];
  } catch {
    return [];
  }
}

// 根据历史记录渲染对话
function renderFromHistory() {
  chatEl.innerHTML = "";  // 清空所有对话
  initializeChat()
  for (const m of history) {
    appendMessage(m.role, m.content);
  }
}

// 初始化聊天窗口，显示欢迎语
function initializeChat() {
  const welcome = [
      "👋 你好，我是你的 AI 助手。",
      "",
      "你有任何问题都可以问我，我会尽力帮你解答！"
    ].join("\n");
  appendMessage("assistant", welcome);
}

// 将消息内容在聊天窗口渲染出来
function appendMessage(role, content) {
  const wrap = document.createElement("div");
  wrap.className = `msg ${role}`;

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = content;

  wrap.appendChild(bubble);
  chatEl.appendChild(wrap);
  // 聊天窗口自动滚动到底部
  chatEl.scrollTop = chatEl.scrollHeight;
  // 流式响应场景中，必须返回气泡元素以便后续更新内容
  return bubble; // 返回以便流式更新
}

// 切换深度思考按钮状态
function updateDeepThinkButton() {
  const btn = document.getElementById("deepthink-btn");
  if (!btn) return;
  btn.classList.toggle("active", deepThink);
  btn.textContent = `深度思考：${deepThink ? "开" : "关"}`;
}

// 设置输入框和按钮的禁用状态 - 正在请求等待响应返回时禁用，防止重复提交
function setPending(pending) {
  inputEl.disabled = pending;
  const submitBtn = formEl.querySelector("button");
  if (submitBtn) submitBtn.disabled = pending;
  // const dtBtn = document.getElementById("deepthink-btn");
  // if (dtBtn) dtBtn.disabled = pending;
}

// 清空聊天记录
function clearConversation(){
  history = [];
  saveHistory();
  chatEl.innerHTML = "";
  initializeChat();
  inputEl.focus();

}

// 初始化 UI（可重复调用但只绑定一次）
function initUI() {
  // 仅当还没有渲染过内容时才初始化/恢复历史
  if (!chatEl.dataset.initialized) {
    history = loadHistory();
    if (history.length > 0) {
      renderFromHistory();
    } else {
      initializeChat();
    }
    chatEl.dataset.initialized = "1";
  }

  // 初始化深度思考开关
  deepThink = loadDeepThink();
  updateDeepThinkButton();

  // 绑定切换深度思考模式按钮
  const deepBtn = document.getElementById("deepthink-btn");
  if (deepBtn && !deepBtn.dataset.bound) {
    deepBtn.addEventListener("click", () => {
      deepThink = !deepThink;
      saveDeepThink();
      updateDeepThinkButton();
      inputEl.focus();
    });
    deepBtn.dataset.bound = "1";
  }

  // 绑定清空按钮
  const clearBtn = document.getElementById("clear-btn");
  if (clearBtn && !clearBtn.dataset.bound) {
    clearBtn.addEventListener("click", () => {
      const ok = confirm("确定要清空本地对话吗？此操作不可撤销。");
      if (!ok) return;
      clearConversation();
    });
    clearBtn.dataset.bound = "1";
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initUI);
} else {
  initUI();
}

formEl.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = inputEl.value.trim();
  if (!text) return;

  // 前端立即渲染用户消息
  appendMessage("user", text);
  history.push({ role: "user", content: text });
  saveHistory();

  inputEl.value = "";
  setPending(true);

  try {
    const assistantBubble = appendMessage("assistant", "");

    const res = await fetch("/api/chat_stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: text,
        // 如不需要上下文，可不传 history
        history,
        deep_think: deepThink
      }),
    });

    if (!res.ok || !res.body) {
      const errText = await (res.text ? res.text() : Promise.resolve(""));
      throw new Error(errText || `HTTP ${res.status}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let acc = "";  // 作用是获取完整的流式返回，用于存入历史
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, { stream: true });
      if (chunk) {
        acc += chunk;
        assistantBubble.textContent += chunk;
        chatEl.scrollTop = chatEl.scrollHeight;
      }
    }

    // 完成后入历史
    const reply = acc || "(无回复)";
    history.push({ role: "assistant", content: reply });
    saveHistory();
  } catch (err) {
    appendMessage("assistant", `出现错误：${err.message}`);
  } finally {
    setPending(false);
    inputEl.focus();
  }
});
