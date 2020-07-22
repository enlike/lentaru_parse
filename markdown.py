import re
from urllib.parse import urlparse, urljoin

from bs4 import BeautifulSoup, NavigableString

CONVERT_HEADING_RE = re.compile(r'convert_h(\d+)')
LINE_BEGINNING_RE = re.compile(r'^', re.MULTILINE)
WHITESPACE_RE = re.compile(r'[\r\n\s\t ]+')
FRAGMENT_ID = '__MARKDOWN_WRAPPER__'
wrapped = f'<div id="{FRAGMENT_ID}">%s</div>'

# Heading styles
ATX = 'atx'
ATX_CLOSED = 'atx_closed'
UNDERLINED = 'underlined'
SETEXT = UNDERLINED

MAX_LEN_TEXT = 80


def escape(text):
    if not text:
        return ''
    return text.replace('_', r'\_')


def _todict(obj):
    return dict((k, getattr(obj, k)) for k in dir(obj) if not k.startswith('_'))


class MarkdownConverter:
    """
    Markdown tags: https://github.com/adam-p/markdown-here/wiki/Markdown-Cheatsheet
    :methods - convert_(TYPE) depends on type what to handle
    """

    class DefaultOptions:
        strip = None
        convert = None
        autolinks = True
        heading_style = UNDERLINED
        bullets = '*+-'  # An iterable of bullet types.
        base_url = None

    class Options(DefaultOptions):
        pass

    def __init__(self, **options):
        # Create an options dictionary. Use DefaultOptions as a base so that
        # it doesn't have to be extended.
        self.options = _todict(self.DefaultOptions)
        self.options.update(_todict(self.Options))
        self.options.update(options)
        if self.options['strip'] is not None and self.options['convert'] is not None:
            raise ValueError('You may specify either tags to strip or tags to'
                             ' convert, but not both.')

    def convert(self, html):
        # We want to take advantage of the html5 parsing, but we don't actually
        # want a full document. Therefore, we'll mark our fragment with an id,
        # create the document, and extract the element with the id.
        html = wrapped % html
        soup = BeautifulSoup(html, 'html.parser')
        return self.process_tag(soup.find(id=FRAGMENT_ID), children_only=True)

    def process_tag(self, node, children_only=False):
        text = ''
        to_italic = {'b-label__credits', 'credits', }
        question = {'question'}
        box_quote = {'box-quote__text'}

        # Convert the children first
        for el in node.children:
            if isinstance(el, NavigableString):
                text += self.process_text(str(el))
            else:
                text += self.process_tag(el)

        if not children_only:
            convert_fn = getattr(self, f'convert_{node.name}', None)
            if convert_fn and self.should_convert_tag(node.name):
                text = convert_fn(node, text)
            node_attrs = node.attrs.get('class', None)
            if node_attrs:
                if set(node_attrs).issubset(to_italic):
                    text = f'\n{self.convert_i(None, text.strip())}\n\n'
                if set(node_attrs).issubset(question):
                    text = self.convert_hn(4, None, text)
                if set(node_attrs).issubset(box_quote):
                    text = self.convert_blockquote(text)
        return text

    def process_text(self, text):
        return escape(WHITESPACE_RE.sub(' ', text or ''))

    def __getattr__(self, attr):
        # Handle headings
        m = CONVERT_HEADING_RE.match(attr)
        if m:
            n = int(m.group(1))

            def convert_tag(el, text):
                return self.convert_hn(n, el, text)

            convert_tag.__name__ = 'convert_h%s' % n
            setattr(self, convert_tag.__name__, convert_tag)
            return convert_tag

        raise AttributeError(attr)

    def should_convert_tag(self, tag):
        tag = tag.lower()
        strip = self.options['strip']
        convert = self.options['convert']
        if strip is not None:
            return tag not in strip
        elif convert is not None:
            return tag in convert
        else:
            return True

    def indent(self, text, level):
        return LINE_BEGINNING_RE.sub('\t' * level, text) if text else ''

    def underline(self, text, pad_char):
        text = (text or '').rstrip()
        return f'{text if text else ""}\n{pad_char * len(text)}\n\n'

    def convert_time(self, el, text):
        return f'{text}\n\n'

    def convert_a(self, el, text):
        href = el.get('href')
        title = el.get('title')
        if self.options['autolinks'] and text == href and not title:
            return f'<{href}>'
        title_part = f' "%s"' % title.replace('"', r'\"') if title else ''
        href = self.full_href(href)
        return f'[{text or ""}]({href if href else ""}{title_part})\n'

    def full_href(self, href):
        """Получить полный путь для тэгов, где нет base_url"""
        scheme, host, path, params, query, fragment = urlparse(href)
        return href if not scheme and host else urljoin(self.options['base_url'], href)

    def convert_b(self, el, text):
        return self.convert_strong(el, text)

    def convert_blockquote(self, text):
        return f'> {text}'

    def convert_br(self, el=None, text=None):
        return '  \n'

    def convert_em(self, el, text):
        return f'*{text if text else ""}*'

    def convert_hn(self, n, el, text):
        style = self.options['heading_style']
        text = text.rstrip()
        if style == UNDERLINED and n <= 2:
            line = '=' if n == 1 else '-'
            return self.underline(text, line)
        hashes = '#' * n
        if style == ATX_CLOSED:
            return f'{hashes} {text} {hashes}\n\n'
        return f'{hashes} {text}\n\n'

    def convert_i(self, el, text):
        return self.convert_em(el, text)

    def convert_list(self, el, text):
        nested = False
        while el:
            if el.name == 'li':
                nested = True
                break
            el = el.parent
        if nested:
            text = '\n' + self.indent(text, 1)
        return '\n' + text + '\n'

    convert_ul = convert_list
    convert_ol = convert_list

    def convert_li(self, el, text):
        parent = el.parent
        if parent is not None and parent.name == 'ol':
            bullet = f'{parent.index(el) + 1}.'
        else:
            depth = -1
            while el:
                if el.name == 'ul':
                    depth += 1
                el = el.parent
            bullets = self.options['bullets']
            bullet = bullets[depth % len(bullets)]
        return f'{bullet} {text}\n'

    def convert_p(self, el, text):
        return f'{text if text else ""}\n\n'

    def convert_strong(self, el, text):
        return f'**{text if text else ""}**'

    def convert_img(self, el, text=None):
        alt = el.attrs.get('alt', '')
        src = el.attrs.get('src', '')
        title = el.attrs.get('title', '')
        title_part = ' "%s"' % title.replace('"', r'\"') if title else ''
        return f'![{alt}]({src}{title_part})\n\n'


def markdownify(html, **options):
    return MarkdownConverter(**options).convert(html)
