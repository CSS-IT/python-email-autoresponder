#!/usr/bin/python
import configparser
import datetime
import email
import email.header
import email.mime.text
import imaplib
import os
import re
import smtplib
import sys
from _socket import gaierror

config = None
config_file_path = "autoresponder.config.ini"
incoming_mail_server = None
outgoing_mail_server = None
statistics = {
    "start_time": datetime.datetime.now(),
    "mails_loading_error": 0,
    "mails_total": 0,
    "mails_processed": 0,
    "mails_in_trash": 0,
    "mails_wrong_sender": 0
}


def run():
    get_config_file_path()
    initialize_configuration()
    connect_to_mail_servers()
    check_folder_names()
    mails = fetch_emails()
    for mail in mails:
        process_email(mail)
    log_statistics()
    shutdown(0)


def get_config_file_path():
    if "--help" in sys.argv or "-h" in sys.argv:
        display_help_text()
    if "--config-path" in sys.argv and len(sys.argv) >= 3:
        global config_file_path
        config_file_path = sys.argv[2]
    if not os.path.isfile(config_file_path):
        shutdown_with_error("Configuration file not found. Expected it at '" + config_file_path + "'.")


def initialize_configuration():
    try:
        # Use RawConfigParser to avoid interpolation of special characters like %
        config_file = configparser.RawConfigParser()
        config_file.read(config_file_path, encoding="UTF-8")
        global config
        config = {
            'in.user': cast(config_file["login credentials"]["mailserver.incoming.username"], str),
            'in.pw': cast(config_file["login credentials"]["mailserver.incoming.password"], str),
            'out.user': cast(config_file["login credentials"]["mailserver.outgoing.username"], str),
            'out.pw': cast(config_file["login credentials"]["mailserver.outgoing.password"], str),
            'display.name': cast(config_file["login credentials"]["mailserver.outgoing.display.name"], str),
            'display.mail': cast(config_file["login credentials"]["mailserver.outgoing.display.mail"], str),
            'in.host': cast(config_file["mail server settings"]["mailserver.incoming.imap.host"], str),
            'in.port': cast(config_file["mail server settings"]["mailserver.incoming.imap.port.ssl"], str),
            'out.host': cast(config_file["mail server settings"]["mailserver.outgoing.smtp.host"], str),
            'out.port': cast(config_file["mail server settings"]["mailserver.outgoing.smtp.port.tls"], str),
            'folders.inbox': cast(config_file["mail server settings"]["mailserver.incoming.folders.inbox.name"], str),
            'folders.trash': cast(config_file["mail server settings"]["mailserver.incoming.folders.trash.name"], str),
            'request.from': cast(config_file["mail content settings"]["mail.request.from"], str),
            'reply.subject': cast(config_file["mail content settings"]["mail.reply.subject"], str).strip()
        }
        
        # Try to get reply.body, but make it optional
        try:
            config['reply.body'] = cast(config_file["mail content settings"]["mail.reply.body"], str).strip()
        except KeyError:
            config['reply.body'] = ""
        
        # Add debug setting with default value False if not specified
        try:
            debug_value = config_file["general settings"]["debug"].lower()
            config['debug'] = debug_value in ['true', '1', 'yes', 'on']
        except (KeyError, AttributeError):
            config['debug'] = False
        
        # Check for external response body file
        config_dir = os.path.dirname(os.path.abspath(config_file_path))
        html_file = os.path.join(config_dir, "responseBody.html")
        
        if os.path.isfile(html_file):
            with open(html_file, 'r', encoding='UTF-8') as f:
                config['reply.body'] = f.read()
                config['reply.body.is_html'] = True
        else:
            config['reply.body.is_html'] = False
    except KeyError as e:
        shutdown_with_error("Configuration file is invalid! (Key not found: " + str(e) + ")")


def connect_to_mail_servers():
    connect_to_imap()
    connect_to_smtp()


def check_folder_names():
    (retcode, msg_count) = incoming_mail_server.select(config['folders.inbox'])
    if retcode != "OK":
        list_available_folders()
        shutdown_with_error("Inbox folder does not exist: " + config['folders.inbox'])
    (retcode, msg_count) = incoming_mail_server.select(config['folders.trash'])
    if retcode != "OK":
        list_available_folders()
        shutdown_with_error("Trash folder does not exist: " + config['folders.trash'])


