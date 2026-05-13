using System.IO;

namespace MRSS.Native.Services;

public static class AppPaths
{
    public const string DatabaseName = "mrss.db";

    public static string DataDirectory
    {
        get
        {
            var basePath = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
            if (string.IsNullOrWhiteSpace(basePath))
            {
                basePath = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
            }

            var path = Path.Combine(basePath, "MRSS");
            Directory.CreateDirectory(path);
            return path;
        }
    }

    public static string DatabasePath => Path.Combine(DataDirectory, DatabaseName);

    public static string IconCacheDirectory
    {
        get
        {
            var path = Path.Combine(DataDirectory, "icons");
            Directory.CreateDirectory(path);
            return path;
        }
    }
}
