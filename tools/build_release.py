"""Create a clean local dist/ directory; never publish or contact a host."""
from pathlib import Path
import argparse
import shutil
import tempfile

from build_projects import SITE, PUBLIC_URL, render_site
from check_site import check_site

MARKER = '.portfolio-build'
MARKER_CONTENT = 'Generated portfolio release. Rebuild with tools/build_release.py.\n'


def build_release(include_drafts=False):
    destination = SITE / 'dist'
    if destination.exists() and (
        destination.is_symlink() or not (destination / MARKER).is_file()
        or (destination / MARKER).read_text(encoding='utf-8') != MARKER_CONTENT
    ):
        raise ValueError('dist/ contains files not owned by this builder; choose a different location for them first.')
    pages = render_site(include_drafts=include_drafts)
    # Stage and validate before replacing an earlier generated release.
    with tempfile.TemporaryDirectory(prefix='.dist-build-', dir=SITE) as temporary:
        stage = Path(temporary)
        for name, html in pages.items():
            (stage / name).write_text(html, encoding='utf-8')
        # Resolve against the source assets without copying documentation or demos.
        for name in ('styles.css', 'script.js', 'gallery.js'):
            shutil.copy2(SITE / name, stage / name)
        (stage / 'assets').symlink_to(SITE / 'assets', target_is_directory=True)
        assets = check_site(stage, pages)
        (stage / 'assets').unlink()
        for relative in assets | {Path('assets/fonts/LICENSE.txt')}:
            if relative.parts[0] == 'assets' and len(relative.parts) > 1 and relative.parts[1] == 'demo':
                raise ValueError(f'Demo artwork cannot be included in the public site: {relative}')
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SITE / relative, target)
        check_site(stage, pages)
        if include_drafts:
            (stage / 'robots.txt').write_text('User-agent: *\nDisallow: /\n', encoding='utf-8')
        else:
            urls = ''.join(f'<url><loc>{PUBLIC_URL}{"" if name == "index.html" else name}</loc></url>' for name in pages)
            (stage / 'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?>\n'
                f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n', encoding='utf-8')
            (stage / 'robots.txt').write_text(f'User-agent: *\nAllow: /\nSitemap: {PUBLIC_URL}sitemap.xml\n', encoding='utf-8')
        (stage / MARKER).write_text(MARKER_CONTENT, encoding='utf-8')
        if destination.exists():
            shutil.rmtree(destination)
        stage.rename(destination)
    print(f'Prepared {len(pages)} pages in {destination}; nothing has been published.')
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--include-drafts', action='store_true', help='Preview only; never deploy this output.')
    build_release(**vars(parser.parse_args()))