def list_available_folders():
    print("\nAvailable IMAP folders on this server:")
    print("=" * 40)
    try:
        # List all folders
        retcode, folders = incoming_mail_server.list()
        if retcode == 'OK':
            for folder in folders:
                # Parse folder name from IMAP response
                folder_str = folder.decode('utf-8')
                # Debug: show raw folder string
                log_debug("Raw folder response: " + folder_str)
                
                # Try different parsing methods
                folder_name = None
                
                # Method 1: Split by quotes
                parts = folder_str.split('"')
                if len(parts) >= 2:
                    folder_name = parts[-2]
                
                # Method 2: If no quotes, try to find folder name after delimiter
                if not folder_name or folder_name == ".":
                    # Look for pattern like (\HasNoChildren) "." "INBOX"
                    import re
                    match = re.search(r'["\s]([^"\s]+)["]*$', folder_str.strip())
                    if match:
                        folder_name = match.group(1)
                
                # Method 3: Split by spaces and take last part
                if not folder_name or folder_name == ".":
                    parts = folder_str.strip().split()
                    if parts:
                        folder_name = parts[-1].strip('"')
                
                if folder_name and folder_name != ".":
                    print("  - " + folder_name)
                else:
                    # Show the raw string if we couldn't parse it
                    print("  - [Could not parse: " + folder_str + "]")
                    
        print("=" * 40)
        print("Please update your config file with the correct folder names.")
        print("Common trash folder names: Trash, Deleted, Deleted Items, Papierkorb, Corbeille\n")
    except Exception as e:
        print("Could not list folders: " + str(e))


def connect_to_imap():
    try:
        log_debug("Connecting to IMAP server " + config['in.host'] + ":" + config['in.port'])
        do_connect_to_imap()
        log_debug("Successfully connected to IMAP server")
    except gaierror:
        shutdown_with_error("IMAP connection failed! Specified host not found.")
    except imaplib.IMAP4_SSL.error as e:
        shutdown_with_error("IMAP login failed! Reason: '" + cast(e.args[0], str, 'UTF-8') + "'.")
    except Exception as e:
        shutdown_with_error("IMAP connection/login failed! Reason: '" + cast(e, str) + "'.")


def do_connect_to_imap():
    global incoming_mail_server
    incoming_mail_server = imaplib.IMAP4_SSL(config['in.host'], config['in.port'])
    (retcode, capabilities) = incoming_mail_server.login(config['in.user'], config['in.pw'])
    if retcode != "OK":
        shutdown_with_error("IMAP login failed! Return code: '" + cast(retcode, str) + "'.")


def connect_to_smtp():
    try:
        log_debug("Connecting to SMTP server " + config['out.host'] + ":" + config['out.port'])
        do_connect_to_smtp()
        log_debug("Successfully connected to SMTP server")
    except gaierror:
        shutdown_with_error("SMTP connection failed! Specified host not found.")
    except smtplib.SMTPAuthenticationError as e:
        shutdown_with_error("SMTP login failed! Reason: '" + cast(e.smtp_error, str, 'UTF-8') + "'.")
    except Exception as e:
        shutdown_with_error("SMTP connection/login failed! Reason: '" + cast(e, str) + "'.")


def do_connect_to_smtp():
    global outgoing_mail_server
    outgoing_mail_server = smtplib.SMTP(config['out.host'], config['out.port'])
    outgoing_mail_server.starttls()
    (retcode, capabilities) = outgoing_mail_server.login(config['out.user'], config['out.pw'])
    if not (retcode == 235 or retcode == 250):
        shutdown_with_error("SMTP login failed! Return code: '" + str(retcode) + "'.")


def fetch_emails():
    # get the message ids from the inbox folder
    incoming_mail_server.select(config['folders.inbox'])
    (retcode, message_indices) = incoming_mail_server.search(None, 'ALL')
    if retcode == 'OK':
        messages = []
        log_debug("Found " + str(len(message_indices[0].split())) + " emails in inbox")
        for message_index in message_indices[0].split():
            # get the actual message for the current index
            (retcode, data) = incoming_mail_server.fetch(message_index, '(RFC822)')
            if retcode == 'OK':
                # parse the message into a useful format
                message = email.message_from_string(data[0][1].decode('utf-8'))
                (retcode, data) = incoming_mail_server.fetch(message_index, "(UID)")
                if retcode == 'OK':
                    mail_uid = parse_uid(cast(data[0], str, 'UTF-8'))
                    message['mailserver_email_uid'] = mail_uid
                    messages.append(message)
                else:
                    statistics['mails_loading_error'] += 1
                    log_warning("Failed to get UID for email with index '" + message_index + "'.")
            else:
                statistics['mails_loading_error'] += 1
                log_warning("Failed to get email with index '" + message_index + "'.")
        statistics['mails_total'] = len(messages)
        return messages
    else:
        return []


