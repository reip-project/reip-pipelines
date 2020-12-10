import os


def setonce(file, func):
    file = os.path.expanduser(file)
    if os.path.isfile(file):
        with open(file, 'r') as f:
            return f.read().rstrip('\n')
    value = str(func())
    os.makedirs(os.path.dirname(os.path.abspath(file)), exist_ok=True)
    with open(file, 'w') as f:
        f.write(value)
    return value
