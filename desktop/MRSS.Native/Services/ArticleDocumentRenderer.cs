using System.Diagnostics;
using System.Net;
using System.Text.RegularExpressions;
using System.Windows;
using System.Windows.Documents;
using System.Windows.Media;
using System.Windows.Navigation;
using HtmlAgilityPack;
using MRSS.Native.Models;

namespace MRSS.Native.Services;

public static partial class ArticleDocumentRenderer
{
    private static readonly Brush TextBrush = Brush("#1F2937");
    private static readonly Brush MutedBrush = Brush("#667085");
    private static readonly Brush LinkBrush = Brush("#0F766E");
    private static readonly Brush CodeBackgroundBrush = Brush("#F3F6FA");

    public static FlowDocument Create(Article? article)
    {
        var document = new FlowDocument
        {
            PagePadding = new Thickness(0),
            ColumnWidth = 100000,
            FontFamily = new FontFamily("Microsoft YaHei UI"),
            FontSize = 15,
            LineHeight = 26,
            Foreground = TextBrush
        };

        if (article is null)
        {
            return document;
        }

        var content = article.ReaderContent;
        if (string.IsNullOrWhiteSpace(content))
        {
            AddPlainText(document, article.ReaderTitle);
            return document;
        }

        var baseUri = Uri.TryCreate(article.Link, UriKind.Absolute, out var link) ? link : null;
        try
        {
            if (LooksLikeHtml(content))
            {
                AddHtml(document, content, baseUri);
            }
            else
            {
                AddPlainText(document, WebUtility.HtmlDecode(content));
            }
        }
        catch
        {
            document.Blocks.Clear();
            AddPlainText(document, article.PlainContent);
        }

        if (document.Blocks.Count == 0)
        {
            AddPlainText(document, article.PlainContent);
        }

        return document;
    }

    private static void AddHtml(FlowDocument document, string html, Uri? baseUri)
    {
        var htmlDocument = new HtmlDocument
        {
            OptionFixNestedTags = true,
            OptionAutoCloseOnEnd = true
        };
        htmlDocument.LoadHtml("<body>" + html + "</body>");
        var root = htmlDocument.DocumentNode.SelectSingleNode("//body") ?? htmlDocument.DocumentNode;
        AddBlocks(document, root.ChildNodes, baseUri);
    }

    private static void AddBlocks(FlowDocument document, HtmlNodeCollection nodes, Uri? baseUri)
    {
        var paragraph = CreateParagraph();
        foreach (var node in nodes)
        {
            if (IsIgnored(node))
            {
                continue;
            }

            if (IsBlockNode(node))
            {
                AddParagraphIfContent(document, paragraph);
                paragraph = CreateParagraph();
                AddBlock(document, node, baseUri);
            }
            else
            {
                AppendInline(paragraph.Inlines, node, baseUri);
            }
        }

        AddParagraphIfContent(document, paragraph);
    }

    private static void AddBlock(FlowDocument document, HtmlNode node, Uri? baseUri)
    {
        var name = NodeName(node);
        switch (name)
        {
            case "h1":
            case "h2":
            case "h3":
            case "h4":
            case "h5":
            case "h6":
                AddHeading(document, node, baseUri, name);
                break;
            case "p":
            case "figcaption":
            case "address":
                AddSimpleParagraph(document, node, baseUri);
                break;
            case "div":
            case "section":
            case "article":
            case "header":
            case "footer":
            case "main":
            case "aside":
            case "figure":
                if (node.ChildNodes.Any(IsBlockNode))
                {
                    AddBlocks(document, node.ChildNodes, baseUri);
                }
                else
                {
                    AddSimpleParagraph(document, node, baseUri);
                }
                break;
            case "ul":
            case "ol":
                document.Blocks.Add(CreateList(node, baseUri, name == "ol"));
                break;
            case "blockquote":
                AddQuote(document, node, baseUri);
                break;
            case "pre":
                AddPreformatted(document, node);
                break;
            case "table":
                AddTableFallback(document, node, baseUri);
                break;
            case "img":
                AddImageLink(document, node, baseUri);
                break;
            case "hr":
                document.Blocks.Add(new Paragraph(new Run(" ")) { Margin = new Thickness(0, 8, 0, 8), BorderBrush = Brush("#E5E7EB"), BorderThickness = new Thickness(0, 1, 0, 0) });
                break;
            default:
                AddSimpleParagraph(document, node, baseUri);
                break;
        }
    }

