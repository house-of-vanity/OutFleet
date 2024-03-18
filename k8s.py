import base64
import json
import yaml
import logging
from kubernetes import client, config
from kubernetes.client.rest import ApiException

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%d-%m-%Y %H:%M:%S",
)

log = logging.getLogger("OutFleet.k8s")
file_handler = logging.FileHandler("sync.log")
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
file_handler.setFormatter(formatter)
log.addHandler(file_handler)

def write_config(config):
    config_map = client.V1ConfigMap(
        api_version="v1",
        kind="ConfigMap",
        metadata=client.V1ObjectMeta(
            name=f"config-outfleet",
            labels={
                "app": "outfleet",
            }
        ),
        data={"config.yaml": yaml.dump(config)}
    )
    try:
        api_response = v1.create_namespaced_config_map(
            namespace=NAMESPACE,
            body=config_map,
        )
    except ApiException as e:
        api_response = v1.patch_namespaced_config_map(
            name="config-outfleet",
            namespace=NAMESPACE,
            body=config_map,
        )

config.load_incluster_config()

v1 = client.CoreV1Api()

NAMESPACE = False
SERVERS = list()
CONFIG = None

log.info("Checking for Kubernetes environment")
try:
    with open("/var/run/secrets/kubernetes.io/serviceaccount/namespace") as f:
        NAMESPACE = f.read().strip()
        log.info(f"Found Kubernetes environment. Namespace {NAMESPACE}")
except IOError:
    log.info("Kubernetes environment not detected")
    pass

# config = v1.list_namespaced_config_map(NAMESPACE, label_selector="app=outfleet").items["data"]["config.yaml"]
try:
    CONFIG = yaml.safe_load(v1.read_namespaced_config_map(name="config-outfleet", namespace=NAMESPACE).data['config.yaml'])
    log.info(f"ConfigMap config.yaml loaded from Kubernetes API. Servers: {len(CONFIG['servers'])}, Clients: {len(CONFIG['clients'])}")
except ApiException as e:
    log.warning(f"ConfigMap not found. Fisrt run?")

#servers = v1.list_namespaced_secret(NAMESPACE, label_selector="app=shadowbox")

if not CONFIG:
    log.info(f"Creating new ConfigMap [config-outfleet]")
    write_config({"clients": [], "servers": [], "ui_hostname": "accessible-address.com"})
    CONFIG = yaml.safe_load(v1.read_namespaced_config_map(name="config-outfleet", namespace=NAMESPACE).data['config.yaml'])

