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
|-- esp32_client.py            # ESP32 microphone and mmWave radar client
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
docker compose up -d --build
```

On ARM64 hosts, Compose first runs a privileged one-shot `binfmt` service to
register amd64 emulation with the host kernel. The bridge starts after this
registration completes. This is needed because the bundled NAOqi SDK is Linux
x86_64. For one-off `docker compose run` commands, do not pass `--no-deps`, so
Compose can run the registration service first.

The bridge is published on port `9999` by default. Set `BRIDGE_PORT` in `.env`
to change the host port, or set `ESP32_PORT` to change the ESP32 server port.
Set `PEPPER_LEDS_ENABLED=false` in `.env` when using Choregraphe's virtual
robot, which does not provide LED hardware. The default is `true` for a real
Pepper.
The container must be able to reach Pepper on TCP port 9559 and the ESP32 audio
server on its configured port. Stop it with `docker compose down`.

`ESP32Client` in `esp32_client.py` uses the same ESP32 for both sensors:
`read_radar_status()` fetches the `/radar` JSON endpoint on HTTP port 80, and
`person_present()` returns its `inRange` value (the firmware's 45–225 cm
capture zone). `start_microphone_recording(on_audio, on_end)` streams microphone PCM over the
configured TCP port, and `stop()` closes that stream. `ESP32AudioClient` is
retained as a backwards-compatible alias.

```sh
sudo docker run --privileged --rm tonistiigi/binfmt --install amd64
sudo docker run --rm --platform linux/amd64 debian:bookworm-slim /bin/echo amd64-ok
```
