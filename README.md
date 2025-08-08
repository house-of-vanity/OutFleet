<p align="center">
  <h1 align="center">OutFleet: Master Your OutLine VPN</h1>

  <p align="center">
    Streamline OutLine VPN experience. OutFleet offers centralized key control for many servers, users and always-updated Dynamic Access Keys instead of ss:// links
    <br/>
    <br/>
    <a href="https://github.com/house-of-vanity/outfleet/issues">Request Feature</a>
  </p>
</p>

![Forks](https://img.shields.io/github/forks/house-of-vanity/outfleet?style=social) ![Stargazers](https://img.shields.io/github/stars/house-of-vanity/outfleet?style=social) ![License](https://img.shields.io/github/license/house-of-vanity/outfleet) 

<img width="1282" height="840" alt="image" src="https://github.com/user-attachments/assets/3b66f928-853b-4af0-8968-1eacb2c16a1c" />

## About The Project

### Key Features

* Centralized Key Management
Administer user keys from one unified dashboard. Add, delete, and allocate users to specific servers effortlessly.

* ![Dynamic Access Keys](https://www.reddit.com/r/outlinevpn/wiki/index/dynamic_access_keys/)
Distribute ssconf:// links that are always up-to-date with your current server configurations. Eliminate the need for manual link updates.

### Why OutFleet?
Tired of juggling multiple home servers and the headache of individually managing users on each? OutFleet was born out of the frustration of not finding a suitable tool for efficiently managing a bunch of home servers. 

## Built With

Django, Postgres SQL and hassle-free deployment using Kubernetes or docker-compose

### Installation

#### Docker compose
Docker deploy is easy:
```
docker-compose up -d
```
#### Kubernetes
I use ArgoCD for deployment. [Take a look](https://gt.hexor.cy/ab/homelab/src/branch/main/k8s/apps/vpn) to `outfleet.yaml` file for manifests.


#### Setup sslocal service on Windows
Shadowsocks servers can be used directly with **sslocal**. For automatic and regular password updates, you can create a Task Scheduler job to rotate the passwords when they change, as OutFleet manages the passwords automatically.
You may run script in Admin PowerShell to create Task for autorun **sslocal** and update connection details automatically using Outfleet API
```PowerShell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force; Invoke-Expression (Invoke-WebRequest -Uri "https://raw.githubusercontent.com/house-of-vanity/OutFleet/refs/heads/master/tools/windows-helper.ps1" -UseBasicParsing).Content
```
[Firefox PluginProxy Switcher and Manager](https://addons.mozilla.org/en-US/firefox/addon/proxy-switcher-and-manager/) && [Chrome plugin Proxy Switcher and Manager](https://chromewebstore.google.com/detail/proxy-switcher-and-manage/onnfghpihccifgojkpnnncpagjcdbjod)

Keep in mind that all user keys are stored in a single **config.yaml** file. If this file is lost, user keys will remain on the servers, but OutFleet will lose the ability to manage them. Handle with extreme caution and use backups.

## Authors

* **UltraDesu** - *Humble amateur developer* - [UltraDesu](https://github.com/house-of-vanity) - *Author*
* **Contributors**
* * @Sanapach
