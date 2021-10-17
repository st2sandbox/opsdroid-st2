# based in part on opsdroid_homeassistant,skill and skill-dialogflow

from opsdroid.skill import Skill


class StackStormActionAliasesSkill(Skill):
    """OpsDroid Skill that forwards matching events to StackStorm.

    This skill gets dynamically reloaded to add all of the matchers
    from StackStorm's action aliases.
    When an action alias is matched, the event that triggered
    it gets transformed into an action execution api call.
    """

    def __init__(self, opsdroid, config, *args, **kwargs):
        super().__init__(opsdroid, config, *args, **kwargs)
        self._st2 = None

    @property
    def st2(self):
        if self._st2 is None:
            # create lazily (opsdroid.connectors not yet known when __init__ called)
            [self._st2] = [
                connector
                for connector in self.opsdroid.connectors
                # todo: pull name from config
                if connector.name == "droidstorm"
            ]
        return self._st2

    async def action_alias(self, event):
        """the primary action alias skill that gets dynamically
        updated with matchers based on StackStorm's config.
        """
        # await event.respond("...")
