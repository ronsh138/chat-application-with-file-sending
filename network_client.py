"""
network_client.py

This module manages all network communication for the client application.

It features a main NetworkThread that runs in the background, handling the
persistent connection to the server for real-time messaging. It listens for
incoming data and uses PyQt's signal/slot mechanism to safely pass information
to the main UI thread, preventing the interface from freezing.

Additionally, it defines dedicated threads for handling file uploads and
downloads, ensuring that large file transfers do not block the primary chat
functionality.
"""

import socket
from PyQt6.QtCore import QThread, pyqtSignal
import protocol
import os
import time


class FileSenderThread(QThread):
    """
    A dedicated QThread to handle the upload of a single file.

    This thread connects to a temporary port provided by the server and sends
    the specified file's contents.
    """
    def __init__(self, host, port, filepath):
        """
        Initializes the file sender thread.

        Args:
            host (str): The server's IP address.
            port (int): The temporary port to connect to for the upload.
            filepath (str): The local path of the file to be sent.
        """
        super().__init__()
        self.host = host
        self.port = port
        self.filepath = filepath

    def run(self):
        """
        Connects to the server's file port and sends the file.
        This is the main execution method for the thread.
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as file_socket:
                # Connect to the specific port the server has opened for this file.
                file_socket.connect((self.host, self.port))
                # Open the file in binary read mode.
                with open(self.filepath, 'rb') as f:
                    # Read and send the file in chunks to manage memory usage.
                    while True:
                        chunk = f.read(4096)
                        if not chunk:
                            break  # End of file.
                        file_socket.sendall(chunk)
            print(f"[FILE SENDER] File '{os.path.basename(self.filepath)}' sent successfully.")
        except Exception as e:
            print(f"[FILE SENDER ERROR] {e}")


class FileReceiverThread(QThread):
    """
    A dedicated QThread to handle the download of a single file.

    This thread connects to a temporary port provided by the server and receives
    the file's contents, saving them to a specified path.
    """
    def __init__(self, host, port, save_path, filesize):
        """
        Initializes the file receiver thread.

        Args:
            host (str): The server's IP address.
            port (int): The temporary port to connect to for the download.
            save_path (str): The local path where the downloaded file will be saved.
            filesize (int): The total size of the file to be received.
        """
        super().__init__()
        self.host = host
        self.port = port
        self.save_path = save_path
        self.filesize = filesize

    def run(self):
        """
        Connects to the server's file port and receives the file.
        This is the main execution method for the thread.
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as file_socket:
                file_socket.connect((self.host, self.port))

                bytes_received = 0
                # Open the destination file in binary write mode.
                with open(self.save_path, 'wb') as f:
                    # Receive data in chunks until the entire file is downloaded.
                    while bytes_received < self.filesize:
                        chunk = file_socket.recv(4096)
                        if not chunk:
                            break  # Connection closed.
                        f.write(chunk)
                        bytes_received += len(chunk)
            print(f"[FILE RECEIVER] File '{os.path.basename(self.save_path)}' received successfully.")
        except Exception as e:
            print(f"[FILE RECEIVER ERROR] {e}")


