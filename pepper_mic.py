# pepper_mic.py

from naoqi import ALBroker
from naoqi import ALModule
from naoqi import ALProxy

import time
import sys

# PEPPER_IP = "127.0.0.1"
PEPPER_IP = "192.168.1.122"
PEPPER_PORT = 9559

MODULE_NAME = "PepperAudioReceiver"


class PepperAudioReceiver(ALModule):

    def __init__(self, name):
        ALModule.__init__(self, name)

        self.audio = ALProxy(
            "ALAudioDevice",
            PEPPER_IP,
            PEPPER_PORT
        )

    def start(self):
        # 16000 Hz
        # channel 3 = front microphone
        # 0 = interleaved
        self.audio.setClientPreferences(
            self.getName(),
            16000,
            3,
            0
        )

        self.audio.subscribe(self.getName())

        print("Microphone subscribed")

    def stop(self):
        try:
            self.audio.unsubscribe(self.getName())
        except:
            pass

        print("Microphone unsubscribed")

    def processRemote(
        self,
        number_of_channels,
        samples_per_channel,
        timestamp,
        buffer
    ):
        print(
            "Received %d samples"
            % samples_per_channel
        )


broker = ALBroker(
    "pythonBroker",
    "0.0.0.0",
    0,
    PEPPER_IP,
    PEPPER_PORT
)

receiver = PepperAudioReceiver(MODULE_NAME)

try:
    receiver.start()

    while True:
        time.sleep(1)

except KeyboardInterrupt:
    receiver.stop()
    broker.shutdown()
    sys.exit(0)

