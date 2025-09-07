"""
main.py

This is the main entry point for the client-side chat application.

It is responsible for initializing the PyQt6 application, managing the overall
application flow (from login to the main chat window), and acting as the
central controller that connects the user interface (from window.py and dialogs.py)
with the background network communication logic (from network_client.py).
"""

import sys
from PyQt6.QtWidgets import QApplication, QMessageBox, QFileDialog
from window import LoginWindow, ChatWindow
from dialogs import CreateGroupDialog
from network_client import NetworkThread

# --- Configuration ---
# You can change the server IP address here.
# '127.0.0.1' or 'localhost' for a server on the same machine.
SERVER_IP = '127.0.0.1'
SERVER_PORT = 12989


class ChatApplication:
    """
    The main controller class for the chat application.

    This class manages the application's state, windows, and the network thread.
    It orchestrates the connections between UI signals and network actions.
    """
    def __init__(self):
        """Initializes the application and its main components."""
        self.app = QApplication(sys.argv)
        self.nickname = None
        self.login_window = LoginWindow()
        self.chat_window = None
        self.network_thread = None

        # Connect the login window's signal to the login attempt logic.
        self.login_window.connect_requested.connect(self.attempt_login)

    def attempt_login(self, nickname):
        """
        Starts the process of connecting to the server.

        This method is triggered when the user requests to connect from the
        LoginWindow. It creates and starts the NetworkThread.

        Args:
            nickname (str): The nickname entered by the user.
        """
        self.nickname = nickname
        # Provide visual feedback to the user that a connection is in progress.
        self.login_window.connect_button.setEnabled(False)
        self.login_window.connect_button.setText("Connecting...")

        # Create the background network thread.
        self.network_thread = NetworkThread(SERVER_IP, SERVER_PORT, self.nickname)

        # --- Connect signals from the NetworkThread to handler methods ---
        self.network_thread.login_successful.connect(self.show_chat_window)
        self.network_thread.message_received.connect(self.handle_chat_messages)
        self.network_thread.disconnected.connect(self.handle_disconnection)

        self.network_thread.start() # Start the thread's run() method.

    def show_chat_window(self):
        """
        Closes the login window and displays the main chat window.

        This is called upon a successful login. It creates the ChatWindow and
        connects all of its signals to the appropriate controller methods.
        """
        self.chat_window = ChatWindow(self.nickname)

        # --- Connect signals FROM the UI TO the controller/network thread ---
        self.chat_window.send_requested.connect(self.send_message)
        self.chat_window.create_group_requested.connect(self.open_create_group_dialog)
        self.chat_window.leave_group_requested.connect(self.leave_group)
        self.chat_window.history_requested.connect(self.get_group_history)
        self.chat_window.file_selected.connect(self.upload_file)
        self.chat_window.download_requested.connect(self.download_file)

        # --- Connect signals FROM the network thread TO the UI ---
        self.network_thread.group_list_updated.connect(self.chat_window.update_group_list)
        self.network_thread.message_history_received.connect(self.chat_window.display_history)
        self.network_thread.download_ready_signal.connect(self.prompt_save_file)

        # Transition from login window to chat window.
        self.login_window.close()
        self.chat_window.show()

    def handle_chat_messages(self, data):
        """Passes incoming messages from the network to the chat window for display."""
        if self.chat_window:
            self.chat_window.append_message(data)

    def prompt_save_file(self, data):
        """
        Opens a 'Save As' dialog when the server is ready to send a file.

        Args:
            data (dict): A dictionary containing port, filename, and filesize.
        """
        port = data.get("port")
        filename = data.get("filename")
        filesize = data.get("filesize")

        # Ask the user where they want to save the file.
        save_path, _ = QFileDialog.getSaveFileName(self.chat_window, "Save File", filename)

        if save_path:
            # Tell the network thread to start the download.
            self.network_thread.start_file_download(port, save_path, filesize)

    def download_file(self, unique_filename):
        """Instructs the network thread to request a file download from the server."""
        self.network_thread.send_download_request(unique_filename)

    def send_message(self, text, group_name):
        """Instructs the network thread to send a chat message."""
        self.network_thread.send_group_message(text, group_name)

    def open_create_group_dialog(self):
        """Opens the dialog for creating a new group."""
        dialog = CreateGroupDialog(self.network_thread, self.chat_window)
        # Connect the dialog's signal to the group creation logic.
        dialog.create_requested.connect(self.create_group)
        dialog.exec() # Show the dialog modally.

    def create_group(self, group_name, members):
        """Instructs the network thread to send a 'create group' request."""
        self.network_thread.send_create_group_request(group_name, members)

    def leave_group(self, group_name):
        """Instructs the network thread to send a 'leave group' request."""
        self.network_thread.send_leave_group_request(group_name)

    def get_group_history(self, group_name):
        """Instructs the network thread to request history for a group."""
        self.network_thread.send_get_history_request(group_name)

    def upload_file(self, filepath, group_name):
        """Instructs the network thread to start the file upload process."""
        self.network_thread.send_upload_request(filepath, group_name)

    def handle_disconnection(self, reason):
        """
        Handles the disconnection event from the network thread.

        It shows an error message to the user and either resets the login
        screen or quits the application.

        Args:
            reason (str): The reason for the disconnection.
        """
        # Determine which window is currently active to use as the parent for the message box.
        parent_window = self.chat_window if self.chat_window and self.chat_window.isVisible() else self.login_window
        QMessageBox.critical(parent_window, "Disconnected", reason)

        if not (self.chat_window and self.chat_window.isVisible()):
            # If disconnection happened at the login screen, re-enable the connect button.
            self.login_window.connect_button.setEnabled(True)
            self.login_window.connect_button.setText("Connect")
        else:
            # If the user was in the chat, quit the application.
            self.app.quit()

    def run(self):
        """Starts the application by showing the login window and running the event loop."""
        self.login_window.show()
        sys.exit(self.app.exec())


if __name__ == "__main__":
    # This is the entry point of the script.
    chat_app = ChatApplication()
    chat_app.run()