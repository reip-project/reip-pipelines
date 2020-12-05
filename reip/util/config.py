import os


def setonce(file, func):
    if os.path.isfile(file):
        with open(file, 'r') as f:
            return f.read().rstrip('\n')
    value = func()
    with open(file, 'w') as f:
        f.write(str(value))
    return value
