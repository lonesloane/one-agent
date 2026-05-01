using System.ComponentModel;

namespace SpikeServer.Tools;

/// <summary>
/// Static tool methods registered as AIFunctions for the spike agent.
/// Names are overridden to snake_case via AIFunctionFactoryOptions so they match
/// the parity reference's instructions string (list_records / create_record).
/// </summary>
internal static class RecordTools
{
    /// <summary>Return a comma-separated list of records.</summary>
    [Description("Return a comma-separated list of records.")]
    public static string ListRecords() =>
        string.Join(", ", RecordStore.List());

    /// <summary>Create a new record with the given name.</summary>
    [Description("Create a new record with the given name.")]
    public static string CreateRecord(
        [Description("Name of the record to create")] string name)
    {
        int total = RecordStore.Add(name);
        return $"Record '{name}' created. Total: {total}.";
    }
}
