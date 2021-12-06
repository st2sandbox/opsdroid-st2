from opsdroid.events import Event, Message


class Announcement(Message):
    """An announcement created by the StackStorm announcement runner.
    
    target is the route which maps too a connector instance
    """


class ResourceCUD(Event):
    """An event created on resource Create/Update/Delete
    """
    
    resource_type = NotImplemented
    # cud is one of: create, update, delete
    cud = NotImplemented
    
    def __init__(self, resource: dict, *args, **kwargs):
        """Create object with minimum properties."""
        super().__init__(*args, **kwargs)
        # decoded json object
        self.resource = resource


class CreateActionAlias(ResourceCUD):
    """An event created on ActionAlias Create
    """
    
    resource_type = "ActionAlias"
    cud = "create"


class UpdateActionAlias(ResourceCUD):
    """An event created on ActionAlias Update
    """
    
    resource_type = "ActionAlias"
    cud = "update"


class DeleteActionAlias(ResourceCUD):
    """An event created on ActionAlias Delete
    """
    
    resource_type = "ActionAlias"
    cud = "delete"


class CreatePack(ResourceCUD):
    """An event created on Pack Create
    """
    
    resource_type = "Pack"
    cud = "create"


class UpdatePack(ResourceCUD):
    """An event created on Pack Update
    """
    
    resource_type = "Pack"
    cud = "update"


class DeletePack(ResourceCUD):
    """An event created on Pack Delete
    """
    
    resource_type = "Pack"
    cud = "delete"


class CreateExecution(ResourceCUD):
    """An event created on Execution Create
    """
    
    resource_type = "Execution"
    cud = "create"


class UpdateExecution(ResourceCUD):
    """An event created on Execution Update
    """
    
    resource_type = "Execution"
    cud = "update"


class DeleteExecution(ResourceCUD):
    """An event created on Execution Delete
    """
    
    resource_type = "Execution"
    cud = "delete"


class CreateExecutionOutput(ResourceCUD):
    """An event created on ExecutionOutput Create
    """
    
    resource_type = "ExecutionOutput"
    cud = "create"


class UpdateExecutionOutput(ResourceCUD):
    """An event created on ExecutionOutput Update
    """
    
    resource_type = "ExecutionOutput"
    cud = "update"


class DeleteExecutionOutput(ResourceCUD):
    """An event created on ExecutionOutput Delete
    """
    
    resource_type = "ExecutionOutput"
    cud = "delete"
