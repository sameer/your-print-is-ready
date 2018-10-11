from collections import namedtuple, OrderedDict
from typing import Dict
from zeroconf import ServiceInfo
import requests
from requests.auth import HTTPDigestAuth
from config import ultimaker_application_name, ultimaker_user_name, ultimaker_credentials_filename
import json

# The mDNS response looks like this:
#   ServiceInfo(
#       type='_printer._tcp.local.',
#       name='ultimakersystem-REDACTED._printer._tcp.local.',
#       address=b'\xc0\xa8\x01\x12',
#       port=80,
#       weight=0,
#       priority=0,
#       server='ultimakersystem-REDACTED.local.',
#       properties={
#           b'type': b'printer',
#           b'hotend_serial_0': b'REDACTED',
#           b'cluster_size': b'1',
#           b'firmware_version': b'4.3.3.20180529',
#           b'machine': b'REDACTED',
#           b'name': b'U1',
#           b'hotend_type_0': b'AA 0.4'
#       }
#   )

# Serial number identifying the machine


class Serial(str):
    def __init__(self, serial_string: str = None):
        self.serial_string = serial_string


# A user/password pair
Credentials = namedtuple('Credentials', ['id', 'key'])


class CredentialsDict(OrderedDict):
    def __init__(self, credentials_filename):
        self.credentials_filename = credentials_filename
        with open(credentials_filename, 'w+') as credentials_file:
            try:
                credentials_json = json.load(credentials_file)
            except Exception as e:
                print(
                    f'Exception in parsing credentials.json, pretending it is empty: {e}')
                credentials_json = {}
        for serial, credentials in credentials_json.items():
            try:
                # Convert json to a dictionary of field to value mappings
                kwargs = dict([(field, credentials[field])
                               for field in Credentials._fields])
                self[Serial(serial_string=serial)] = Credentials(**kwargs)
            except Exception as e:
                print(
                    f'Exception in parsing a credential in credentials.json with serial {serial}, skipping it: {e}')

    def save(self):
        credentials_json: Dict[str, str] = {}
        for serial, credentials in credentials_json.items():
            credentials_json[serial] = credentials._asdict()
        with open(self.credentials_filename, 'w+') as credentials_file:
            json.dump(self, credentials_file)


ultimaker_credentials_dict: Dict[Serial, Credentials] = CredentialsDict(
    ultimaker_credentials_filename)


class Printer():
    def __init__(self, name, address, port):
        self.name = name
        self.address = address
        self.port = port
        self.credentials_dict = ultimaker_credentials_dict

    def acquire_credentials(self):
        if self.name in self.credentials_dict:
            if self.get_auth_verify():
                return
            else:
                del self.credentials_dict[self.name]
        credentials_json = self.post_auth_request()
        self.save_credentials(credentials_json)

    def is_authorized(self) -> bool:
        if self.name in self.credentials_dict:
            if self.get_auth_verify():
                return self.get_auth_check() == "authorized"
        return False

    def save_credentials(self, credentials_json: Dict):
        self.credentials_dict[Credentials(**credentials_json)]
        self.credentials_dict.save()

    def post_auth_request(self) -> Dict:
        res = requests.post(url=f"{self.address}/auth/request",
                            data={'application': ultimaker_application_name, 'user': ultimaker_user_name})
        return json.load(res.content)

    def get_auth_check(self) -> str:
        res = requests.get(url=f"{self.address}/auth/check",
                           params={'id': self.credentials_dict[self.name].id})
        return json.load(res.content)["message"]

    def get_auth_verify(self) -> bool:
        credentials = self.credentials_dict[self.name]
        res = requests.get(url=f"{self.address}/auth/verify",
                           auth=HTTPDigestAuth(credentials.id, credentials.key))
        return res.ok
