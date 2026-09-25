import unittest

from builder import markup


class markup_tests(unittest.TestCase):
    def test_paragraphs(self):
        doc = markup.parse("one line\ncontinues here\n\nsecond paragraph")
        self.assertEqual(doc.html, "<p>one line continues here</p>\n\n<p>second paragraph</p>")
        self.assertEqual(doc.words, 6)

    def test_headings_get_ids(self):
        doc = markup.parse("== the fall of rome\n\n=== why? {#why-rome}\n\n== the fall of rome")
        self.assertEqual(doc.headings, [
            (2, "the-fall-of-rome", "the fall of rome"),
            (3, "why-rome", "why?"),
            (2, "the-fall-of-rome-2", "the fall of rome"),
        ])
        self.assertIn('<h2 id="the-fall-of-rome">', doc.html)

    def test_reserved_ids_are_avoided(self):
        doc = markup.parse("== people", reserved=("people",))
        self.assertEqual(doc.headings[0][1], "people-2")

    def test_lists(self):
        doc = markup.parse("- one\n- two\n\n+ first\n+ second")
        self.assertIn("<ul>\n<li>one</li>\n<li>two</li>\n</ul>", doc.html)
        self.assertIn("<ol>\n<li>first</li>\n<li>second</li>\n</ol>", doc.html)

    def test_quote(self):
        doc = markup.parse("> a quote\n> goes on")
        self.assertEqual(doc.html, "<blockquote>a quote goes on</blockquote>")

    def test_table(self):
        doc = markup.parse("| a | b |\n|---|---|\n| 1 | 2 |")
        self.assertIn("<tr><th>a</th><th>b</th></tr>", doc.html)
        self.assertIn("<tr><td>1</td><td>2</td></tr>", doc.html)

    def test_inline(self):
        doc = markup.parse("**bold** and _italic_ and [a link](http://example.com)")
        self.assertEqual(doc.html, '<p><b>bold</b> and <i>italic</i> and <a href="http://example.com">a link</a></p>')

    def test_glossary_people_and_part_links(self):
        doc = markup.parse("[[mandate of heaven]], [[supernova|supernovas]], [[@confucius]], [[part:the-beginning|part 1]]")
        self.assertIn('<a href="glossary.html#mandate-of-heaven" class="term">mandate of heaven</a>', doc.html)
        self.assertIn('<a href="glossary.html#supernova" class="term">supernovas</a>', doc.html)
        self.assertIn('<a href="people.html#confucius">confucius</a>', doc.html)
        self.assertIn('<a href="the-beginning.html">part 1</a>', doc.html)
        self.assertEqual(doc.terms, {"mandate-of-heaven", "supernova"})
        self.assertEqual(doc.people, {"confucius"})
        self.assertEqual(doc.parts, {"the-beginning"})

    def test_html_is_escaped(self):
        doc = markup.parse("<script>alert(1)</script> & more")
        self.assertNotIn("<script>", doc.html)
        self.assertIn("&lt;script&gt;", doc.html)
        self.assertIn("&amp; more", doc.html)

    def test_writer_notes_are_hidden(self):
        doc = markup.parse("# a note for the writer\nvisible")
        self.assertEqual(doc.html, "<p>visible</p>")

    def test_rule(self):
        self.assertEqual(markup.parse("---").html, "<hr>")


if __name__ == "__main__":
    unittest.main()
