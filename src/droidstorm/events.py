from opsdroid.events import Event, Message


class StackStormAnnouncement(Message):
    """An announcement created by the StackStorm announcement runner.
    """


class StackStormResourceCUDEvent(Event):
    """An event created on resource Create/Update/Delete
    """
    
    resource_type = NotImplemented
    
    def __init__(self, resource: dict, action: str, *args, **kwargs):
        """Create object with minimum properties."""
        super().__init__(*args, **kwargs)
        # decoded json object
        self.resource = resource
        # action is one of: create, update, delete
        self.action = action


class StackStormActionAliasEvent(StackStormResourceCUDEvent):
    """An event created on ActionAlias Create/Update/Delete
    """
    
    resource_type = "ActionAlias"