    private static void AddHeading(FlowDocument document, HtmlNode node, Uri? baseUri, string tag)
    {
        var size = tag switch
        {
            "h1" => 24.0,
            "h2" => 21.0,
            "h3" => 18.0,
            _ => 16.0
        };
        var paragraph = CreateParagraph();
        paragraph.FontSize = size;
        paragraph.FontWeight = FontWeights.Bold;
        paragraph.LineHeight = size + 9;
        paragraph.Margin = new Thickness(0, document.Blocks.Count == 0 ? 0 : 14, 0, 9);
        AppendInlineChildren(paragraph.Inlines, node, baseUri);
        AddParagraphIfContent(document, paragraph);
    }

    private static void AddSimpleParagraph(FlowDocument document, HtmlNode node, Uri? baseUri)
    {
        var paragraph = CreateParagraph();
        AppendInlineChildren(paragraph.Inlines, node, baseUri);
        AddParagraphIfContent(document, paragraph);
    }

    private static void AddQuote(FlowDocument document, HtmlNode node, Uri? baseUri)
    {
        var paragraph = CreateParagraph();
        paragraph.Foreground = MutedBrush;
        paragraph.Margin = new Thickness(16, 4, 0, 14);
        AppendInlineChildren(paragraph.Inlines, node, baseUri);
        AddParagraphIfContent(document, paragraph);
    }

    private static void AddPreformatted(FlowDocument document, HtmlNode node)
    {
        var text = WebUtility.HtmlDecode(node.InnerText).Trim('\r', '\n');
        if (string.IsNullOrWhiteSpace(text))
        {
            return;
        }

        var paragraph = new Paragraph(new Run(text))
        {
            FontFamily = new FontFamily("Consolas"),
            FontSize = 13,
            LineHeight = 20,
            Background = CodeBackgroundBrush,
            Margin = new Thickness(0, 4, 0, 14)
        };
        document.Blocks.Add(paragraph);
    }

    private static List CreateList(HtmlNode node, Uri? baseUri, bool ordered)
    {
        var list = new List
        {
            MarkerStyle = ordered ? TextMarkerStyle.Decimal : TextMarkerStyle.Disc,
            Margin = new Thickness(22, 2, 0, 14),
            Padding = new Thickness(0)
        };

        foreach (var itemNode in node.ChildNodes.Where(child => NodeName(child) == "li"))
        {
            var item = new ListItem();
            AddListItemBlocks(item, itemNode, baseUri);
            if (item.Blocks.Count == 0)
            {
                item.Blocks.Add(new Paragraph(new Run(WebUtility.HtmlDecode(itemNode.InnerText).Trim())));
            }

            list.ListItems.Add(item);
        }

        return list;
    }

    private static void AddListItemBlocks(ListItem item, HtmlNode itemNode, Uri? baseUri)
    {
        var paragraph = CreateParagraph();
        paragraph.Margin = new Thickness(0, 0, 0, 5);
        foreach (var child in itemNode.ChildNodes)
        {
            if (IsIgnored(child))
            {
                continue;
            }

            var name = NodeName(child);
            if (name is "ul" or "ol")
            {
                AddParagraphIfContent(item.Blocks, paragraph);
                paragraph = CreateParagraph();
                item.Blocks.Add(CreateList(child, baseUri, name == "ol"));
            }
            else if (IsBlockNode(child) && name is not "p" and not "div")
            {
                AddParagraphIfContent(item.Blocks, paragraph);
                paragraph = CreateParagraph();
                var nested = CreateParagraph();
                AppendInlineChildren(nested.Inlines, child, baseUri);
                AddParagraphIfContent(item.Blocks, nested);
            }
            else
            {
            AppendInline(paragraph.Inlines, child, baseUri);
        }
        }

        AddParagraphIfContent(item.Blocks, paragraph);
    }

