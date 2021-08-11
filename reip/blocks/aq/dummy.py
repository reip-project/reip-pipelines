import random
import numpy as np
import reip


class DemoData(reip.Block):
    
    def __init__(self, **kw):
        super().__init__(**kw)

    def init(self):
        pass

    def process(self, meta=None):
        pc_vals = np.random.uniform(low=0, high=10000, size=(7,))
        pm_vals = np.random.uniform(low=0.5, high=10.0, size=(7,))
        return 'PC0.1,%i,PC0.3,%i,PC0.5,%i,PC1.0,%i,PC2.5,%i,PC5.0,%i,PC10,%i \
                ,PM0.1,%f,PM0.3,%f,PM0.5,%f,PM1.0,%f,PM2.5,%f,PM5.0,%f,PM10,%f,IPS-S-#########,abcdefg######=' \
                % (pc_vals[0], pc_vals[1], pc_vals[2], pc_vals[3], pc_vals[4], pc_vals[5], pc_vals[6], \
                    pm_vals[0], pm_vals[1], pm_vals[2], pm_vals[3], pm_vals[4], pm_vals[5], pm_vals[6]) \
                , meta


    def finish(self):
        pass
