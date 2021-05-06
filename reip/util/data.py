import json
import numpy as np


def jsondump(data, **kw):
    return json.dumps(data, cls=JSONDataEncoder, **kw)

class JSONDataEncoder(json.JSONEncoder):
    """ Special json encoder for numpy types """
    def default(self, obj):
        if isinstance(obj, np.generic):
            return obj.item()
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)

