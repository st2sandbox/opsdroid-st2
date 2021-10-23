"""A connector for StackStorm."""

from opsdroid.connector import Connector, register_event
from opsdroid.events import Event
from st2client.client import DEFAULT_API_PORT, DEFAULT_AUTH_PORT, DEFAULT_STREAM_PORT, DEFAULT_API_VERSION, Client
from voluptuous import Inclusive, Required

_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = {
    "api_version": str,
    "cacert": str,
    Required("base_url"): str,
    # these use separate ports assuming we talk directly with
    # the backend services as this is a backend service.
    # To use a load balancer instead of the ports, all of these need to be set.
    "api_url": str,
    "auth_url": str,
    "stream_url": str,
    # credentials (token or api_key are best)
    "token": str,
    "api_key": str,
    Inclusive("username", "login"): str,
    Inclusive("password", "login"): str,
} 


class StackStormConnector(Connector):
    """An OpsDroid Connector that brings the StackStorm event stream into OpsDroid.
    
    This connector is responsible for communication with StackStorm.
    It handles connecting to StackStorm to get the event stream.
    Then, it wraps those events in an OpsDroid event to be handled by
    parsers, matchers, and skills designed to work with StackStorm events.
    
    This also handles making StackStorm api calls for any skills that need to
    retrieve more data from or that need to make changes in, StackStorm.
    """
    
    def __init__(self, config, opsdroid):
        _LOGGER.debug(_("Starting StackStorm Connector."))
        super().__init__(config, opsdroid=opsdroid)
        self.name = config.get("name", "st2") 
        self.client = None

        # be explicit with Client config
        self.api_version = api_version = config.get(
            "api_version", DEFAULT_API_VERSION
        )
        self.base_url = base_url = config["base_url"]
        self.api_url = config.get(
            "api_url", f"{base_url}:{DEFAULT_API_PORT}/{api_version}"
        )
        self.auth_url = config.get(
            "auth_url", f"{base_url}:{DEFAULT_AUTH_PORT}/{api_version}"
        )
        self.stream_url = config.get(
            "api_url", f"{base_url}:{DEFAULT_STREAM_PORT}/{api_version}"
        )
        
        token = config.get("token")
        api_key = config.get("api_key")
        username = config.get("username")
        if not token and not api_key and not username:
            _LOGGER.error("You must define at least one StackStorm auth method.")

    async def connect(self):
        # create st2 client
        token = self.config.get("token", None)
        api_key = self.config.get("api_key", None)
        client = Client(
            api_version=self.api_version,
            base_url=self.base_url,
            api_url=self.api_url,
            auth_url=self.auth_url,
            stream_url=self.stream_url,
            # we verify ssl certs by default
            cacert=self.config.get("cacert", True),
            # TODO: how does OpsDroid enable debug mode
            debug=self.config.get("debug", False),
            token=token,
            api_key=api_key,
        )
        if not token and not api_key:
            username = self.config.get("username")
            password = self.config.get("password")
            token = Token()
            client.tokens.create(
                token,
                auth=(username=username, password=password),
            )
            client.token = token
        # issue whoami to check auth
        client.get_user_info()
        # TODO: there isn't an api yet register, just to list.
        # register with StackStorm service registry
        # client.managers["ServiceRegistryGroups"]
        # client.managers["ServiceRegistryMembers"]

        self.client = client

    async def disconnect(self):
        # unregister from registry
        # close client
        pass

    async def listen(self):
        event_types = [
            # "st2.announcement__*",
            "st2.announcement__chatops",
            # "st2.workflow__create",
            # "st2.workflow__update",
            # "st2.workflow__delete",
            # "st2.execution__create",
            # "st2.execution__update",
            # "st2.execution__delete",
            # "st2.execution.output__create",
            # "st2.execution.output__update",
            # "st2.execution.output__delete",
            # "st2.workflow.status__*",
            # "st2.trigger__create",
            # "st2.trigger__update",
            # "st2.trigger__delete",
            # "st2.trigger_instances_dispatch__trigger_instance",
            # "st2.sensor__create",
            # "st2.sensor__update",
            # "st2.sensor__delete",
            # TODO: need action alias event and pack event
        ]
        event_stream = self.client.managers["Stream"].listen(
            event_types,
            # **kwargs,
        ):
        # create event steam generator
        while True:
            event = await next(event_stream)
            
            # Convert to opsdroid Message object
            #
            # Message objects take a pointer to the connector to
            # allow the skills to call the respond method
            message = Message(
                raw_message.text,
                raw_message.user,
                raw_message.room,
                self
            )
            
            # Parse the message with opsdroid
            await opsdroid.parse(message)

    async def respond(self):
        pass
    .    ,    .    ,    .    ,    .    ,    .    ,    .    ,    .    ,    .    |    .  |
