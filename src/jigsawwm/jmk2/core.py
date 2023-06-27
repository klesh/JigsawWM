import logging
import time
import typing
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass

from jigsawwm.w32.sendinput import send_combination
from jigsawwm.w32.vk import *

logger = logging.getLogger(__name__)
# for executing callback function
executor = ThreadPoolExecutor(max_workers=100)


def execute(func):
    return executor.submit(func)


@dataclass
class JmkEvent:
    vk: Vk
    pressed: bool
    system: bool = False

    __repr__ = (
        lambda self: f"JmkEvent({self.vk.name}, {'down' if self.pressed else 'up'}, {'sys' if self.system else 'sim'})"
    )


JmkHandler = typing.Callable[[JmkEvent], bool]


class JmkLayerKey(JmkHandler):
    state: "JmkCore" = None
    layer: int = None
    vk: Vk = None

    __repr__ = lambda self: f"JmkLayerKey(layer={self.layer}, vk={self.vk.name})"

    def other_key(self, evt: JmkEvent):
        pass


class JmkKey(JmkLayerKey):
    func: callable = None
    key: Vk = None
    swallow: bool

    def __init__(self, kf, swallow: bool = True):
        if isinstance(kf, str):
            kf = parse_combination(kf)
        if isinstance(kf, list):
            kf = lambda: send_combination(kf)
        if callable(kf):
            self.func = kf
        else:
            self.key = kf
        self.swallow = swallow

    def __call__(self, evt: JmkEvent) -> bool:
        if self.func and not evt.pressed:
            logger.debug("[JmkKey func] %s >>> ")
            execute(self.func)
            return self.swallow
        elif self.key:
            logger.debug("[JmkKey key] %s >>>")
            return self.state.next_handler(JmkEvent(self.key, evt.pressed))


class JmkTapHold(JmkLayerKey):
    tap: typing.Optional[Vk] = None
    hold: typing.Optional[typing.Union[Vk, str]] = None
    on_hold_down: typing.Optional[typing.Callable] = None
    on_hold_up: typing.Optional[typing.Callable] = None
    on_tap: typing.Optional[typing.Callable] = None
    term: float = 0.2
    pressed: int = 0
    held: bool = False
    quick_tap_term: float
    last_tapped_at: float = 0
    quick_tap: bool = False
    timer: Future = None
    tapped_down: bool = False

    def __init__(
        self,
        tap: Vk = None,
        hold: Vk = None,
        on_hold_down: callable = None,
        on_hold_up: callable = None,
        on_tap: callable = None,
        term: float = 0.2,
        quick_tap_term: float = 0.12,
    ):
        self.tap = tap
        self.hold = hold
        self.on_hold_down = on_hold_down
        self.on_hold_up = on_hold_up
        self.on_tap = on_tap
        self.term = term
        self.quick_tap_term = quick_tap_term
        self.timer = None
        # check empty

    def holddown(self):
        self.held = True
        if self.on_hold_down:
            logger.debug("[JmkTapHold hold] on_hold_down")
            execute(self.on_hold_down)
        if self.hold:
            if isinstance(self.hold, Vk):
                evt = JmkEvent(self.hold, True)
                logger.debug("[JmkTapHold hold] %s >>>", evt)
                self.state.next_handler(evt)
            else:
                self.state.activate_layer(self.hold)

    def tapdown(self):
        if self.tapped_down:
            return
        if self.on_tap:
            logger.debug("[JmkTapHold tap] on_tap")
            execute(self.on_tap)
        if self.tap:
            evt_down = JmkEvent(self.tap, True)
            logger.debug("[JmkTapHold tap] %s >>>", evt_down)
            self.state.next_handler(evt_down)
        self.last_tapped_at = time.time()
        self.tapped_down = True

    def holding_timer(self):
        time.sleep(self.term)
        logger.debug("[JmkTapHold holding_timer] waken")
        self.timer = None
        if self.pressed and time.time() - self.pressed > self.term:
            self.holddown()

    def other_key(self, evt: JmkEvent):
        if not self.timer or not self.pressed:
            return
        logger.debug("[JmkTapHold other_key] %s >>>", evt)
        self.timer.cancel()
        self.timer = None
        self.tapdown()
        self.pressed = 0  # stop the timer

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
            evt = JmkEvent(evt.vk, evt.pressed)
            logger.debug("[JmkTapHold quicktap] %s >>>", evt)
            return self.state.next_handler(evt)
        # tap hold
        if evt.pressed:
            if not self.pressed:
                self.pressed = time.time()
                self.timer = execute(self.holding_timer)
        else:
            self.pressed = 0
            if self.held:  # hold up
                self.held = False
                if self.on_hold_up:
                    execute(self.on_hold_up)
                if self.hold:
                    if isinstance(self.hold, Vk):
                        evt = JmkEvent(self.hold, False)
                        logger.debug("[JmkTapHold hold] %s >>>", evt)
                        self.state.next_handler(evt)
                    else:
                        self.state.deactivate_layer(self.hold)
            else:  # tap
                self.tapdown()
                if self.tap:
                    self.tapped_down = False
                    evt_up = JmkEvent(self.tap, False)
                    logger.debug("[JmkTapHold tap] %s >>>", evt_up)
                    self.state.next_handler(evt_up)
        return True


JmkLayer = typing.Dict[Vk, JmkHandler]


class JmkCore(JmkHandler):
    next_handler: JmkHandler
    layers: typing.List[JmkLayer]
    active_layers: typing.Set[int]
    routes: JmkLayer

    def __init__(
        self,
        next_handler: JmkHandler,
        layers: typing.List[JmkLayer],
    ):
        if len(layers) < 1:
            raise ValueError("layers must have at least one layer")
        for index, layer in enumerate(layers):
            if not isinstance(layer, dict):
                raise TypeError("layer must be a dict")
            for vk, handler in layer.items():
                if not isinstance(vk, Vk):
                    raise TypeError("layer key must be a Vk")
                if not callable(handler):
                    raise TypeError("layer value must be a JmkHandler")
                if handler.layer is not None:
                    raise ValueError("layer value must not have layer index")
                handler.state = self
                handler.layer = index
                handler.vk = vk
        self.next_handler = next_handler
        self.layers = layers
        self.active_layers = set()
        self.routes = {}

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

    def get_active_layer(self) -> JmkLayer:
        i = len(self.layers) - 1
        while i > 0:
            if i in self.active_layers:
                return self.layers[i]
            i -= 1
        return self.layers[0]

    def __call__(self, evt: JmkEvent) -> bool:
        # route is to prevent key is still held down after layer switch
        route = None
        for vk, rt in self.routes.items():
            if vk == evt.vk:
                route = rt
            else:
                rt.other_key(evt)
        if route and not evt.pressed:
            self.routes.pop(evt.vk)
        elif not route:
            layer = self.get_active_layer()
            route = layer.get(evt.vk)
            if route and evt.pressed:
                logger.debug("found route %s for %s", route, evt)
                self.routes[evt.vk] = route
        if route:
            logger.debug("routing %s to %s", evt, route)
            return route(evt)
        return self.next_handler(evt)
