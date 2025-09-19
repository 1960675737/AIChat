# 创建数据库表，同时创建好索引

import sqlite3
import os

# 数据库文件路径
DB_PATH = "chat.db"

def init_database():
    """初始化数据库表结构"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 创建会话表
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        deep_think BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # 创建消息表
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
    )
    """)
    
    # 创建索引
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_messages_session_id 
    ON messages(session_id, created_at)
    """)
    
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_sessions_updated_at 
    ON sessions(updated_at DESC)
    """)
    
    conn.commit()
    conn.close()
    print(f"数据库初始化完成: {DB_PATH}")

if __name__ == "__main__":
    init_database()