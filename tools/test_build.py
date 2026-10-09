"""Regression checks for content updates and the publication boundary."""
import copy
from html import escape
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import build_projects
import build_release
from check_site import check_site


class SiteBuildTests(unittest.TestCase):
    def setUp(self):
        source = build_projects.SITE
        self.directory = tempfile.TemporaryDirectory(prefix='olsterra-build-test-')
        self.addCleanup(self.directory.cleanup)
        self.site = Path(self.directory.name)
        for name in ('templates', 'content'):
            shutil.copytree(source / name, self.site / name)
        for name in ('fonts', 'demo'):
            shutil.copytree(source / 'assets' / name, self.site / 'assets' / name)
        shutil.copy2(source / 'assets/favicon.svg', self.site / 'assets/favicon.svg')
        images = self.site / 'assets/images'
        images.mkdir()
        fixture = Path(__file__).parent / 'fixtures/pixel.jpg'
        for name in ('olya', 'pinkly', 'aurema', 'o-sh', 'tane', 'bdf', 'event-umarova'):
            shutil.copy2(fixture, images / f'{name}.jpg')
        for name in ('styles.css', 'script.js', 'gallery.js'):
            shutil.copy2(source / name, self.site / name)
        for module in (build_projects, build_release):
            context = patch.object(module, 'SITE', self.site)
            context.start()
            self.addCleanup(context.stop)
        self.projects = json.loads((Path(__file__).parent / 'fixtures/projects.json').read_text(encoding='utf-8'))
        self.save('projects', self.projects)

    def save(self, name, data):
        (self.site / 'content' / f'{name}.json').write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')

    def test_one_edit_updates_home_catalogue_and_case(self):
        self.projects[0]['description'] = 'Новое описание & <детали>'
        self.save('projects', self.projects)
        pages = build_projects.render_site()
        for name in ('index.html', 'projects.html', 'project-pinkly.html'):
            self.assertIn(escape(self.projects[0]['description']), pages[name])
            self.assertNotIn('Интерфейс AI-конструктора сайтов', pages[name])
        self.projects[0]['featured'] = False
        self.save('projects', self.projects)
        pages = build_projects.render_site()
        self.assertNotIn('project-pinkly.html', pages['index.html'])
        self.assertIn('project-pinkly.html', pages['projects.html'])

    def test_shared_contact_changes_on_every_page(self):
        profile = build_projects.read_content('site')
        profile['email'] = 'portfolio@example.com'
        self.save('site', profile)
        for html in build_projects.render_site(preview_blocks=True).values():
            self.assertIn('mailto:portfolio@example.com', html)
            self.assertNotIn('olsterra22@gmail.com', html)

    def test_reordering_and_adding_updates_count_links_and_next_project(self):
        added = copy.deepcopy(self.projects[0])
        added.update(slug='new-case', name='Новый кейс', featured=True)
        self.save('projects', [self.projects[2], added, self.projects[1]])
        pages = build_projects.render_site()
        self.assertEqual(len(pages), 5)
        self.assertIn('03 проекта', pages['projects.html'])
        self.assertIn('class="next-project" href="project-new-case.html"', pages['project-o-sh.html'])
        self.assertIn('class="next-project" href="project-o-sh.html"', pages['project-aurema.html'])
        self.assertIn('project-new-case.html', pages['index.html'])
        self.assertNotIn('project-pinkly.html', '\n'.join(pages.values()))

    def test_invalid_content_does_not_replace_existing_pages(self):
        sentinel = self.site / 'index.html'
        sentinel.write_text('Previous working page', encoding='utf-8')
        self.projects[-1]['blocks'][0]['src'] = 'assets/images/missing.jpg'
        self.save('projects', self.projects)
        with self.assertRaisesRegex(ValueError, 'Invalid local image'):
            build_projects.build()
        self.assertEqual(sentinel.read_text(), 'Previous working page')

    def test_invalid_image_metadata_and_slug_are_rejected(self):
        for change in ({'width': 4.5}, {'height': True}, {'alt': ' '}, {'src': '../outside.jpg'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                build_projects.image_attributes(self.projects[0]['cover'] | change)
        self.projects[1]['slug'] = self.projects[0]['slug']
        self.save('projects', self.projects)
        with self.assertRaisesRegex(ValueError, 'unique'):
            build_projects.render_site()

    def test_block_library_keeps_all_five_layouts_and_case_body(self):
        pages = build_projects.render_site(preview_blocks=True)
        library = pages['block-library.html']
        for kind in build_projects.BLOCK_KINDS:
            self.assertIn(f'case-block--{kind}', library)
        self.assertEqual(library.count(' data-gallery '), 7)
        self.assertEqual(library.count('<p class="case-body">'), 2)
        self.assertIn('noindex, nofollow', library)
        for name, html in pages.items():
            (self.site / name).write_text(html, encoding='utf-8')
        check_site(self.site)

    def test_release_excludes_private_material_and_removes_stale_output(self):
        # Release contents must come from templates, never stale preview HTML.
        (self.site / 'index.html').write_text('Stale preview', encoding='utf-8')
        destination = build_release.build_release()
        files = {str(p.relative_to(destination)) for p in destination.rglob('*') if p.is_file()}
        self.assertEqual(len(list(destination.glob('*.html'))), 8)
        self.assertIn('assets/fonts/LICENSE.txt', files)
        for name in files:
            self.assertFalse(name.startswith(('templates/', 'content/', 'tools/', 'output/', 'assets/demo/')))
        self.assertNotIn('block-library.html', files)
        self.assertNotIn('Stale preview', (destination / 'index.html').read_text())
        self.save('projects', [self.projects[0]])
        build_release.build_release()
        self.assertFalse((destination / 'project-aurema.html').exists())
        self.assertFalse((destination / 'assets/images/aurema.jpg').exists())
        self.assertEqual(len(list(destination.glob('*.html'))), 3)
        check_site(destination)

    def test_release_does_not_overwrite_unmanaged_directory(self):
        destination = self.site / 'dist'
        destination.mkdir()
        existing = destination / 'my-file.txt'
        existing.write_text('Keep this', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'not owned'):
            build_release.build_release()
        self.assertEqual(existing.read_text(), 'Keep this')

    def test_checker_reports_broken_anchors(self):
        pages = build_projects.render_site()
        for name, html in pages.items():
            (self.site / name).write_text(html, encoding='utf-8')
        home = self.site / 'index.html'
        home.write_text(home.read_text().replace('href="#work"', 'href="#missing"'), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'missing anchor #missing'):
            check_site(self.site)

    def test_incomplete_draft_does_not_enter_public_site(self):
        self.projects.append({'name': 'Незаконченный', 'slug': 'draft-case'})
        self.save('projects', self.projects)
        pages = build_projects.render_site()
        self.assertEqual(len(pages), 8)
        self.assertNotIn('draft-case', '\n'.join(pages.values()))
        with self.assertRaises(ValueError):
            build_projects.render_site(include_drafts=True)

    def test_unpublishing_removes_page_links_and_unused_artwork(self):
        build_release.build_release()
        self.projects[1]['published'] = False
        self.save('projects', self.projects)
        destination = build_release.build_release()
        pages = build_projects.render_site()
        self.assertNotIn('project-aurema.html', '\n'.join(pages.values()))
        self.assertFalse((destination / 'project-aurema.html').exists())
        self.assertFalse((destination / 'assets/images/aurema.jpg').exists())

    def test_preview_includes_ready_draft_with_noindex(self):
        self.projects[1]['published'] = False
        self.save('projects', self.projects)
        pages = build_projects.render_site(include_drafts=True)
        self.assertIn('project-aurema.html', pages)
        for html in pages.values():
            self.assertIn('noindex, nofollow', html)

    def test_empty_public_selection_keeps_previous_release(self):
        destination = build_release.build_release()
        previous = (destination / 'index.html').read_bytes()
        for project in self.projects:
            project['published'] = False
        self.save('projects', self.projects)
        with self.assertRaisesRegex(ValueError, 'at least one published'):
            build_release.build_release()
        self.assertEqual((destination / 'index.html').read_bytes(), previous)

    def test_cms_image_without_dimensions_has_natural_height(self):
        image = self.projects[0]['cover']
        image.pop('width', None)
        image.pop('height', None)
        attributes = build_projects.image_attributes(image)
        self.assertIn('src=', attributes)
        self.assertNotIn('height=', attributes)


if __name__ == '__main__':
    unittest.main()
