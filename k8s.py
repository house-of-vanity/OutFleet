import base64
import json
import uuid
import yaml
import logging
import threading
import time

import lib
from kubernetes import client, config as kube_config
from kubernetes.client.rest import ApiException

log = logging.getLogger("OutFleet.k8s")

NAMESPACE = False
SERVERS = list()
CONFIG = None
V1 = None
K8S_DETECTED = False


def discovery_servers():
    global CONFIG
    interval = 60
    log = logging.getLogger("OutFleet.discovery")

    if K8S_DETECTED:
        while True:
            pods = V1.list_namespaced_pod(NAMESPACE, label_selector="app=shadowbox")
            log.debug(f"Started discovery thread every {interval}")
            for pod in pods.items:
                log.debug(f"Found Outline server pod {pod.metadata.name}")
                container_log = V1.read_namespaced_pod_log(name=pod.metadata.name, namespace=NAMESPACE, container='manager-config-json')
                secret = json.loads(container_log.replace('\'', '\"'))
                config = lib.get_config()
                config_servers = find_server(secret, config["servers"])
                #log.info(f"config_servers {config_servers}")
                if len(config_servers) > 0:
                    log.debug(f"Already exist")
                    pass
                else:
                    with lib.lock:
                        config["servers"][str(uuid.uuid4())] = {
                            "cert": secret["certSha256"],
                            "name": f"{pod.metadata.name}",
                            "comment": f"{pod.spec.node_name}",
                            "url": secret["apiUrl"],
                        }
                        write_config(config)
                    log.info(f"Added discovered server")
            time.sleep(interval)
        
        



def find_server(search_data, servers):
    found_servers = {}
    for server_id, server_info in servers.items():
        if server_info["url"] == search_data["apiUrl"] and server_info["cert"] == search_data["certSha256"]:
            found_servers[server_id] = server_info
    return found_servers



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
        api_response = V1.create_namespaced_config_map(
            namespace=NAMESPACE,
            body=config_map,
        )
    except ApiException as e:
        api_response = V1.patch_namespaced_config_map(
            name="config-outfleet",
            namespace=NAMESPACE,
            body=config_map,
        )
    log.info("Updated config in Kubernetes ConfigMap [config-outfleet]")


def reload_config():
    global CONFIG
    while True:
        new_config = yaml.safe_load(V1.read_namespaced_config_map(name="config-outfleet", namespace=NAMESPACE).data['config.yaml'])
        with lib.lock:
            CONFIG = new_config
        log.debug(f"Synced system config with ConfigMap [config-outfleet].")
        time.sleep(30)


try:
    kube_config.load_incluster_config()
    V1 = client.CoreV1Api()
    if V1 != None:
        K8S_DETECTED = True
    try:
        with open("/var/run/secrets/kubernetes.io/serviceaccount/namespace") as f:
            NAMESPACE = f.read().strip()
        log.info(f"Found Kubernetes environment. Deployed to namespace '{NAMESPACE}'")
        try:
            CONFIG = yaml.safe_load(V1.read_namespaced_config_map(name="config-outfleet", namespace=NAMESPACE).data['config.yaml'])
            log.info(f"ConfigMap loaded from Kubernetes API. Servers: {len(CONFIG['servers'])}, Clients: {len(CONFIG['clients'])}. Started monitoring for changes every minute.")
        except Exception as e:
            try:
                write_config({"clients": [], "servers": {}, "ui_hostname": "accessible-address.com"})
                CONFIG = yaml.safe_load(V1.read_namespaced_config_map(name="config-outfleet", namespace=NAMESPACE).data['config.yaml'])
                log.info("Created new ConfigMap [config-outfleet]. Started monitoring for changes every minute.")
            except Exception as e:
                log.info(f"Failed to create new ConfigMap [config-outfleet] {e}")
        thread = threading.Thread(target=reload_config)
        thread.start()
        
    except:
        log.info("Kubernetes environment not detected")
except:
    log.info("Kubernetes environment not detected")

