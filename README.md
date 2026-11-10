# Pepper Python Bridge

The bridge runs under Python 2.7 because the NAOqi Python SDK uses Python 2.7.
The Docker image extracts the NAOqi Linux x86_64 SDK archive and configures
`PYTHONPATH`, `QI_SDK_PREFIX`, and `LD_LIBRARY_PATH` for it. The SDK archive is
not stored in Git because of its size; download it separately from the [SoftBank
Robotics Developer Center](https://doc.aldebaran.com/2-8/dev/community_software.html#retrieving-software).
Place `pynaoqi-python2.7-2.8.7.4-linux64-20210819_141148.tar.gz` in the project
root before building. It is ignored by Git but remains available to Docker.

## Project layout

```text
.
|-- Dockerfile                 # Image build and SDK setup
|-- compose.yaml               # Docker Compose service
|-- docker/
|   `-- entrypoint.sh          # Starts the bridge with Python 2.7
|-- pepper_bridge.py           # TCP bridge entry point
|-- pepper_controller.py       # Pepper/NAOqi control
|-- esp32_audio_client.py      # ESP32 microphone connection
|-- bridge_protocol.py         # Shared wire protocol
`-- .gitignore                 # Keeps the locally downloaded SDK out of Git
```

## Build

Build from the repository root after placing the SDK archive there:

```sh
docker build -t pepper-bridge .
```

To use a different compatible SDK archive in the build context:

```sh
docker build --build-arg NAOQI_SDK_ARCHIVE=your-sdk.tar.gz -t pepper-bridge .
```

## Run with Docker Compose

Set `PEPPER_IP` and `ESP32_IP` in `.env` (copy `.env.example` as a starting point):

```sh
docker compose up --build
```

The bridge is published on port `9999` by default. Set `BRIDGE_PORT` in `.env`
to change the host port, or set `ESP32_PORT` to change the ESP32 server port.
The container must be able to reach Pepper on TCP port 9559 and the ESP32 audio
server on its configured port. Stop it with `docker compose down`.