def process_email(mail):
    try:
        mail_from = email.header.decode_header(mail['From'])
        mail_sender = mail_from[-1]
        mail_sender = cast(mail_sender[0], str, 'UTF-8')
        log_debug("Processing email from: " + mail_sender)
        
        # Check if we should filter by sender or respond to all emails
        if config['request.from'] == '' or config['request.from'] == '*':
            # No filtering - respond to all emails
            log_debug("No sender filter active - responding to email")
            reply_to_email(mail)
            delete_email(mail)
        elif config['request.from'] in mail_sender:
            # Filter by sender
            log_debug("Sender matches filter '" + config['request.from'] + "' - responding to email")
            reply_to_email(mail)
            delete_email(mail)
        else:
            log_debug("Sender does not match filter '" + config['request.from'] + "' - skipping email")
            statistics['mails_wrong_sender'] += 1
        statistics['mails_processed'] += 1
    except Exception as e:
        log_warning("Unexpected error while processing email: '" + str(e) + "'.")


def reply_to_email(mail):
    try:
        # Try to get Reply-To header, fallback to From if not present
        if mail.get('Reply-To'):
            # Decode Reply-To header
            reply_to_header = email.header.decode_header(mail['Reply-To'])
            if reply_to_header and reply_to_header[0]:
                receiver_email = str(reply_to_header[0][0])
                # Clean up the email address
                receiver_email = receiver_email.strip()
                # Remove any angle brackets if present
                if '<' in receiver_email and '>' in receiver_email:
                    email_match = re.search(r'<(.+?)>', receiver_email)
                    if email_match:
                        receiver_email = email_match.group(1)
            else:
                raise ValueError("Empty Reply-To header")
        else:
            # Extract email from From header
            from_header = email.header.decode_header(mail['From'])
            from_str = ''
            for part, encoding in from_header:
                if isinstance(part, bytes):
                    from_str += part.decode(encoding or 'utf-8', errors='ignore')
                else:
                    from_str += str(part)
            
            # Extract email address from string like "Name <email@example.com>"
            email_match = re.search(r'<(.+?)>', from_str)
            if email_match:
                receiver_email = email_match.group(1)
            else:
                # If no angle brackets, assume the whole string is the email
                receiver_email = from_str.strip()
        
        # Validate email format (basic check)
        if not receiver_email or '@' not in receiver_email:
            raise ValueError("Invalid email format: " + str(receiver_email))
        
        log_debug("Sending reply to: " + str(receiver_email))
        
        # Replace template variables in subject and body
        reply_subject = replace_template_variables(config['reply.subject'], mail)
        reply_body = replace_template_variables(config['reply.body'], mail)
        
        # Create appropriate message type based on content
        if config.get('reply.body.is_html', False):
            # Create HTML email
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
            
            message = MIMEMultipart('alternative')
            message['Subject'] = reply_subject
            message['To'] = receiver_email
            message['From'] = email.utils.formataddr((
                cast(email.header.Header(config['display.name'], 'utf-8'), str), config['display.mail']))
            
            # Create plain text version (strip HTML tags for basic plain text)
            plain_text = re.sub('<[^<]+?>', '', reply_body)
            part1 = MIMEText(plain_text, 'plain', 'utf-8')
            part2 = MIMEText(reply_body, 'html', 'utf-8')
            
            message.attach(part1)
            message.attach(part2)
        else:
            # Create plain text email
            message = email.mime.text.MIMEText(reply_body, 'plain', 'utf-8')
            message['Subject'] = reply_subject
            message['To'] = receiver_email
            message['From'] = email.utils.formataddr((
                cast(email.header.Header(config['display.name'], 'utf-8'), str), config['display.mail']))
        
        outgoing_mail_server.sendmail(config['display.mail'], receiver_email, message.as_string())
        log_debug("Reply sent successfully")
        
    except Exception as e:
        # If we can't send the reply due to invalid email address, just log it
        log_warning("Could not send reply due to invalid recipient address: " + str(e))
        # Don't re-raise - we still want to delete the email


def delete_email(mail):
    log_debug("Moving email to trash folder")
    result = incoming_mail_server.uid('COPY', mail['mailserver_email_uid'], config['folders.trash'])
    if result[0] == "OK":
        statistics['mails_in_trash'] += 1
        log_debug("Email moved to trash successfully")
    else:
        log_warning("Copying email to trash failed. Reason: " + str(result))
    incoming_mail_server.uid('STORE', mail['mailserver_email_uid'], '+FLAGS', r'(\Deleted)')
    incoming_mail_server.expunge()


