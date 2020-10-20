import os
import inspect
from . import text


def check_block(block, match='', *a):
    '''Only print out only blocks that match the query text. For debugging specific subclasses.'''
    if (not match or match.lower() in block.__class__.__name__.lower()
            or match.lower() in getattr(block, 'name', '').lower()):
        text.printasone(text.block_text(str(block), text.l_(*a)), flush=True)


def block_stack(message=None, fn=None, offset=0):
    stack = inspect.stack()
    f = stack[offset+1]
    return text.block_text(
        message,
        text.blue(text.l_(f.function, f.lineno, f.filename)), '',
        text.tbl(*(
            (f.function, f.lineno, f.filename, f'>>> {f.code_context[0].strip()}')
            for f in stack[offset+2:]
            if not fn or fn in f.filename
        )), ch=text.yellow('*')
    )

def print_stack(message=None, *a, offset=0, **kw):
    text.printasone(block_stack(message, *a, offset=offset + 1, **kw), flush=True)


def short_stack(match=None, file=False, sep=' << ', n=None):
    '''Print out a compressed view of the stack.'''
    return sep.join(
        (f'{f.function} ({os.path.basename(f.filename)}:{f.lineno})'
         if file else f.function)
        for f in inspect.stack()[1:][:n]
        if not match or match in f.filename
    )
