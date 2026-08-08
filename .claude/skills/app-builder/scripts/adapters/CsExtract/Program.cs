// C# extraction: file list on stdin, index records as JSONL on stdout.
//
// Uses Roslyn -- the compiler's own parser -- rather than pattern matching, and
// emits the same record shapes the Python and TypeScript extractors emit, so
// nothing downstream has to know which produced them.
//
// One process for the whole repository. Syntax only: no compilation is built,
// because resolving references would need every project restored, and the
// structure of a family is visible without it. The cost of that choice is named
// in references/languages.md -- extension methods cannot be resolved.

using System.Text.Json;
using System.Text.Json.Nodes;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;

var root = args.Length > 0 ? args[0].Replace('\\', '/') : "";
var payload = JsonNode.Parse(Console.In.ReadToEnd())!;
var repo = payload["repo"]!.GetValue<string>();

string Rel(string absolute)
{
    var p = absolute.Replace('\\', '/');
    return p.StartsWith(root, StringComparison.OrdinalIgnoreCase) && root.Length > 0
        ? p[(root.Length + 1)..] : p;
}

static string Trunc(string? s, int n = 160)
{
    s = string.Join(' ', (s ?? "").Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries));
    return s.Length <= n ? s : s[..(n - 1)] + "…";
}

// `_repository` from `_repository.GetBySpec(...)`, `Foo` from `Foo.Bar.Baz()`.
static string? CallRoot(ExpressionSyntax expr)
{
    while (true)
    {
        switch (expr)
        {
            case IdentifierNameSyntax id: return id.Identifier.Text;
            case MemberAccessExpressionSyntax ma: expr = ma.Expression; continue;
            case InvocationExpressionSyntax inv: expr = inv.Expression; continue;
            case ObjectCreationExpressionSyntax oc:
                return oc.Type.ToString().Split('<')[0];
            case ParenthesizedExpressionSyntax pe: expr = pe.Expression; continue;
            case PostfixUnaryExpressionSyntax pu: expr = pu.Operand; continue;
            case MemberBindingExpressionSyntax: return null;
            default: return null;
        }
    }
}

// Each entry is `[name, line]`: the call's own line, not the enclosing
// method's, which is the difference between being pointed at a call site and
// being pointed at a long method and told to look.
static JsonArray Pair(string name, int line) =>
    new JsonArray(name, line);

static bool HasPair(List<(string Name, int Line)> list, string name, int line) =>
    list.Any(e => e.Name == name && e.Line == line);

static (List<(string Name, int Line)> calls, List<(string Name, int Line)> invokes)
    Calls(SyntaxNode body, SyntaxTree tree)
{
    var calls = new List<(string Name, int Line)>();
    var invokes = new List<(string Name, int Line)>();
    foreach (var inv in body.DescendantNodes().OfType<InvocationExpressionSyntax>())
    {
        var line = tree.GetLineSpan(inv.Span).StartLinePosition.Line + 1;
        switch (inv.Expression)
        {
            case MemberAccessExpressionSyntax ma:
            {
                var r = CallRoot(ma.Expression);
                if (r is not null)
                {
                    var entry = $"{r}.{ma.Name.Identifier.Text}";
                    if (!HasPair(calls, entry, line)) calls.Add((entry, line));
                }
                break;
            }
            case IdentifierNameSyntax id:
                if (!HasPair(invokes, id.Identifier.Text, line))
                    invokes.Add((id.Identifier.Text, line));
                break;
        }
    }
    return (calls, invokes);
}

static List<string> Attributes(SyntaxList<AttributeListSyntax> lists) =>
    lists.SelectMany(l => l.Attributes).Select(a => a.ToString()).ToList();

static List<string> Modifiers(SyntaxTokenList tokens) =>
    tokens.Select(t => t.Text).ToList();

