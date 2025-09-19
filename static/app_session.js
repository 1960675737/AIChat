// DOM 元素
const chatEl = document.getElementById("chat");
const formEl = document.getElementById("chat-form");
const inputEl = document.getElementById("msg");
const sessionListEl = document.getElementById("session-list");
const sessionTitleEl = document.getElementById("session-title");
const deepthinkBtn = document.getElementById("deepthink-btn");
const deleteSessionBtn = document.getElementById("delete-session-btn");
const newSessionBtn = document.getElementById("new-session-btn");

// 会话管理状态
let currentSessionId = null;   // 所有处理逻辑中，需要维护当前会话ID
let currentSession = null;
let sessions = [];

// API 调用函数
const api = {
  // 创建新会话
  async createSession(title = "新会话", deepThink = false) {
    const res = await fetch("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, deep_think: deepThink }),
    });
    if (!res.ok) throw new Error(`创建会话失败: ${res.status}`);
    return await res.json();
  },

  // 获取会话列表
  async getSessions() {
    const res = await fetch("/api/sessions");
    if (!res.ok) throw new Error(`获取会话列表失败: ${res.status}`);
    const data = await res.json();
    return data.sessions;
  },

  // 获取单个会话
  async getSession(sessionId) {
    const res = await fetch(`/api/sessions/${sessionId}`);
    if (!res.ok) throw new Error(`获取会话失败: ${res.status}`);
    return await res.json();
  },

  // 更新会话
  async updateSession(sessionId, updates) {
    const res = await fetch(`/api/sessions/${sessionId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updates),
    });
    if (!res.ok) throw new Error(`更新会话失败: ${res.status}`);
    return await res.json();
  },

  // 删除会话
  async deleteSession(sessionId) {
    const res = await fetch(`/api/sessions/${sessionId}`, {
      method: "DELETE",
    });
    if (!res.ok) throw new Error(`删除会话失败: ${res.status}`);
    return await res.json();
  },

  // 获取会话消息
  async getMessages(sessionId) {
    const res = await fetch(`/api/sessions/${sessionId}/messages`);
    if (!res.ok) throw new Error(`获取消息失败: ${res.status}`);
    const data = await res.json();
    return data.messages;
  },
};

// 时间格式化
function formatTime(isoString) {
  const date = new Date(isoString);
  const now = new Date();
  const diff = now - date;
  
  if (diff < 60000) return "刚刚";
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`;
  if (diff < 604800000) return `${Math.floor(diff / 86400000)} 天前`;
  
  return date.toLocaleDateString();
}

// 渲染会话列表
function renderSessionList() {
  sessionListEl.innerHTML = "";
  
  sessions.forEach(session => {
    const div = document.createElement("div");
    div.className = "session-item";
    if (session.id === currentSessionId) {
      div.classList.add("active");
    }
    
    const titleDiv = document.createElement("div");
    titleDiv.className = "session-item-title";
    titleDiv.textContent = session.title;
    
    const metaDiv = document.createElement("div");
    metaDiv.className = "session-item-meta";
    metaDiv.textContent = formatTime(session.updated_at);
    
    div.appendChild(titleDiv);
    div.appendChild(metaDiv);

    // 对会话列表中的每个会话绑定click事件，用于切换到该会话
    div.addEventListener("click", () => switchSession(session.id));
    sessionListEl.appendChild(div);
  });
}

// 切换会话， 每次切换会话需要重新渲染主聊天区内容，并且需要重新渲染历史会话列表，对当前选中会话高亮
async function switchSession(sessionId) {
  // sessionId 在历史会话列表渲染时给每个会话都绑定了click事件（切换会话逻辑），并且传入了对应的session.id
  if (sessionId === currentSessionId) return;
  
  try {
    currentSessionId = sessionId;
    currentSession = await api.getSession(sessionId);
    
    // 更新UI
    sessionTitleEl.textContent = currentSession.title;
    updateDeepThinkButton(currentSession.deep_think);
    
    // 清空聊天区
    chatEl.innerHTML = "";
    
    // 加载消息历史
    const messages = await api.getMessages(sessionId);
    if (messages.length === 0) {
      initializeChat();
    } else {
      messages.forEach(msg => {
        appendMessage(msg.role, msg.content);
      });
    }
    
    // 更新会话列表高亮
    renderSessionList();
    
    // 启用输入
    inputEl.disabled = false;
    inputEl.focus();
  } catch (err) {
    console.error("切换会话失败:", err);
    alert("切换会话失败: " + err.message);
  }
}

// 创建新会话 先调用API创建一条新会话记录，然后获取所有会话记录并渲染，最后切换到新会话
async function createNewSession() {
  try {
    const deepThink = currentSession ? currentSession.deep_think : false;
    const session = await api.createSession("新会话", deepThink);
    
    // 刷新会话列表
    await loadSessions();
    
    // 切换到新会话
    await switchSession(session.id);
  } catch (err) {
    console.error("创建会话失败:", err);
    alert("创建会话失败: " + err.message);
  }
}

// 删除当前会话  当前会话id作为全局变量在维护  先调用API删除当前会话，然后获取所有会话记录并渲染，聊天框选择最新的会话记录展示，若没有则新建会话
async function deleteCurrentSession() {
  if (!currentSessionId) return;
  
  const ok = confirm("确定要删除当前会话吗？此操作不可撤销。");
  if (!ok) return;
  
  try {
    await api.deleteSession(currentSessionId);
    
    // 刷新会话列表
    await loadSessions();
    
    // 如果还有会话，切换到最新的；否则创建新会话
    if (sessions.length > 0) {
      await switchSession(sessions[0].id);
    } else {
      await createNewSession();
    }
  } catch (err) {
    console.error("删除会话失败:", err);
    alert("删除会话失败: " + err.message);
  }
}

// 加载会话列表  先获取所有会话记录，然后渲染
async function loadSessions() {
  try {
    sessions = await api.getSessions();
    renderSessionList();
  } catch (err) {
    console.error("加载会话列表失败:", err);
  }
}

// 初始化聊天窗口
function initializeChat() {
  const welcome = [
    "👋 你好，我是你的 AI 助手。",
    "",
    "你有任何问题都可以问我，我会尽力帮你解答！"
  ].join("\n");
  appendMessage("assistant", welcome);
}

// 添加消息到聊天窗口
function appendMessage(role, content) {
  const wrap = document.createElement("div");
  wrap.className = `msg ${role}`;

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = content;

  wrap.appendChild(bubble);
  chatEl.appendChild(wrap);
  chatEl.scrollTop = chatEl.scrollHeight;
  return bubble;
}

// 更新深度思考按钮
function updateDeepThinkButton(active) {
  if (!deepthinkBtn) return;
  deepthinkBtn.classList.toggle("active", active);
  deepthinkBtn.textContent = `深度思考：${active ? "开" : "关"}`;
}

// 设置UI禁用状态
function setPending(pending) {
  inputEl.disabled = pending;
  const submitBtn = formEl.querySelector("button[type='submit']");
  if (submitBtn) submitBtn.disabled = pending;
  newSessionBtn.disabled = pending;
  deleteSessionBtn.disabled = pending;
  deepthinkBtn.disabled = pending;
}

// 处理表单提交
async function handleSubmit(e) {
  e.preventDefault();  // 阻止浏览器对当前事件的默认行为 —— 提交表单并刷新页面
  
  if (!currentSessionId) {
    alert("请先选择或创建一个会话");
    return;
  }
  
  const text = inputEl.value.trim();
  if (!text) return;

  // 立即渲染用户消息
  appendMessage("user", text);
  inputEl.value = "";
  setPending(true);

  try {
    const assistantBubble = appendMessage("assistant", "");

    const res = await fetch("/api/chat_stream_v2", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: currentSessionId,
        message: text,
      }),
    });

    if (!res.ok || !res.body) {
      const errText = await (res.text ? res.text() : Promise.resolve(""));
      throw new Error(errText || `HTTP ${res.status}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let acc = "";
    
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, { stream: true });
      if (chunk) {
        acc += chunk;
        assistantBubble.textContent = acc;
        chatEl.scrollTop = chatEl.scrollHeight;
      }
    }

    // 刷新会话列表以更新 会话的更新时间
    await loadSessions();
  } catch (err) {
    appendMessage("assistant", `出现错误：${err.message}`);
  } finally {
    setPending(false);
    inputEl.focus();
  }
}

// 切换深度思考
async function toggleDeepThink() {
  if (!currentSession) return;
  
  try {
    const newValue = !currentSession.deep_think;
    await api.updateSession(currentSessionId, { deep_think: newValue });
    currentSession.deep_think = newValue;
    updateDeepThinkButton(newValue);
  } catch (err) {
    console.error("更新深度思考模式失败:", err);
    alert("更新失败: " + err.message);
  }
}

// 初始化应用
async function init() {
  // 绑定事件
  formEl.addEventListener("submit", handleSubmit);
  newSessionBtn.addEventListener("click", createNewSession);
  deleteSessionBtn.addEventListener("click", deleteCurrentSession);
  deepthinkBtn.addEventListener("click", toggleDeepThink);
  
  // 加载会话列表
  await loadSessions();
  
  // 如果有会话，切换到最新的会话完成聊天区渲染；否则创建新会话
  if (sessions.length > 0) {
    await switchSession(sessions[0].id);   // todo：会出现会话列表重复渲染问题
  } else {
    await createNewSession();
  }
}

// 页面加载完成后初始化

/*
如果文档状态处于 "loading"（加载中），就监听DOMContentLoaded事件（当 DOM 加载完成时触发），在事件触发时执行init()；
如果文档已经加载完成（非 loading 状态），则直接执行init()。
 */
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}