def parse_uid(data):
    pattern_uid = re.compile(r'\d+ \(UID (?P<uid>\d+)\)')
    match = pattern_uid.match(data)
    return match.group('uid')


def get_email_body(mail):
    """Extract the body text from an email message."""
    body = ""
    
    if mail.is_multipart():
        # Walk through all parts
        for part in mail.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get('Content-Disposition', ''))
            
            # Skip attachments
            if 'attachment' in content_disposition:
                continue
                
            # Get text/plain and text/html parts
            if content_type == 'text/plain':
                try:
                    body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    break  # Prefer plain text
                except:
                    pass
            elif content_type == 'text/html' and not body:
                try:
                    html_body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                    # Simple HTML to text conversion
                    body = re.sub('<[^<]+?>', '', html_body)
                except:
                    pass
    else:
        # Not multipart - just get the payload
        try:
            body = mail.get_payload(decode=True).decode('utf-8', errors='ignore')
        except:
            body = str(mail.get_payload())
    
    return body.strip()


def replace_template_variables(text, mail):
    """Replace template variables with actual values from the email."""
    # Get original subject
    subject = mail.get('Subject', '')
    if subject:
        decoded_subject = email.header.decode_header(subject)
        subject_str = ''
        for part, encoding in decoded_subject:
            if isinstance(part, bytes):
                subject_str += part.decode(encoding or 'utf-8', errors='ignore')
            else:
                subject_str += str(part)
        subject = subject_str
    
    # Get original body
    body = get_email_body(mail)
    
    # Replace variables
    text = text.replace('[SUBJECT]', subject)
    text = text.replace('[BODY]', body)
    
    # Also support lowercase variants
    text = text.replace('[subject]', subject)
    text = text.replace('[body]', body)
    
    return text


def cast(obj, to_type, options=None):
    try:
        if options is None:
            return to_type(obj)
        else:
            return to_type(obj, options)
    except ValueError and TypeError:
        return obj


def shutdown_with_error(message):
    message = "Error! " + str(message)
    message += "\nCurrent configuration file path: '" + str(config_file_path) + "'."
    if config is not None:
        # Create a safe version of config without passwords
        safe_config = config.copy()
        if 'in.pw' in safe_config:
            safe_config['in.pw'] = '******'
        if 'out.pw' in safe_config:
            safe_config['out.pw'] = '******'
        message += "\nCurrent configuration: " + str(safe_config)
    print(message)
    shutdown(-1)


def log_warning(message):
    print("Warning! " + message)


def log_debug(message):
    if config and config.get('debug', False):
        print("[DEBUG] " + message)


def log_statistics():
    if config.get('debug', False):
        run_time = datetime.datetime.now() - statistics['start_time']
        total_mails = statistics['mails_total']
        loading_errors = statistics['mails_loading_error']
        wrong_sender_count = statistics['mails_wrong_sender']
        processing_errors = total_mails - statistics['mails_processed']
        moving_errors = statistics['mails_processed'] - statistics['mails_in_trash'] - statistics['mails_wrong_sender']
        total_warnings = loading_errors + processing_errors + moving_errors
        message = "Executed "
        message += "without warnings " if total_warnings == 0 else "with " + str(total_warnings) + " warnings "
        message += "in " + str(run_time.total_seconds()) + " seconds. "
        message += "Found " + str(total_mails) + " emails in inbox"
        message += ". " if wrong_sender_count == 0 else " with " + str(wrong_sender_count) + " emails from wrong senders. "
        message += "Processed " + str(statistics['mails_processed']) + \
                   " emails, replied to " + str(total_mails - wrong_sender_count) + " emails. "
        if total_warnings != 0:
            message += "Encountered " + str(loading_errors) + " errors while loading emails, " + \
                       str(processing_errors) + " errors while processing emails and " + \
                       str(moving_errors) + " errors while moving emails to trash."
        print(message)


def display_help_text():
    print("Options:")
    print("\t--help: Display this help information")
    print("\t--config-path <path/to/config/file>: "
          "Override path to config file (defaults to same directory as the script is)")
    exit(0)


def shutdown(error_code):
    if incoming_mail_server is not None:
        try:
            incoming_mail_server.close()
        except Exception:
            pass
        try:
            incoming_mail_server.logout()
        except Exception:
            pass
    if outgoing_mail_server is not None:
        try:
            outgoing_mail_server.quit()
        except Exception:
            pass
    exit(error_code)


run()
