namespace SpikeServer.Tools;

/// <summary>
/// In-memory record store seeded with two initial values.
/// Thread-safety is not required for the spike (single-threaded request flow).
/// </summary>
internal static class RecordStore
{
    private static readonly List<string> _records = ["alpha", "beta"];

    /// <summary>Returns the current record list as a read-only view.</summary>
    public static IReadOnlyList<string> List() => _records.AsReadOnly();

    /// <summary>Appends <paramref name="name"/> and returns the new total count.</summary>
    public static int Add(string name)
    {
        _records.Add(name);
        return _records.Count;
    }
}
