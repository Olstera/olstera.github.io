"""Render the homepage, catalogue and cases from shared templates and JSON.

Uses only the Python standard library. Use --preview-blocks to also rebuild
the unlisted, noindex block library. Generated HTML needs no browser-side build.
"""
import argparse
from html import escape
import json
from pathlib import Path
import re
from string import Template
from urllib.parse import urlsplit

from typography import bind_short_words, typography_html

SITE = Path(__file__).resolve().parents[1]
BLOCK_KINDS = {'text', 'image', 'image-wide', 'image-pair', 'mobile-gallery'}
COVER_FORMATS = {'pinkly', 'square', 'portrait', 'landscape'}
PUBLIC_URL = 'https://olstera.github.io/'


def required_text(item, key):
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'Missing or empty text: {key}')
    return value


def template(template_name, **values):
    source = (SITE / 'templates' / f'{template_name}.html').read_text(encoding='utf-8')
    return Template(source).substitute(values).strip()


def image_attributes(item, eager=False):
    """Validate local artwork once for listing covers and case media."""
    src = required_text(item, 'src')
    path = Path(src)
    if (urlsplit(src).scheme or '?' in src or '#' in src or path.is_absolute()
            or '..' in path.parts or path.parts[0] != 'assets'
            or not (SITE / path).resolve().is_relative_to((SITE / 'assets').resolve())
            or not (SITE / path).is_file()):
        raise ValueError(f'Invalid local image: {src}')
    if path.suffix.lower() not in {'.jpg', '.jpeg', '.png', '.webp', '.avif', '.gif', '.svg'}:
        raise ValueError(f'Unsupported image format: {src}')
    alt = required_text(item, 'alt')
    attributes = f'src="{escape(src, quote=True)}" alt="{escape(alt, quote=True)}"'
    for key in ('width', 'height'):
        if key in item:
            value = item[key]
            if type(value) is not int or value <= 0:
                raise ValueError(f'Invalid {key}: {src}')
            attributes += f' {key}="{value}"'
    return attributes + (' fetchpriority="high"' if eager else ' loading="lazy"')


def render_image(item, project_name, block_title, eager=False):
    """Use the same natural-height media and lightbox trigger in every layout."""
    attributes = image_attributes(item, eager)
    theme = ' case-image--pinkly' if item.get('theme') == 'pinkly' else ''
    caption = escape(bind_short_words(f"{project_name} — {item.get('caption') or block_title}"))
    src = escape(item['src'], quote=True)
    note = f'<figcaption class="case-media-caption">{escape(item["caption"])}</figcaption>' if item.get('caption') else ''
    return f'''<figure class="case-media">
      <a class="case-image-link" href="{src}" data-gallery data-caption="{caption}" aria-label="Открыть изображение: {caption}">
        <span class="case-image{theme}"><img {attributes}></span>
        <span class="case-image-hint text-link" aria-hidden="true">Увеличить изображение ↗</span>
      </a>{note}
    </figure>'''


def render_blocks(project):
    output = []
    image_seen = False
    for index, block in enumerate(project['blocks'], 1):
        kind = block['kind']
        if kind not in BLOCK_KINDS:
            raise ValueError(f'Unknown block kind: {kind}')
        title = escape(required_text(block, 'title'))
        heading_id = f'case-block-{index}-title'
        label = f'<div class="case-block-heading"><span class="catalog-index">{index:02d} /</span><h2 id="{heading_id}">{title}</h2></div>'
        if kind in ('image', 'image-wide'):
            content = render_image(block, project['name'], block['title'], eager=not image_seen)
            image_seen = True
        elif kind in ('image-pair', 'mobile-gallery'):
            items = block['images']
            if not isinstance(items, list) or (kind == 'image-pair' and len(items) != 2) or (kind == 'mobile-gallery' and len(items) < 2):
                raise ValueError(f'{kind}: expected two images or a gallery with at least two images.')
            cards = []
            for item in items:
                cards.append(render_image(item, project['name'], block['title'], eager=not image_seen))
                image_seen = True
            mobile = kind == 'mobile-gallery'
            css = ' case-image-grid--mobile' if mobile else ''
            region = f' tabindex="0" role="region" aria-labelledby="{heading_id}"' if mobile else ''
            hint = '<p class="case-gallery-hint">Листайте экраны в сторону →</p>' if mobile else ''
            content = f'<div class="case-image-group"><div class="case-image-grid{css}"{region}>{"".join(cards)}</div>{hint}</div>'
        else:
            paragraphs = required_text(block, 'text').split('\n\n')
            content = '<div class="case-copy">' + ''.join(f'<p class="case-body">{escape(p.strip())}</p>' for p in paragraphs if p.strip()) + '</div>'
        output.append(f'<section class="case-block case-block--{kind}" aria-labelledby="{heading_id}">{label}{content}</section>')
    return '\n'.join(output)


