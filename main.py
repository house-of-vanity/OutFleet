import yaml
import logging
from datetime import datetime
import random
import string

from flask import Flask, render_template, request, url_for, redirect

from lib import Server

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%d-%m-%Y %H:%M:%S')
log = logging.getLogger('OutlineFleet')

SERVERS = list()
CLIENTS = list()
app = Flask(__name__)


def format_timestamp(ts):
    return datetime.fromtimestamp(ts // 1000).strftime('%Y-%m-%d %H:%M:%S')


def random_string(length=12):
    letters = string.ascii_letters + string.digits

    return ''.join(random.choice(letters) for i in range(length))


def update_state():
    global SERVERS
    global CLIENTS
    SERVERS = list()
    CLIENTS = list()
    config = dict()
    try:
        with open("config.yaml", "r") as file:
            config = yaml.safe_load(file)
    except:
        with open("config.yaml", "w"):
            pass

    if config:
        servers = config.get('servers', list())
        for server_id, server_config in servers.items():
            server = Server(url=server_config["url"], cert=server_config["cert"], comment=server_config["comment"])
            SERVERS.append(server)
            log.info("Server found: %s", server.info()["name"])

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
            format_timestamp=format_timestamp)
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
                log.info("%s", server.create_key(request.form.get('name')))
        update_state()
        return redirect(url_for('index', nt="User has been added"))


if __name__ == '__main__':
    update_state()
    app.run()
