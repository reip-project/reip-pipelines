FROM kpine/raspberrypi-pyarrow-plasma:latest

RUN install_packages portaudio19-dev alsa-utils python3-scipy && rm -rf /var/lib/apt/lists/*

# RUN pip install reip

COPY requirements.txt .
RUN pip install -r ./requirements.txt --no-cache-dir --extra-index-url https://www.piwheels.org/simple

COPY ../ /reip
RUN pip install -e /reip --no-deps
