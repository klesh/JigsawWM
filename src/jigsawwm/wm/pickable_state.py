"""PickableState is the base class of all stateful classes that are pickleable"""

class PickableState:
    """PickableState is the base class of all stateful classes that are pickleable"""
    def __getstate__(self):
        state = self.__dict__.copy()
        del state['config']
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