static JsonObject Method(BaseMethodDeclarationSyntax m, string name,
                         FileLinePositionSpan span, SyntaxTree tree)
{
    SyntaxNode? body = (SyntaxNode?)m.Body ?? m.ExpressionBody;
    // Both branches must name the tuple elements, or the inferred type of the
    // conditional drops the names and `.Name`/`.Line` stop existing.
    var (calls, invokes) = body is null
        ? (new List<(string Name, int Line)>(), new List<(string Name, int Line)>())
        : Calls(body, tree);
    var returns = m is MethodDeclarationSyntax md ? md.ReturnType.ToString() : null;
    return new JsonObject
    {
        ["name"] = name,
        ["decorators"] = new JsonArray(Attributes(m.AttributeLists)
            .Select(a => (JsonNode)a!).ToArray()),
        ["params"] = new JsonArray(m.ParameterList.Parameters
            .Select(p => (JsonNode)p.Identifier.Text!).ToArray()),
        ["returns"] = returns,
        ["line"] = span.StartLinePosition.Line + 1,
        ["end"] = span.EndLinePosition.Line + 1,
        ["async"] = Modifiers(m.Modifiers).Contains("async"),
        ["calls"] = new JsonArray(calls.Select(c => (JsonNode)Pair(c.Name, c.Line)).ToArray()),
        ["invokes"] = new JsonArray(invokes.Select(c => (JsonNode)Pair(c.Name, c.Line)).ToArray()),
    };
}

// Partial types are one type written across several files. `shape` counts
// classes, so leaving them separate would count one type three times and skew
// every percentage in the family. They are merged by fully qualified name.
var classes = new Dictionary<string, JsonObject>();
var order = new List<string>();
var records = new List<JsonObject>();

