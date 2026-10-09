"""Keep short Russian function words with the following word in visible copy."""
from html import escape, unescape
from html.parser import HTMLParser
import re

SHORT_WORDS = (
    'а', 'и', 'но', 'да', 'или', 'в', 'во', 'к', 'ко', 'с', 'со', 'у',
    'о', 'об', 'обо', 'от', 'ото', 'до', 'из', 'изо', 'за', 'по', 'под',
    'над', 'на', 'при', 'про', 'для', 'без', 'не', 'ни',
)
WORD_SPACE = re.compile(
    r'(?<![\w-])(?P<word>' + '|'.join(SHORT_WORDS)
    + r')(?P<space>[ \t\r\n]+)(?=[«„“"\'(\[]*\w)', re.IGNORECASE,
)
NBSP = '\u00a0'


def bind_short_words(text):
    return WORD_SPACE.sub(lambda match: match['word'] + NBSP, text)


class Typographer(HTMLParser):
    """Preserve markup and attributes; process text across inline elements."""
    INLINE = {'a', 'span', 'strong', 'em', 'b', 'i', 'small', 'mark', 'abbr', 'sup', 'sub', 's', 'u'}
    EXCLUDED = {'script', 'style', 'pre', 'code', 'textarea', 'svg', 'math'}

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.output = []
        self.flow = []
        self.in_body = False
        self.excluded = 0

    def flush(self):
        text = ''.join(value for _, value in self.flow)
        edits = {}
        for match in WORD_SPACE.finditer(text):
            start, end = match.span('space')
            edits.update((index, NBSP if index == start else '') for index in range(start, end))
        offset = 0
        for index, value in self.flow:
            result = ''.join(edits.get(offset + i, char) for i, char in enumerate(value))
            self.output[index] = escape(result, quote=False)
            offset += len(value)
        self.flow.clear()

    def handle_starttag(self, tag, attrs):
        if tag not in self.INLINE:
            self.flush()
        self.output.append(self.get_starttag_text())
        if tag == 'body':
            self.in_body = True
        if tag in self.EXCLUDED:
            self.excluded += 1

    def handle_endtag(self, tag):
        if tag not in self.INLINE:
            self.flush()
        self.output.append(f'</{tag}>')
        if tag == 'body':
            self.in_body = False
        if tag in self.EXCLUDED:
            self.excluded -= 1

    def handle_startendtag(self, tag, attrs):
        self.flush()
        self.output.append(self.get_starttag_text())

    def handle_data(self, data):
        if self.in_body and not self.excluded:
            self.flow.append((len(self.output), data))
        self.output.append(data)

    def handle_entityref(self, name):
        self.entity(f'&{name};')

    def handle_charref(self, name):
        self.entity(f'&#{name};')

    def entity(self, source):
        if self.in_body and not self.excluded:
            self.handle_data(unescape(source))
        else:
            self.output.append(source)

    def handle_decl(self, decl):
        self.output.append(f'<!{decl}>')

    def handle_comment(self, data):
        self.output.append(f'<!--{data}-->')


def typography_html(source):
    parser = Typographer()
    parser.feed(source)
    parser.close()
    parser.flush()
    return ''.join(parser.output)