    private static void AddTableFallback(FlowDocument document, HtmlNode node, Uri? baseUri)
    {
        foreach (var row in node.Descendants("tr"))
        {
            var cells = row.ChildNodes
                .Where(child => NodeName(child) is "td" or "th")
                .Select(child => WebUtility.HtmlDecode(child.InnerText).Trim())
                .Where(text => text.Length > 0)
                .ToList();
            if (cells.Count > 0)
            {
                document.Blocks.Add(new Paragraph(new Run(string.Join("  |  ", cells))) { Margin = new Thickness(0, 0, 0, 8) });
            }
        }

        if (!node.Descendants("tr").Any())
        {
            AddSimpleParagraph(document, node, baseUri);
        }
    }

    private static void AddImageLink(FlowDocument document, HtmlNode node, Uri? baseUri)
    {
        var paragraph = CreateParagraph();
        AppendImageLink(paragraph.Inlines, node, baseUri);
        AddParagraphIfContent(document, paragraph);
    }

    private static void AddPlainText(FlowDocument document, string? text)
    {
        var decoded = WebUtility.HtmlDecode(text ?? "").Replace("\r\n", "\n").Replace('\r', '\n').Trim();
        if (decoded.Length == 0)
        {
            return;
        }

        var paragraphs = PlainParagraphRegex().Split(decoded).Where(part => !string.IsNullOrWhiteSpace(part));
        foreach (var part in paragraphs)
        {
            var paragraph = CreateParagraph();
            var lines = part.Split('\n');
            for (var i = 0; i < lines.Length; i++)
            {
                if (i > 0)
                {
                    paragraph.Inlines.Add(new LineBreak());
                }

                paragraph.Inlines.Add(new Run(lines[i].TrimEnd()));
            }

            AddParagraphIfContent(document, paragraph);
        }
    }

    private static void AppendInlineChildren(InlineCollection inlines, HtmlNode node, Uri? baseUri, bool insideLink = false)
    {
        foreach (var child in node.ChildNodes)
        {
            AppendInline(inlines, child, baseUri, insideLink);
        }
    }

    private static void AppendInline(InlineCollection inlines, HtmlNode node, Uri? baseUri, bool insideLink = false)
    {
        if (IsIgnored(node))
        {
            return;
        }

        if (node.NodeType == HtmlNodeType.Text)
        {
            var text = NormalizeInlineText(WebUtility.HtmlDecode(node.InnerText));
            if (text.Length > 0)
            {
                inlines.Add(new Run(text));
            }

            return;
        }

        var name = NodeName(node);
        switch (name)
        {
            case "br":
                inlines.Add(new LineBreak());
                break;
            case "strong":
            case "b":
                var bold = new Bold();
                AppendInlineChildren(bold.Inlines, node, baseUri, insideLink);
                inlines.Add(bold);
                break;
            case "em":
            case "i":
                var italic = new Italic();
                AppendInlineChildren(italic.Inlines, node, baseUri, insideLink);
                inlines.Add(italic);
                break;
            case "code":
            case "kbd":
            case "samp":
                var code = new Span { FontFamily = new FontFamily("Consolas"), Background = CodeBackgroundBrush };
                AppendInlineChildren(code.Inlines, node, baseUri, insideLink);
                inlines.Add(code);
                break;
            case "a":
                if (insideLink)
                {
                    AppendInlineChildren(inlines, node, baseUri, true);
                }
                else
                {
                    AppendLink(inlines, node, baseUri);
                }
                break;
            case "img":
                if (insideLink)
                {
                    AppendImageText(inlines, node);
                }
                else
                {
                    AppendImageLink(inlines, node, baseUri);
                }
                break;
            case "ul":
            case "ol":
                foreach (var li in node.ChildNodes.Where(child => NodeName(child) == "li"))
                {
                    inlines.Add(new LineBreak());
                    inlines.Add(new Run(name == "ol" ? "1. " : "• "));
                    AppendInlineChildren(inlines, li, baseUri, insideLink);
                }
                break;
            default:
                AppendInlineChildren(inlines, node, baseUri, insideLink);
                break;
        }
    }

