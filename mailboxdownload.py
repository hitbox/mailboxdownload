import argparse
import base64
import importlib.util
import json
import logging.config
import os

from configparser import ConfigParser
from pprint import pprint

import msal
import requests

from msal import ConfidentialClientApplication

APPNAME = 'mailboxdownload'
FILEATTACHMENT_TYPE = '#microsoft.graph.fileAttachment'

logger = logging.getLogger(APPNAME)

def unique_for_exists(path):
    test = path
    i = 0
    while os.path.exists(test):
        root, ext = os.path.splitext(path)
        test = f'{root}.{i}{ext}'
        i += 1
    return test

def messages_url(mailbox):
    return f"https://graph.microsoft.com/v1.0/users/{mailbox}/mailFolders('Inbox')/messages"

def attachments_url(mailbox, message):
    message_id = message['id']
    return f"https://graph.microsoft.com/v1.0/users/{mailbox}/messages/{message_id}/attachments"

def iter_messages(mailbox, headers):
    url = messages_url(mailbox)
    while url:
        response = requests.get(url, headers=headers)
        data = response.json()
        for msg in data.get('value', []):
            yield msg
        url = data.get('@odata.nextLink')

def iter_attachments(mailbox, message, headers):
    attach_url = attachments_url(mailbox, message)
    attach_resp = requests.get(attach_url, headers=headers)
    attach_resp.raise_for_status()
    attachments = attach_resp.json().get('value', [])
    yield from attachments

def ensure_log_dirs():
    for logger_name in logging.root.manager.loggerDict:
        logger = logging.getLogger(logger_name)
        for handler in logger.handlers:
            if hasattr(handler, 'baseFilename'):
                directory = os.path.dirname(handler.baseFilename)
                os.makedirs(directory, exist_ok=True)

def ensure_dir_for(path):
    directory = os.path.dirname(os.path.abspath(path))
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
    return path

def realmain(cp):
    appconf = cp[APPNAME]

    filename = appconf.get('filename', '{message[subject]} - {attachment[name]}')
    archive_path = appconf['message_archive']
    mailbox = appconf['mailbox']
    tenant_id = appconf['tenant_id']
    client_id = appconf['client_id']
    client_secret = appconf['client_secret']
    authority = f"https://login.microsoftonline.com/{tenant_id}"
    scope = ["https://graph.microsoft.com/.default"]

    # Ensure directories exists

    if os.path.exists(archive_path):
        with open(archive_path, 'r') as archive_file:
            archive = json.load(archive_file)
    else:
        logger.info('archive %s not found using empty list', archive_path)
        archive = list()

    app = ConfidentialClientApplication(
        client_id,
        authority = authority,
        client_credential = client_secret
    )

    result = app.acquire_token_for_client(scopes=scope)
    if 'access_token' not in result:
        raise KeyError(f"Failed to get token: {result.get('error_description')}")

    # Emails sent daily at 1800 ET
    token = result["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    for message in iter_messages(mailbox, headers):
        message_id = message['id']
        if not message.get('hasAttachments'):
            logger.info('skip no-attachments message: %s', message['id'])
            continue

        attachments = iter_attachments(mailbox, message, headers)
        for attachment_index, attachment in enumerate(attachments):
            attachment_name = attachment.get('name')

            # Check message, attachment pair already seen.
            if any(
                arch['message_id'] == message_id
                and
                arch['attachment_name'] == attachment_name
                for arch in archive
            ):
                logger.info('skip attachment %s for message: %s',
                            attachment_name, message_id)
                continue

            # Format string for download filename
            context = {
                'message': message,
                'attachment': attachment,
            }
            path = unique_for_exists(os.path.normpath(filename.format(**context)))
            logger.info('read message id: %s, attachment: %s', message['id'], path)
            if attachment.get('@odata.type') == FILEATTACHMENT_TYPE:
                content_bytes = attachment.get('contentBytes')
                if content_bytes:
                    # Save attachment to file, creating dirs if missing.
                    data = base64.b64decode(content_bytes)
                    ensure_dir_for(path)
                    with open(path, 'wb') as output_file:
                        output_file.write(data)
                        logger.info('%s saved to %s', attachment_name, path)
                    # Save data to archive list
                    archive.append({
                        'message_id': message_id,
                        'attachment_name': attachment_name,
                        'saved': path,
                    })

    # Save archive to file.
    os.makedirs(os.path.dirname(archive_path), exist_ok=True)
    with open(archive_path, 'w') as archive_file:
        json.dump(archive, archive_file)

def argument_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('config')
    parser.add_argument('--debug')
    return parser

def main(argv=None):
    parser = argument_parser()
    args = parser.parse_args(argv)

    cp = ConfigParser()
    cp.read(args.config)

    if set(['loggers', 'handlers', 'formatters']).issubset(cp):
        logging.config.fileConfig(cp, disable_existing_loggers=False)

    try:
        realmain(cp)
    except:
        logger.exception('An exception occurred.')

if __name__ == '__main__':
    main()
