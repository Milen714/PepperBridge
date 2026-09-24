import sys
import time
import socket
import numpy as np
from naoqi import ALModule, ALProxy, ALBroker

# Global instance variable to prevent Python 2.7 garbage collection
sound_receiver_instance = None

class SoundReceiverModule(ALModule):
    def __init__(self, name, robot_ip, robot_port=9559):
        ALModule.__init__(self, name)
        self.audio_device = ALProxy("ALAudioDevice", robot_ip, robot_port)
        self.module_name = name
        
        # Whisper Specifications: 16000Hz, Mono PCM 16-bit
        self.sample_rate = 16000  
        self.channels = 3         # 3 gives us Front, Rear, Left channels
        self.deinterleave = 0     
        
        # Set up a raw TCP Socket Server to bridge data to Python 3
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(("0.0.0.0", 50005))
        self.server_socket.listen(1)
        self.server_socket.setblocking(0) # Non-blocking so it doesn't hang Pepper
        self.client_conn = None
        print("[SOCKET] Server listening on port 50005. Waiting for Python 3 Whisper client...")

    def start_listening(self):
        self.audio_device.setClientPreferences(
            self.module_name, 
            self.sample_rate, 
            self.channels, 
            self.deinterleave
        )
        self.audio_device.subscribe(self.module_name)
        print("[NAOQI] Subscribed to Pepper's Microphones. Streaming live...")

    def check_for_connections(self):
        """ Periodically checks if a Python 3 Whisper script has connected """
        if not self.client_conn:
            try:
                self.client_conn, addr = self.server_socket.accept()
                print("\n[SOCKET] Connected to Whisper streamer client at: {}".format(addr))
            except socket.error:
                pass # No client connected yet

    def stop_listening(self):
        try:
            self.audio_device.unsubscribe(self.module_name)
            print("\n[NAOQI] Unsubscribed cleanly.")
        except Exception as e:
            print("\n[NAOQI] Error unsubscribing: {}".format(e))
            
        if self.client_conn:
            self.client_conn.close()
        self.server_socket.close()

    def processRemote(self, nbOfChannels, nbOfSamplesByChannel, timeStamp, inputBuffer):
        """ Continuous live audio callback from Pepper """
        # Convert raw string buffer to signed 16-bit PCM array
        audio_data_interleaved = np.fromstring(str(inputBuffer), dtype=np.int16)
        
        # Reshape to isolate channels
        audio_data = np.reshape(audio_data_interleaved, (nbOfChannels, nbOfSamplesByChannel), 'F')
        
        # Squeeze down to Channel 0 (Front Microphone)
        front_mic = audio_data[0]
        raw_pcm_bytes = front_mic.tobytes()
        
        # Stream the raw bytes over the TCP socket to Python 3 if connected
        if self.client_conn:
            try:
                self.client_conn.sendall(raw_pcm_bytes)
                sys.stdout.write("\r[STREAMING] Sending audio buffer live...")
            except socket.error:
                print("\n[SOCKET] Client disconnected.")
                self.client_conn = None
        else:
            sys.stdout.write("\r[IDLE] Microphone active. Waiting for Whisper script connection...")
        
        sys.stdout.flush()


if __name__ == "__main__":
    ROBOT_IP = "192.168.1.122"
    PORT = 9559

    myBroker = ALBroker("myBroker", "0.0.0.0", 0, ROBOT_IP, PORT)

    try:
        global sound_receiver_instance
        sound_receiver_instance = SoundReceiverModule("sound_receiver_instance", ROBOT_IP, PORT)
        sound_receiver_instance.start_listening()
        
        print("Press Ctrl+C to stop script manually.")
        while True:
            # Keep checking for incoming Python 3 streaming clients
            sound_receiver_instance.check_for_connections()
            time.sleep(0.2)
            
    except KeyboardInterrupt:
        print("\n[INFO] Stopping due to KeyboardInterrupt...")
    finally:
        if sound_receiver_instance:
            sound_receiver_instance.stop_listening()
        myBroker.shutdown()
        sys.exit(0)
