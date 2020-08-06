import inspect
from . import text


def check_block(block, match='', *a):
    '''Only print out only blocks that match the query text. For debugging specific subclasses.'''
    if (not match or match.lower() in block.__class__.__name__.lower()
            or match.lower() in getattr(block, 'name', '').lower()):
        print(text.block_text(str(block), text.l_(*a)), flush=True)


def print_stack(message=None, fn=None):
    stack = inspect.stack()
    f = stack[1]
    print(text.block_text(
        message,
        text.blue(text.l_(f.function, f.lineno, f.filename)), '',
        text.tbl(*(
            (f.function, f.lineno, f.filename, f'>>> {f.code_context[0].strip()}')
            for f in stack[2:]
            if not fn or fn in f.filename
        )), ch=text.yellow('*')
    ))

def short_stack(filename=True, sep=' << '):
    '''Print out a compressed view of the stack.'''
    return sep.join(
        (f'{f.function} ({os.path.basename(filename)}:{f.lineno})'
         if filename else f.function)
        for f in inspect.stack()[1:]
        if not fn or fn in f.filename
    )
