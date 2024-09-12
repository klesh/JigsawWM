"""JmkCore is the core of the JMK feature, it handles the key events and dispatches
them to the registered handlers."""

import logging
import abc
import typing
import time
from dataclasses import dataclass, field
from functools import partial
from threading import Lock

from jigsawwm.w32.vk import Vk, parse_combination, expand_combination
from jigsawwm.w32.sendinput import send_combination


logger = logging.getLogger(__name__)

JmkCombination = typing.Union[typing.List[Vk], str]
JmkDelayCall = typing.Callable[[float, typing.Callable, typing.Any], None]


@dataclass
class JmkEvent:
    """A jmk event that contains the key/button, pressed state,
    system state(does it came from the OS) and extra data"""

    vk: Vk
    pressed: bool
    system: bool = False
    flags: int = 0
    extra: any = 0
    time: float = field(default_factory=time.time)

    def __repr__(self) -> str:
        evt = "down" if self.pressed else "up"
        src = "sys" if self.system else "sim"
        return f"JmkEvent({self.vk.name}, {evt}, {src}, {self.flags}, {self.extra})"

    def same(self, other: "JmkEvent") -> bool:
        """Check if two events are the same"""
        return self.vk == other.vk and self.pressed == other.pressed


class JmkHandler:
    """A handler that handles events"""

    next_handler: "JmkHandler"
    delay_call: typing.Optional[JmkDelayCall] = None

    def __call__(self, evt: JmkEvent):
        """Handle the event"""

    def pipe(self, next_handler: "JmkHandler") -> "JmkHandler":
        """Pipe the handler to the next handler"""
        next_handler.delay_call = self.delay_call
        self.next_handler = next_handler
        return next_handler


@dataclass
class JmkTrigger:
    """Key trigger"""

    keys: typing.Iterable[Vk]
    callback: typing.Callable
    release_callback: typing.Callable = None
    triggerred: bool = False
    lit_keys: typing.Set[Vk] = None
    first_lit_at: float = None
    _lock: Lock = field(default_factory=Lock)

    def trigger(self):
        """Trigger"""
        logger.info("keys triggered: %s", self.keys)
        self.triggerred = True
        release_cb = self.callback()
        if release_cb:
            self.release_callback = release_cb

    def release(self):
        """Release"""
        if not self.triggerred:
            return
        logger.info("keys released: %s", self.keys)
        if not self.triggerred:
            return
        self.triggerred = False
        if self.release_callback:
            self.release_callback()


JmkTriggerDef = typing.Tuple[
    JmkCombination, typing.Callable, typing.Optional[typing.Callable]
]
JmkTriggerDefs = typing.List[JmkTriggerDef]


class JmkTriggers(JmkHandler):
    """A handler that handles triggers."""

    triggers: typing.Dict[typing.FrozenSet[Vk], JmkTrigger]

    def __init__(
        self,
        triggers: JmkTriggerDefs = None,
    ):
        super().__init__()
        self.triggers = {}
        if triggers:
            self.register_triggers(triggers)

    def check_comb(self, comb: typing.List[Vk]):
        """Check if a combination is valid."""

    def expand_comb(self, comb: JmkCombination) -> typing.List[typing.List[Vk]]:
        """Expand a combination to a list of combinations."""
        if isinstance(comb, str):
            comb = parse_combination(comb)
        self.check_comb(comb)
        return expand_combination(comb)

    def register_triggers(
        self,
        triggers: JmkTriggerDefs,
    ):
        """Register triggers"""
        for args in triggers:
            self.register(*args)

    def register(
        self,
        comb: JmkCombination,
        cb: typing.Union[typing.Callable, str],
        release_cb: typing.Callable = None,
    ):
        """Register a trigger."""
        if isinstance(cb, str):
            new_comb = parse_combination(cb)
            cb = partial(send_combination, *new_comb)
        for keys in self.expand_comb(comb):
            if frozenset(keys) in self.triggers:
                raise ValueError(f"hotkey {keys} already registered")
            trigger = JmkTrigger(keys, cb, release_cb)
            self.triggers[frozenset(keys)] = trigger

    def unregister(self, comb: JmkCombination):
        """Unregister a hotkey."""
        for keys in self.expand_comb(comb):
            self.triggers.pop(frozenset(keys))

    def __call__(self, evt: JmkEvent):
        self.next_handler(evt)


class JmkLayerKey(JmkHandler):
    """A key handler that can be used in a layer"""

    state: "JmkCore" = None
    layer: typing.Optional[int] = None
    vk: Vk = None

    def __repr__(self):
        return f"{self.__class__.__name__}(layer={self.layer}, vk={self.vk.name})"

    def other_key(self, evt: JmkEvent):
        """Intercept other key events"""

    @abc.abstractmethod
    def __call__(self, evt: JmkEvent):
        """Handle the key event"""