    private static void AppendLink(InlineCollection inlines, HtmlNode node, Uri? baseUri)
    {
        var href = WebUtility.HtmlDecode(node.GetAttributeValue("href", "")).Trim();
        var uri = ResolveUri(href, baseUri);
        if (uri is null)
        {
            AppendInlineChildren(inlines, node, baseUri);
            return;
        }

        var link = new Hyperlink { NavigateUri = uri, Foreground = LinkBrush };
        link.RequestNavigate += OpenLink;
        AppendInlineChildren(link.Inlines, node, baseUri, true);
        if (link.Inlines.Count == 0)
        {
            link.Inlines.Add(new Run(uri.ToString()));
        }

        inlines.Add(link);
    }

    private static void AppendImageLink(InlineCollection inlines, HtmlNode node, Uri? baseUri)
    {
        var src = WebUtility.HtmlDecode(node.GetAttributeValue("src", "")).Trim();
        var uri = ResolveUri(src, baseUri);
        if (uri is null)
        {
            return;
        }

        var alt = WebUtility.HtmlDecode(node.GetAttributeValue("alt", "")).Trim();
        var link = new Hyperlink(new Run(ImageText(alt)))
        {
            NavigateUri = uri,
            Foreground = LinkBrush
        };
        link.RequestNavigate += OpenLink;
        inlines.Add(link);
    }

    private static void AppendImageText(InlineCollection inlines, HtmlNode node)
    {
        var alt = WebUtility.HtmlDecode(node.GetAttributeValue("alt", "")).Trim();
        inlines.Add(new Run(ImageText(alt)));
    }

    private static string ImageText(string alt)
    {
        return string.IsNullOrWhiteSpace(alt) ? "[图片]" : $"[图片：{alt}]";
    }

    private static Paragraph CreateParagraph()
    {
        return new Paragraph
        {
            Margin = new Thickness(0, 0, 0, 13),
            LineHeight = 26
        };
    }

    private static void AddParagraphIfContent(FlowDocument document, Paragraph paragraph)
    {
        AddParagraphIfContent(document.Blocks, paragraph);
    }

    private static void AddParagraphIfContent(BlockCollection blocks, Paragraph paragraph)
    {
        if (HasText(paragraph))
        {
            blocks.Add(paragraph);
        }
    }

    private static bool HasText(Paragraph paragraph)
    {
        return new TextRange(paragraph.ContentStart, paragraph.ContentEnd).Text.Trim().Length > 0;
    }

    private static bool IsIgnored(HtmlNode node)
    {
        var name = NodeName(node);
        return node.NodeType == HtmlNodeType.Comment || name is "script" or "style" or "noscript" or "svg";
    }

    private static bool IsBlockNode(HtmlNode node)
    {
        if (node.NodeType != HtmlNodeType.Element)
        {
            return false;
        }

        return NodeName(node) is "p" or "div" or "section" or "article" or "header" or "footer" or "main" or "aside"
            or "h1" or "h2" or "h3" or "h4" or "h5" or "h6"
            or "ul" or "ol" or "li" or "blockquote" or "pre" or "table" or "tr" or "hr" or "figure" or "figcaption" or "address";
    }

    private static string NodeName(HtmlNode node)
    {
        return node.Name.ToLowerInvariant();
    }

    private static bool LooksLikeHtml(string value)
    {
        return HtmlTagRegex().IsMatch(value);
    }

    private static string NormalizeInlineText(string text)
    {
        return InlineSpaceRegex().Replace(text, " ");
    }

    private static Uri? ResolveUri(string value, Uri? baseUri)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return null;
        }

        if (Uri.TryCreate(value, UriKind.Absolute, out var absolute))
        {
            return absolute;
        }

        return baseUri is not null && Uri.TryCreate(baseUri, value, out var relative) ? relative : null;
    }

    private static void OpenLink(object sender, RequestNavigateEventArgs e)
    {
        Process.Start(new ProcessStartInfo(e.Uri.ToString()) { UseShellExecute = true });
        e.Handled = true;
    }

    private static Brush Brush(string value)
    {
        var brush = (SolidColorBrush)new BrushConverter().ConvertFromString(value)!;
        brush.Freeze();
        return brush;
    }

    [GeneratedRegex("<\\s*/?\\s*[a-zA-Z][^>]*>")]
    private static partial Regex HtmlTagRegex();

    [GeneratedRegex("[\\t\\r\\n ]+")]
    private static partial Regex InlineSpaceRegex();

    [GeneratedRegex("\\n\\s*\\n+")]
    private static partial Regex PlainParagraphRegex();
}
