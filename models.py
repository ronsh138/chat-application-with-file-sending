# models.py
import protocol

class User:
    """Represents a connected user."""
    def __init__(self, connection, nickname):
        self.connection = connection
        self.nickname = nickname

class GroupChat:
    """Represents a single group chat room in memory."""
    def __init__(self, name):
        self.name = name
        self.members = []

    def add_member(self, user):
        """Adds a user to the group."""
        if user not in self.members:
            self.members.append(user)

    def remove_member(self, user):
        """Removes a user from the group."""
        if user in self.members:
            self.members.remove(user)

    def broadcast(self, data, sender_user):
        """Sends a message to all members of the group except the sender."""
        for member in self.members:
            if member != sender_user:
                protocol.send_message(member.connection, data)