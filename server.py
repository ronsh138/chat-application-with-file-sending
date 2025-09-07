"""
server.py

This module is the core of the chat application's backend. It defines and runs
the main ChatServer, which is responsible for listening for incoming client
connections, managing user sessions, handling real-time communication, and
orchestrating all backend logic.

The server uses multithreading to handle multiple clients concurrently. It also
spawns separate threads for handling file transfers to prevent blocking the
main communication flow.
"""

import socket
import threading
from datetime import datetime
import protocol
import data_base
from models import User, GroupChat
import os
import time
import json


class FileReceiverThread(threading.Thread):
    """
    A dedicated thread to handle an incoming file upload from a client.

    This thread opens a temporary socket on a specified port, waits for the
    client to connect, and receives the file data, saving it to the
    'server_files' directory.
    """
    def __init__(self, port, unique_filename, filesize):
        """
        Initializes the file receiver thread.

        Args:
            port (int): The port number to listen on for the file transfer.
            unique_filename (str): The unique filename to save the file as on the server.
            filesize (int): The total size of the file in bytes.
        """
        super().__init__()
        self.port = port
        self.unique_filename = unique_filename
        self.filesize = filesize
        self.host = '0.0.0.0'  # Listen on all available network interfaces.

    def run(self):
        """The main execution method for the thread."""
        # Ensure the directory for storing files exists.
        if not os.path.exists('server_files'):
            os.makedirs('server_files')

        filepath = os.path.join('server_files', self.unique_filename)

        try:
            # Create a temporary listening socket for the file transfer.
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as file_socket:
                file_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                file_socket.bind((self.host, self.port))
                file_socket.listen()
                conn, addr = file_socket.accept()
                with conn:
                    print(f"[FILE SERVER] Connection for {self.unique_filename} from {addr}.")
                    bytes_received = 0
                    # Receive the file in chunks until the full size is reached.
                    with open(filepath, 'wb') as f:
                        while bytes_received < self.filesize:
                            chunk = conn.recv(4096)
                            if not chunk:
                                break  # Connection closed unexpectedly.
                            f.write(chunk)
                            bytes_received += len(chunk)
                    print(f"[FILE SERVER] File '{self.unique_filename}' received successfully.")
        except Exception as e:
            print(f"[FILE SERVER ERROR] {e}")


class FileSenderThread(threading.Thread):
    """
    A dedicated thread to handle sending a file to a client.

    This thread opens a temporary socket on a specified port, waits for the
    client to connect, and then reads the requested file from disk and sends
    it over the connection.
    """
    def __init__(self, port, filepath):
        """
        Initializes the file sender thread.

        Args:
            port (int): The port number to listen on for the file transfer.
            filepath (str): The full path to the file that needs to be sent.
        """
        super().__init__()
        self.port = port
        self.filepath = filepath
        self.host = '0.0.0.0'

    def run(self):
        """The main execution method for the thread."""
        try:
            # Create a temporary listening socket.
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as file_socket:
                file_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                file_socket.bind((self.host, self.port))
                file_socket.listen()
                conn, addr = file_socket.accept()
                with conn:
                    print(f"[FILE SENDER] Sending {os.path.basename(self.filepath)} to {addr}.")
                    # Read the file in chunks and send it to the client.
                    with open(self.filepath, 'rb') as f:
                        while True:
                            chunk = f.read(4096)
                            if not chunk:
                                break  # End of file.
                            conn.sendall(chunk)
                    print(f"[FILE SENDER] File sent successfully.")
        except Exception as e:
            print(f"[FILE SENDER ERROR] {e}")


