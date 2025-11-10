import argparse
import base64
import importlib.util
import logging.config
import os
import os
import sys

from configparser import ConfigParser
from pprint import pprint

import msal
import requests

from msal import ConfidentialClientApplication
from schema import GraphMessageSchema

APPNAME = 'mailboxdownload'

logger = logging.getLogger(APPNAME)

class GraphSource:

    endpoint_string = 'https://graph.microsoft.com/v1.0/users/{username}/messages'

    authority_string = 'https://login.microsoftonline.com/{tenant_id}'

    def __init__(
        self,
        *, # keyword arguments only
        tenant_id,
        client_id,
        secret,
        scopes,
        username,
        password,
        schema = None,
        select = None,
        **options,
    ):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.secret = secret
        self.scopes = scopes
        self.username = username
        self.password = password
        if schema is None:
            schema = GraphMessageSchema()
        self.schema = schema
        self.options = options

    @property
    def authority(self):
        return self.authority_string.format(tenant_id=self.tenant_id)

    @property
    def endpoint(self):
        context = {
            'username': self.username,
        }
        return self.endpoint_string.format(**context)

    def itermessages(self):
        app = msal.ConfidentialClientApplication(
            client_id = self.client_id,
            authority = self.authority,
            client_credential = self.secret,
        )
        # NOTE: in practice, the checks and loops over in hello_graph_api
        #       always go to username/password.
        token_result = app.acquire_token_by_username_password(
            self.username, self.password, scopes=self.scopes,
        )
        access_token = token_result['access_token']
        # accumulate messages until no nextLink
        headers = {'Authorization': f'Bearer {access_token}'}
        endpoint = self.endpoint
        while True:
            response = requests.get(endpoint, headers=headers)
            response.raise_for_status()
            data = response.json()
            messages = data['value']
            if self.schema:
                messages = self.schema.load(messages, many=True)
            yield from messages
            if '@odata.nextLink' not in data:
                break
            endpoint = data['@odata.nextLink']


class MailboxDownload:

    def __init__(
        self,
        *,
        source,
        dest,
    ):
        self.source = source
        self.dest = dest


def load_module_from_path(path, module_name = None):
    """
    Dynamically load a Python file as a module, like Flask does with config .py files.

    Args:
        path (str): Path to the Python file to load.
        module_name (str | None): Optional name to assign to the loaded module.
                                  Defaults to basename of the file (without extension).
    """
    path = os.path.abspath(path)

    if not os.path.exists(path):
        raise FileNotFoundError(f"Config file not found: {path}")

    if module_name is None:
        module_name = os.path.splitext(os.path.basename(path))[0]

    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module from {path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('config')
    parser.add_argument('--debug')
    args = parser.parse_args(argv)

    cp = ConfigParser()
    cp.read(args.config)

    appconf = cp[APPNAME]

    mailbox = appconf['mailbox']
    tenant_id = appconf['tenant_id']
    client_id = appconf['client_id']
    client_secret = appconf['client_secret']
    authority = f"https://login.microsoftonline.com/{tenant_id}"
    scope = ["https://graph.microsoft.com/.default"]

    app = ConfidentialClientApplication(
        client_id,
        authority = authority,
        client_credential = client_secret
    )

    message_schema = GraphMessageSchema()

    result = app.acquire_token_for_client(scopes=scope)
    if "access_token" not in result:
        raise Exception(f"Failed to get token: {result.get('error_description')}")

    # Emails sent daily at 1800 ET
    token = result["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://graph.microsoft.com/v1.0/users/{mailbox}/mailFolders('Inbox')/messages"
    resp = requests.get(url, headers=headers)
    messages = resp.json()
    for message in messages['value']:
        message = message_schema.load(message)
        pprint(message)
    breakpoint()

if __name__ == '__main__':
    main()
