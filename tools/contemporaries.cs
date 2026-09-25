// contemporaries: works out which people on the site were alive at the same time.
//
// reads site/data/history.json (written by the builder) and prints tab
// separated lines the builder reads back:
//
//   with   person   other person   years they were both alive
//   count  person   how many other people were alive during their life
//
// for each person it picks up to four others, preferring people from other
// parts of the world ("meanwhile, elsewhere") and then the longest overlap.
// only people whose birth and death years are both known are used.
//
// needs the .net 10 sdk, which can run a single .cs file with no project:
//
//   dotnet run tools/contemporaries.cs -- site/data/history.json

using System.Text.Json;

if (args.Length != 1)
{
    Console.Error.WriteLine("usage: dotnet run tools/contemporaries.cs -- history.json");
    return 2;
}

List<Person> people;
try
{
    people = Person.Load(args[0]);
}
catch (Exception e) when (e is IOException or JsonException or KeyNotFoundException or InvalidOperationException)
{
    Console.Error.WriteLine($"contemporaries: cannot read {args[0]}: {e.Message}");
    return 1;
}

const int perPerson = 4;
var overlaps = Overlaps.Find(people);

var output = new System.Text.StringBuilder();
foreach (var p in people)
{
    var mine = overlaps.TryGetValue(p.Slug, out var list) ? list : [];
    var picked = mine
        .OrderByDescending(o => o.Other.Region != p.Region)
        .ThenByDescending(o => o.Years)
        .ThenBy(o => o.Other.Born)
        .Take(perPerson);
    foreach (var o in picked)
        output.Append($"with\t{p.Slug}\t{o.Other.Slug}\t{o.Years}\n");
    output.Append($"count\t{p.Slug}\t{mine.Count}\n");
}

// write utf-8 without a byte order mark, whatever the console thinks
using (var stdout = Console.OpenStandardOutput())
{
    var bytes = new System.Text.UTF8Encoding(false).GetBytes(output.ToString());
    stdout.Write(bytes, 0, bytes.Length);
}
return 0;


record Person(string Slug, string Name, string Region, int Born, int Died)
{
    // reads the "people" list without reflection, so it also works trimmed or aot compiled
    public static List<Person> Load(string path)
    {
        using var doc = JsonDocument.Parse(File.ReadAllBytes(path));
        var list = new List<Person>();
        foreach (var p in doc.RootElement.GetProperty("people").EnumerateArray())
        {
            if (!p.GetProperty("known").GetBoolean())
                continue;
            list.Add(new Person(
                p.GetProperty("slug").GetString()!,
                p.GetProperty("name").GetString()!,
                p.GetProperty("region").GetString()!,
                (int)Math.Round(p.GetProperty("born").GetDouble()),
                (int)Math.Round(p.GetProperty("died").GetDouble())));
        }
        return list;
    }
}

record Overlap(Person Other, int Years);

static class Overlaps
{
    // a sweep over births: walk through people in order of birth, keeping the
    // ones still alive in a list sorted by death year. anyone who died before
    // the new person was born drops off the front; everyone left overlapped.
    public static Dictionary<string, List<Overlap>> Find(List<Person> people)
    {
        var result = people.ToDictionary(p => p.Slug, _ => new List<Overlap>());
        var alive = new PriorityQueue<Person, int>();
        var living = new HashSet<Person>();

        foreach (var p in people.OrderBy(p => p.Born).ThenBy(p => p.Slug, StringComparer.Ordinal))
        {
            while (alive.TryPeek(out var first, out var died) && died < p.Born)
            {
                alive.Dequeue();
                living.Remove(first);
            }
            foreach (var q in living)
            {
                int years = Math.Min(p.Died, q.Died) - p.Born;
                if (years < 1)
                    continue;
                result[p.Slug].Add(new Overlap(q, years));
                result[q.Slug].Add(new Overlap(p, years));
            }
            alive.Enqueue(p, p.Died);
            living.Add(p);
        }
        return result;
    }
}