class JmkKey(JmkLayerKey):
    """The basic key handler in a layer

    :param kf: can be a Vk(map key to another key), a string, a list of
               Vk(map key to a combination) or a callable (a function to execute)
    :param swallow: whether to swallow the event, normally True
    """

    keys_or_func: typing.Union[typing.List[Vk], typing.Callable]

    def __init__(
        self,
        keys_or_func: typing.Union[Vk, str, typing.List[Vk], typing.Callable],
    ):
        super().__init__()
        if isinstance(keys_or_func, str):
            keys_or_func = parse_combination(keys_or_func)
        if isinstance(keys_or_func, Vk):
            keys_or_func = [keys_or_func]
        self.keys_or_func = keys_or_func

    def __call__(self, evt: JmkEvent):
        if isinstance(self.keys_or_func, list):
            if evt.pressed:
                for key in self.keys_or_func:
                    self.state.next_handler(JmkEvent(key, evt.pressed))
            else:
                for key in reversed(self.keys_or_func):
                    self.state.next_handler(JmkEvent(key, evt.pressed))
        elif not evt.pressed:
            self.keys_or_func()


class JmkTapHold(JmkLayerKey):
    """A advanced key handler that can be used in a layer

    :param tap: map the key to another key when tapped
    :param hold: map the key to another key when hold
    :param on_hold_down: a function to execute when hold down
    :param on_hold_up: a function to execute when hold up
    :param on_tap: a function to execute when tapped
    :param term: the term to determine whether it is a hold
    :param quick_tap_term: tap a key and then hold it down within this term will enter quick
                        tap mode, when activated, the tap key will be sent as long as the
                        key is hold. It is useful for dual function keys like using key A as
                        the Alt key and you want to input a bunch of A
    """

    tap: typing.Optional[Vk] = None
    hold: typing.Optional[typing.Union[Vk, str]] = None
    on_hold_down: typing.Optional[typing.Callable] = None
    on_hold_up: typing.Optional[typing.Callable] = None
    on_tap: typing.Optional[typing.Callable] = None
    term: float = 0.2
    quick_tap_term: float
    last_tapped_at: float = 0
    quick_tap: bool = False
    other_pressed_keys: typing.Set[Vk]
    resend: typing.List[JmkEvent]
    pressed: int = 0
    held: bool = False

    def __init__(
        self,
        tap: Vk = None,
        hold: Vk = None,
        on_hold_down: callable = None,
        on_hold_up: callable = None,
        on_tap: callable = None,
        term: float = 0.2,
        quick_tap_term: float = 0.2,
    ):
        super().__init__()
        self.tap = tap
        self.hold = hold
        self.on_hold_down = on_hold_down
        self.on_hold_up = on_hold_up
        self.on_tap = on_tap
        self.term = term
        self.quick_tap_term = quick_tap_term
        self.other_pressed_keys = set()
        self.resend = []
        self.pressed = 0
        self.held = False

    def check_hold(self):
        """Check if the key is hold"""
        if (
            self.pressed > self.last_tapped_at
            and time.time() - self.pressed > self.term
        ):
            self.hold_down()

    def hold_down(self):
        """Handle the hold_down event"""
        if self.held:
            # hold_down might be triggered multiple places
            return
        self.held = True
        logger.debug("%s hold down", self)
        if self.on_hold_down:
            logger.debug("%s on_hold_down", self)
            self.on_hold_down()
        if self.hold:
            if isinstance(self.hold, Vk):
                evt = JmkEvent(self.hold, True)
                logger.debug("%s %s down >>>", self, evt)
                self.state.next_handler(evt)
            else:
                self.state.activate_layer(self.hold)
        self.flush_resend()

    def hold_up(self):
        """Handle the hold_up event"""
        self.pressed = 0
        self.held = False
        self.other_pressed_keys.clear()
        logger.debug("%s hold up", self)
        if self.on_hold_up:
            logger.debug("%s on_hold_up", self)
            self.on_hold_up()
        if self.hold:
            if isinstance(self.hold, Vk):
                evt = JmkEvent(self.hold, False)
                logger.debug("%s %s up >>>", self, evt)
                self.state.next_handler(evt)
            else:
                self.state.deactivate_layer(self.hold)

    def tap_down_up(self):
        """Handle the tap_down_up event"""
        self.pressed = 0
        self.held = False
        logger.debug("%s tapped", self)
        if self.tap:
            evt_down = JmkEvent(self.tap, True)
            logger.debug("%s %s >>>", self, evt_down)
            self.state.next_handler(evt_down)
            evt_up = JmkEvent(self.tap, False)
            logger.debug("%s %s >>>", self, evt_up)
            self.state.next_handler(evt_up)
        if self.on_tap:
            logger.debug("%s on_tap", self)
            self.on_tap()
        self.last_tapped_at = time.time()
        self.flush_resend()

    def other_key(self, evt: JmkEvent) -> bool:
        """Intercept other key events"""
        # intercept timing: after key down, before hold/tap determined
        if not self.pressed or self.held:
            return False
        logger.debug("%s queue other key %s >>>", self, evt)
        self.resend.append(evt)
        if evt.pressed:
            self.other_pressed_keys.add(evt.vk)
        elif evt.vk in self.other_pressed_keys:
            # there was a key tapping, we shal get into the holding mode immediately
            self.other_pressed_keys.remove(evt.vk)
            self.hold_down()
        # wheel up/down doesn't have a key down event
        if evt.vk in (
            Vk.WHEEL_UP,
            Vk.WHEEL_DOWN,
        ):
            self.hold_down()
        # or timeout
        self.check_hold()
        # delay the key until we know if it's a tap or hold
        return True

    def flush_resend(self):
        """Flush the resend queue"""
        if self.resend:
            for evt in self.resend:
                logger.debug("%s resend %s >>>", self, evt)
                self.state(evt)  # pylint: disable=not-callable
        self.resend.clear()

    def __call__(self, evt: JmkEvent):
        # quick tap check
        if (
            evt.pressed
            and self.last_tapped_at
            and time.time() - self.last_tapped_at < self.quick_tap_term
        ):
            self.quick_tap = True
        if self.quick_tap:
            if not evt.pressed:
                self.last_tapped_at = 0
                self.quick_tap = False
            evt = JmkEvent(self.tap or evt.vk, evt.pressed)
            logger.debug("%s quick tap %s >>>", self, evt)
            return self.state.next_handler(evt)
        # tap hold
        if evt.pressed:
            if not self.pressed:
                # initial state
                self.pressed = evt.time
                if self.state.delay_call:
                    self.state.delay_call(self.term, self.check_hold)
            else:
                self.check_hold()
        else:
            # reset state
            self.check_hold()
            if self.held:
                self.hold_up()
            else:
                self.tap_down_up()