class ChatServer:
    """
    The main class for the chat server.

    Manages all server state, including connected users and active group chats.
    Listens for new connections and spawns threads to handle each client.
    """
    def __init__(self, host='0.0.0.0', port=12989):
        """Initializes the chat server."""
        data_base.init_db()  # Ensure database and tables are created.
        self.host = host
        self.port = port
        self.users = {}  # Dictionary to map connections to User objects.
        self.groups = {}  # Dictionary to map group names to GroupChat objects.
        self.lock = threading.Lock()  # A lock to prevent race conditions when accessing shared state.
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.next_file_port = 12395  # Starting port number for file transfers.
        self.load_groups_from_db()

    def load_groups_from_db(self):
        """
        Loads all existing group names from the database into memory on startup.
        This allows the server to manage groups that were created in previous sessions.
        """
        group_names = data_base.get_all_group_names()
        for name in group_names:
            self.groups[name] = GroupChat(name)

        # The 'General' group is essential and should always exist in memory.
        if "General" not in self.groups:
            self.groups["General"] = GroupChat("General")

        print(f"[SERVER] Loaded {len(self.groups)} groups from database into memory.")

    def get_timestamp(self, full=False):
        """
        Generates a formatted timestamp string.

        Args:
            full (bool): If True, returns the full date and time. Otherwise, returns only the time.
        Returns:
            str: The formatted timestamp.
        """
        if full:
            return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return datetime.now().strftime('%H:%M:%S')

    def handle_client(self, conn, addr):
        """

        Main logic for handling a single client connection. This runs in its own thread.

        It manages the entire lifecycle of a client: nickname registration, message
        processing, and cleanup upon disconnection.
        """
        current_user = None
        nickname = None
        try:
            # Step 1: Nickname Registration Loop
            while True:
                data = protocol.receive_message(conn)
                # First message must be a nickname registration.
                if not data or data.get("type") != "nickname": return
                temp_nickname = data.get("nickname", "").strip()
                with self.lock:
                    # Check if the nickname is valid and not already in use.
                    if not temp_nickname or any(user.nickname == temp_nickname for user in self.users.values()):
                        response = protocol.create_server_response("error", "Nickname is empty or already in use.")
                        protocol.send_message(conn, response)
                        return  # Close connection if nickname is invalid.
                    else:
                        nickname = temp_nickname
                        response = protocol.create_server_response("ok", "Welcome to the chat!")
                        protocol.send_message(conn, response)
                        break  # Nickname is valid, exit registration loop.

            # Step 2: Finalize User Setup
            ip_address = addr[0]
            data_base.add_or_update_user(nickname, ip_address)
            data_base.add_user_to_group(nickname, "General") # Every new user joins General.
            current_user = User(conn, nickname)

            user_groups = data_base.get_user_groups(nickname)

            # Add the user to the server's live state (users list and group member lists).
            with self.lock:
                self.users[conn] = current_user
                for group_name in user_groups:
                    if group_name in self.groups:
                        self.groups[group_name].add_member(current_user)

            print(f"[NICKNAME SET] {addr} is now known as {nickname}.")

            # Send the user their list of groups.
            group_list_message = protocol.create_update_group_list_message(user_groups)
            protocol.send_message(conn, group_list_message)

            # Announce the new user's arrival in the 'General' chat.
            if "General" in self.groups:
                join_message = protocol.create_system_message(f"{nickname} has joined the chat!", self.get_timestamp(),
                                                              group_name="General")
                self.groups["General"].broadcast(join_message, None) # Broadcast to all, no sender to exclude.

            # Step 3: Main Message Processing Loop
            while True:
                data = protocol.receive_message(conn)
                if data is None: break  # Client disconnected.

                msg_type = data.get("type")

                # Route the message to the appropriate handler based on its type.
                if msg_type == "upload_request":
                    self.handle_upload_request(current_user, data)
                elif msg_type == "download_request":
                    self.handle_download_request(current_user, data)
                elif msg_type == "search_users":
                    self.handle_user_search(conn, data.get("query"))
                elif msg_type == "create_group":
                    self.handle_group_creation(current_user, data)
                elif msg_type == "leave_group":
                    self.handle_leave_group(current_user, data)
                elif msg_type == "get_history":
                    self.handle_get_history(conn, data.get("group_name"))
                elif msg_type == "chat":
                    group_name = data.get("group_name")
                    message_text = data.get("message")
                    timestamp_str = self.get_timestamp(full=True)
                    with self.lock:
                        target_group = self.groups.get(group_name)
                    if target_group:
                        # Save to DB and then broadcast to live users.
                        data_base.save_message(group_name, nickname, message_text, timestamp_str)
                        chat_message = protocol.create_chat_message(
                            nickname, message_text, self.get_timestamp(), group_name
                        )
                        target_group.broadcast(chat_message, current_user)
        finally:
            # Step 4: Cleanup on Disconnection
            if current_user:
                with self.lock:
                    if conn in self.users: del self.users[conn]
                    # Remove user from all in-memory group member lists.
                    for group in self.groups.values():
                        group.remove_member(current_user)
            if nickname:
                print(f"[DISCONNECTED] {addr} ({nickname}) disconnected.")
            else:
                print(f"[DISCONNECTED] {addr} (Unknown) disconnected.")
            conn.close()

    def handle_upload_request(self, sender_user, data):
        """Handles a client's request to upload a file."""
        group_name = data.get("group_name")
        filename = data.get("filename")
        filesize = data.get("filesize")

        with self.lock:
            port = self.next_file_port
            self.next_file_port += 1

        unique_filename = f"{int(time.time())}_{os.path.basename(filename)}"

        # Start a thread to listen for the file.
        receiver_thread = FileReceiverThread(port, unique_filename, filesize)
        receiver_thread.start()

        # Tell the client which port to connect to.
        response = protocol.create_upload_ready_response(port, unique_filename)
        protocol.send_message(sender_user.connection, response)

        # Create a notification message for the group chat.
        notification = protocol.create_file_notification(
            sender_user.nickname, filename, unique_filename, group_name, self.get_timestamp()
        )

        # Save the notification as a system message in the database.
        message_to_save = json.dumps(notification)
        data_base.save_message(group_name, "system", message_to_save, self.get_timestamp(full=True))

        # Broadcast the file notification to all members of the group.
        with self.lock:
            target_group = self.groups.get(group_name)
            if target_group:
                target_group.broadcast(notification, None)

    def handle_download_request(self, requesting_user, data):
        """Handles a client's request to download a file."""
        unique_filename = data.get("unique_filename")
        filepath = os.path.join('server_files', unique_filename)

        if os.path.exists(filepath):
            with self.lock:
                port = self.next_file_port
                self.next_file_port += 1

            filesize = os.path.getsize(filepath)
            original_filename = "_".join(unique_filename.split('_')[1:]) # Reconstruct original name

            # Start a thread to send the file.
            sender_thread = FileSenderThread(port, filepath)
            sender_thread.start()

            # Tell the client where to connect to download the file.
            response = protocol.create_download_ready_response(port, original_filename, filesize)
            protocol.send_message(requesting_user.connection, response)
        else:
            print(f"[SERVER ERROR] File not found: {unique_filename}")
            # Optionally, send an error message back to the client here.

    def handle_user_search(self, conn, query):
        """Handles a user search request from a client."""
        results = data_base.search_users(query)
        response = protocol.create_search_results_message(results)
        protocol.send_message(conn, response)

    def handle_group_creation(self, creator_user, data):
        """Handles a request to create a new group."""
        group_name = data.get("group_name")
        members = data.get("members")

        if data_base.create_group(group_name, creator_user.nickname, members):
            all_member_nicknames = set(members + [creator_user.nickname])
            with self.lock:
                # Create the group in memory.
                if group_name not in self.groups:
                    self.groups[group_name] = GroupChat(group_name)
                # Add all members to the in-memory group and notify them.
                for conn, user in self.users.items():
                    if user.nickname in all_member_nicknames:
                        self.groups[group_name].add_member(user)
                        # Send an updated group list to each new member.
                        user_groups = data_base.get_user_groups(user.nickname)
                        update_msg = protocol.create_update_group_list_message(user_groups)
                        protocol.send_message(conn, update_msg)

    def handle_leave_group(self, user_to_remove, data):
        """Handles a request for a user to leave a group."""
        group_name = data.get("group_name")
        nickname = user_to_remove.nickname
        if group_name == "General": return  # Users cannot leave the General group.

        data_base.remove_user_from_group(nickname, group_name)

        with self.lock:
            target_group = self.groups.get(group_name)
            if target_group:
                # Notify the group that the user has left.
                leave_notification = protocol.create_system_message(
                    f"{nickname} has left the group.", self.get_timestamp(), group_name=group_name
                )
                target_group.broadcast(leave_notification, user_to_remove)
                # Remove the user from the in-memory group.
                target_group.remove_member(user_to_remove)

        # Send the updated group list back to the user who left.
        updated_groups = data_base.get_user_groups(nickname)
        update_msg = protocol.create_update_group_list_message(updated_groups)
        protocol.send_message(user_to_remove.connection, update_msg)

    def handle_get_history(self, conn, group_name):
        """Handles a request for a group's message history."""
        history = data_base.get_group_history(group_name)
        response = protocol.create_group_history_response(history)
        protocol.send_message(conn, response)

    def start(self):
        """Binds the server socket and starts the main listening loop."""
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen()
        print(f"[LISTENING] Server is listening on {self.host}:{self.port}")

        while True:
            conn, addr = self.server_socket.accept()
            print(f"[NEW CONNECTION] {addr} connected.")
            # Create and start a new thread for each connecting client.
            thread = threading.Thread(target=self.handle_client, args=(conn, addr))
            thread.start()


if __name__ == "__main__":
    chat_server = ChatServer()
    chat_server.start()