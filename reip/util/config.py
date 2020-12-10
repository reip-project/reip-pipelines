import os


def setonce(file, func):
    if os.path.isfile(file):
        with open(file, 'r') as f:
            return f.read().rstrip('\n')
    value = str(func())
    with open(file, 'w') as f:
        f.write(value)
    return value
