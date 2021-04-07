import re


def pascal2snake(text):
    return re.sub(r'((?<=[a-z0-9])[A-Z]|(?!^)(?<!_)[A-Z](?=[a-z]))', r'_\1', text).lower()
def snake2pascal(text):
    return ''.join(x.title() for x in text.split('_'))

def snake2kebab(text):
    return text.replace('_', '-')
def kebab2snake(text):
    return text.replace('-', '_')

def pascal2camel(text):
    return text[0].lower() + text[1:] if text else ''
def camel2pascal(text):
    return text[0].upper() + text[1:] if text else ''

# for convenience
def pascal2kebab(text):
    return snake2kebab(pascal2snake(text))
def kebab2pascal(text):
    return snake2pascal(kebab2snake(text))


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
    return '{}{{}}{}'.format(start, end).format

red = _text_wrapper(C.FAIL)
blue = _text_wrapper(C.OKBLUE)
green = _text_wrapper(C.OKGREEN)
yellow = _text_wrapper(C.WARNING)
bold = _text_wrapper(C.BOLD)
underline = _text_wrapper(C.UNDERLINE)

t4 = ' '*4
t2 = ' '*2

def printasone(*txt, end='\n', **kw):
    print(' '.join(map(str, txt)) + end, end='', **kw)

# block text helpers

def indent(x, n=1, w=4, ch=' '):
    '''Indent text using spaces.'''
    return ''.join(ch * w * n + l for l in str(x).splitlines(keepends=True))

def tabindent(x, n=1, w=4):
    '''Indent text using tabs.'''
    return indent(space2tab(x, w=w), w=1, n=n, ch='\t')


def tab2space(text, w=4):
    return text.replace('\t', ' '*w)

def space2tab(text, w=4):
    return text.replace(' '*w, '\t')


def trim_indent(text, tw=2):
    '''Remove any common indent from text.

    Arguments:
        text (str): the text to re-indent.
        tw (int): the number of spaces per tab character.
    '''
    # normalize tabs to spaces
    lines = text.replace('\t', ' '*tw).splitlines()
    # get the min indent to norm to
    m = min([len(l) - len(l.lstrip()) for l in lines if l.strip()], default=0)
    # rejoin the text with the proper indent
    return '\n'.join([l[m:] for l in lines])


def striplines(text):
    '''Like text.strip() but it only removes lines with purely whitespace and
    leaves text indentation.'''
    lines = text.splitlines()
    i, j = 0, len(lines)
    while not lines[i].strip():
        i += 1
    while not lines[j-1].strip():
        j -= 1
    return '\n'.join(lines[i:j])

def strip_each_line(txt):
    return '\n'.join(l.rstrip() for l in txt.splitlines())

def comment(txt, ch='#', n=1, spaces=1):
    '''Apply prefix to each line. Defaults to python comments.'''
    ch, spaces = ch*n, " "*spaces
    return '\n'.join('{}{}{}'.format(ch, spaces, l) for l in txt.splitlines())


def block_text(*txts, n=20, ch='*', div=''):
    '''Create a block of text with a character border.'''
    return ch * n + '\n{}\n'.format(comment(b_(*txts, div=div), ch=ch)) + ch * n

def b_(*lines, div=''):
    '''Convert arguments to lines. Lines can be tuples (will be joined by a space.)'''
    div = '\n{}\n'.format(div) if div else '\n'
    return div.join(
        l_(*l) if isinstance(l, (list, tuple)) else str(l)
        for l in lines if l is not None)

def l_(*line, div=' '):
    '''Convert arguments to a space separated string'''
    return div.join(map(str, line))


def fw_(*line, w=20, right=False):
    '''As a fixed width string'''
    return f"{l_(*line):{'>' if right else '<'}{w}}"

def tbl(*rows, buffer=2):
    '''Format as a table. Calculates column widths.'''
    rows = [[str(c) for c in cs] for cs in rows]
    widths = [max((len(c) for c in cs), default=0) for cs in zip(*rows)]
    return b_(*([fw_(c, w=w + buffer-1) for c, w in zip(cs, widths)] for cs in rows))



# class Translate:
#     def __init__(self, *modes, max_jumps=4):
#         self.modes = {}
#         for mode in modes:
#             self.add(*mode, resolve=0)
#         self.resolve_missing(max_jumps)

#     def add(self, src, dest, translate, reverse=None, resolve=True):
#         for k1, k2, func in [(src, dest, translate), (dest, src, reverse)]:
#             if func is not None:
#                 if k1 not in self.modes:
#                     self.modes[k1] = {}
#                 self.modes[k1][k2] = self._wrap(func, k1, k2)
#         self.resolve_missing(resolve)
#         return self

#     def resolve_missing(self, max_jumps=3):
#         for i in range(int(max_jumps)):
#             missing = {k: set(self.modes) - set(d) - {k} for k, d in self.modes.items()}
#             if not any(missing.values()):
#                 break
#             for k, missg in missing.items():
#                 for m in missg:
#                     common = set(self.modes[k]) & set(self.modes[m])
#                     if common:
#                         common = common.pop()
#                         self.modes[k][m] = self.chain(k, common, m)
#                         self.modes[m][k] = self.chain(m, common, k)
#         return self

#     def __getattr__(self, key):
#         if '2' in key:
#             k1, k2 = key.split('2')
#             return self.modes[k1][k2]
#         raise KeyError(key)

#     def chain(self, *ks):
#         def inner(x):
#             for k1, k2 in zip(ks[:-1], ks[1:]):
#                 x = self.modes[k1][k2](x)
#             return x
#         return self._wrap(inner, *ks)

#     def _wrap(self, func, *ks):
#         func.__name__ = '2'.join(ks)
#         func.__qualname__ = '{}.{}'.format(self.__class__.__qualname__, func.__name__)
#         return func

# case = Translate(
#     ('pascal', 'snake', 
#      lambda text: re.sub(r'((?<=[a-z0-9])[A-Z]|(?!^)(?<!_)[A-Z](?=[a-z]))', r'_\1', text).lower(),
#      lambda text: ''.join(x.title() for x in text.split('_'))),
#     ('snake', 'kebab', 
#      lambda text: text.replace('_', '-'),
#      lambda text: ''.join(x.title() for x in text.split('_'))),
#     ('camel', 'pascal', 
#      lambda text: text[0].lower() + text[1:] if text else '',
#      lambda text: text[0].upper() + text[1:] if text else ''),
# )


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
