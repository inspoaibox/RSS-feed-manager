namespace MRSS.Native.Models;

public enum NavKind
{
    All,
    Category,
    Feed,
    Uncategorized
}

public sealed class NavItem
{
    public NavKind Kind { get; init; }
    public int? Id { get; init; }
    public string Title { get; init; } = "";
    public string Subtitle { get; init; } = "";
    public int Level { get; init; }
    public string IconText { get; init; } = "";
    public string? IconPath { get; init; }
    public string IconColor { get; init; } = "#0F766E";
    public bool IsExpanded { get; init; }
    public bool HasChildren { get; init; }
    public bool HasIconPath => !string.IsNullOrWhiteSpace(IconPath);
    public bool HasNoIconPath => !HasIconPath;
    public bool CanToggle => HasChildren;
    public string ExpandGlyph => !HasChildren ? "" : IsExpanded ? "⌄" : "›";

    public string Key => Kind == NavKind.All ? "all" : $"{Kind}:{Id}";
}

public sealed class FilterChoice
{
    public string Label { get; init; } = "";
    public bool IsSelected { get; init; }
}
