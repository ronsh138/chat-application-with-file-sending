"""
window.py

This module defines the main graphical user interface (GUI) windows for the
client application using the PyQt6 framework.

It includes the initial LoginWindow for user setup and the main ChatWindow,
which serves as the primary interface for messaging, group management, and
file sharing. The windows are designed to be decoupled from the network logic,
communicating user actions via signals.
"""

from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QTextEdit, QListWidget, QMessageBox, QFileDialog, QTextBrowser)
from PyQt6.QtCore import pyqtSignal, QUrl, Qt
from datetime import datetime


class LoginWindow(QWidget):
    """
    The initial window shown to the user to enter their nickname.
    """
    # Signal emitted when the user clicks the 'Connect' button with a valid nickname.
    connect_requested = pyqtSignal(str)

    def __init__(self):
        """Initializes the LoginWindow UI components."""
        super().__init__()
        self.setWindowTitle("Login to Chat")
        self.setFixedSize(300, 150)

        # --- UI Layout Setup ---
        layout = QVBoxLayout()
        self.setLayout(layout)
        self.nickname_label = QLabel("Choose your nickname:")
        self.nickname_input = QLineEdit()
        self.connect_button = QPushButton("Connect")
        layout.addWidget(self.nickname_label)
        layout.addWidget(self.nickname_input)
        layout.addWidget(self.connect_button)

        # --- Connecting Signals and Slots ---
        self.connect_button.clicked.connect(self.on_connect)

    def on_connect(self):
        """
        Slot called when the 'Connect' button is clicked.
        It validates the input and emits the connect_requested signal.
        """
        nickname = self.nickname_input.text().strip()
        if nickname:
            self.connect_requested.emit(nickname)


