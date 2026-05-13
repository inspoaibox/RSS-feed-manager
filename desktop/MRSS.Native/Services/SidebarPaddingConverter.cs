using System.Globalization;
using System.Windows;
using System.Windows.Data;

namespace MRSS.Native.Services;

public sealed class SidebarPaddingConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
    {
        var level = value is int intValue ? intValue : 0;
        return new Thickness(10 + level * 18, 8, 10, 8);
    }

    public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture)
    {
        throw new NotSupportedException();
    }
}
