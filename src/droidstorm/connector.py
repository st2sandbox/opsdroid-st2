"""A connector for StackStorm."""

import asyncio
import threading

from typing import TYPE_CHECKING

from aiohttp import ClientSession
from aiohttp_sse_client import client as sse_client
import orjson
from opsdroid.connector import Connector, register_event
from opsdroid.events import Event
from st2client.client import DEFAULT_API_PORT, DEFAULT_AUTH_PORT, DEFAULT_STREAM_PORT, DEFAULT_API_VERSION, Client
from voluptuous import Inclusive, Required
from yarl import URL

import .events as st2_events

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

        self._st2_event_types = [
            "st2.announcement__*",
            # we add a route for each connector
            # chatops => all bots; hubot => Hubot; errbot => err-StackStorm'
            # "st2.announcement__chatops",
            # "st2.announcement__hubot",  # odd. Hubot does not seem to listen for this
            # "st2.announcement__errbot",
            # "st2.announcement__<connector>",
            # users can add their own route with core.announcement action
            # "st2.announcement__<user-defined route>",
            #
            # route specified in action metadata:
            #    notify.on-complete
            #    notify.on-success
            #    notify.on-failure
            # or route specified when creating ActionAliasExecution
            # with the notification-route. This effectively
            # overrides action metadata's
            #    notify.on-complete.routes = [notification-route]
            # but, hubot does not seem to do anything with announcement__hubot
            # errbot only listens for __errbot and instructions say to
            # change the default route from chatops to errbot.

            # "st2.execution__create",
            # "st2.execution__update",
            # "st2.execution__delete",
            # "st2.execution.output__create",
            # "st2.execution.output__update",
            # "st2.execution.output__delete",
            
            # these events are not available in the event stream
            # but they could be if the streaming server listened to them
            # "st2.workflow__create",
            # "st2.workflow__update",
            # "st2.workflow__delete",
            # "st2.workflow.status__*",
            # "st2.trigger__create",
            # "st2.trigger__update",
            # "st2.trigger__delete",
            # "st2.trigger_instances_dispatch__trigger_instance",
            # "st2.sensor__create",
            # "st2.sensor__update",
            # "st2.sensor__delete",

            # TODO: st2 needs new actionalias and pack events in event stream
            # "st2.actionalias__create",
            # "st2.actionalias__update",
            # "st2.actionalias__delete",
            # "st2.pack__create",
            # "st2.pack__update",
            # "st2.pack__delete",
        ]

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
            # TODO: this is a blocking api call
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
        # we need to register to the groups with something like tooz
        # st2 uses: st2common.service_setup.register_service_in_service_registry
        # but we need to reimplements it because it pulls in:
        # st2 logging (lots of py2 compat)
        # oslo_config (ancient version, lots of globals, lots of import side effects)
        # st2common.services.coordination
        # st2common.util.system_info.get_process_info() #safe for us to use

        self.client = client

        # st2client is not async, and doesn't emit event types,
        # so we roll out own.
        self._events_session = ClientSession()

        # https://api.stackstorm.com/stream/v1/stream/#/stream_controller.get_all
        event_stream_url = URL(self.stream_url) / "stream" %
            {"events": ",".join(self._st2_event_types)}
        headers = {}
        api_key = self.config.get("api_key", None)
        if api_key:
            headers["St2-Api-Key"] = api_key
        else:
            headers["X-Auth-Token"] = self.client.token
        self.event_stream = sse_client.EventSource(
            event_stream_url,
            # option={"method": "GET"},
            # reconnection_time=,
            # max_connect_retry=,
            session=self._events_session,
            # on_open=,
            # on_message=,
            # on_error=,
            # **kwargs
            headers=headers,
        )
        await self.event_stream.connect()

    async def disconnect(self):
        # unregister from registry
        # close client
        await self.event_stream.close()
        await self._events_session.close()

    async def listen(self):
        event: sse_client.MessageEvent
        try:
            async for event in self.event_stream:
                # If an execution on the API server takes too long, the message
                # can be empty. In this case, rerun the query.
                if not event.data:
                    continue
                await self._parse_st2_event(event)
        except ConnectionError:
            pass

        # how ST2 generated events server-side:
        #
        # the persistence layer publishes db model objects to rmq
        # the st2 stream server listens to the transport queue (rmq)
        # on behalf of each client (filtered per client request)
        # rmq messages are pickled db model objects
        # except announcement which is a dict
        # for db models:
        # st2common.stream.BaseListener.processor.process()
        # processes each queue message and constructs the event name
        # event_name = f"{exchange}__{routing_key}"
        # and the body is built using model. from_model(body)
        # where model is an API model object
        # that gets encoded to json in
        # st2stream.controllers.v1.stream.format()
        # the BaseAPI object defines
        # __json__(self): vars(self)
        # so the props of the json object are the attributes of the api object
        # the st2client uses sseclient to get the message stream
        # each message has an event (type) and json encoded data
        # the st2client only yields the decoded data:
        # eg: yield orjson.loads(message.data)
        # so I might need a separate listener for each event type

    async def _parse_st2_event(self, raw_event: sse_client.MessageEvent):
        # Convert to opsdroid Message/Event and have pass to OpsDroid
        #
        # Message/Event objects take a pointer to the connector to
        # allow the skills to call the respond method

        # raw_event.type: str  # event field or None
        # raw_event.message: str  # event field
        # raw_event.data: str  # data field as encoded json
        # raw_event.origin: str  # str(response.real_url.origin())
        # raw_event.last_event_id: str  # id field

        if not raw_event.type or not raw_event.type. startswith("st2."):
            # log unknown event. this should not happen
            return

        # drop initial "st2." and split
        resource_type, route = raw_event.type[4:].split("__", 1)

        # st2 returns event.data as encoded json
        data = orjson.loads(raw_event.data)

        if resource_type == "announcement":
            if route in ["hubot", "errbot"]:
                # not for us. ignore it.
                # chatops => all bots; hubot => Hubot; errbot => err-StackStorm
                # TODO: Make this ignore list configurable.
                return
            event = st2_events.Announcement(
                text=data,
                route=route,
                raw_event=raw_event,
                connector=self,
            )
        elif resource_type == "actionalias":
            if route == "create":
                event = st2_events.CreateActionAlias(
                    resource=data,
                    raw_event=raw_event,
                    connector=self,
                )
            elif route == "update":
                event = st2_events.UpdateActionAlias(
                    resource=data,
                    raw_event=raw_event,
                    connector=self,
                )
            elif route == "delete":
                event = st2_events.DeleteActionAlias(
                    resource=data,
                    raw_event=raw_event,
                    connector=self,
                )
            else:
                # unknown route
                return
        elif resource_type == "pack":
            if route == "create":
                event = st2_events.CreatePack(
                    resource=data,
                    raw_event=raw_event,
                    connector=self,
                )
            elif route == "update":
                event = st2_events.UpdatePack(
                    resource=data,
                    raw_event=raw_event,
                    connector=self,
                )
            elif route == "delete":
                event = st2_events.DeletePack(
                    resource=data,
                    raw_event=raw_event,
                    connector=self,
                )
            else:
                # unknown route
                return
        elif resource_type == "execution":
            if route == "create":
                event = st2_events.CreateExecution(
                    resource=data,
                    raw_event=raw_event,
                    connector=self,
                )
            elif route == "update":
                event = st2_events.UpdateExecution(
                    resource=data,
                    raw_event=raw_event,
                    connector=self,
                )
            elif route == "delete":
                event = st2_events.DeleteExecution(
                    resource=data,
                    raw_event=raw_event,
                    connector=self,
                )
            else:
                # unknown route
                return
        elif resource_type == "execution.output":
            if route == "create":
                event = st2_events.CreateExecutionOutput(
                    resource=data,
                    raw_event=raw_event,
                    connector=self,
                )
            elif route == "update":
                event = st2_events.UpdateExecutionOutput(
                    resource=data,
                    raw_event=raw_event,
                    connector=self,
                )
            elif route == "delete":
                event = st2_events.DeleteExecutionOutput(
                    resource=data,
                    raw_event=raw_event,
                    connector=self,
                )
            else:
                # unknown route
                return
        else:  # unknown resource_type. assume cud
            event = st2_events.ResourceCUD(
                resource=data,
                raw_event=raw_event,
                connector=self,
            )
            event.resource_type = resource_type
            event.cud = route

        # Parse the message/event with opsdroid which triggers skills
        await self.opsdroid.parse(event)

    # async def respond(self):
    #    pass
#   .    ,    .    ,    .    ,    .    ,    .    ,    .    ,    .    ,    .    |    .  |