class ChatWindow(QWidget):
    """
    The main chat interface window.

    This window contains the group list, chat display, message input, and
    all associated controls. It handles UI updates based on data received
    from the network thread and emits signals based on user interactions.
    """
    # --- Signals to communicate user actions to the main controller ---
    send_requested = pyqtSignal(str, str)         # (message_text, group_name)
    create_group_requested = pyqtSignal()
    leave_group_requested = pyqtSignal(str)       # (group_name)
    history_requested = pyqtSignal(str)           # (group_name)
    file_selected = pyqtSignal(str, str)          # (filepath, group_name)
    download_requested = pyqtSignal(str)          # (unique_filename)

    def __init__(self, nickname):
        """
        Initializes the main ChatWindow.

        Args:
            nickname (str): The nickname of the current user.
        """
        super().__init__()
        self.nickname = nickname
        self.current_group = None
        self.setWindowTitle(f"Chat - {self.nickname}")
        self.setMinimumSize(700, 500)

        # --- UI Layout Setup ---
        main_layout = QHBoxLayout()
        self.setLayout(main_layout)

        # Left Panel (Groups)
        left_panel_layout = QVBoxLayout()
        self.group_list_widget = QListWidget()
        self.create_group_button = QPushButton("Create Group")
        self.leave_group_button = QPushButton("Leave Group")
        left_panel_layout.addWidget(QLabel("Groups"))
        left_panel_layout.addWidget(self.group_list_widget)
        left_panel_layout.addWidget(self.create_group_button)
        left_panel_layout.addWidget(self.leave_group_button)
        left_panel_widget = QWidget()
        left_panel_widget.setLayout(left_panel_layout)

        # Right Panel (Chat Display and Input)
        self.right_panel_layout = QVBoxLayout() # Stored as an instance variable to allow modifications
        self.chat_display = QTextBrowser() # Use QTextBrowser to handle rich text (like links)
        self.chat_display.setReadOnly(True)

        input_layout = QHBoxLayout()
        self.message_input = QLineEdit()
        self.attach_file_button = QPushButton("📎") # Emoji for attach icon
        self.attach_file_button.setFixedWidth(40)
        self.send_button = QPushButton("Send")
        input_layout.addWidget(self.message_input)
        input_layout.addWidget(self.attach_file_button)
        input_layout.addWidget(self.send_button)

        self.right_panel_layout.addWidget(self.chat_display)
        self.right_panel_layout.addLayout(input_layout)
        right_panel_widget = QWidget()
        right_panel_widget.setLayout(self.right_panel_layout)

        # Add panels to the main layout
        main_layout.addWidget(left_panel_widget, 1)  # 1/4 of the width
        main_layout.addWidget(right_panel_widget, 3) # 3/4 of the width

        # --- Connecting Signals and Slots ---
        self.send_button.clicked.connect(self.on_send)
        self.message_input.returnPressed.connect(self.on_send)
        self.create_group_button.clicked.connect(self.create_group_requested.emit)
        self.group_list_widget.currentItemChanged.connect(self.on_group_selected)
        self.leave_group_button.clicked.connect(self.on_leave_group)
        self.attach_file_button.clicked.connect(self.on_attach_file)
        self.chat_display.anchorClicked.connect(self.on_link_clicked) # For handling file download links

    def on_link_clicked(self, url: QUrl):
        """Handles when a user clicks a hyperlink (file download) in the chat display."""
        unique_filename = url.toString()
        print(f"Download requested for: {unique_filename}")
        self.download_requested.emit(unique_filename)
        # Prevent the widget from trying to navigate to the URL.
        self.chat_display.setSource(QUrl())

    def on_attach_file(self):
        """Opens a file dialog for the user to select a file to upload."""
        if not self.current_group:
            QMessageBox.warning(self, "No Group Selected", "Please select a group before sending a file.")
            return

        filepath, _ = QFileDialog.getOpenFileName(self, "Select File to Send")
        if filepath:
            self.file_selected.emit(filepath, self.current_group)

    def on_group_selected(self, current_item, previous_item):
        """Slot called when the user selects a different group from the list."""
        if current_item:
            # To ensure a clean slate and prevent any display bugs, we replace the chat widget.
            self.chat_display.deleteLater()
            self.chat_display = QTextBrowser()
            self.chat_display.setReadOnly(True)
            self.chat_display.anchorClicked.connect(self.on_link_clicked) # Reconnect signal
            self.right_panel_layout.insertWidget(0, self.chat_display) # Insert at the top of the layout

            self.current_group = current_item.text()
            self.leave_group_button.setEnabled(self.current_group != "General") # Cannot leave 'General'
            self.history_requested.emit(self.current_group) # Request history for the new group
        else:
            self.current_group = None
            self.leave_group_button.setEnabled(False)

    def on_leave_group(self):
        """Handles the 'Leave Group' button click, showing a confirmation dialog."""
        if not self.current_group or self.current_group == "General":
            return
        reply = QMessageBox.question(self, "Confirm Leave",
                                     f"Are you sure you want to leave the group '{self.current_group}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.leave_group_requested.emit(self.current_group)

    def update_group_list(self, groups):
        """
        Updates the list of groups in the UI, trying to preserve the current selection.
        """
        current_selection = self.current_group
        self.group_list_widget.clear()
        self.group_list_widget.addItems(groups)
        if current_selection in groups:
            # Re-select the group the user was previously viewing.
            items = self.group_list_widget.findItems(current_selection, Qt.MatchFlag.MatchExactly)
            if items:
                self.group_list_widget.setCurrentItem(items[0])
        elif self.group_list_widget.count() > 0:
            # If the old group is gone, select the first group in the list.
            self.group_list_widget.setCurrentRow(0)

    def on_send(self):
        """
        Handles the send button click or enter press in the message input.
        Sends the message and also displays it locally immediately.
        """
        text = self.message_input.text().strip()
        if text and self.current_group:
            # Emit signal to send message over the network.
            self.send_requested.emit(text, self.current_group)
            # Create a local copy of the message data to display immediately.
            # This provides instant feedback to the user.
            local_message_data = {
                "type": "chat",
                "nickname": self.nickname,
                "message": text,
                "timestamp": datetime.now().strftime('%H:%M:%S'),
                "group_name": self.current_group
            }
            self.append_message(local_message_data)
            self.message_input.clear()

    def append_message(self, data):
        """
        Appends a message to the chat display, formatted according to its type.
        """
        # Only display the message if it belongs to the currently viewed group.
        if self.chat_display.isVisible() and data.get("group_name") == self.current_group:
            msg_type = data.get("type")
            timestamp = data.get("timestamp", "")

            if msg_type == "file_notification":
                sender = data.get('sender')
                filename = data.get('filename')
                unique_filename = data.get('unique_filename')
                # Use HTML to create a clickable link for downloading.
                html = f"""
                <p style="margin: 0;">
                    ({timestamp}) <b>{sender}</b> sent a file: 
                    <a href="{unique_filename}" style="color: #2980b9; text-decoration: none;">
                        {filename} (Download)
                    </a>
                </p>
                """
                self.chat_display.append(html)
            elif msg_type == "chat":
                nickname = data.get('nickname')
                message = data.get('message')
                self.chat_display.append(f"({timestamp}) {nickname}: {message}")
            elif msg_type == "system":
                message = data.get('message')
                self.chat_display.append(f"({timestamp}) [{message}]")
            else:
                return # Ignore unknown message types.

            # Automatically scroll to the bottom to show the newest message.
            self.chat_display.ensureCursorVisible()

    def display_history(self, history):
        """
        Displays a batch of historical messages in the chat window.
        """
        for msg_data in history:
            self.append_message(msg_data)
        self.chat_display.setPlaceholderText(f"You are now in '{self.current_group}'")