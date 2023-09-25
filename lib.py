import logging
from typing import TypedDict, List
from outline_vpn.outline_vpn import OutlineKey, OutlineVPN
import yaml

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%d-%m-%Y %H:%M:%S')
log = logging.getLogger('OutlineFleet.lib')


class ServerDict(TypedDict):
    name: str
    url: str
    cert: str
    comment: str
    server_id: str
    metrics_enabled: str
    created_timestamp_ms: int
    version: str
    port_for_new_access_keys: int
    hostname_for_access_keys: str
    keys: List[OutlineKey]


class Server:
    def __init__(self,
                 url: str,
                 cert: str,
                 comment: str,
                 ):
        self.client = OutlineVPN(api_url=url, cert_sha256=cert)
        self.data: ServerDict = {
            'name': self.client.get_server_information()["name"],
            'url': url,
            'cert': cert,
            'comment': comment,
            'server_id': self.client.get_server_information()["serverId"],
            'metrics_enabled': self.client.get_server_information()["metricsEnabled"],
            'created_timestamp_ms': self.client.get_server_information()["createdTimestampMs"],
            'version': self.client.get_server_information()["version"],
            'port_for_new_access_keys': self.client.get_server_information()["portForNewAccessKeys"],
            'hostname_for_access_keys': self.client.get_server_information()["hostnameForAccessKeys"],
            'keys': self.client.get_keys()
        }

    def info(self) -> ServerDict:
        return self.data

    def apply_config(self, config):
        if config.get("name"):
            self.client.set_server_name(config.get("name"))
            log.info("Changed %s name to '%s'", self.data["server_id"], config.get("name"))
        if config.get("metrics"):
            self.client.set_metrics_status(True if config.get("metrics") == 'True' else False)
            log.info("Changed %s metrics status to '%s'", self.data["server_id"], config.get("metrics"))
        if config.get("port_for_new_access_keys"):
            self.client.set_port_new_for_access_keys(int(config.get("port_for_new_access_keys")))
            log.info("Changed %s port_for_new_access_keys to '%s'", self.data["server_id"], config.get("port_for_new_access_keys"))
        if config.get("hostname_for_access_keys"):
            self.client.set_hostname(config.get("hostname_for_access_keys"))
            log.info("Changed %s hostname_for_access_keys to '%s'", self.data["server_id"], config.get("hostname_for_access_keys"))
        if config.get("comment"):
            with open("config.yaml", "r") as file:
                config_file = yaml.safe_load(file) or {}
            config_file["servers"][self.data['server_id']]['comment'] = config.get("comment")
            with open("config.yaml", "w") as file:
                yaml.safe_dump(config_file, file)
            log.info("Changed %s comment to '%s'", self.data["server_id"], config.get("comment"))

    def create_key(self, key_name):
        return self.client.create_key(key_name)