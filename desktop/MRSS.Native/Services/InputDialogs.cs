using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;

namespace MRSS.Native.Services;

public static class InputDialogs
{
    public static string? AskText(Window owner, string title, string label, string initial = "", bool password = false)
    {
        var window = DialogWindow(owner, title, 440, 190);
        var root = DialogRoot(window);
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });

        root.Children.Add(new TextBlock
        {
            Text = label,
            FontSize = 14,
            FontWeight = FontWeights.SemiBold,
            Margin = new Thickness(0, 0, 0, 8)
        });

        Control input;
        if (password)
        {
            var box = new PasswordBox { Height = 36, Password = initial };
            input = box;
        }
        else
        {
            var box = new TextBox { Height = 36, Text = initial };
            input = box;
        }

        Grid.SetRow(input, 1);
        root.Children.Add(input);

        var buttons = Buttons(window, () => password ? ((PasswordBox)input).Password : ((TextBox)input).Text);
        Grid.SetRow(buttons, 2);
        root.Children.Add(buttons);

        window.Content = root;
        window.Loaded += (_, _) => input.Focus();
        return window.ShowDialog() == true ? (string?)window.Tag : null;
    }

    public static int? AskInt(Window owner, string title, string label, int initial, int min, int max)
    {
        while (true)
        {
            var raw = AskText(owner, title, label, initial.ToString());
            if (raw is null)
            {
                return null;
            }

            if (int.TryParse(raw.Trim(), out var value) && value >= min && value <= max)
            {
                return value;
            }

            MessageBox.Show(owner, $"请输入 {min} 到 {max} 之间的数字。", title, MessageBoxButton.OK, MessageBoxImage.Warning);
        }
    }

    private static Window DialogWindow(Window owner, string title, double width, double height)
    {
        return new Window
        {
            Owner = owner,
            Title = title,
            Width = width,
            Height = height,
            WindowStartupLocation = WindowStartupLocation.CenterOwner,
            ResizeMode = ResizeMode.NoResize,
            Background = System.Windows.Media.Brushes.White,
            ShowInTaskbar = false
        };
    }

    private static Grid DialogRoot(Window window)
    {
        var root = new Grid { Margin = new Thickness(22) };
        root.InputBindings.Add(new KeyBinding(new RelayCommand(() => window.DialogResult = false), Key.Escape, ModifierKeys.None));
        return root;
    }

    private static FrameworkElement Buttons(Window window, Func<string> getValue)
    {
        var panel = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            HorizontalAlignment = HorizontalAlignment.Right,
            Margin = new Thickness(0, 18, 0, 0)
        };
        var cancel = new Button { Content = "取消", Width = 82, Height = 34, Margin = new Thickness(0, 0, 8, 0) };
        cancel.Click += (_, _) => window.DialogResult = false;
        var ok = new Button { Content = "确定", Width = 82, Height = 34, IsDefault = true };
        ok.Click += (_, _) =>
        {
            window.Tag = getValue();
            window.DialogResult = true;
        };
        panel.Children.Add(cancel);
        panel.Children.Add(ok);
        return panel;
    }
}
