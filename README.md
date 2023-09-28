<br/>
<p align="center">
  <h3 align="center">OutFleet: Master Your OutLine VPN</h3>

  <p align="center">
    Streamline OutLine VPN experience. OutFleet offers centralized key control for many servers and always-updated Dynamic Access Keys instead of ss:// links
    <br/>
    <br/>
    <a href="https://github.com/house-of-vanity/outfleet/issues">Request Feature</a>
  </p>
</p>

![Forks](https://img.shields.io/github/forks/house-of-vanity/outfleet?style=social) ![Stargazers](https://img.shields.io/github/stars/house-of-vanity/outfleet?style=social) ![License](https://img.shields.io/github/license/house-of-vanity/outfleet) 

## About The Project

![Screen Shot](img/servers.png)

### Key Features

* Centralized Key Management
Administer user keys from one unified dashboard. Add, delete, and allocate users to specific servers effortlessly.

* ![Dynamic Access Keys](https://www.reddit.com/r/outlinevpn/wiki/index/dynamic_access_keys/)
Distribute ssconf:// links that are always up-to-date with your current server configurations. Eliminate the need for manual link updates.

### Why OutFleet?
Tired of juggling multiple home servers and the headache of individually managing users on each? OutFleet was born out of the frustration of not finding a suitable tool for efficiently managing a bunch of home servers. 

## Built With

Python, Flask and offer hassle-free deployment.

### Installation

Docker deploy is easy:
```
docker run --restart always -p 5000:5000 -d --name OutFleet --mount type=bind,source=/etc/outfleet/config.yaml,target=/app/config.yaml ultradesu/outfleet:0.0.4
```

## Authors

* **UltraDesu** - *Humble amateur developer* - [UltraDesu](https://github.com/house-of-vanity) - *All the work*
