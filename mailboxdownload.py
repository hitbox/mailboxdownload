import argparse
import base64
import importlib.util
import json
import logging.config
import os
import sys

from datetime import datetime
from configparser import ConfigParser
from pprint import pprint

import msal
import requests

from bs4 import BeautifulSoup
from msal import ConfidentialClientApplication

from parse import parse_wgl_table

APPNAME = 'mailboxdownload'
FILEATTACHMENT_TYPE = '#microsoft.graph.fileAttachment'

logger = logging.getLogger(APPNAME)

class GraphClient:
    """
    Convenience for iterating messages and attachments in mailboxes through MS Graph.
    """

    scopes = ["https://graph.microsoft.com/.default"]

    def __init__(self, tenant_id, client_id, client_secret):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.token = None

    @classmethod
    def from_config(cls, appconf):
        tenant_id = appconf['tenant_id']
        client_id = appconf['client_id']
        client_secret = appconf['client_secret']
        return cls(tenant_id, client_id, client_secret)

    @property
    def authority(self):
        return f"https://login.microsoftonline.com/{self.tenant_id}"

    @property
    def headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    def messages_url(self, mailbox):
        return (
            f"https://graph.microsoft.com/v1.0/users/{mailbox}"
            f"/mailFolders('Inbox')/messages"
        )


    def attachments_url(self, mailbox, message):
        message_id = message['id']
        return (
            f"https://graph.microsoft.com/v1.0/users/{mailbox}/"
            f"messages/{message_id}/attachments"
        )

    def ensure_token(self):
        if self.token is None:
            app = ConfidentialClientApplication(
                self.client_id,
                client_credential = self.client_secret,
                authority = self.authority,
            )

            result = app.acquire_token_for_client(scopes=self.scopes)
            if 'access_token' not in result:
                raise KeyError(f"Failed to get token: {result.get('error_description')}")

            self.token = result["access_token"]

    def iter_messages(self, mailbox):
        self.ensure_token()
        url = self.messages_url(mailbox)
        while url:
            response = requests.get(url, headers=self.headers)
            data = response.json()
            for msg in data.get('value', []):
                yield msg
            url = data.get('@odata.nextLink')

    def iter_attachments(self, mailbox, message):
        attach_url = self.attachments_url(mailbox, message)
        attach_resp = requests.get(attach_url, headers=self.headers)
        attach_resp.raise_for_status()
        attachments = attach_resp.json().get('value', [])
        yield from attachments

    def iter_messages_with_attachments(self, mailbox):
        for message in self.iter_messages(mailbox):
            attachments = self.iter_attachments(mailbox, message)
            for attachment in attachments:
                yield (message, attachment)


def unique_for_exists(path):
    test = path
    i = 0
    while os.path.exists(test):
        root, ext = os.path.splitext(path)
        test = f'{root}.{i}{ext}'
        i += 1
    return test

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

def is_html_attachment(attachment):
    odata_type = attachment['@odata.type']
    odata_media_content_type = attachment['@odata.mediaContentType']
    return (
        odata_type == '#microsoft.graph.fileAttachment'
        and
        odata_media_content_type == 'text/html'
    )

def decode_attachment_file(attachment):
    content_bytes = attachment.get('contentBytes')
    if content_bytes:
        # Save attachment to file, creating dirs if missing.
        data = base64.b64decode(content_bytes)
        return data

def argument_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('config')
    parser.add_argument('--debug')
    return parser

def parse_wgl_legend(legend_table_soup):
    """
    Parse the legend table into a (bgcolor, description) dict.
    """
    legend = {}
    # The legend table is a three-column table describing the color codes for
    # rows and what they mean.
    for row in legend_table_soup('tr'):
        # The first <td> is empty. Alignment I guess.
        empty_td, legend_key, legend_description = row('td')
        bgcolor = legend_key['bgcolor']
        description = legend_description.get_text()
        legend[bgcolor] = description
    return legend

def find_or_raise(soup, *args, **kwargs):
    result = soup.find(*args, **kwargs)
    if not result:
        raise ValueError(
            f'Soup not found for {args}, {kwargs}')
    return result

def upsert_fresh_message_attachments(
    client,
    session,
    model,
    schema,
    mailbox,
):
    """
    Update or insert new records for session/model from mailbox html
    attachments parsed and deserialized by schema.
    """
    pairs = client.iter_messages_with_attachments(mailbox)
    for message, attachment in pairs:
        exists = model.instance_for_message_attachment(session, message, attachment)
        if not exists:
            if is_html_attachment(attachment):
                html = decode_attachment_file(attachment)
                soup = BeautifulSoup(html, 'html.parser')
                report_table = find_or_raise(soup, 'table', id='tblReportList')
                for data in parse_wgl_table(report_table):
                    data = schema.load(data)
                    instance = model.one_or_none_from_data(session, data)
                    if instance is None:
                        instance = model.new_from_data(data, message, attachment)
                        session.add(instance)
                        logger.info('added %s', data)
                    else:
                        instance.update_from_data(data, message, attachment)
                        logger.info('updated %s', data)

    session.commit()
