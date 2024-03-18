import argparse
import logging
import threading
from typing import TypedDict, List
from outline_vpn.outline_vpn import OutlineKey, OutlineVPN
import yaml
import k8s


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%d-%m-%Y %H:%M:%S",
)

log = logging.getLogger(f'OutFleet.lib')
parser = argparse.ArgumentParser()
parser.add_argument(
    "-c",
    "--config",
    default="/usr/local/etc/outfleet/config.yaml",
    help="Config file location",
)

lock = threading.Lock()


args = parser.parse_args()
def get_config():
    if k8s.CONFIG:
        return k8s.CONFIG
    else:
        try:
            with open(args.config, "r") as file:
                config = yaml.safe_load(file)
        except:
            try:
                with open(args.config, "w"):
                    pass
            except Exception as exp:
                log.error(f"Couldn't create config. {exp}")
                return None
        return config
    
def write_config(config):
    if k8s.CONFIG:
        k8s.write_config(config)
    else:
        try:
            with open(args.config, "w") as file:
                yaml.safe_dump(config, file)
        except Exception as e:
            log.error(f"Couldn't write Outfleet config: {e}")


class ServerDict(TypedDict):
    server_id: str
    local_server_id: str
    name: str
    url: str
    cert: str
    comment: str
    metrics_enabled: str
    created_timestamp_ms: int
    version: str
    port_for_new_access_keys: int
    hostname_for_access_keys: str
    keys: List[OutlineKey]


class Server:
    def __init__(
        self,
        url: str,
        cert: str,
        comment: str,
        # read from config. not the same as real server id you can get from api
        local_server_id: str,
    ):
        self.client = OutlineVPN(api_url=url, cert_sha256=cert)
        self.data: ServerDict = {
            "local_server_id": local_server_id,
            "name": self.client.get_server_information()["name"],
            "url": url,
            "cert": cert,
            "comment": comment,
            "server_id": self.client.get_server_information()["serverId"],
            "metrics_enabled": self.client.get_server_information()["metricsEnabled"],
            "created_timestamp_ms": self.client.get_server_information()[
                "createdTimestampMs"
            ],
            "version": self.client.get_server_information()["version"],
            "port_for_new_access_keys": self.client.get_server_information()[
                "portForNewAccessKeys"
            ],
            "hostname_for_access_keys": self.client.get_server_information()[
                "hostnameForAccessKeys"
            ],
            "keys": self.client.get_keys(),
        }
        self.log = logging.getLogger(f'OutFleet.server[{self.data["name"]}]')
        file_handler = logging.FileHandler("sync.log")
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(formatter)
        self.log.addHandler(file_handler)

    def info(self) -> ServerDict:
        return self.data

    def check_client(self, name):
        # Looking for any users with provided name. len(result) != 1 is a problem.
        result = []
        for key in self.client.get_keys():
            if key.key_id == name:
                result.append(name)
                self.log.info(f"check_client found client `{name}` config is correct.")
        if len(result) != 1:
            self.log.warning(
                f"check_client found client `{name}` inconsistent. Found {len(result)} keys."
            )
            return False
        else:
            return True

    def apply_config(self, config, CFG_PATH):
        if config.get("name"):
            self.client.set_server_name(config.get("name"))
            self.log.info(
                "Changed %s name to '%s'", self.data["local_server_id"], config.get("name")
            )
        if config.get("metrics"):
            self.client.set_metrics_status(
                True if config.get("metrics") == "True" else False
            )
            self.log.info(
                "Changed %s metrics status to '%s'",
                self.data["local_server_id"],
                config.get("metrics"),
            )
        if config.get("port_for_new_access_keys"):
            self.client.set_port_new_for_access_keys(
                int(config.get("port_for_new_access_keys"))
            )
            self.log.info(
                "Changed %s port_for_new_access_keys to '%s'",
                self.data["local_server_id"],
                config.get("port_for_new_access_keys"),
            )
        if config.get("hostname_for_access_keys"):
            self.client.set_hostname(config.get("hostname_for_access_keys"))
            self.log.info(
                "Changed %s hostname_for_access_keys to '%s'",
                self.data["local_server_id"],
                config.get("hostname_for_access_keys"),
            )
        if config.get("comment"):
            config_file = get_config()
            config_file["servers"][self.data["local_server_id"]]["comment"] = config.get(
                "comment"
            )
            write_config(config_file)
            self.log.info(
                "Changed %s comment to '%s'",
                self.data["local_server_id"],
                config.get("comment"),
            )

    def create_key(self, key_name):
        self.client.create_key(key_id=key_name, name=key_name)
        self.log.info("New key created: %s", key_name)
        return True

    def rename_key(self, key_id, new_name):
        self.log.info("Key %s renamed: %s", key_id, new_name)
        return self.client.rename_key(key_id, new_name)

    def delete_key(self, key_id):
        self.log.info("Key %s deleted", key_id)
        return self.client.delete_key(key_id)
