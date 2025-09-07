"""
data_base.py

This module provides a set of standalone functions to handle all interactions
with the application's SQLite database (`chat_clients.db`). It is designed to
be a direct, functional interface for the server.

Each function is self-contained and manages its own database connection,
ensuring that connections are opened and closed for each specific operation.
This module is responsible for initializing the database schema and handling all
data storage and retrieval tasks, including users, groups, and messages.
"""

import sqlite3
from datetime import datetime
import json

DATABASE_FILE = "chat_clients.db"


def init_db():
    """
    Initializes the database.

    Creates the database file and all necessary tables (users, groups,
    group_members, messages) if they do not already exist. It also ensures
    that a default 'General' group is created on the first run.
    """
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    # Table for storing user information. Nickname is the primary key.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            nickname TEXT PRIMARY KEY,
            first_seen TEXT,
            last_seen TEXT,
            ip_address TEXT
        )
    ''')

    # Table for storing group information.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS groups (
            group_id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_name TEXT UNIQUE NOT NULL,
            created_at TEXT
        )
    ''')

    # Junction table to manage the many-to-many relationship between users and groups.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS group_members (
            group_id INTEGER,
            user_nickname TEXT,
            FOREIGN KEY(group_id) REFERENCES groups(group_id),
            FOREIGN KEY(user_nickname) REFERENCES users(nickname),
            PRIMARY KEY (group_id, user_nickname)
        )
    ''')

    # Table for storing all chat messages.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            user_nickname TEXT,
            content TEXT,
            timestamp TEXT,
            FOREIGN KEY(group_id) REFERENCES groups(group_id),
            FOREIGN KEY(user_nickname) REFERENCES users(nickname)
        )
    ''')

    # Ensure the 'General' group always exists.
    cursor.execute("SELECT group_id FROM groups WHERE group_name = 'General'")
    if cursor.fetchone() is None:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("INSERT INTO groups (group_name, created_at) VALUES ('General', ?)", (now,))
        print("[DATABASE] Default 'General' group created.")

    conn.commit()
    conn.close()
    print("[DATABASE] Database initialized successfully.")


def add_or_update_user(nickname, ip_address):
    """
    Adds a new user to the database or updates an existing one.

    If the nickname doesn't exist, a new record is created.
    If the nickname already exists, the 'last_seen' timestamp and 'ip_address' are updated.

    Args:
        nickname (str): The user's unique nickname.
        ip_address (str): The user's current IP address.
    """
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        # Attempt to insert a new user.
        cursor.execute('''
            INSERT INTO users (nickname, first_seen, last_seen, ip_address)
            VALUES (?, ?, ?, ?)
        ''', (nickname, now, now, ip_address))
    except sqlite3.IntegrityError:
        # If the insert fails due to a unique key constraint, the user already exists.
        # Update the existing user's record instead.
        cursor.execute('''
            UPDATE users
            SET last_seen = ?, ip_address = ?
            WHERE nickname = ?
        ''', (now, ip_address, nickname))
    conn.commit()
    conn.close()


