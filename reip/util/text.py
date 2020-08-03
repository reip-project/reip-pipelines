
# Text formatting

class C:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def _text_wrapper(start, end=C.ENDC):
    return f'{start}{{}}{end}'.format

red = _text_wrapper(C.FAIL)
blue = _text_wrapper(C.OKBLUE)
green = _text_wrapper(C.OKGREEN)
yellow = _text_wrapper(C.WARNING)
bold = _text_wrapper(C.BOLD)
underline = _text_wrapper(C.UNDERLINE)

t4 = ' '*4
t2 = ' '*2

# block text helpers

def indent(x, w=4, n=1, ch=' '):
    '''Indent text using spaces.'''
    return ''.join(' ' * w * n + l for l in str(x).splitlines(keepends=True))

def tabindent(x, n=1):
    return indent(x, w=1, n=n, ch='\t')

def comment(txt, ch='#', n=1, spaces=1):
    '''Apply prefix to each line. Defaults to python comments.'''
    ch, spaces = ch*n, " "*spaces
    return '\n'.join(f'{ch}{spaces}{l}' for l in txt.splitlines())


def block_text(*txts, n=20, ch='*'):
    '''Create a block of text with a character border.'''
    return ch * n + f'\n{comment(b_(*txts), ch=ch)}\n' + ch * n

def b_(*lines):
    '''Convert arguments to lines. Lines can be tuples (will be joined by a space.)'''
    return '\n'.join(
        l_(*l) if isinstance(l, (list, tuple)) else str(l)
        for l in lines if l is not None)

def l_(*line):
    '''Convert arguments to a space separated string'''
    return ' '.join(map(str, line))


def fw_(*line, w=20):
    '''As a fixed width string'''
    return f'{l_(*line):<{w}}'

def tbl(*rows, buffer=2):
    rows = [[str(c) for c in cs] for cs in rows]
    widths = [max((len(c) for c in cs), default=0) for cs in zip(*rows)]
    return b_(*([fw_(c, w=w + buffer) for c, w in zip(cs, widths)] for cs in rows ))


if __name__ == '__main__':
    print(red('this should be red'))
    print(blue('this should be blue'))
    print(green('this should be green'))
    print(yellow('this should be yellow'))
    print(underline('this should be underline'))

    print()
    print(b_(
        ('hi', blue('im blue'), 56),
        'okay',
        '',
        red('bloop'),
    ))

    print()
    print(block_text(
        l_('hiiii', red('okay')),
        bold('well'),
        green('alright'),
    ))
