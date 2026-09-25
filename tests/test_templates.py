import unittest

from builder.templates import template_error, template


def render(source, **ctx):
    return template(source).render(ctx)


class template_tests(unittest.TestCase):
    def test_variables_are_escaped(self):
        self.assertEqual(render("hi {{ name }}", name="<b>"), "hi &lt;b&gt;")
        self.assertEqual(render("{{ name|raw }}", name="<b>"), "<b>")

    def test_dotted_lookup(self):
        self.assertEqual(render("{{ a.b.c }}", a={"b": {"c": 5}}), "5")
        self.assertEqual(render("{{ a.b.c }}", a={}), "")

    def test_filters(self):
        self.assertEqual(render("{{ n|commas }}", n=1234567), "1,234,567")
        self.assertEqual(render("{{ xs|length }}", xs=[1, 2, 3]), "3")
        self.assertEqual(render("{{ s|slug }}", s="the dark ages"), "the-dark-ages")

    def test_if(self):
        src = "{% if a %}a{% elif b %}b{% else %}c{% endif %}"
        self.assertEqual(render(src, a=1), "a")
        self.assertEqual(render(src, b=1), "b")
        self.assertEqual(render(src), "c")
        self.assertEqual(render("{% if not a %}no{% endif %}"), "no")
        self.assertEqual(render("{% if x == y %}same{% endif %}", x=2, y=2), "same")
        self.assertEqual(render("{% if a and b %}both{% endif %}", a=1, b=0), "")
        self.assertEqual(render("{% if a or b %}one{% endif %}", a=0, b=1), "one")

    def test_for(self):
        src = "{% for x in xs %}{{ loop.index }}:{{ x }}{% if not loop.last %},{% endif %}{% endfor %}"
        self.assertEqual(render(src, xs=["a", "b", "c"]), "1:a,2:b,3:c")

    def test_for_else_and_unpacking(self):
        self.assertEqual(render("{% for x in xs %}{{ x }}{% else %}none{% endfor %}", xs=[]), "none")
        self.assertEqual(render("{% for k, v in d %}{{ k }}={{ v }};{% endfor %}", d={"a": 1}), "a=1;")

    def test_comments(self):
        self.assertEqual(render("a{# hidden #}b"), "ab")

    def test_errors(self):
        for bad in ("{% if a %}", "{% endif %}", "{% for x in %}{% endfor %}", "{{ x|nope }}", "{% dance %}"):
            with self.assertRaises(template_error, msg=bad):
                template(bad)


if __name__ == "__main__":
    unittest.main()
