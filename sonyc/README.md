# SONYC Node - REIP Style

First flash the SD card
 - Download the latest Raspbian image: https://www.raspberrypi.org/downloads/raspbian/
 - Install Etcher: https://www.balena.io/etcher/
 - Insert the flash card and run Etcher's instructions to flash Raspbian to the SD.

After it's done flashing, you need to setup ssh and wifi so we can connect to it automatically. If you want to use different wifi, just change the username and password in the wpa_supplicant file.
```bash
...
git clone https://github.com/sonyc-project/sonyc-backend.git
git checkout bs_dev
python scripts/setup_new_sd.py
```

Then eject the sd card - you're all set! Now insert it into the raspberry pi.

### Prepare

```bash
sudo apt-get install libffi-dev libssl-dev
sudo apt install python3-dev
sudo apt-get install -y python3 python3-pip
```

### Install Docker
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
sudo pip3 install docker-compose
```

### Dev Setup
```bash
git clone https://github.com/sonyc-project/sonycnode.git
git clone https://github.com/reip-project/reip-pipelines.git
cd sonycnode
git checkout reip

docker build -t sonyc:latest .

docker run --rm -it --device /dev/snd \
    -v $(pwd)/../reip:/reip -v $(pwd)/models:/app/models \
    -v $(pwd)/node.py:/app/node.py sonyc:latest
```
