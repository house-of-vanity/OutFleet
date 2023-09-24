from outline_vpn.outline_vpn import OutlineVPN
import yaml
import logging
from datetime import datetime

from flask import Flask, render_template, request, url_for, redirect

from lib import Server

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%d-%m-%Y %H:%M:%S')
log = logging.getLogger('OutlineFleet')

SERVERS = list()
app = Flask(__name__)


def format_timestamp(ts):
    return datetime.fromtimestamp(ts//1000).strftime('%Y-%m-%d %H:%M:%S')


def update_state():
    global SERVERS
    SERVERS = list()
    config = dict()
    try:
        with open("config.yaml", "r") as file:
            config = yaml.safe_load(file)
    except:
        with open("config.yaml", "w"):
            pass

    if config:
        servers = config.get('servers', None)
        for server_id, config in servers.items():
            server = Server(url=config["url"], cert=config["cert"], comment=config["comment"])
            SERVERS.append(server)
            log.info("Server found: %s", server.info()["name"])


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'GET':
        return render_template(
            'index.html',
            SERVERS=SERVERS,
            nt=request.args.get('nt'),
            nl=request.args.get('nl'),
            selected_server=request.args.get('selected_server'),
            format_timestamp=format_timestamp)
    else:
        server = request.form['server_id']
        server = next((item for item in SERVERS if item.info()["server_id"] == server), None)
        server.apply_config(request.form)
        update_state()
        return redirect(url_for('index', nt="Updated Outline VPN Server", selected_server=request.args.get('selected_server')))


@app.route('/add_server', methods=['GET', 'POST'])
def add_server():
    if request.method == 'GET':
        return render_template('add_server.html')
    else:
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


if __name__ == '__main__':
    update_state()
    app.run()
