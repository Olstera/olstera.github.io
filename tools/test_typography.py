"""Protect wrapping without changing links, markup, or code examples."""
import unittest

from typography import bind_short_words, typography_html


class TypographyTests(unittest.TestCase):
    def test_short_words_quotes_and_chains(self):
        self.assertEqual(
            bind_short_words('И в команде, а не в одиночку. Для «нового сайта».'),
            'И\u00a0в\u00a0команде, а\u00a0не\u00a0в\u00a0одиночку. Для\u00a0«нового сайта».',
        )
        self.assertEqual(bind_short_words('дизайн, и, возможно, запуск'), 'дизайн, и, возможно, запуск')
        self.assertEqual(bind_short_words('дизайн-про тест, словоиз тест'), 'дизайн-про тест, словоиз тест')

    def test_inline_markup_and_html_entities(self):
        html = '<body><p>Работа в <strong>команде</strong> и &laquo;визуал&raquo;.</p></body>'
        self.assertEqual(typography_html(html), '<body><p>Работа в\u00a0<strong>команде</strong> и\u00a0«визуал».</p></body>')

    def test_attributes_code_and_explicit_breaks_are_preserved(self):
        html = '''<!doctype html><html><head><title>И в заголовке</title></head><body>
<a href="/path?q=в команде" title="И в подсказке">В начало</a>
<script>const value = "и в команде";</script><style>/* и в стиле */</style>
<pre>и в примере <code>в коде</code></pre><textarea>И в форме</textarea>
<p>Дизайн и<br>визуал</p><p>в</p><p>команде</p>
</body></html>'''
        self.assertEqual(typography_html(html), html.replace('>В начало<', '>В\u00a0начало<'))

    def test_escaped_user_text_stays_escaped_and_processing_is_idempotent(self):
        html = '<body><p>И &lt;script&gt;не код&lt;/script&gt;, но &quot;текст&quot;.</p><p>И&nbsp;уже&#160;готово.</p></body>'
        result = typography_html(html)
        self.assertNotIn('<script>', result)
        self.assertIn('но\u00a0"текст"', result)
        self.assertEqual(typography_html(result), result)


if __name__ == '__main__':
    unittest.main()
