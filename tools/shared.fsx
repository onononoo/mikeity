// shared.fsx: finds the figures, places, and ideas that more than one religion
// on the site talks about, like abraham (ibrahim in islam) or karma.
//
//   dotnet fsi tools/shared.fsx site/data/history.json data/shared.json
//
// history.json is written by the builder; shared.json lists what to look for
// and the different names each thing goes by. for every thing and every
// religion it counts the mentions in the story, timeline, people, and glossary,
// and picks the best page to link to: a person's entry, then a glossary term,
// then the first timeline entry, then the story itself. it prints tab
// separated lines the builder reads back:
//
//   match   kind   label   religion   mentions   url
//
// needs only the .net sdk (fsi is included), no project file.

open System
open System.IO
open System.Text
open System.Text.Json
open System.Text.RegularExpressions

// ------------------------------------------------------------------ types

type Kind =
    | Figure
    | Place
    | Idea

type Thing =
    { Kind: Kind
      Label: string
      Names: string list
      Not: string list }

/// one searchable piece of a religion's pages, and where it lives
type Chunk =
    { Text: string
      Url: string
      Rank: int } // lower is a better page to link to

type Religion =
    { Slug: string
      Name: string
      Chunks: Chunk list }

type Match =
    { Thing: Thing
      Religion: Religion
      Mentions: int
      Url: string }

// ------------------------------------------------------------------ reading json

let str (e: JsonElement) (name: string) =
    match e.TryGetProperty name with
    | true, v when v.ValueKind = JsonValueKind.String -> v.GetString()
    | _ -> ""

let items (e: JsonElement) (name: string) =
    match e.TryGetProperty name with
    | true, v when v.ValueKind = JsonValueKind.Array -> v.EnumerateArray() |> List.ofSeq
    | _ -> []

let kindOf =
    function
    | "figure" -> Figure
    | "place" -> Place
    | "idea" -> Idea
    | other -> failwithf "unknown kind %A in shared.json" other

let loadThings (path: string) =
    use doc = JsonDocument.Parse(File.ReadAllText path)
    [ for t in doc.RootElement.EnumerateArray() ->
          { Kind = kindOf (str t "kind")
            Label = str t "label"
            Names = items t "names" |> List.map (fun n -> n.GetString())
            Not = items t "not" |> List.map (fun n -> n.GetString()) } ]

let loadReligions (path: string) =
    use doc = JsonDocument.Parse(File.ReadAllText path)
    [ for r in items doc.RootElement "religions" ->
          let slug = str r "slug"
          let page name = sprintf "%s/%s" slug name
          let people =
              items r "people"
              |> List.map (fun p ->
                  { Text = String.Join(" ", str p "name", str p "role", str p "about")
                    Url = page ("people.html#" + str p "slug")
                    Rank = 0 })
          let terms =
              items r "glossary"
              |> List.map (fun t ->
                  { Text = str t "term" + " " + str t "definition"
                    Url = page ("glossary.html#" + str t "slug")
                    Rank = 1 })
          let events =
              items r "events"
              |> List.map (fun e ->
                  { Text = str e "text"
                    Url = page (sprintf "timeline.html#event-%d" (e.GetProperty("id").GetInt32()))
                    Rank = 2 })
          let story = { Text = str r "story"; Url = page "index.html"; Rank = 3 }
          { Slug = slug
            Name = str r "name"
            Chunks = people @ terms @ events @ [ story ] } ]

// ------------------------------------------------------------------ matching

/// a whole-word, case-insensitive pattern for any of a thing's names
let patternFor (thing: Thing) =
    let alternatives = thing.Names |> List.map Regex.Escape |> String.concat "|"
    Regex(sprintf @"\b(?:%s)\b" alternatives, RegexOptions.IgnoreCase ||| RegexOptions.Compiled)

let countIn (thing: Thing) (pattern: Regex) (text: string) =
    // blank out phrases that must not count, like "mary magdalene" for mary
    let cleaned =
        thing.Not
        |> List.fold (fun (t: string) phrase -> Regex.Replace(t, Regex.Escape phrase, " ", RegexOptions.IgnoreCase)) text
    pattern.Matches(cleaned).Count

let findMatches (things: Thing list) (religions: Religion list) =
    [ for thing in things do
          let pattern = patternFor thing
          for religion in religions do
              let hits =
                  religion.Chunks
                  |> List.map (fun c -> c, countIn thing pattern c.Text)
                  |> List.filter (fun (_, n) -> n > 0)
              if not hits.IsEmpty then
                  // where a thing has its own person or term entry, link to that;
                  // otherwise to the chunk that mentions it most, earliest first
                  let best, _ = hits |> List.sortBy (fun (c, n) -> c.Rank, -n) |> List.head
                  yield
                      { Thing = thing
                        Religion = religion
                        Mentions = hits |> List.sumBy snd
                        Url = best.Url } ]

// ------------------------------------------------------------------ main

let clean (s: string) = s.Replace('\t', ' ').Replace('\n', ' ')

let kindName =
    function
    | Figure -> "figure"
    | Place -> "place"
    | Idea -> "idea"

let run (history: string) (sharedPath: string) =
    let religions = loadReligions history
    if religions.IsEmpty then failwith "history.json has no religions"
    let things = loadThings sharedPath
    let matches = findMatches things religions

    let out = StringBuilder()
    for m in matches do
        out.AppendFormat(
            "match\t{0}\t{1}\t{2}\t{3}\t{4}\n",
            kindName m.Thing.Kind, clean m.Thing.Label, m.Religion.Slug, m.Mentions, m.Url
        )
        |> ignore

    // utf-8 with no byte order mark, whatever the console is set to
    let bytes = UTF8Encoding(false).GetBytes(out.ToString())
    use stdout = Console.OpenStandardOutput()
    stdout.Write(bytes, 0, bytes.Length)

match fsi.CommandLineArgs |> Array.toList |> List.tail with
| [ history; sharedPath ] ->
    try
        run history sharedPath
    with e ->
        eprintfn "shared.fsx: %s" e.Message
        exit 1
| _ ->
    eprintfn "usage: dotnet fsi tools/shared.fsx history.json shared.json"
    exit 2
