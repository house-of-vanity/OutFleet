import yaml
import logging
from datetime import datetime
import random
import string

from flask import Flask, render_template, request, url_for, redirect
from flask_cors import CORS
from lib import Server

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%d-%m-%Y %H:%M:%S')

log = logging.getLogger('OutFleet')

SERVERS = list()
CLIENTS = dict()
HOSTNAME = ''
app = Flask(__name__)
CORS(app)

def format_timestamp(ts):
    return datetime.fromtimestamp(ts // 1000).strftime('%Y-%m-%d %H:%M:%S')


def random_string(length=64):
    letters = string.ascii_letters + string.digits

    return ''.join(random.choice(letters) for i in range(length))


def update_state():
    global SERVERS
    global CLIENTS
    global HOSTNAME
    SERVERS = list()
    CLIENTS = dict()
    config = dict()
    try:
        with open("config.yaml", "r") as file:
            config = yaml.safe_load(file)
    except:
        with open("config.yaml", "w"):
            pass

    if config:
        HOSTNAME = config.get('ui_hostname', 'my-own-ssl-ENABLED-domain.com')
        servers = config.get('servers', list())
        for server_id, server_config in servers.items():
            try:
                server = Server(url=server_config["url"], cert=server_config["cert"], comment=server_config["comment"])
                SERVERS.append(server)
                log.info("Server found: %s", server.info()["name"])
            except Exception as e:
                log.warning("Can't access server: %s - %s", server_config["url"], e)

        CLIENTS = config.get('clients', list())


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'GET':
        return render_template(
            'index.html',
            SERVERS=SERVERS,
            nt=request.args.get('nt'),
            nl=request.args.get('nl'),
            selected_server=request.args.get('selected_server'),
            add_server=request.args.get('add_server', None),
            format_timestamp=format_timestamp,
        )
    else:
        server = request.form['server_id']
        server = next((item for item in SERVERS if item.info()["server_id"] == server), None)
        server.apply_config(request.form)
        update_state()
        return redirect(
            url_for('index', nt="Updated Outline VPN Server", selected_server=request.args.get('selected_server')))


@app.route('/clients', methods=['GET', 'POST'])
def clients():
    if request.method == 'GET':
        return render_template(
            'clients.html',
            SERVERS=SERVERS,
            CLIENTS=CLIENTS,
            nt=request.args.get('nt'),
            nl=request.args.get('nl'),
            selected_client=request.args.get('selected_client'),
            add_client=request.args.get('add_client', None),
            format_timestamp=format_timestamp,
            dynamic_hostname=HOSTNAME,
        )
    else:
        server = request.form['server_id']
        server = next((item for item in SERVERS if item.info()["server_id"] == server), None)
        server.apply_config(request.form)
        update_state()
        return redirect(
            url_for('index', nt="Updated Outline VPN Server", selected_server=request.args.get('selected_server')))


@app.route('/add_server', methods=['POST'])
def add_server():
    if request.method == 'post':
        with open("config.yaml", "r") as file:
            config = yaml.safe_load(file) or {}

        servers = config.get('servers', dict())

        try:
            new_server = Server(url=request.form['url'], cert=request.form['cert'], comment=request.form['comment'])
        except:
            return redirect(url_for('index', nt="Couldn't access Outline VPN Server", nl="error"))

        servers[new_server.data["server_id"]] = {
            'name': new_server.data["name"],
            'url': new_server.data["url"],
            'comment': new_server.data["comment"],
            'cert': request.form['cert']
        }
        config["servers"] = servers
        with open("config.yaml", "w") as file:
            yaml.safe_dump(config, file)
        update_state()
        return redirect(url_for('index', nt="Added Outline VPN Server"))


@app.route('/add_client', methods=['POST'])
def add_client():
    if request.method == 'POST':
        with open("config.yaml", "r") as file:
            config = yaml.safe_load(file) or {}

        clients = config.get('clients', dict())
        user_id = request.form.get('user_id', random_string())

        clients[user_id] = {
            'name': request.form.get('name'),
            'comment': request.form.get('comment'),
            'servers': request.form.getlist('servers')
        }
        config["clients"] = clients
        with open("config.yaml", "w") as file:
            yaml.safe_dump(config, file)

        for server in SERVERS:
            if server.data["server_id"] in request.form.getlist('servers'):
                client = next((item for item in server.data["keys"] if item.name == request.form.get('old_name')), None)
                if client:
                    if client.name == request.form.get('name'):
                        pass
                    else:
                        server.rename_key(client.key_id, request.form.get('name'))
                else:
                    server.create_key(request.form.get('name'))
            else:
                client = next((item for item in server.data["keys"] if item.name == request.form.get('old_name')), None)
                if client:
                    server.delete_key(client.key_id)
        update_state()
        return redirect(url_for('clients', nt="Clients updated", selected_client=request.form.get('user_id')))


@app.route('/del_client', methods=['POST'])
def del_client():
    if request.method == 'POST':
        with open("config.yaml", "r") as file:
            config = yaml.safe_load(file) or {}

        clients = config.get('clients', dict())
        user_id = request.form.get('user_id')
        if user_id in clients:
            for server in SERVERS:
                client = next((item for item in server.data["keys"] if item.name == request.form.get('name')), None)
                if client:
                    server.delete_key(client.key_id)

        config["clients"].pop(user_id)
        with open("config.yaml", "w") as file:
            yaml.safe_dump(config, file)
    update_state()
    return redirect(url_for('clients', nt="User has been deleted"))


@app.route('/dynamic/<server_name>/<client_id>', methods=['GET'])
def dynamic(server_name, client_id):
    client = next((keys for client, keys in CLIENTS.items() if client == client_id), None)
    server = next((item for item in SERVERS if item.info()["name"] == server_name), None)
    key = next((item for item in server.data["keys"] if item.name == client["name"]), None)
    if server and client and key:
        if server.data["server_id"] in client["servers"]:
            log.info("Dynamic config for %s requested by '%s'", server.data["name"], client["name"])

            return {
              "server": server.data["hostname_for_access_keys"],
              "server_port": key.port,
              "password": key.password,
              "method": key.method,
              "info": "Managed by OutFleet [github.com/house-of-vanity/OutFleet/]"
            }
    return "Hey buddy, i think you got the wrong door the leather-club is two blocks down"

if __name__ == '__main__':
    update_state()
    app.run(host='0.0.0.0')
