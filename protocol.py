"""
protocol.py

This module is the backbone of the client-server communication. It defines a set of
"creator" functions that build standardized message dictionaries for every possible
action in the application (e.g., sending a chat message, creating a group, etc.).

It also provides two core functions, `send_message` and `receive_message`, which handle
the serialization (dict -> JSON -> bytes) and deserialization (bytes -> JSON -> dict)
of these messages for network transmission.

The protocol is based on sending and receiving JSON strings over a TCP socket.
"""

import json
import socket

# --- Message Creators for File Transfer ---

def create_download_ready_response(port, filename, filesize):
    return {"type": "download_ready", "port": port, "filename": filename, "filesize": filesize}


def create_download_request(unique_filename):
    return {"type": "download_request", "unique_filename": unique_filename}


def create_upload_request(group_name, filename, filesize):
    return {"type": "upload_request", "group_name": group_name, "filename": filename, "filesize": filesize}


def create_upload_ready_response(port, unique_filename):
    return {"type": "upload_ready", "port": port, "unique_filename": unique_filename}


def create_file_notification(sender, filename, unique_filename, group_name, timestamp):
    return {
        "type": "file_notification",
        "sender": sender,
        "filename": filename,
        "unique_filename": unique_filename,
        "group_name": group_name,
        "timestamp": timestamp
    }

# --- Message Creators for Group and User Management ---

def create_leave_group_request(group_name):
    return {"type": "leave_group", "group_name": group_name}


def create_search_users_message(query):
    return {"type": "search_users", "query": query}


def create_search_results_message(results):
    return {"type": "search_results", "results": results}


def create_group_message_request(group_name, members):
    return {"type": "create_group", "group_name": group_name, "members": members}


def create_update_group_list_message(groups):
    return {"type": "update_group_list", "groups": groups}


# --- Message Creators for General Communication and Chat ---

def create_server_response(status, message):
    """
    Creates a generic response from the server (e.g., login success/failure).
    Args:
        status (str): The status of the response (e.g., 'ok', 'error').
        message (str): A descriptive message for the user.
    """
    return {"type": "server_response", "status": status, "message": message}


def create_chat_message(nickname, message_text, timestamp, group_name):
    return {"type": "chat", "nickname": nickname, "message": message_text, "timestamp": timestamp,
            "group_name": group_name}


def create_system_message(message_text, timestamp, group_name=None):
    msg = {"type": "system", "message": message_text, "timestamp": timestamp}
    if group_name:
        msg["group_name"] = group_name
    return msg


def create_nickname_message(nickname):
    return {"type": "nickname", "nickname": nickname}


def create_client_message(message_text, group_name):
    """
    Creates a chat message from the client's perspective to be sent to the server.
    """
    return {"type": "chat", "message": message_text, "group_name": group_name}


def create_get_history_request(group_name):
    return {"type": "get_history", "group_name": group_name}


def create_group_history_response(history):
    return {"type": "group_history_response", "history": history}


# --- Core Send/Receive Functions ---

def send_message(sock, data):
    """
    Serializes a dictionary to a JSON string and sends it over a socket.

    Args:
        sock (socket.socket): The socket to send the data through.
        data (dict): The message dictionary to send.

    Returns:
        bool: True if sending was successful, False otherwise.
    """
    if not sock:
        return False
    try:
        # Convert the dictionary to a JSON string, then encode to bytes
        json_string = json.dumps(data)
        sock.sendall(json_string.encode('utf-8'))
        return True
    except (ConnectionError, Exception) as e:
        # Handle cases where the socket is closed or another error occurs
        print(f"[PROTOCOL ERROR] Error on send: {e}")
        return False


def receive_message(sock):
    """
    Receives bytes from a socket, decodes them, and deserializes them into a dictionary.

    Note: This function assumes a message will be received in a single recv call
    with a buffer size of 2048 bytes. This might not be sufficient for very
    large messages (like long chat histories).

    Args:
        sock (socket.socket): The socket to receive data from.

    Returns:
        dict or None: The received message dictionary, or None if the client
                      disconnected or an error occurred.
    """
    if not sock:
        return None
    try:
        # Receive up to 2048 bytes from the socket
        message_bytes = sock.recv(2048)
        # If no bytes are received, the connection is closed
        if not message_bytes:
            return None
        # Decode the bytes to a string and parse the JSON
        json_string = message_bytes.decode('utf-8')
        return json.loads(json_string)
    except (json.JSONDecodeError, ConnectionError, Exception) as e:
        # Handle JSON errors, disconnections, or other issues
        print(f"[PROTOCOL ERROR] Error on receive: {e}")
        return None
