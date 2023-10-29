import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from jigsawwm.w32.vk import *

logger = logging.getLogger(__name__)
# for executing callback function
handle_exc = None
executor = ThreadPoolExecutor(max_workers=100)


def execute(func, *args, **kwargs):
    """Execute a function in a thread pool and print the exception if any

    :param func: the function to execute
    :param args: the arguments to pass to the function
    :param kwargs: the keyword arguments to pass to the function
    """

    def wrapped():
        logger.debug("[JmkCore] executing %s", func)
        try:
            func()
        except Exception as e:
            if handle_exc:
                handle_exc(e)
            logger.exception(e)

    return executor.submit(wrapped, *args, **kwargs)


@dataclass
class JmkEvent:
    """A jmk event that contains the key/button, pressed state, system state(does it came from the OS) and extra data"""

    vk: Vk
    pressed: bool
    system: bool = False
    flags: int = 0
    extra: int = 0
    time: float = field(default_factory=time.time)

    __repr__ = (
        lambda self: f"JmkEvent({self.vk.name}, {'down' if self.pressed else 'up'}, {'sys' if self.system else 'sim'}, {self.flags}, {self.extra})"
    )


JmkHandler = typing.Callable[[JmkEvent], bool]


class JmkLayerKey(JmkHandler):
    """A key handler that can be used in a layer"""

    state: "JmkCore" = None
    layer: int = None
    vk: Vk = None

    __repr__ = (
        lambda self: f"{self.__class__.__name__}(layer={self.layer}, vk={self.vk.name})"
    )

    def other_key(self, evt: JmkEvent):
        pass


class JmkKey(JmkLayerKey):
    """The basic key handler in a layer

    :param kf: can be a Vk(map key to another key), a string, a list of Vk(map key to a combination) or a callable (a function to execute)
    :param swallow: whether to swallow the event, normally True
    """

    keys_or_func: typing.Union[typing.List[Vk], typing.Callable]
    swallow: bool

    def __init__(
        self,
        keys_or_func: typing.Union[Vk, str, typing.List[Vk], typing.Callable],
        swallow: bool = True,
    ):
        if isinstance(keys_or_func, str):
            keys_or_func = parse_combination(keys_or_func)
        if isinstance(keys_or_func, Vk):
            keys_or_func = [keys_or_func]
        self.keys_or_func = keys_or_func
        self.swallow = swallow

    def __call__(self, evt: JmkEvent) -> bool:
        if isinstance(self.keys_or_func, list):
            if evt.pressed:
                for key in self.keys_or_func:
                    self.state.next_handler(JmkEvent(key, evt.pressed))
            else:
                for key in reversed(self.keys_or_func):
                    self.state.next_handler(JmkEvent(key, evt.pressed))
        elif not evt.pressed:
            execute(self.keys_or_func)
        return self.swallow


class JmkTapHold(JmkLayerKey):
    """A advanced key handler that can be used in a layer

    :param tap: map the key to another key when tapped
    :param hold: map the key to another key when hold
    :param on_hold_down: a function to execute when hold down
    :param on_hold_up: a function to execute when hold up
    :param on_tap: a function to execute when tapped
    :param term: the term to determine whether it is a hold
    :param quick_tap_term: tap a key and then hold it down within this term will enter quick tap mode,
                        when activated, the tap key will be sent as long as the key is hold. It is useful for
                        dual function keys like using key A as the Alt key and you want to input a bunch of A
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
        if time.time() - self.pressed > self.term:
            self.hold_down()

    def hold_down(self):
        if self.held:
            # hold_down might be triggered multiple places
            return
        self.held = True
        logger.debug("%s hold down", self)
        if self.on_hold_down:
            logger.debug("%s on_hold_down", self)
            execute(self.on_hold_down)
        if self.hold:
            if isinstance(self.hold, Vk):
                evt = JmkEvent(self.hold, True)
                logger.debug("%s %s down >>>", self, evt)
                self.state.next_handler(evt)
            else:
                self.state.activate_layer(self.hold)
        self.flush_resend()

    def hold_up(self):
        self.pressed = 0
        self.held = False
        self.other_pressed_keys.clear()
        logger.debug("%s hold up", self)
        if self.on_hold_up:
            logger.debug("%s on_hold_up", self)
            execute(self.on_hold_up)
        if self.hold:
            if isinstance(self.hold, Vk):
                evt = JmkEvent(self.hold, False)
                logger.debug("%s %s up >>>", self, evt)
                self.state.next_handler(evt)
            else:
                self.state.deactivate_layer(self.hold)

    def tap_down_up(self):
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
            execute(self.on_tap)
        self.last_tapped_at = time.time()
        self.flush_resend()

    def other_key(self, evt: JmkEvent) -> bool:
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
        if self.resend:
            for evt in self.resend:
                logger.debug("%s resend %s >>>", self, evt)
                self.state(evt)
        self.resend.clear()

    def __call__(self, evt: JmkEvent) -> bool:
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
            else:
                self.check_hold()
        else:
            # reset state
            self.check_hold()
            if self.held:
                self.hold_up()
            else:
                self.tap_down_up()
        return True


JmkLayer = typing.Dict[Vk, JmkHandler]


class JmkCore(JmkHandler):
    """JmkCore is the core of JmkHandler, it handles the key events and dispatches them to the registered handlers.

    :param next_handler: the next handler to dispatch the event to
    :param layers: the layers
    """

    next_handler: JmkHandler
    layers: typing.List[JmkLayer]
    active_layers: typing.Set[int]
    routes: JmkLayer

    def __init__(
        self,
        next_handler: JmkHandler,
        layers: typing.List[JmkLayer] = None,
    ):
        if len(layers) < 1:
            raise ValueError("layers must have at least one layer")
        self.layers = [{}]
        for index, layer in enumerate(layers):
            if not isinstance(layer, dict):
                raise TypeError("layer must be a dict")
            for vk, handler in layer.items():
                self.register(vk, handler, index)
        self.next_handler = next_handler
        self.active_layers = {0}
        self.routes = {}

    def register(self, vk: Vk, handler: JmkLayerKey, layer: int = 0):
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
        if index < 1 or index >= len(self.layers):
            err = IndexError(f"layer index {index} out of range")
            logger.error(err)
            raise err

    def activate_layer(self, index: int):
        # self.check_index(index)
        logger.debug(f"activating layer {index}")
        self.active_layers.add(index)

    def deactivate_layer(self, index: int):
        # self.check_index(index)
        logger.debug(f"deactivating layer {index}")
        self.active_layers.remove(index)

    def find_route(self, vk: Vk) -> typing.Optional[JmkLayerKey]:
        i = len(self.layers) - 1
        while i >= 0:
            if i in self.active_layers and vk in self.layers[i]:
                return self.layers[i][vk]
            i -= 1

    def __call__(self, evt: JmkEvent) -> bool:
        # route is to handle situation that a key is still held down after layer turned off
        route = None
        for vk, rt in self.routes.items():
            if vk == evt.vk:
                route = rt
            elif rt.other_key(evt):
                # key is intercepted by other key, most likely a TapHold
                return True
        if route and not evt.pressed:
            self.routes.pop(evt.vk)
        elif not route:
            route = self.find_route(evt.vk)
            if route and evt.pressed:
                self.routes[evt.vk] = route
        if route:
            logger.debug("routing %s to %s", evt, route)
            return route(evt)
        return self.next_handler(evt)
