# Python E-Mail Autoresponder

Simple python script that connects to a mail server via IMAP and SMTP and replies to emails in the inbox using the Reply-To header.
You can filter by sender address or respond to all emails. Supports HTML formatted responses.
Mails that have been replied to are deleted afterwards.

### Dependencies

This script runs on python3 and is written for the purpose of running as a cronjob.

To run it you'll only need  **python3**.

### Important Notes on Passwords

This script supports strong passwords with special characters. The configuration file uses raw parsing, so you can use any characters in your passwords including `%`, `$`, `@`, etc. without escaping.

### Installation

To install, simply download a copy of the project (see screenshot below) and extract it to whatever folder you like.

![Github Archive Download](https://user-images.githubusercontent.com/6501308/33236233-4de2d6fe-d24d-11e7-9581-9a59d9615c12.PNG)

Alternatively, on UNIX systems you can run

``wget https://github.com/sunborn23/python-email-autoresponder/archive/master.zip && unzip master.zip``

to download and then extract all project files.

### Configuration 

Before first run, you need to adapt the project to your needs by editing the `autoresponder.config.ini` file with a text editor.

The required configuration items for the individual sections are listed below.

**Section [login credentials]**

| Configuration Item | Description |
| ------------------ | ----------- |
| mailserver.incoming.username     | The username to use for logging in at the IMAP server hosting the inbox, usually an email address. |
| mailserver.incoming.password     | The password to use for logging in at the IMAP server hosting the inbox. |
| mailserver.outgoing.username     | The username to use for logging in at the SMTP server for sending the reply, usually an email address. |
| mailserver.outgoing.password     | The password to use for logging in at the SMTP server for sending the reply. |
| mailserver.outgoing.display.name | The name to use in the email's "From" field indicating where the reply email is from. |
| mailserver.outgoing.display.mail | The email address to use in the email's "From" field, should normally be a no-reply address. |

**Section [mail server settings]**

| Configuration Item | Description  |
| ------------------ | ------------ |
| mailserver.incoming.imap.host     | The hostname, domain or IP of the IMAP server hosting the inbox. |
| mailserver.incoming.imap.port.ssl | The port to use for SSL communication with the IMAP server. |
| mailserver.outgoing.smtp.host     | The hostname, domain or IP of the SMTP server for sending the reply. |
| mailserver.outgoing.smtp.port.tls | The port to use for TLS communication with the SMTP server. |
| mailserver.folders.inbox.name     | The name of the inbox folder, normally this is "Inbox". |
| mailserver.folders.trash.name     | The name of the trash folder, normally this is "Trash" or "Deleted Items". |

**Section [mail content settings]**

| Configuration Item | Description |
| ------------------ | ----------- |
| mail.request.from  | The sender email address to check new mails against. Use `*` or leave empty to respond to all emails. |
| mail.reply.subject | The subject line of the reply email. |
| mail.reply.body    | The plain text body of the reply email. This is used only if no `responseBody.html` file is present. |

**Section [general settings]** (optional)

| Configuration Item | Description |
| ------------------ | ----------- |
| debug              | Enable debug logging. Set to `true`, `1`, `yes`, or `on` to enable. Default is `false`. |

### HTML Email Support

To send HTML formatted emails instead of plain text:

1. Create a file named `responseBody.html` in the same directory as your `autoresponder.config.ini`
2. Add your HTML content to this file
3. The script will automatically detect and use the HTML file
4. Both HTML and plain text versions will be sent (multipart email)

Example `responseBody.html`:
```html
<html>
<body>
<h1>Automatic Reply</h1>
<p>Thank you for your email!</p>
<p>We have received your message and will respond <strong>as soon as possible</strong>.</p>
<br>
<p>Best regards,<br>
Your Support Team</p>
</body>
</html>
```

After configuring the project, you can run it manually to test if your configuration works.

### Manual Usage

For testing purposes you can run the script from the shell. To do so, navigate to the project directory and run 

    python3 run_autoresponder.py

If you want to run the script multiple times with different configurations on each executions, 
you can achieve that by running

    python3 run_autoresponder.py --config-path /the/path/to/your/config/file/autoresponder.config.ini

### Usage as a cronjob

For production use you can configure it as a cronjob.

From the shell, run:

	crontab -e

Then append to the file (replace "/the/path/to/the/project/folder" by the actual path to these files):

	*/1 * * * * python3 /the/path/to/the/project/folder/run_autoresponder.py

This will run the script every minute.

You can use any [Online](https://crontab-generator.org/) 
[Cron](https://www.freeformatter.com/cron-expression-generator-quartz.html) 
[Expression](http://www.cronmaker.com/) 
[Generator](http://cron.nmonitoring.com/cron-generator.html) for generating other cron expressions.

For info on how to craft the cron expression yourself, run `man crontab`.