def read_content(name):
    return json.loads((SITE / 'content' / f'{name}.json').read_text(encoding='utf-8'))


def load_projects(include_drafts=False):
    projects = read_content('projects')
    if not isinstance(projects, list) or not projects:
        raise ValueError('At least one project is required.')
    for project in projects:
        if not isinstance(project, dict) or type(project.get('published', False)) is not bool:
            raise ValueError('Each project must be an object with a boolean published field.')
    # A newly created, incomplete draft must never break the public build.
    projects = [p for p in projects if include_drafts or p.get('published', False)]
    if not projects:
        raise ValueError('Keep at least one published project before deploying.')
    slugs = [required_text(p, 'slug') for p in projects]
    if len(set(slugs)) != len(slugs) or any(not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', s) for s in slugs):
        raise ValueError('Project slugs must be unique lowercase URL segments.')
    for project in projects:
        for key in ('name', 'description', 'type', 'role', 'intro'):
            required_text(project, key)
        if not isinstance(project.get('blocks'), list) or not project['blocks']:
            raise ValueError(f'{project["slug"]}: at least one content block is required.')
        if type(project.get('featured', False)) is not bool:
            raise ValueError(f'{project["slug"]}: featured must be true or false.')
        cover = project.get('cover')
        if not isinstance(cover, dict) or cover.get('format') not in COVER_FORMATS:
            raise ValueError(f'{project["slug"]}: invalid cover format.')
        image_attributes(cover)
    return projects


def site_context():
    profile = read_content('site')
    for key in ('owner_surname', 'owner_first_name', 'telegram_url', 'instagram_url', 'email'):
        required_text(profile, key)
    for key in ('telegram_url', 'instagram_url'):
        url = urlsplit(profile[key])
        if url.scheme != 'https' or not url.netloc:
            raise ValueError(f'{key}: expected an HTTPS URL.')
    if not re.fullmatch(r'[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+', profile['email']):
        raise ValueError('Invalid contact email.')
    if type(profile.get('copyright_year')) is not int or profile['copyright_year'] < 2000:
        raise ValueError('Invalid copyright year.')
    profile['owner_name'] = f'{profile["owner_surname"]} {profile["owner_first_name"]}'
    return {key: escape(str(value), quote=True) for key, value in profile.items()}


def render_shell(profile, page, title, description, preview=False, filename=None):
    home = page == 'index'
    archive = page == 'projects'
    home_href = '#intro' if home else 'index.html#intro'
    links = [
        (home_href, 'Обо мне', home),
        ('#work' if home else '#projects' if archive else 'projects.html', 'Проекты', not home),
        ('#approach' if home else 'index.html#approach', 'Подход', False),
        ('#contact', 'Контакты', False),
    ]
    navigation = []
    for index, (href, label, active) in enumerate(links, 1):
        current = ' data-current-page aria-current="page"' if active and page == 'project' else ' aria-current="location"' if active else ''
        css = ' is-active' if active else ''
        navigation.append(f'<a class="nav-link{css}" href="{href}"{current}><span class="nav-index">{index:02d}</span>{label}</a>')
    canonical = PUBLIC_URL + (filename or ('' if home else 'projects.html'))
    social_meta = '' if preview else f'''<link rel="canonical" href="{canonical}">
    <meta property="og:type" content="website">
    <meta property="og:locale" content="ru_RU">
    <meta property="og:title" content="{title}">
    <meta property="og:description" content="{description}">
    <meta property="og:url" content="{canonical}">
    <meta name="twitter:card" content="summary">'''
    return {
        'head': template('partials/head', page_title=title, page_description=description,
                         social_meta=social_meta,
                         robots='<meta name="robots" content="noindex, nofollow">' if preview else '',
                         extra_scripts='<script src="gallery.js" defer></script>' if page == 'project' else ''),
        'sidebar': template('partials/sidebar', **profile, home_href=home_href, navigation='\n        '.join(navigation)),
        'footer': template('partials/footer', **profile, back_to_top='#intro' if home else '#projects' if archive else '#project'),
    }


def project_url(project):
    return f'project-{project["slug"]}.html'


def render_card(project, index, homepage=False):
    cover = project['cover']
    values = {key: escape(project[key], quote=True) for key in ('name', 'description', 'type')}
    if homepage:
        card_class = ' project-featured' if index == 0 else ''
        cover_class = 'pinkly-cover' if cover['format'] == 'pinkly' else 'cropped-cover'
    else:
        position = index % 6
        card_class = ' catalog-card--wide' if position in (0, 3) else ' catalog-card--offset' if position in (2, 5) else ''
        if position == 3:
            card_class += ' catalog-card--reverse'
        cover_class = f'catalog-cover--{cover["format"]}'
    return template('project-card' if homepage else 'catalog-card', **values,
                    url=project_url(project), card_class=card_class, cover_class=cover_class,
                    image_attributes=image_attributes(cover, eager=not homepage and index == 0),
                    index=index + 1, display_index=f'{index + 1:02d}')


def project_count(count):
    suffix = 'проект' if count % 10 == 1 and count % 100 != 11 else 'проекта' if count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14) else 'проектов'
    return f'{count:02d} {suffix}'


