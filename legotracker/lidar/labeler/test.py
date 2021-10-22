import labeler_module
import numpy as np


if __name__ == '__main__':
    print("Hi")
    print(labeler_module.in_bounds_func(0, 1, 100, 100))

    mask = np.zeros((10, 11), dtype=np.uint32)
    mask[:3, :3] = 10
    mask[7:, 7:] = 15
    mask[5, :] = 10

    data = np.zeros((10, 10), dtype=np.double)
    data[:, :5] = 1
    data[:, 5:] = 10

    print(mask, "\n")
    print(data, "\n")

    labeler_module.label(mask, data, 5)

    print(mask, "\n")
    print(data, "\n")

