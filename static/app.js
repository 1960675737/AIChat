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
  chatEl.scrollTop = chatEl.scrollHeight;
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

// 页面加载时初始化 有历史记录则加载历史记录，否则显示欢迎语
document.addEventListener("DOMContentLoaded", () => {
  history = loadHistory();
  if (history.length > 0) {
    renderFromHistory();
  } else {
    initializeChat();
  }

  // 初始化深度思考开关
  deepThink = loadDeepThink();
  updateDeepThinkButton();

  const deepBtn = document.getElementById("deepthink-btn");
  console.log("获取到的按钮元素：", deepBtn);
  if (deepBtn) {
    deepBtn.addEventListener("click", () => {
      deepThink = !deepThink;
      console.log("深度思考状态切换为：", deepThink);
      saveDeepThink();
      updateDeepThinkButton();
      inputEl.focus();
    });
  }

  // 绑定清空按钮
  const clearBtn = document.getElementById("clear-btn");
  if (clearBtn) {
    clearBtn.addEventListener("click", () => {
      const ok = confirm("确定要清空本地对话吗？此操作不可撤销。");
      if (!ok) return;
      clearConversation();
    });
  }
});

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
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: text,
        // 如不需要上下文，可不传 history
        history,
        deep_think: deepThink
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || `HTTP ${res.status}`);
    }

    const data = await res.json();
    const reply = data.reply || "(无回复)";
    appendMessage("assistant", reply);
    history.push({ role: "assistant", content: reply });
    saveHistory();
  } catch (err) {
    appendMessage("assistant", `出现错误：${err.message}`);
  } finally {
    setPending(false);
    inputEl.focus();
  }
});