def render_site(preview_blocks=False, include_drafts=False):
    """Render everything in memory before replacing any generated files."""
    projects = load_projects(include_drafts)
    profile = site_context()
    featured = [project for project in projects if project.get('featured', False)]
    rendered = {
        'index.html': template('index', **render_shell(profile, 'index',
                              f'{profile["owner_name"]} — веб-дизайнер',
                              f'{profile["owner_name"]} — веб-дизайнер. Сайты, интерфейсы и AI-визуал. Избранные проекты и подход к работе.'),
                              featured_projects='\n'.join(render_card(p, i, homepage=True) for i, p in enumerate(featured))),
        'projects.html': template('projects', **render_shell(profile, 'projects',
                                 f'Все проекты — {profile["owner_name"]}',
                                 f'{profile["owner_name"]}: сайты, интерфейсы и визуальные концепции.'),
                                 project_count=project_count(len(projects)),
                                 catalog_projects='\n'.join(render_card(p, i) for i, p in enumerate(projects))),
    }

    def page(project, next_project, index, total, preview=False):
        values = {key: escape(project[key], quote=True) for key in ('name', 'description', 'type', 'role', 'intro')}
        shell = render_shell(profile, 'project', f'{values["name"]} — {profile["owner_name"]}',
                             f'{values["description"]} — {profile["owner_name"]}.', preview,
                             None if preview else project_url(project))
        return template('project', **shell, **values, blocks=render_blocks(project),
                        index=index, total=total, next_name=escape(next_project['name']),
                        next_url=project_url(next_project))

    for index, project in enumerate(projects):
        rendered[project_url(project)] = page(project, projects[(index + 1) % len(projects)], f'{index + 1:02d}', f'{len(projects):02d}')
    if preview_blocks:
        example = read_content('block-examples')
        rendered['block-library.html'] = page(example, projects[0], 'UI-кит', '05 типов', preview=True)
    if include_drafts:
        rendered = {name: html.replace('<head>', '<head>\n<meta name="robots" content="noindex, nofollow">', 1)
                    for name, html in rendered.items()}
    return {name: typography_html(html) + '\n' for name, html in rendered.items()}


def build(preview_blocks=False):
    rendered = render_site(preview_blocks)
    for name, html in rendered.items():
        (SITE / name).write_text(html, encoding='utf-8')
    print(f'Rendered {len(rendered)} pages.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview-blocks', action='store_true')
    build(**vars(parser.parse_args()))
