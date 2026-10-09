"""Check generated HTML, local links, anchors and referenced assets offline."""
import argparse
from html.parser import HTMLParser
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

SITE = Path(__file__).resolve().parents[1]


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.ids = set()
        self.references = []
        self.labels = []
        self.errors = []
        self.headings = 0
        self.title = False
        self.language = False
        self.feed(html)
        if self.headings != 1:
            self.errors.append(f'Expected one H1, found {self.headings}')
        if not self.title or not self.language:
            self.errors.append('Missing page title or document language')

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        identifier = attrs.get('id')
        if identifier:
            if identifier in self.ids:
                self.errors.append(f'Duplicate ID: {identifier}')
            self.ids.add(identifier)
        if tag == 'h1':
            self.headings += 1
        if tag == 'title':
            self.title = True
        if tag == 'html':
            self.language = bool(attrs.get('lang'))
        if tag == 'img' and 'alt' not in attrs:
            self.errors.append('Image is missing alt text')
        for attr in ('href', 'src'):
            if attrs.get(attr):
                self.references.append(attrs[attr])
        for attr in ('aria-labelledby', 'aria-describedby'):
            self.labels.extend(attrs.get(attr, '').split())


def local_reference(base, url):
    parsed = urlsplit(url)
    if parsed.scheme or parsed.netloc:
        return None
    path = Path(unquote(parsed.path))
    if path.is_absolute() or '..' in path.parts:
        raise ValueError(f'Local URL must stay inside the published site: {url}')
    return (base.parent / path if parsed.path else base), unquote(parsed.fragment)


def check_site(root, pages=None):
    root = Path(root).resolve()
    names = sorted(pages if pages is not None else (p.name for p in root.glob('*.html')))
    if not names:
        raise ValueError('No HTML pages to check')
    parsed = {Path(name): Page((root / name).read_text(encoding='utf-8')) for name in names}
    errors = []
    assets = set()
    for name, page in parsed.items():
        errors.extend(f'{name}: {error}' for error in page.errors)
        errors.extend(f'{name}: missing label #{label}' for label in page.labels if label not in page.ids)
        for url in page.references:
            try:
                reference = local_reference(name, url)
            except ValueError as error:
                errors.append(f'{name}: {error}')
                continue
            if reference is None:
                continue
            path, anchor = reference
            if not (root / path).is_file():
                errors.append(f'{name}: missing file {url}')
            elif path.suffix == '.html':
                if path not in parsed:
                    errors.append(f'{name}: page not included in this build: {path}')
                elif anchor and anchor not in parsed[path].ids:
                    errors.append(f'{name}: missing anchor {url}')
            else:
                assets.add(path)
    # Include font and image dependencies referenced by local CSS.
    for path in list(assets):
        if path.suffix != '.css':
            continue
        for url in re.findall(r'url\([\s\'"]*([^\)\'"\s]+)', (root / path).read_text(encoding='utf-8')):
            reference = local_reference(path, url)
            if reference is not None:
                asset, _ = reference
                if not (root / asset).is_file():
                    errors.append(f'{path}: missing CSS asset {url}')
                assets.add(asset)
    if errors:
        raise ValueError('\n'.join(errors))
    return assets


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', nargs='?', type=Path, default=SITE)
    args = parser.parse_args()
    assets = check_site(args.directory)
    print(f'Links, anchors and image descriptions checked; {len(assets)} referenced assets.')