def get_user_groups(nickname):
    """
    Retrieves a list of all groups that a user is a member of.

    Args:
        nickname (str): The nickname of the user.

    Returns:
        list: A list of strings, where each string is a group name.
    """
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT g.group_name
        FROM groups g
        JOIN group_members gm ON g.group_id = gm.group_id
        WHERE gm.user_nickname = ?
    ''', (nickname,))
    groups = [row[0] for row in cursor.fetchall()]
    conn.close()
    return groups


def add_user_to_group(nickname, group_name):
    """
    Adds a specified user to a specified group.

    If the user is already in the group, the operation is ignored.

    Args:
        nickname (str): The nickname of the user to add.
        group_name (str): The name of the group to join.
    """
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    try:
        # First, find the group's ID from its name.
        cursor.execute("SELECT group_id FROM groups WHERE group_name = ?", (group_name,))
        result = cursor.fetchone()
        if result:
            group_id = result[0]
            # 'INSERT OR IGNORE' prevents errors if the user is already a member.
            cursor.execute("INSERT OR IGNORE INTO group_members (group_id, user_nickname) VALUES (?, ?)",
                           (group_id, nickname))
            conn.commit()
    finally:
        # Ensure the connection is always closed.
        conn.close()


def search_users(query, limit=10):
    """
    Searches for users whose nicknames start with the given query string.

    Args:
        query (str): The prefix of the nickname to search for.
        limit (int): The maximum number of results to return.

    Returns:
        list: A list of matching nicknames.
    """
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    # The '%' wildcard matches any sequence of characters.
    cursor.execute("SELECT nickname FROM users WHERE nickname LIKE ? LIMIT ?", (query + '%', limit))
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return users


def create_group(group_name, creator_nickname, members):
    """
    Creates a new group and adds the specified members.

    Args:
        group_name (str): The name for the new group. Must be unique.
        creator_nickname (str): The nickname of the user creating the group.
        members (list): A list of other nicknames to add to the group.

    Returns:
        bool: True if the group was created successfully, False if the group name already exists.
    """
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        # Create the new group.
        cursor.execute("INSERT INTO groups (group_name, created_at) VALUES (?, ?)", (group_name, now))
        group_id = cursor.lastrowid

        # Add all members (including the creator) to the group.
        # A 'set' is used to automatically handle any duplicate names.
        all_members = set(members + [creator_nickname])
        for member_nickname in all_members:
            cursor.execute("INSERT INTO group_members (group_id, user_nickname) VALUES (?, ?)",
                           (group_id, member_nickname))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # This error occurs if the group_name is not unique.
        return False
    finally:
        conn.close()


def get_all_group_names():
    """
    Retrieves the names of all existing groups.

    Returns:
        list: A list of all group names as strings.
    """
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT group_name FROM groups")
    group_names = [row[0] for row in cursor.fetchall()]
    conn.close()
    return group_names


def remove_user_from_group(nickname, group_name):
    """
    Removes a user from a specified group.

    Args:
        nickname (str): The nickname of the user to remove.
        group_name (str): The name of the group to leave.
    """
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    try:
        # Get the group_id for the given group_name.
        cursor.execute("SELECT group_id FROM groups WHERE group_name = ?", (group_name,))
        result = cursor.fetchone()
        if result:
            group_id = result[0]
            # Delete the corresponding entry from the members table.
            cursor.execute("DELETE FROM group_members WHERE group_id = ? AND user_nickname = ?", (group_id, nickname))
            conn.commit()
    except Exception as e:
        print(f"[DATABASE ERROR] Failed to remove user from group: {e}")
    finally:
        conn.close()


def save_message(group_name, nickname, message_content, timestamp):
    """
    Saves a chat message to the database.

    Args:
        group_name (str): The name of the group where the message was sent.
        nickname (str): The nickname of the message sender.
        message_content (str): The content of the message.
        timestamp (str): The timestamp of the message.
    """
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    try:
        # Get the group_id for the given group_name.
        cursor.execute("SELECT group_id FROM groups WHERE group_name = ?", (group_name,))
        result = cursor.fetchone()
        if result:
            group_id = result[0]
            # Insert the new message record.
            cursor.execute('''
                INSERT INTO messages (group_id, user_nickname, content, timestamp)
                VALUES (?, ?, ?, ?)
            ''', (group_id, nickname, message_content, timestamp))
            conn.commit()
    except Exception as e:
        print(f"[DATABASE ERROR] Failed to save message: {e}")
    finally:
        conn.close()


def get_group_history(group_name, limit=50):
    """
    Retrieves the most recent message history for a specific group.

    It tries to parse message content as JSON (for system messages or files)
    but falls back to treating it as a standard chat message if parsing fails.

    Args:
        group_name (str): The name of the group.
        limit (int): The maximum number of recent messages to retrieve.

    Returns:
        list: A list of message dictionaries, formatted for the client.
    """
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    history = []
    try:
        cursor.execute("SELECT group_id FROM groups WHERE group_name = ?", (group_name,))
        result = cursor.fetchone()
        if result:
            group_id = result[0]
            # Calculate offset to get only the last 'limit' messages.
            cursor.execute("SELECT COUNT(*) FROM messages WHERE group_id = ?", (group_id,))
            total_messages = cursor.fetchone()[0]
            offset = max(0, total_messages - limit)

            # Retrieve the messages.
            cursor.execute('''
                SELECT user_nickname, content, timestamp
                FROM messages
                WHERE group_id = ?
                ORDER BY timestamp ASC
                LIMIT ? OFFSET ?
            ''', (group_id, limit, offset))

            for row in cursor.fetchall():
                nickname, content, timestamp_full = row
                # Format the timestamp for display.
                timestamp_short = datetime.strptime(timestamp_full, '%Y-%m-%d %H:%M:%S').strftime('%H:%M:%S')

                try:
                    # Attempt to load the message content as JSON (e.g., for file notifications).
                    msg_data = json.loads(content)
                    if 'timestamp' in msg_data:
                        msg_data['timestamp'] = timestamp_short # Update with formatted time
                    history.append(msg_data)
                except (json.JSONDecodeError, TypeError):
                    # If it's not valid JSON, treat it as a standard text message.
                    history.append({
                        "type": "chat",
                        "nickname": nickname,
                        "message": content,
                        "timestamp": timestamp_short,
                        "group_name": group_name
                    })
    except Exception as e:
        print(f"[DATABASE ERROR] Failed to get group history: {e}")
    finally:
        conn.close()
    return history