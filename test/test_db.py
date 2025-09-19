import sqlite3

DB_PATH = "../chat.db"


def query_database():
    # 连接数据库
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # 1. 查询所有会话（sessions表）
        print("===== 所有会话 =====")
        cursor.execute("SELECT * FROM sessions")
        sessions = cursor.fetchall()
        # 获取表字段名（方便查看）
        session_columns = [desc[0] for desc in cursor.description]
        print(session_columns)  # 打印字段名
        for session in sessions:
            print(session)  # 打印每条会话记录

        # 2. 查询所有消息（messages表）
        print("\n===== 所有消息 =====")
        cursor.execute("SELECT * FROM messages")
        messages = cursor.fetchall()
        message_columns = [desc[0] for desc in cursor.description]
        print(message_columns)  # 打印字段名
        for message in messages:
            print(message)  # 打印每条消息记录

    except sqlite3.Error as e:
        print(f"查询出错: {e}")
    finally:
        # 关闭连接
        conn.close()


if __name__ == "__main__":
    query_database()