foreach (var entry in payload["files"]!.AsArray())
{
    var absolute = entry!["path"]!.GetValue<string>();
    var mtime = entry["mtime"]!.GetValue<long>();
    var commit = entry["commit"];
    string source;
    try { source = File.ReadAllText(absolute); }
    catch (Exception e)
    {
        records.Add(new JsonObject
        {
            ["k"] = "unreadable", ["lang"] = "csharp", ["repo"] = repo,
            ["path"] = Rel(absolute), ["error"] = Trunc(e.Message, 200),
        });
        continue;
    }

    var relpath = Rel(absolute);
    var tree = CSharpSyntaxTree.ParseText(source, path: absolute);
    var unit = (CompilationUnitSyntax)tree.GetRoot();

    var usings = new JsonArray();
    foreach (var u in unit.DescendantNodes().OfType<UsingDirectiveSyntax>())
    {
        usings.Add(new JsonObject
        {
            ["mod"] = u.Name?.ToString() ?? u.NamespaceOrType?.ToString() ?? "",
            ["name"] = u.Alias?.Name.Identifier.Text,
            ["as"] = u.Alias?.Name.Identifier.Text,
        });
    }

    var hasEntryPoint = unit.DescendantNodes().OfType<MethodDeclarationSyntax>()
        .Any(m => m.Identifier.Text == "Main"
                  && Modifiers(m.Modifiers).Contains("static"))
        || Path.GetFileName(absolute) == "Program.cs";

    records.Add(new JsonObject
    {
        ["k"] = "module", ["lang"] = "csharp", ["repo"] = repo, ["path"] = relpath,
        ["pkg"] = unit.DescendantNodes().OfType<BaseNamespaceDeclarationSyntax>()
            .Select(n => n.Name.ToString()).FirstOrDefault() ?? "",
        ["dir"] = relpath.Contains('/') ? relpath[..relpath.LastIndexOf('/')] : "",
        ["loc"] = source.Split('\n').Length,
        ["mtime"] = mtime,
        ["commit"] = commit?.DeepClone(),
        ["main"] = hasEntryPoint,
        // C# has no re-export file; a namespace is visible without one.
        ["exports"] = new JsonArray(),
        ["imports"] = usings,
        ["doc"] = null,
    });

    foreach (var type in unit.DescendantNodes().OfType<TypeDeclarationSyntax>())
    {
        var ns = type.Ancestors().OfType<BaseNamespaceDeclarationSyntax>()
            .Select(n => n.Name.ToString()).FirstOrDefault() ?? "";
        var key = $"{ns}.{type.Identifier.Text}";
        var span = tree.GetLineSpan(type.Span);

        var attrs = new JsonArray();
        var assigns = new JsonArray();
        var methods = new JsonArray();
        var nested = new JsonArray();

        foreach (var member in type.Members)
        {
            switch (member)
            {
                case PropertyDeclarationSyntax p:
                    attrs.Add(new JsonObject
                    {
                        ["name"] = p.Identifier.Text,
                        ["ann"] = p.Type.ToString(),
                        ["call"] = (p.Initializer?.Value as InvocationExpressionSyntax)
                            ?.Expression.ToString()
                            ?? (p.Initializer?.Value as ObjectCreationExpressionSyntax)
                            ?.Type.ToString(),
                        ["args"] = new JsonArray(),
                        ["kw"] = new JsonArray(Modifiers(p.Modifiers)
                            .Select(m => (JsonNode)m!).ToArray()),
                    });
                    break;
                case FieldDeclarationSyntax f:
                    foreach (var v in f.Declaration.Variables)
                    {
                        var target = Modifiers(f.Modifiers).Contains("static")
                                     || Modifiers(f.Modifiers).Contains("const")
                            ? assigns : attrs;
                        if (target == assigns)
                            assigns.Add(new JsonObject
                            {
                                ["name"] = v.Identifier.Text,
                                ["value"] = Trunc(v.Initializer?.Value.ToString(), 240),
                            });
                        else
                            attrs.Add(new JsonObject
                            {
                                ["name"] = v.Identifier.Text,
                                ["ann"] = f.Declaration.Type.ToString(),
                                ["call"] = (v.Initializer?.Value as ObjectCreationExpressionSyntax)
                                    ?.Type.ToString(),
                                ["args"] = new JsonArray(),
                                ["kw"] = new JsonArray(),
                            });
                    }
                    break;
                case MethodDeclarationSyntax m:
                    methods.Add(Method(m, m.Identifier.Text, tree.GetLineSpan(m.Span), tree));
                    break;
                case ConstructorDeclarationSyntax c:
                    methods.Add(Method(c, ".ctor", tree.GetLineSpan(c.Span), tree));
                    break;
                case TypeDeclarationSyntax n:
                    nested.Add(n.Identifier.Text);
                    break;
            }
        }

        if (classes.TryGetValue(key, out var existing))
        {
            foreach (var a in attrs) ((JsonArray)existing["attrs"]!).Add(a!.DeepClone());
            foreach (var a in assigns) ((JsonArray)existing["assigns"]!).Add(a!.DeepClone());
            foreach (var m in methods) ((JsonArray)existing["methods"]!).Add(m!.DeepClone());
            foreach (var b in type.BaseList?.Types.Select(t => t.ToString()) ?? [])
            {
                var bases = (JsonArray)existing["bases"]!;
                if (!bases.Any(x => x!.GetValue<string>() == b)) bases.Add(b);
            }
            continue;
        }

        var kind = type switch
        {
            InterfaceDeclarationSyntax => "interface",
            StructDeclarationSyntax => "struct",
            RecordDeclarationSyntax => "record",
            _ => "class",
        };

        var rec = new JsonObject
        {
            ["k"] = "class", ["lang"] = "csharp", ["repo"] = repo, ["path"] = relpath,
            ["mtime"] = mtime, ["commit"] = commit?.DeepClone(),
            ["name"] = type.Identifier.Text,
            ["kind"] = kind,
            ["bases"] = new JsonArray((type.BaseList?.Types.Select(t => t.ToString()) ?? [])
                .Select(b => (JsonNode)b!).ToArray()),
            ["keywords"] = new JsonArray(Modifiers(type.Modifiers)
                .Select(m => (JsonNode)m!).ToArray()),
            ["decorators"] = new JsonArray(Attributes(type.AttributeLists)
                .Select(a => (JsonNode)a!).ToArray()),
            ["line"] = span.StartLinePosition.Line + 1,
            ["end"] = span.EndLinePosition.Line + 1,
            ["attrs"] = attrs, ["assigns"] = assigns,
            ["methods"] = methods, ["nested"] = nested,
            ["doc"] = null,
        };
        classes[key] = rec;
        order.Add(key);
    }
}

var options = new JsonSerializerOptions { WriteIndented = false };
var writer = Console.Out;
foreach (var r in records) writer.WriteLine(r.ToJsonString(options));
foreach (var key in order) writer.WriteLine(classes[key].ToJsonString(options));
writer.Flush();
