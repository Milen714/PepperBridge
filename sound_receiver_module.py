import sys
import time
import socket
import numpy as np
from naoqi import ALModule, ALProxy, ALBroker

class SoundReceiverModule(ALModule):
    def __init__(self, robot_ip, robot_port=9559, server_socket=None):
            self.module_name = "SoundReceiverModule"
            ALModule.__init__(self, self.module_name)
            self.audio_device = ALProxy("ALAudioDevice", robot_ip, robot_port)
            
            # Whisper Specifications: 16000Hz, Mono PCM 16-bit
            self.sample_rate = 16000  
            self.channels = 3         # 3 gives us Front, Rear, Left channels
            self.deinterleave = 0

            self.server_socket = server_socket

    def start_listening(self, server_socket=None):
            if server_socket is not None:
                self.server_socket = server_socket

            print("[NAOQI] Setting microphone preferences for module '{}'.".format(self.module_name))
            self.audio_device.setClientPreferences(
                self.module_name, 
                self.sample_rate, 
                self.channels, 
                self.deinterleave
            )
            print("[NAOQI] Subscribing module '{}'.".format(self.module_name))
            self.audio_device.subscribe(self.module_name)
            print("[NAOQI] Subscribed to Pepper's Microphones. Streaming live...")

    def stop_listening(self):
            try:
                self.audio_device.unsubscribe(self.module_name)
                print("\n[NAOQI] Unsubscribed cleanly.")
            except Exception as e:
                print("\n[NAOQI] Error unsubscribing: {}".format(e))

    def processRemote(self, nbOfChannels, nbOfSamplesByChannel, timeStamp, inputBuffer):
            """ Continuous live audio callback from Pepper """
            print("[NAOQI] processRemote entered: channels={}, samples={}.".format(
                nbOfChannels, nbOfSamplesByChannel))
            try:
                # Convert raw string buffer to signed 16-bit PCM array.
                audio_data_interleaved = np.fromstring(str(inputBuffer), dtype=np.int16)

                # Reshape to isolate channels.
                audio_data = np.reshape(
                    audio_data_interleaved,
                    (nbOfChannels, nbOfSamplesByChannel),
                    'F'
                )

                # Squeeze down to Channel 0 (Front Microphone).
                front_mic = audio_data[0]
                raw_pcm_bytes = front_mic.tostring()
                print("[NAOQI] Received {} bytes of audio data from Pepper's microphones.".format(
                    len(raw_pcm_bytes)))

                if self.server_socket:
                    try:
                        print("[SOCKET] Sending {} bytes of audio data to client...".format(
                            len(raw_pcm_bytes)))
                        self.server_socket.sendall(raw_pcm_bytes)
                    except socket.error as e:
                        print("\n[SOCKET] Client disconnected: {}".format(e))
            except Exception as e:
                print("[NAOQI] processRemote failed: {}".format(e))

            sys.stdout.flush()