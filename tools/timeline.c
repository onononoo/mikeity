/*
 * timeline: print the history of the world as text, in a terminal.
 *
 * reads the tab separated file the builder writes (site/data/events.tsv)
 * and prints the events, filtered by years, part, region, or words.
 *
 * build:   gcc -std=c99 -O2 -Wall -Wextra -o tools/timeline tools/timeline.c
 * run:     tools/timeline --from "500 bce" --to 1500 --grep rome
 *          tools/timeline --part 10
 *          tools/timeline --histogram
 *
 * years can be written as 1492, -500, "500 bce", "476 ce", "66 mya" or
 * "4.5 bya". years ago are counted back from 1950, like the rest of the site.
 */

#include <ctype.h>
#include <errno.h>
#include <float.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define present_year 1950.0
#define max_line 8192
#define date_width 24

struct event {
	double start;
	double end;
	int part;
	char *date;
	char *region;
	char *text;
};

struct list {
	struct event *items;
	size_t count;
	size_t cap;
};

struct options {
	const char *file;
	double from;
	double to;
	int part;
	const char *grep;
	const char *region;
	int count_only;
	int histogram;
	int width;
};

/* ------------------------------------------------------------ small helpers */

static void die(const char *msg, const char *detail)
{
	fprintf(stderr, "timeline: %s%s%s\n", msg, detail ? ": " : "", detail ? detail : "");
	exit(2);
}

static char *copy(const char *s)
{
	size_t n = strlen(s) + 1;
	char *p = malloc(n);
	if (!p)
		die("out of memory", NULL);
	memcpy(p, s, n);
	return p;
}

/* case-insensitive "does haystack contain needle" (strcasestr is not standard c) */
static int contains(const char *haystack, const char *needle)
{
	size_t n = strlen(needle);
	if (n == 0)
		return 1;
	for (; *haystack; haystack++) {
		size_t i = 0;
		while (i < n && haystack[i] &&
		       tolower((unsigned char)haystack[i]) == tolower((unsigned char)needle[i]))
			i++;
		if (i == n)
			return 1;
	}
	return 0;
}

/* ------------------------------------------------------------ year parsing */

/*
 * turn text like "500 bce", "1492", "-44", "66 mya" into a number.
 * returns 1 on success and stores the year in *out.
 */
static int parse_year(const char *text, double *out)
{
	char buf[64];
	size_t j = 0;
	char *end;
	double n;

	/* lowercase and drop spaces, commas, and a leading "c." */
	for (const char *p = text; *p && j < sizeof buf - 1; p++) {
		if (isspace((unsigned char)*p) || *p == ',')
			continue;
		buf[j++] = (char)tolower((unsigned char)*p);
	}
	buf[j] = '\0';
	if (strncmp(buf, "c.", 2) == 0)
		memmove(buf, buf + 2, strlen(buf + 2) + 1);
	if (buf[0] == '\0')
		return 0;

	errno = 0;
	n = strtod(buf, &end);
	if (end == buf || errno == ERANGE)
		return 0;

	if (*end == '\0' || strcmp(end, "ce") == 0 || strcmp(end, "ad") == 0)
		*out = n;
	else if (strcmp(end, "bce") == 0 || strcmp(end, "bc") == 0)
		*out = -n;
	else if (strcmp(end, "bya") == 0 || strcmp(end, "billionyearsago") == 0)
		*out = present_year - n * 1e9;
	else if (strcmp(end, "mya") == 0 || strcmp(end, "millionyearsago") == 0)
		*out = present_year - n * 1e6;
	else if (strcmp(end, "kya") == 0 || strcmp(end, "thousandyearsago") == 0)
		*out = present_year - n * 1e3;
	else if (strcmp(end, "yearsago") == 0)
		*out = present_year - n;
	else
		return 0;
	return 1;
}

/* ------------------------------------------------------------ reading the file */

static void push(struct list *l, struct event e)
{
	if (l->count == l->cap) {
		l->cap = l->cap ? l->cap * 2 : 256;
		l->items = realloc(l->items, l->cap * sizeof *l->items);
		if (!l->items)
			die("out of memory", NULL);
	}
	l->items[l->count++] = e;
}

/* split a line on tabs in place. returns the number of fields found. */
static int split_tabs(char *line, char **fields, int max)
{
	int n = 0;
	char *p = line;
	while (n < max) {
		fields[n++] = p;
		p = strchr(p, '\t');
		if (!p)
			break;
		*p++ = '\0';
	}
	return n;
}

static struct list load(const char *path)
{
	struct list l = { 0 };
	char line[max_line];
	int lineno = 0;
	FILE *f = fopen(path, "r");

	if (!f)
		die("cannot open file (build the site first)", path);

	while (fgets(line, sizeof line, f)) {
		char *fields[6];
		struct event e;
		lineno++;

		line[strcspn(line, "\r\n")] = '\0';
		if (line[0] == '#' || line[0] == '\0')
			continue;
		if (split_tabs(line, fields, 6) != 6) {
			fprintf(stderr, "timeline: skipping bad line %d\n", lineno);
			continue;
		}
		e.start = strtod(fields[0], NULL);
		e.end = strtod(fields[1], NULL);
		e.date = copy(fields[2]);
		e.part = atoi(fields[3]);
		e.region = copy(fields[4]);
		e.text = copy(fields[5]);
		push(&l, e);
	}
	fclose(f);
	return l;
}

static void free_list(struct list *l)
{
	for (size_t i = 0; i < l->count; i++) {
		free(l->items[i].date);
		free(l->items[i].region);
		free(l->items[i].text);
	}
	free(l->items);
}

/* ------------------------------------------------------------ output */

