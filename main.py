import threading
import time
import yaml
import logging
from datetime import datetime
import random
import string
import argparse
import uuid


import k8s
from flask import Flask, render_template, request, url_for, redirect
from flask_cors import CORS
from lib import Server, write_config, get_config, args


logging.getLogger("werkzeug").setLevel(logging.ERROR)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%d-%m-%Y %H:%M:%S",
)

log = logging.getLogger("OutFleet")
file_handler = logging.FileHandler("sync.log")
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
file_handler.setFormatter(formatter)
log.addHandler(file_handler)


CFG_PATH = args.config
NAMESPACE = k8s.NAMESPACE
SERVERS = list()
BROKEN_SERVERS = list()
CLIENTS = dict()
VERSION = '4'
HOSTNAME = ""
app = Flask(__name__)
CORS(app)


def format_timestamp(ts):
    return datetime.fromtimestamp(ts // 1000).strftime("%Y-%m-%d %H:%M:%S")


def random_string(length=64):
    letters = string.ascii_letters + string.digits

    return "".join(random.choice(letters) for i in range(length))



def update_state():
    while True:
        global SERVERS
        global CLIENTS
        global BROKEN_SERVERS
        global HOSTNAME

        SERVERS = list()
        BROKEN_SERVERS = list()
        CLIENTS = dict()
        config = get_config()

        if config:
            HOSTNAME = config.get("ui_hostname", "my-own-SSL-ENABLED-domain.com")
            servers = config.get("servers", dict())
            for local_server_id, server_config in servers.items():
                try:
                    server = Server(
                        url=server_config["url"],
                        cert=server_config["cert"],
                        comment=server_config["comment"],
                        local_server_id=local_server_id,
                    )
                    SERVERS.append(server)
                    log.debug(
                        "Server state updated: %s, [%s]",
                        server.info()["name"],
                        local_server_id,
                    )
                except Exception as e:
                    BROKEN_SERVERS.append({
                        "config": server_config,
                        "error": e,
                        "id": local_server_id
                    })
                    log.warning("Can't access server: %s - %s", server_config["url"], e)

            CLIENTS = config.get("clients", dict())
        time.sleep(40)


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        #if request.args.get("broken") == True:
        return render_template(
            "index.html",
            SERVERS=SERVERS,
            VERSION=VERSION,
            K8S_NAMESPACE=k8s.NAMESPACE,
            BROKEN_SERVERS=BROKEN_SERVERS,
            nt=request.args.get("nt"),
            nl=request.args.get("nl"),
            selected_server=request.args.get("selected_server"),
            broken=request.args.get("broken", False),
            add_server=request.args.get("add_server", None),
            format_timestamp=format_timestamp,
        )
    elif request.method == "POST":
        server = request.form["server_id"]
        server = next(
            (item for item in SERVERS if item.info()["local_server_id"] == server), None
        )
        server.apply_config(request.form, CFG_PATH)
        update_state()
        return redirect(
            url_for(
                "index",
                nt="Updated Outline VPN Server",
                selected_server=request.args.get("selected_server"),
            )
        )
    else:
        return redirect(url_for("index"))


@app.route("/clients", methods=["GET", "POST"])
def clients():
    if request.method == "GET":
        return render_template(
            "clients.html",
            SERVERS=SERVERS,
            CLIENTS=CLIENTS,
            VERSION=VERSION,
            K8S_NAMESPACE=k8s.NAMESPACE,
            nt=request.args.get("nt"),
            nl=request.args.get("nl"),
            selected_client=request.args.get("selected_client"),
            add_client=request.args.get("add_client", None),
            format_timestamp=format_timestamp,
            dynamic_hostname=HOSTNAME,
        )


@app.route("/add_server", methods=["POST"])
def add_server():
    if request.method == "POST":
        try:
            config = get_config()
            servers = config.get("servers", dict())
            local_server_id = str(uuid.uuid4())

            new_server = Server(
                url=request.form["url"],
                cert=request.form["cert"],
                comment=request.form["comment"],
                local_server_id=local_server_id,
            )

            servers[new_server.data["local_server_id"]] = {
                "name": new_server.data["name"],
                "url": new_server.data["url"],
                "comment": new_server.data["comment"],
                "cert": request.form["cert"],
            }
            config["servers"] = servers
            write_config(config)
            log.info("Added server: %s", new_server.data["name"])
            update_state()
            return redirect(url_for("index", nt="Added Outline VPN Server"))
        except Exception as e:
            return redirect(
                url_for(
                    "index", nt=f"Couldn't access Outline VPN Server: {e}", nl="error"
                )
            )

@app.route("/del_server", methods=["POST"])
def del_server():
    if request.method == "POST":
        config = get_config()

        local_server_id = request.form.get("local_server_id")
        server_name = None
        try:
            server_name = config["servers"].pop(local_server_id)["name"]
        except KeyError as e:
                pass
        for client_id, client_config in config["clients"].items():
            try:
                client_config["servers"].remove(local_server_id)
            except ValueError as e:
                pass
        write_config(config)
        log.info("Deleting server %s [%s]", server_name, request.form.get("local_server_id"))
    update_state()
    return redirect(url_for("index", nt=f"Server {server_name} has been deleted"))


@app.route("/add_client", methods=["POST"])
def add_client():
    if request.method == "POST":
        config = get_config()

        clients = config.get("clients", dict())
        user_id = request.form.get("user_id", random_string())

        clients[user_id] = {
            "name": request.form.get("name"),
            "comment": request.form.get("comment"),
            "servers": request.form.getlist("servers"),
        }
        config["clients"] = clients
        write_config(config)
        log.info("Client %s updated", request.form.get("name"))

        for server in SERVERS:
            if server.data["local_server_id"] in request.form.getlist("servers"):
                client = next(
                    (
                        item
                        for item in server.data["keys"]
                        if item.name == request.form.get("old_name")
                    ),
                    None,
                )
                if client:
                    if client.name == request.form.get("name"):
                        pass
                    else:
                        server.rename_key(client.key_id, request.form.get("name"))
                        log.info(
                            "Renaming key %s to %s on server %s",
                            request.form.get("old_name"),
                            request.form.get("name"),
                            server.data["name"],
                        )
                else:
                    server.create_key(request.form.get("name"))
                    log.info(
                        "Creating key %s on server %s",
                        request.form.get("name"),
                        server.data["name"],
                    )
            else:
                client = next(
                    (
                        item
                        for item in server.data["keys"]
                        if item.name == request.form.get("old_name")
                    ),
                    None,
                )
                if client:
                    server.delete_key(client.key_id)
                    log.info(
                        "Deleting key %s on server %s",
                        request.form.get("name"),
                        server.data["name"],
                    )
        update_state()
        return redirect(
            url_for(
                "clients",
                nt="Clients updated",
                selected_client=request.form.get("user_id"),
            )
        )
    else:
        return redirect(url_for("clients"))


@app.route("/del_client", methods=["POST"])
def del_client():
    if request.method == "POST":
        config = get_config()
        clients = config.get("clients", dict())
        user_id = request.form.get("user_id")
        if user_id in clients:
            for server in SERVERS:
                client = next(
                    (
                        item
                        for item in server.data["keys"]
                        if item.name == request.form.get("name")
                    ),
                    None,
                )
                if client:
                    server.delete_key(client.key_id)

        config["clients"].pop(user_id)
        write_config(config)
        log.info("Deleting client %s", request.form.get("name"))
    update_state()
    return redirect(url_for("clients", nt="User has been deleted"))


@app.route("/dynamic/<server_name>/<client_id>", methods=["GET"], strict_slashes=False)
def dynamic(server_name, client_id):
    try:
        client = next(
            (keys for client, keys in CLIENTS.items() if client == client_id), None
        )
        server = next(
            (item for item in SERVERS if item.info()["name"] == server_name), None
        )
        key = next(
            (item for item in server.data["keys"] if item.key_id == client["name"]), None
        )
        if server and client and key:
            if server.data["local_server_id"] in client["servers"]:
                log.info(
                    "Client %s wants ssconf for %s", client["name"], server.data["name"]
                )
                return {
                    "server": server.data["hostname_for_access_keys"],
                    "server_port": key.port,
                    "password": key.password,
                    "method": key.method,
                    "info": "Managed by OutFleet [github.com/house-of-vanity/OutFleet/]",
                }
        else:
            log.warning(
                "Hack attempt! Client %s denied by ACL on %s",
                client["name"],
                server.data["name"],
            )
            return "Hey buddy, i think you got the wrong door the leather-club is two blocks down"
    except:
        log.warning("Hack attempt! Client or server doesn't exist. SCAM")
        return "Hey buddy, i think you got the wrong door the leather-club is two blocks down"


@app.route("/dynamic/", methods=["GET"], strict_slashes=False)
def _dynamic():
    log.warning("Hack attempt! Client or server doesn't exist. SCAM")
    return (
        "Hey buddy, i think you got the wrong door the leather-club is two blocks down"
    )


@app.route("/sync", methods=["GET", "POST"])
def sync():
    if request.method == "GET":
        try:
            with open("sync.log", "r") as file:
                lines = file.readlines()
        except:
            lines = []
        return render_template(
            "sync.html",
            SERVERS=SERVERS,
            CLIENTS=CLIENTS,
            lines=lines,
        )
    if request.method == "POST":
        log = logging.getLogger("sync")
        file_handler = logging.FileHandler("sync.log")
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(formatter)
        log.addHandler(file_handler)
        if request.form.get("wipe") == 'all':
            for server in SERVERS:
                log.info("Wiping all keys on [%s]", server.data["name"])
                for client in server.data['keys']:
                    server.delete_key(client.key_id)

        server_hash = {}
        for server in SERVERS:
            server_hash[server.data["local_server_id"]] = server
        for key, client in CLIENTS.items():
            for u_server_id in client["servers"]:
                if u_server_id in server_hash:
                    if not server_hash[u_server_id].check_client(client["name"]):
                        log.warning(
                            f"Client {client['name']} absent on {server_hash[u_server_id].data['name']}"
                        )
                        server_hash[u_server_id].create_key(client["name"])
                    else:
                        log.info(
                            f"Client {client['name']} already present on {server_hash[u_server_id].data['name']}"
                        )
                else:
                    log.info(
                        f"Client {client['name']} incorrect server_id {u_server_id}"
                    )
        update_state()
        return redirect(url_for("sync"))


if __name__ == "__main__":
    thread = threading.Thread(target=update_state)
    thread.start()
    app.run(host="0.0.0.0")