JmkLayer = typing.Dict[Vk, JmkHandler]


class JmkCore(JmkHandler):
    """JmkCore is the core of JmkHandler, it handles the key events and dispatches them
    to the registered handlers.

    :param next_handler: the next handler to dispatch the event to
    :param layers: the layers
    """

    layers: typing.List[JmkLayer] = [{}]
    active_layers: typing.Set[int]
    routes: JmkLayer

    def __init__(
        self,
        layers: typing.List[JmkLayer] = None,
    ):
        super().__init__()
        self.active_layers = {0}
        self.routes = {}
        if layers:
            self.register_layers(layers)

    def register_layers(self, layers: typing.List[JmkLayer]):
        """Register layers"""
        if len(layers) < 1:
            raise ValueError("layers must have at least one layer")
        self.layers = [{}]
        for index, layer in enumerate(layers):
            if not isinstance(layer, dict):
                raise TypeError("layer must be a dict")
            for vk, handler in layer.items():
                self.register(vk, handler, index)

    def register(self, vk: Vk, handler: JmkLayerKey, layer: int = 0):
        """Register a key handler to a layer"""
        if not isinstance(vk, Vk):
            raise TypeError("layer key must be a Vk")
        if not isinstance(handler, JmkLayerKey):
            raise TypeError("layer value must be a JmkLayerKey")
        if handler.layer is not None:
            raise ValueError("layer value must not have layer index")
        handler.state = self
        handler.layer = layer
        handler.vk = vk
        while len(self.layers) <= layer:
            self.layers.append({})
        self.layers[layer][vk] = handler

    def check_index(self, index: int):
        """Check if the index is valid"""
        if index < 1 or index >= len(self.layers):
            err = IndexError(f"layer index {index} out of range")
            logger.error(err)
            raise err

    def activate_layer(self, index: int):
        """Activate a layer"""
        logger.debug("activating layer %d", index)
        self.active_layers.add(index)

    def deactivate_layer(self, index: int):
        """Deactivate a layer"""
        logger.debug("deactivating layer %d", index)
        self.active_layers.remove(index)

    def find_route(self, vk: Vk) -> typing.Optional[JmkLayerKey]:
        """Find a route for a key"""
        i = len(self.layers) - 1
        while i >= 0:
            if i in self.active_layers and vk in self.layers[i]:
                return self.layers[i][vk]
            i -= 1

    def __call__(self, evt: JmkEvent):
        # route is to handle situation that a key is still held down after layer turned off
        route = None
        for vk, rt in self.routes.items():
            if vk == evt.vk:
                route = rt
            elif rt.other_key(evt):
                # key is intercepted by other key, most likely a TapHold
                return
        if route and not evt.pressed:
            self.routes.pop(evt.vk)
        elif not route:
            route = self.find_route(evt.vk)
            if route and evt.pressed:
                self.routes[evt.vk] = route
        if route:
            logger.debug("routing %s to %s", evt, route)
            return route(evt)
        self.next_handler(evt)