/* how many columns a utf-8 string takes up (continuation bytes take none) */
static int display_width(const char *s)
{
	int n = 0;
	for (; *s; s++)
		if (((unsigned char)*s & 0xc0) != 0x80)
			n++;
	return n;
}

/* print a string padded with spaces to `width` columns */
static void print_padded(const char *s, int width)
{
	int pad = width - display_width(s);
	fputs(s, stdout);
	while (pad-- > 0)
		putchar(' ');
}

/* print text wrapped to `width` columns, with later lines indented */
static void print_wrapped(const char *text, int indent, int width)
{
	int room = width - indent;
	int col = 0;
	const char *p = text;

	if (room < 20)
		room = 20;
	while (*p) {
		const char *word = p;
		int len;
		while (*p && *p != ' ')
			p++;
		len = (int)(p - word);
		if (col > 0 && col + 1 + len > room) {
			printf("\n%*s", indent, "");
			col = 0;
		} else if (col > 0) {
			putchar(' ');
			col++;
		}
		fwrite(word, 1, (size_t)len, stdout);
		col += len;
		while (*p == ' ')
			p++;
	}
	putchar('\n');
}

static int matches(const struct event *e, const struct options *o)
{
	if (e->end < o->from || e->start > o->to)
		return 0;
	if (o->part && e->part != o->part)
		return 0;
	if (o->region && !contains(e->region, o->region))
		return 0;
	if (o->grep && !contains(e->text, o->grep) && !contains(e->date, o->grep))
		return 0;
	return 1;
}

static void histogram(const struct list *l, const struct options *o)
{
	int counts[32] = { 0 };
	int biggest = 0;
	int top = 0;

	for (size_t i = 0; i < l->count; i++) {
		const struct event *e = &l->items[i];
		if (!matches(e, o) || e->part < 1 || e->part > 31)
			continue;
		counts[e->part]++;
		if (e->part > top)
			top = e->part;
	}
	for (int p = 1; p <= top; p++)
		if (counts[p] > biggest)
			biggest = counts[p];

	printf("events per part\n\n");
	for (int p = 1; p <= top; p++) {
		int bar = biggest ? (counts[p] * 50 + biggest - 1) / biggest : 0;
		printf("  part %2d  %4d  ", p, counts[p]);
		for (int k = 0; k < bar; k++)
			putchar('#');
		putchar('\n');
	}
}

static void usage(void)
{
	puts("usage: timeline [options]\n"
	     "\n"
	     "  -f, --from YEAR      only events that end on or after this year\n"
	     "  -t, --to YEAR        only events that start on or before this year\n"
	     "  -p, --part N         only events in part N (1 to 11)\n"
	     "  -r, --region WORDS   only events whose region contains these words\n"
	     "  -g, --grep WORDS     only events whose text contains these words\n"
	     "  -c, --count          just print how many events match\n"
	     "  -H, --histogram      print a bar chart of events per part\n"
	     "  -w, --width N        wrap lines at N columns (default 80)\n"
	     "      --file PATH      read events from PATH (default site/data/events.tsv)\n"
	     "  -h, --help           show this help\n"
	     "\n"
	     "years look like 1492, -500, \"500 bce\", \"476 ce\", \"66 mya\", \"4.5 bya\".");
}

/* ------------------------------------------------------------ main */

int main(int argc, char **argv)
{
	struct options o = { "site/data/events.tsv", -DBL_MAX, DBL_MAX, 0, NULL, NULL, 0, 0, 80 };
	struct list l;
	size_t shown = 0;

	for (int i = 1; i < argc; i++) {
		const char *a = argv[i];
		const char *next = i + 1 < argc ? argv[i + 1] : NULL;
		int takes_value = 1;

		if (!strcmp(a, "-h") || !strcmp(a, "--help")) {
			usage();
			return 0;
		} else if (!strcmp(a, "-c") || !strcmp(a, "--count")) {
			o.count_only = 1;
			takes_value = 0;
		} else if (!strcmp(a, "-H") || !strcmp(a, "--histogram")) {
			o.histogram = 1;
			takes_value = 0;
		} else if (!next) {
			die("missing value after", a);
		} else if (!strcmp(a, "-f") || !strcmp(a, "--from")) {
			if (!parse_year(next, &o.from))
				die("cannot read year", next);
		} else if (!strcmp(a, "-t") || !strcmp(a, "--to")) {
			if (!parse_year(next, &o.to))
				die("cannot read year", next);
		} else if (!strcmp(a, "-p") || !strcmp(a, "--part")) {
			o.part = atoi(next);
			if (o.part < 1)
				die("part must be a number from 1 up", next);
		} else if (!strcmp(a, "-r") || !strcmp(a, "--region")) {
			o.region = next;
		} else if (!strcmp(a, "-g") || !strcmp(a, "--grep")) {
			o.grep = next;
		} else if (!strcmp(a, "-w") || !strcmp(a, "--width")) {
			o.width = atoi(next);
		} else if (!strcmp(a, "--file")) {
			o.file = next;
		} else {
			usage();
			return 2;
		}
		if (takes_value)
			i++;
	}

	l = load(o.file);

	if (o.histogram) {
		histogram(&l, &o);
		free_list(&l);
		return 0;
	}

	for (size_t i = 0; i < l.count; i++) {
		const struct event *e = &l.items[i];
		if (!matches(e, &o))
			continue;
		shown++;
		if (o.count_only)
			continue;
		print_padded(e->date, date_width);
		putchar(' ');
		print_wrapped(e->text, date_width + 1, o.width);
	}

	if (o.count_only)
		printf("%zu\n", shown);
	else
		printf("\n%zu of %zu events\n", shown, l.count);

	free_list(&l);
	return 0;
}