class NetworkThread(QThread):
    """
    The main background thread for handling all non-file network communication.

    It manages the primary socket connection to the server, handles the login
    process, and listens continuously for incoming messages. It uses signals
    to safely communicate with the main UI thread.
    """
    # --- Signals to communicate with the UI thread ---
    disconnected = pyqtSignal(str)
    message_received = pyqtSignal(dict)
    login_successful = pyqtSignal()
    group_list_updated = pyqtSignal(list)
    search_results_received = pyqtSignal(list)
    message_history_received = pyqtSignal(list)
    download_ready_signal = pyqtSignal(dict)

    def __init__(self, ip, port, nickname):
        """
        Initializes the network thread.

        Args:
            ip (str): The server IP address to connect to.
            port (int): The server port to connect to.
            nickname (str): The user's chosen nickname for this session.
        """
        super().__init__()
        self.ip = ip
        self.port = port
        self.nickname = nickname
        self.socket = None
        self.file_sender = None    # To hold reference to the file sending thread.
        self.file_receiver = None  # To hold reference to the file receiving thread.
        self.upload_requests = {}  # A dictionary to track pending file uploads.

    def run(self):
        """
        The main loop for the network thread.

        Connects to the server, performs the login handshake, and then enters
        a loop to listen for and process incoming messages.
        """
        # Step 1: Connect to the server.
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.ip, self.port))
        except Exception as e:
            self.disconnected.emit(f"Failed to connect to server: {e}")
            return

        # Step 2: Perform login handshake.
        nickname_msg = protocol.create_nickname_message(self.nickname)
        if not protocol.send_message(self.socket, nickname_msg):
            self.disconnected.emit("Failed to send nickname to server.")
            return

        response = protocol.receive_message(self.socket)
        if response and response.get("type") == "server_response":
            if response.get("status") == "error":
                self.disconnected.emit(response.get("message"))
                return
            elif response.get("status") == "ok":
                self.login_successful.emit()  # Signal to the UI that login was successful.
        else:
            self.disconnected.emit("Invalid or no response from server during login.")
            return

        # Step 3: Enter the main listening loop.
        while True:
            data = protocol.receive_message(self.socket)
            if data is None:
                self.disconnected.emit("Connection to server was lost.")
                break

            msg_type = data.get("type")
            # Route incoming messages to the correct signal based on their type.
            if msg_type == "upload_ready":
                # Server is ready for our file upload.
                port = data.get("port")
                key = data.get("unique_filename")
                filepath = self.upload_requests.pop(key, None) # Get the filepath we stored earlier.
                if filepath:
                    self.file_sender = FileSenderThread(self.ip, port, filepath)
                    self.file_sender.start()
                else:
                    print(f"Error: Could not find original filepath for key {key}")

            elif msg_type == "download_ready":
                # Server is ready to send us a file.
                self.download_ready_signal.emit(data)

            elif msg_type == "update_group_list":
                self.group_list_updated.emit(data.get("groups", []))
            elif msg_type == "search_results":
                self.search_results_received.emit(data.get("results", []))
            elif msg_type == "group_history_response":
                self.message_history_received.emit(data.get("history", []))
            elif msg_type in ["chat", "system", "file_notification"]:
                self.message_received.emit(data)

    def start_file_download(self, port, save_path, filesize):
        """Creates and starts a thread to download a file."""
        self.file_receiver = FileReceiverThread(self.ip, port, save_path, filesize)
        self.file_receiver.start()

    def send_download_request(self, unique_filename):
        """Sends a request to the server to download a file."""
        request_msg = protocol.create_download_request(unique_filename)
        self.send_message(request_msg)

    def send_upload_request(self, filepath, group_name):
        """Sends a request to the server to upload a file."""
        try:
            filename = os.path.basename(filepath)
            filesize = os.path.getsize(filepath)
            request_msg = protocol.create_upload_request(group_name, filename, filesize)

            # Temporarily store the filepath locally, keyed by a unique identifier.
            # This allows us to retrieve it when the server sends "upload_ready".
            unique_key = f"{int(time.time())}_{filename}"
            request_msg['unique_filename_key'] = unique_key
            self.upload_requests[unique_key] = filepath

            self.send_message(request_msg)
        except FileNotFoundError:
            print(f"Error: File not found at {filepath}")

    def send_message(self, message_data):
        """A generic helper method to send any message to the server."""
        if self.socket:
            protocol.send_message(self.socket, message_data)

    # --- Methods for sending specific types of messages ---

    def send_leave_group_request(self, group_name):
        """Sends a request to leave a group."""
        request_msg = protocol.create_leave_group_request(group_name)
        self.send_message(request_msg)

    def send_group_message(self, text, group_name):
        """Sends a standard chat message to a group."""
        chat_msg = protocol.create_client_message(text, group_name)
        self.send_message(chat_msg)

    def send_search_request(self, query):
        """Sends a user search query to the server."""
        search_msg = protocol.create_search_users_message(query)
        self.send_message(search_msg)

    def send_create_group_request(self, group_name, members):
        """Sends a request to create a new group."""
        request_msg = protocol.create_group_message_request(group_name, members)
        self.send_message(request_msg)

    def send_get_history_request(self, group_name):
        """Sends a request for a group's message history."""
        request_msg = protocol.create_get_history_request(group_name)

        self.send_message(request_msg)
