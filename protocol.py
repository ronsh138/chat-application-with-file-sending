"""
protocol.py

Defines the communication rules (protocol) for the chat application.

This module contains functions to create, send, and receive structured
JSON messages. It implements a message framing system using a 4-byte
length prefix to ensure that complete messages are always received over
the TCP stream, preventing errors from concatenated messages.
"""

import json
import socket
import struct  # Import the struct module for packing/unpacking the message length

# --- Helper functions for the new, robust sending/receiving logic ---

def recvall(sock, n):
    """
    Helper function to receive exactly 'n' bytes from a socket.

    This is crucial for a stream-based protocol like TCP to ensure the
    full message is received.

    Args:
        sock (socket.socket): The socket to receive data from.
        n (int): The number of bytes to receive.

    Returns:
        bytes: The received data, or None if the connection is closed.
    """
    data = bytearray()
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data.extend(packet)
    return data


def send_message(sock, data):
    """
    Sends a dictionary as a JSON-encoded, length-prefixed message.

    First, it packs the length of the message into a 4-byte header.
    Then, it sends the header followed by the actual message data.

    Args:
        sock (socket.socket): The socket to send data through.
        data (dict): The dictionary object to send.

    Returns:
        bool: True if sending was successful, False otherwise.
    """
    if not sock:
        return False
    try:
        # 1. Convert the dictionary to a JSON string, then to bytes.
        json_bytes = json.dumps(data).encode('utf-8')
        # 2. Get the length of the message bytes.
        message_length = len(json_bytes)
        # 3. Pack the length into a 4-byte header (network byte order).
        header = struct.pack('!I', message_length)
        # 4. Send the header, followed by the message.
        sock.sendall(header + json_bytes)
        return True
    except (ConnectionError, Exception) as e:
        print(f"[PROTOCOL ERROR] Error on send: {e}")
        return False


def receive_message(sock):
    """
    Receives a complete, length-prefixed message from the socket.

    First, it reads the 4-byte header to determine the message length.
    Then, it reads that exact number of bytes to get the complete message.

    Args:
        sock (socket.socket): The socket to receive data from.

    Returns:
        dict: The received dictionary object, or None if the connection
              is closed or an error occurs.
    """
    if not sock:
        return None
    try:
        # 1. Read the 4-byte header to get the message length.
        raw_msglen = recvall(sock, 4)
        if not raw_msglen:
            return None
        # 2. Unpack the header to get the length as an integer.
        msglen = struct.unpack('!I', raw_msglen)[0]
        # 3. Read the full message body based on the determined length.
        json_bytes = recvall(sock, msglen)
        if not json_bytes:
            return None
        # 4. Decode the bytes to a string and parse the JSON.
        return json.loads(json_bytes.decode('utf-8'))
    except (json.JSONDecodeError, ConnectionError, struct.error, Exception) as e:
        print(f"[PROTOCOL ERROR] Error on receive: {e}")
        return None

# --- Message Creation Functions (Unchanged) ---

def create_download_ready_response(port, filename, filesize):
    """Server -> Client: Acknowledgment that the file is ready for download on a specific port."""
    return {"type": "download_ready", "port": port, "filename": filename, "filesize": filesize}


def create_download_request(unique_filename):
    """Client -> Server: Request to download a specific file."""
    return {"type": "download_request", "unique_filename": unique_filename}


def create_leave_group_request(group_name):
    """Creates a client request to leave a group."""
    return {"type": "leave_group", "group_name": group_name}


def create_search_users_message(query):
    """Creates a message to search for users."""
    return {"type": "search_users", "query": query}


def create_search_results_message(results):
    """Creates a message containing user search results."""
    return {"type": "search_results", "results": results}


def create_group_message_request(group_name, members):
    """Creates a client request to form a new group."""
    return {"type": "create_group", "group_name": group_name, "members": members}


def create_update_group_list_message(groups):
    """Creates a message to send the list of groups to a client."""
    return {"type": "update_group_list", "groups": groups}


def create_server_response(status, message):
    """Creates a response from the server (e.g., login success/failure)."""
    return {"type": "server_response", "status": status, "message": message}


def create_chat_message(nickname, message_text, timestamp, group_name):
    """Creates a dictionary for a standard chat message with a timestamp AND group name."""
    return {"type": "chat", "nickname": nickname, "message": message_text, "timestamp": timestamp,
            "group_name": group_name}


def create_system_message(message_text, timestamp, group_name=None):
    """Creates a system message, optionally for a specific group."""
    msg = {"type": "system", "message": message_text, "timestamp": timestamp}
    if group_name:
        msg["group_name"] = group_name
    return msg


def create_nickname_message(nickname):
    """Creates a dictionary for the initial nickname registration."""
    return {"type": "nickname", "nickname": nickname}


def create_client_message(message_text, group_name):
    """Creates a chat message from the client, specifying the target group."""
    return {"type": "chat", "message": message_text, "group_name": group_name}


def create_get_history_request(group_name):
    """Creates a client request for a group's chat history."""
    return {"type": "get_history", "group_name": group_name}


def create_group_history_response(history):
    """Creates a server response containing chat history."""
    return {"type": "group_history_response", "history": history}


def create_upload_request(group_name, filename, filesize):
    """Client -> Server: Request to upload a file."""
    return {"type": "upload_request", "group_name": group_name, "filename": filename, "filesize": filesize}


def create_upload_ready_response(port, unique_filename):
    """Server -> Client: Acknowledgment that the server is ready for upload on a specific port."""
    return {"type": "upload_ready", "port": port, "unique_filename": unique_filename}


def create_file_notification(sender, filename, unique_filename, group_name, timestamp):
    """Server -> Group: Notification that a file has been uploaded."""
    return {
        "type": "file_notification",
        "sender": sender,
        "filename": filename,
        "unique_filename": unique_filename,
        "group_name": group_name,
        "timestamp": timestamp
    }


