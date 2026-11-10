FROM python:2.7-slim

ENV APP_DIR=/opt/pepper-bridge \
    QI_SDK_PREFIX=/opt/naoqi-sdk \
    PYTHONPATH=/opt/naoqi-sdk/lib/python2.7/site-packages \
    LD_LIBRARY_PATH=/opt/naoqi-sdk/lib \
    BRIDGE_HOST=0.0.0.0 \
    BRIDGE_PORT=9999

WORKDIR ${APP_DIR}

# The archive is supplied with the build context. Extract it to a stable SDK path.
ARG NAOQI_SDK_ARCHIVE=pynaoqi-python2.7-2.8.7.4-linux64-20210819_141148.tar.gz
COPY ${NAOQI_SDK_ARCHIVE} /tmp/naoqi-sdk.tar.gz
# Keep the base image's Python runtime consistent; the SDK also bundles its
# own libpython2.7, which must not override that runtime through LD_LIBRARY_PATH.
RUN mkdir -p "${QI_SDK_PREFIX}" \
    && tar -xzf /tmp/naoqi-sdk.tar.gz --strip-components=1 -C "${QI_SDK_PREFIX}" \
    && rm -f "${QI_SDK_PREFIX}"/lib/libpython2.7.so "${QI_SDK_PREFIX}"/lib/libpython2.7.so.* \
    && rm /tmp/naoqi-sdk.tar.gz

COPY animated_speech.py bridge_protocol.py bridgewithstream.py ear_led_animator.py \
     esp32_audio_client.py explore.py localize.py pepper_bridge.py pepper_controller.py \
     relocalize.py test.py ${APP_DIR}/
COPY docker/entrypoint.sh /usr/local/bin/pepper-bridge-entrypoint
RUN chmod +x /usr/local/bin/pepper-bridge-entrypoint

EXPOSE 9999
ENTRYPOINT ["/usr/local/bin/pepper-bridge-entrypoint"]
