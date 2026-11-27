FROM python:2.7-slim

ENV APP_DIR=/opt/pepper-bridge \
    QI_SDK_PREFIX=/opt/naoqi-sdk \
    PYTHONPATH=/opt/naoqi-sdk/lib/python2.7/site-packages \
    LD_LIBRARY_PATH=/opt/naoqi-sdk/lib:/usr/lib/x86_64-linux-gnu:/lib/x86_64-linux-gnu \
    BRIDGE_HOST=0.0.0.0 \
    BRIDGE_PORT=9999

WORKDIR ${APP_DIR}

# Use buster main only (keeps libc6 pinned to 2.28-10) and stub /sbin/ldconfig
# during apt-get to avoid the qemu-x86_64 SIGSEGV in Buster's static ldconfig.real.
RUN printf 'deb http://archive.debian.org/debian buster main\n' > /etc/apt/sources.list \
    && mv /sbin/ldconfig /sbin/ldconfig.orig \
    && printf '#!/bin/sh\nexit 0\n' > /sbin/ldconfig \
    && chmod +x /sbin/ldconfig \
    && apt-get -o Acquire::Check-Valid-Until=false update \
    && apt-get install -y --no-install-recommends \
    alsa-utils \
    gcc \
    libc6-dev \
    portaudio19-dev \
    && mv /sbin/ldconfig.orig /sbin/ldconfig \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "PyAudio==0.2.11"

# Map container ALSA capture to the Pi 5's adau7002 I2S device via plug
COPY docker/asound.conf /etc/asound.conf

# The archive is supplied with the build context. Extract it to a stable SDK path.
ARG NAOQI_SDK_ARCHIVE=pynaoqi-python2.7-2.8.7.4-linux64-20210819_141148.tar.gz
COPY ${NAOQI_SDK_ARCHIVE} /tmp/naoqi-sdk.tar.gz
COPY docker/extract_sdk.py /tmp/extract_sdk.py
# Keep the base image's Python runtime consistent; the SDK also bundles its
# own libpython2.7, which must not override that runtime through LD_LIBRARY_PATH.
RUN python2.7 /tmp/extract_sdk.py /tmp/naoqi-sdk.tar.gz "${QI_SDK_PREFIX}"

COPY *.py ${APP_DIR}/
COPY docker/entrypoint.sh /usr/local/bin/pepper-bridge-entrypoint

EXPOSE 9999
ENTRYPOINT ["sh", "/usr/local/bin/pepper-bridge-entrypoint"]