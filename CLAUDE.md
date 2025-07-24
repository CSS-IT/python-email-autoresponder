# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python 3 email autoresponder that monitors an IMAP inbox and automatically replies to incoming emails. It's a single-file script (`run_autoresponder.py`) that uses only Python standard library modules.

## Running the Application

```bash
# Basic usage (requires configuration file)
python3 run_autoresponder.py

# With custom config file
python3 run_autoresponder.py /path/to/config.ini
```

## Configuration

The application requires an `autoresponder.config.ini` file. Create one from the example:
```bash
cp autoresponder.config.ini.example autoresponder.config.ini
# Then edit with your mail server details
```

For HTML emails, create a response template:
```bash
cp responseBody.html.example responseBody.html
# Edit to customize the HTML template
```

## Code Architecture

The codebase follows a procedural architecture with these main components:

1. **Configuration Loading**: Uses `configparser.RawConfigParser` to handle special characters in passwords
2. **Server Connections**: Manages both IMAP (incoming) and SMTP (outgoing) connections
3. **Email Processing**: Fetches emails, applies filters, sends replies, and moves to trash
4. **Error Handling**: Centralized through `shutdown_with_error()` function

Key functions:
- `connect_to_imap()` / `connect_to_smtp()`: Server connection management
- `process_email()`: Core logic for email processing
- `send_reply()`: Handles reply composition and sending
- `cast()`: Safe type conversion utility

## Important Patterns

- **Global State**: Configuration and server connections are stored in global variables
- **Template Variables**: `[SUBJECT]` and `[BODY]` are replaced in response templates
- **Debug Mode**: When enabled in config, prints detailed operation logs
- **Error Recovery**: No automatic retry - errors cause immediate shutdown

## Development Notes

- No external dependencies - uses only Python standard library
- No test suite or linting configuration present
- Requires Python 3 (uses features not available in Python 2)
- Configuration uses raw parsing to avoid interpolation issues with special characters

## Common Tasks

### Adding New Configuration Options
1. Add to `autoresponder.config.ini.example`
2. Update the configuration loading section in `run_autoresponder.py`
3. Update README.md documentation tables

### Modifying Email Processing Logic
The main processing happens in the `process_email()` function. Key areas:
- Email filtering: Check sender against `filters_senderContains`
- Reply address selection: Uses Reply-To header, falls back to From
- Template processing: Variable replacement happens in `send_reply()`

### Debugging Issues
1. Enable debug mode in config: `debug = true`
2. Check console output for detailed operation logs
3. Common issues are in server connections (ports, SSL/TLS) and authentication