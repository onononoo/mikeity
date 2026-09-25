/*
 * chart: draws the timeline as svg bar charts.
 *
 * reads the tab separated file the builder writes (site/data/events.tsv) and
 * writes two pictures into a folder:
 *
 *   deep-time.svg   every event, on a log scale of years ago, so the big bang
 *                   and last week both fit on one line
 *   recent.svg      the last five thousand years, one bar per century, with
 *                   each bar split up by the part of the story it belongs to
 *
 * the builder compiles and runs this by itself. to do it by hand:
 *
 *   g++ -std=c++17 -O2 -Wall -Wextra -o tools/bin/chart tools/chart.cpp
 *   tools/bin/chart site/data/events.tsv site/images
 *
 * it prints one line per chart: file name, width, height, and a short
 * description, separated by tabs. the builder reads that to make the <img> tags.
 */

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace fs = std::filesystem;

namespace {

// ------------------------------------------------------------------ data

struct event {
	double start = 0;
	double end = 0;
	int part = 0;
	std::string date;
	std::string region;
	std::string text;
};

std::vector<std::string> split(const std::string &line, char sep)
{
	std::vector<std::string> out;
	std::string field;
	std::istringstream in(line);
	while (std::getline(in, field, sep))
		out.push_back(field);
	return out;
}

std::vector<event> load(const fs::path &path)
{
	std::ifstream in(path);
	if (!in)
		throw std::runtime_error("cannot read " + path.string());

	std::vector<event> events;
	std::string line;
	int number = 0;
	while (std::getline(in, line)) {
		number++;
		if (!line.empty() && line.back() == '\r')
			line.pop_back();
		if (line.empty() || line[0] == '#')
			continue;
		auto f = split(line, '\t');
		if (f.size() < 6)
			throw std::runtime_error("line " + std::to_string(number) + " has too few columns");
		event e;
		e.start = std::stod(f[0]);
		e.end = std::stod(f[1]);
		e.date = f[2];
		e.part = std::stoi(f[3]);
		e.region = f[4];
		e.text = f[5];
		events.push_back(std::move(e));
	}
	return events;
}

// ------------------------------------------------------------------ svg

std::string escape(const std::string &s)
{
	std::string out;
	out.reserve(s.size());
	for (char c : s) {
		switch (c) {
		case '&': out += "&amp;"; break;
		case '<': out += "&lt;"; break;
		case '>': out += "&gt;"; break;
		case '"': out += "&quot;"; break;
		default: out += c;
		}
	}
	return out;
}

std::string num(double v)
{
	std::ostringstream s;
	s.precision(1);
	s << std::fixed << v;
	std::string t = s.str();
	if (t.size() > 2 && t.compare(t.size() - 2, 2, ".0") == 0)
		t.resize(t.size() - 2);
	return t;
}

// a very small svg writer. shapes are added in order and written out at the end.
class svg {
public:
	svg(int w, int h) : width(w), height(h) {}

	void rect(double x, double y, double w, double h, const std::string &fill,
	          const std::string &title = "")
	{
		body << "<rect x=\"" << num(x) << "\" y=\"" << num(y) << "\" width=\"" << num(w)
		     << "\" height=\"" << num(h) << "\" fill=\"" << fill << "\"";
		if (title.empty())
			body << "/>\n";
		else
			body << "><title>" << escape(title) << "</title></rect>\n";
	}

	void line(double x1, double y1, double x2, double y2, const std::string &stroke,
	          bool dashed = false)
	{
		body << "<line x1=\"" << num(x1) << "\" y1=\"" << num(y1) << "\" x2=\"" << num(x2)
		     << "\" y2=\"" << num(y2) << "\" stroke=\"" << stroke << "\""
		     << (dashed ? " stroke-dasharray=\"2,3\"" : "") << "/>\n";
	}

	void text(double x, double y, const std::string &s, const std::string &anchor = "start",
	          int size = 12, bool bold = false)
	{
		body << "<text x=\"" << num(x) << "\" y=\"" << num(y) << "\" font-size=\"" << size
		     << "\" text-anchor=\"" << anchor << "\"" << (bold ? " font-weight=\"bold\"" : "")
		     << ">" << escape(s) << "</text>\n";
	}

