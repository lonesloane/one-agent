namespace SpikeServer.Logging;

/// <summary>
/// Thin request logger for the AG-UI endpoint boundary.
/// Logs each incoming request's method, path, Content-Type, and body length so that
/// F1 (approval not rendered) and F2 (multi-turn 400) symptoms can be diagnosed from
/// logs alone without an attached debugger.
/// </summary>
/// <remarks>
/// Hand-rolled because the package Microsoft.Agents.AI.Hosting.AGUI.AspNetCore 1.3.0-preview.260423.1
/// exposes no built-in tracing extension (verified 2026-05-01 by reflection: only 2 public
/// types in the assembly). Registered as Singleton; stateless beyond the injected logger.
/// </remarks>
internal sealed class AGUIRequestLogger
{
    private readonly ILogger<AGUIRequestLogger> _logger;

    public AGUIRequestLogger(ILogger<AGUIRequestLogger> logger)
    {
        _logger = logger;
    }

    /// <summary>
    /// Middleware delegate that logs AG-UI request metadata then calls the next handler.
    /// </summary>
    public async Task LogRequestAsync(HttpContext context, RequestDelegate next)
    {
        // Enable buffering so the body can be read for length inspection without consuming
        // it before the AGUI handler can deserialize it.
        context.Request.EnableBuffering();

        long bodyLength = context.Request.ContentLength ?? -1;
        string contentType = context.Request.ContentType ?? "(none)";
        string method = context.Request.Method;
        string path = context.Request.Path;

        _logger.LogInformation(
            "AG-UI request {Method} {Path} Content-Type={ContentType} ContentLength={BodyLength}",
            method, path, contentType, bodyLength);

        // Seek back so the downstream AGUI handler can read the body.
        if (context.Request.Body.CanSeek)
        {
            context.Request.Body.Seek(0, SeekOrigin.Begin);
        }

        long startTimestamp = System.Diagnostics.Stopwatch.GetTimestamp();

        try
        {
            await next(context);
        }
        catch (Exception ex)
        {
            _logger.LogError(
                ex,
                "AG-UI handler threw exception for {Method} {Path}",
                method, path);
            throw;
        }
        finally
        {
            double elapsedMs = System.Diagnostics.Stopwatch.GetElapsedTime(startTimestamp).TotalMilliseconds;
            _logger.LogInformation(
                "AG-UI response {Method} {Path} StatusCode={StatusCode} ElapsedMs={ElapsedMs:F1}",
                method, path, context.Response.StatusCode, elapsedMs);
        }
    }
}
