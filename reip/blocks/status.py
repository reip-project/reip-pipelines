import os
from .block import Block
from reip.utils.state import State


STATE = {}

class status(Block):
    '''Add a parameter to the status body.'''
    def __init__(self, state_dir='/tmp', name='state', **kw):
        super().__init__(**kw)
        self.state = State(os.path.join(state_dir, (name or 'state') + '.db'), {
            'status': {}, 'one_time_status': {},
        })


class add_status(status):
    pass


class get_status(status):
    pass