	void save(const fs::path &path, const std::string &title) const
	{
		std::ofstream out(path, std::ios::binary);
		if (!out)
			throw std::runtime_error("cannot write " + path.string());
		out << "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
		    << "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"" << width << "\" height=\""
		    << height << "\" viewBox=\"0 0 " << width << " " << height << "\""
		    << " font-family=\"times new roman, times, serif\">\n"
		    << "<title>" << escape(title) << "</title>\n"
		    << "<rect width=\"100%\" height=\"100%\" fill=\"#ffffff\"/>\n"
		    << body.str() << "</svg>\n";
	}

	const int width;
	const int height;

private:
	std::ostringstream body;
};

// plain, old web safe colors, one for each part of the story
const char *part_colors[] = {
	"#000000", "#663300", "#996600", "#cc9900", "#990000", "#660066",
	"#000099", "#006666", "#336600", "#999999", "#0066cc",
};

const char *color_for(int part)
{
	int n = sizeof part_colors / sizeof part_colors[0];
	return part_colors[((part - 1) % n + n) % n];
}

struct plot_area {
	double left, top, right, bottom;
	double width() const { return right - left; }
	double height() const { return bottom - top; }
};

// draws horizontal grid lines and their labels, and returns the scale's top value
double y_axis(svg &out, const plot_area &a, int biggest)
{
	// pick a step of 1, 2, or 5 times a power of ten so there are 4 to 8 lines
	double step = 1;
	for (double mag = 1; mag <= 1e6; mag *= 10) {
		for (double k : {1.0, 2.0, 5.0}) {
			step = k * mag;
			if (biggest / step <= 6)
				goto chosen;
		}
	}
chosen:
	double top = std::max(step, std::ceil(biggest / step) * step);
	for (double v = 0; v <= top + 0.5; v += step) {
		double y = a.bottom - a.height() * v / top;
		out.line(a.left, y, a.right, y, v == 0 ? "#000000" : "#cccccc", v != 0);
		out.text(a.left - 4, y + 4, num(v), "end", 11);
	}
	return top;
}

// ------------------------------------------------------------------ chart 1: deep time

// "years ago" is counted from just after the newest event, so nothing is zero
double years_ago(const event &e, double now)
{
	return std::max(1.0, now - e.start);
}

std::string power_label(int p)
{
	static const std::map<int, std::string> names = {
		{0, "1 year"},     {1, "10 years"},    {2, "100 years"},    {3, "1,000 years"},
		{4, "10,000"},     {5, "100,000"},     {6, "1 million"},    {7, "10 million"},
		{8, "100 million"}, {9, "1 billion"},  {10, "10 billion"},
	};
	auto it = names.find(p);
	return it == names.end() ? "10^" + std::to_string(p) : it->second;
}

std::string deep_time(const std::vector<event> &events, const fs::path &dir)
{
	const int bins_per_power = 5;
	const int powers = 11;  // 10^0 up to 10^11 years ago
	const int bins = bins_per_power * powers;

	double now = 0;
	for (const auto &e : events)
		now = std::max(now, e.end);
	now += 1;

	std::vector<int> count(bins, 0);
	for (const auto &e : events) {
		int b = static_cast<int>(std::log10(years_ago(e, now)) * bins_per_power);
		count[std::clamp(b, 0, bins - 1)]++;
	}
	int biggest = *std::max_element(count.begin(), count.end());

	svg out(740, 300);
	plot_area a{44, 30, 730, 250};
	out.text(a.left, 18, "events by how long ago they happened (log scale: each step is ten times further back)", "start", 13, true);
	double top = y_axis(out, a, biggest);

	// time runs left to right, so the oldest bins are drawn first
	double w = a.width() / bins;
	for (int i = 0; i < bins; i++) {
		int b = bins - 1 - i;
		if (!count[b])
			continue;
		double h = a.height() * count[b] / top;
		double lo = std::pow(10.0, b / double(bins_per_power));
		double hi = std::pow(10.0, (b + 1) / double(bins_per_power));
		std::string tip = std::to_string(count[b]) + " events, " + num(lo) + " to " + num(hi) + " years ago";
		out.rect(a.left + i * w + 1, a.bottom - h, w - 2, h, "#000080", tip);
	}
	for (int p = 0; p <= powers; p++) {
		double x = a.left + a.width() * (powers - p) / powers;
		out.line(x, a.bottom, x, a.bottom + 5, "#000000");
		if (p % 2 == 0)
			out.text(x, a.bottom + 18, power_label(p) + (p == 0 ? " ago" : ""), p == 0 ? "end" : "middle", 11);
	}
	out.text(a.left + a.width() / 2, a.bottom + 40, "years ago", "middle", 12);

	fs::path file = dir / "deep-time.svg";
	std::string about = "a bar chart of all " + std::to_string(events.size())
		+ " events on a log scale of years ago";
	out.save(file, about);
	return file.filename().string() + "\t" + std::to_string(out.width) + "\t"
		+ std::to_string(out.height) + "\t" + about;
}

// ------------------------------------------------------------------ chart 2: recent centuries

std::string century_label(int c)
{
	if (c == 0)
		return "1 ce";  // there is no year zero
	return c < 0 ? std::to_string(-c * 100) + " bce" : std::to_string(c * 100);
}

std::string recent(const std::vector<event> &events, const fs::path &dir)
{
	const int first = -30;  // 3000 bce
	double newest = -1e18;
	for (const auto &e : events)
		newest = std::max(newest, e.start);
	const int last = static_cast<int>(std::floor(newest / 100.0));
	const int n = last - first + 1;

	// counts[century][part]
	std::vector<std::map<int, int>> counts(n);
	std::map<int, int> parts_seen;
	int kept = 0;
	for (const auto &e : events) {
		int c = static_cast<int>(std::floor(e.start / 100.0));
		if (c < first || c > last)
			continue;
		counts[c - first][e.part]++;
		parts_seen[e.part]++;
		kept++;
	}
	int biggest = 0;
	for (const auto &m : counts) {
		int t = 0;
		for (const auto &[part, k] : m)
			t += k;
		biggest = std::max(biggest, t);
	}

	svg out(740, 300);
	plot_area a{44, 30, 730, 250};
	out.text(a.left, 18, "events in each century since 3000 bce, coloured by part", "start", 13, true);
	double top = y_axis(out, a, std::max(biggest, 1));

	double w = a.width() / n;
	for (int i = 0; i < n; i++) {
		double y = a.bottom;
		for (const auto &[part, k] : counts[i]) {
			double h = a.height() * k / top;
			y -= h;
			std::string tip = century_label(first + i) + " to " + century_label(first + i + 1)
				+ ": " + std::to_string(k) + " events in part " + std::to_string(part);
			out.rect(a.left + i * w + 0.5, y, std::max(w - 1, 1.0), h, color_for(part), tip);
		}
		if ((first + i) % 5 == 0) {
			double x = a.left + i * w;
			out.line(x, a.bottom, x, a.bottom + 5, "#000000");
			out.text(x, a.bottom + 18, century_label(first + i), "middle", 11);
		}
	}

	// a legend in one row under the axis
	double x = a.left;
	for (const auto &[part, k] : parts_seen) {
		out.rect(x, a.bottom + 34, 10, 10, color_for(part));
		out.text(x + 14, a.bottom + 43, "part " + std::to_string(part), "start", 11);
		x += 62;
	}

	fs::path file = dir / "recent.svg";
	std::string about = "a stacked bar chart of the " + std::to_string(kept)
		+ " events since 3000 bce, one bar per century";
	out.save(file, about);
	return file.filename().string() + "\t" + std::to_string(out.width) + "\t"
		+ std::to_string(out.height) + "\t" + about;
}

}  // namespace

int main(int argc, char **argv)
{
	if (argc != 3) {
		std::cerr << "usage: chart events.tsv output-folder\n";
		return 2;
	}
	try {
		auto events = load(argv[1]);
		if (events.empty())
			throw std::runtime_error("no events in " + std::string(argv[1]));
		fs::path dir = argv[2];
		fs::create_directories(dir);
		std::cout << deep_time(events, dir) << "\n" << recent(events, dir) << "\n";
	} catch (const std::exception &e) {
		std::cerr << "chart: " << e.what() << "\n";
		return 1;
	}
	return 0;
}
