"""
dialogs.py

This module contains the definitions for various pop-up dialog windows used
in the client application's user interface.

Each dialog is a self-contained component responsible for a specific task,
such as creating a new group. They are built using the PyQt6 framework.
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                             QPushButton, QListWidget, QMessageBox)
from PyQt6.QtCore import pyqtSignal, Qt


class CreateGroupDialog(QDialog):
    """
    A dialog window that allows the user to create a new group chat.

    It provides fields for a group name and a user search mechanism to find
    and select members to invite. When the user confirms, it emits a signal
    with the group name and the list of selected members.
    """
    # Signal emitted when the 'Create' button is clicked with valid data.
    # Arguments are: group_name (str), members_list (list)
    create_requested = pyqtSignal(str, list)

    def __init__(self, network_thread, parent=None):
        """
        Initializes the Create Group dialog.

        Args:
            network_thread: An instance of the running NetworkThread, used to
                            send search requests to the server.
            parent (QWidget, optional): The parent widget for this dialog.
        """
        super().__init__(parent)
        self.network_thread = network_thread

        self.setWindowTitle("Create New Group")
        self.setMinimumWidth(400)

        # --- UI Layout Setup ---
        layout = QVBoxLayout()
        self.setLayout(layout)

        layout.addWidget(QLabel("Group Name:"))
        self.group_name_input = QLineEdit()
        layout.addWidget(self.group_name_input)

        layout.addWidget(QLabel("Invite Users (Search by Name):"))
        self.user_search_input = QLineEdit()
        self.user_search_input.setPlaceholderText("Type to search for users...")
        layout.addWidget(self.user_search_input)

        # Layout for the two member lists (search results and selected members)
        members_layout = QHBoxLayout()

        search_results_layout = QVBoxLayout()
        search_results_layout.addWidget(QLabel("Search Results:"))
        self.search_results_list = QListWidget()
        search_results_layout.addWidget(self.search_results_list)

        selected_members_layout = QVBoxLayout()
        selected_members_layout.addWidget(QLabel("Selected Members:"))
        self.selected_members_list = QListWidget()
        selected_members_layout.addWidget(self.selected_members_list)

        members_layout.addLayout(search_results_layout)
        members_layout.addLayout(selected_members_layout)
        layout.addLayout(members_layout)

        self.create_button = QPushButton("Create")
        layout.addWidget(self.create_button)

        # --- Connecting Signals and Slots ---
        # When user types in the search box, trigger a search.
        self.user_search_input.textChanged.connect(self.on_search_text_changed)
        # When network thread gets search results, update the list.
        self.network_thread.search_results_received.connect(self.update_search_results)
        # Double-clicking a user in search results adds them to the selected list.
        self.search_results_list.itemDoubleClicked.connect(self.add_member)
        # Double-clicking a user in the selected list removes them.
        self.selected_members_list.itemDoubleClicked.connect(self.remove_member)
        # Clicking the create button triggers the final creation logic.
        self.create_button.clicked.connect(self.on_create)

    def on_search_text_changed(self, text):
        """
        Slot that is called whenever the text in the user search input changes.
        """
        if text.strip():
            # Send a search request to the server via the network thread.
            self.network_thread.send_search_request(text.strip())
        else:
            # Clear results if the search box is empty.
            self.search_results_list.clear()

    def update_search_results(self, results):
        """
        Slot that updates the search results list with data from the server.
        """
        self.search_results_list.clear()
        self.search_results_list.addItems(results)

    def add_member(self, item):
        """
        Slot to move a user from the search results to the selected members list.
        """
        nickname = item.text()
        # Check if the user is already in the selected list to avoid duplicates.
        if not self.selected_members_list.findItems(nickname, Qt.MatchFlag.MatchExactly):
            self.selected_members_list.addItem(nickname)
        # Remove the item from the search results list.
        self.search_results_list.takeItem(self.search_results_list.row(item))

    def remove_member(self, item):
        """
        Slot to remove a user from the selected members list.
        """
        self.selected_members_list.takeItem(self.selected_members_list.row(item))
        # Note: We don't add the user back to the search results to keep it simple.
        # The user can just search for them again if needed.

    def on_create(self):
        """
        Slot that is called when the 'Create' button is clicked.

        It validates the input and, if valid, emits the create_requested signal.
        """
        group_name = self.group_name_input.text().strip()
        if not group_name:
            QMessageBox.warning(self, "Input Error", "Group name cannot be empty.")
            return

        # Compile a list of all nicknames from the selected members list.
        members = [self.selected_members_list.item(i).text() for i in range(self.selected_members_list.count())]

        if not members:
            QMessageBox.warning(self, "Input Error", "You must invite at least one other user.")
            return

        # Emit the signal with the necessary data for the main window to handle.
        self.create_requested.emit(group_name, members)
        # Close the dialog with an "Accepted" status.
        self.accept()