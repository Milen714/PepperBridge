from naoqi import ALProxy, ALBroker, ALModule
import math
import time
import struct

from sound_receiver_module import SoundReceiverModule


class PepperController(object):

    def __init__(self, ip, port=9559, server_socket=None):
        self.motion = ALProxy("ALMotion", ip, port)
        self.posture = ALProxy("ALRobotPosture", ip, port)
        self.tts = ALProxy("ALTextToSpeech", ip, port)
        self.animated_speech = ALProxy("ALAnimatedSpeech", ip, port)
        self.speaking_movement = ALProxy("ALSpeakingMovement", ip, port)
        self.awareness = ALProxy("ALBasicAwareness", ip, port)
        self.tablet = ALProxy("ALTabletService", ip, port)
        self.audio = ALProxy("ALAudioDevice", ip, port)
        # self.broker = ALProxy("ALBroker", ip, port)
        self.sound_receiver = SoundReceiverModule(ip, port, server_socket)

        self.server_socket = server_socket

    def start_looking_at_user(self):
        self.awareness.setEngagementMode("FullyEngaged")
        self.awareness.setTrackingMode("Head")
        self.awareness.startAwareness()

    def stop_looking_at_user(self):
        self.awareness.stopAwareness()

    def speak(self, text="Hello! Nice to meet you.", audio_buffer=None):
        try:
            self.motion.wakeUp()
            
            # Start from a predictable position.
            self.posture.goToPosture("StandInit", 0.4)
            self.start_looking_at_user()

            self.tts.setVolume(0.0)  
            # Enable animated speech
            self.animated_speech.setBodyLanguageMode(2)  # 2 = Contextual mode
            self.speaking_movement.setEnabled(True)
            if not isinstance(text, unicode):
                text = text.decode("utf-8")
            self.animated_speech.post.say(text.encode("utf-8"))
            if audio_buffer:
                print("Playing raw audio buffer alongside speech...")
                self.play_raw_audio_buffer(audio_buffer)
            # Back to a neutral posture.
            # self.posture.goToPosture("StandInit", 0.3)
            # self.stop_looking_at_user()
        except Exception as e:
            print("Error during speech: {}".format(e))
            self.posture.goToPosture("StandInit", 0.5)
            self.stop_looking_at_user()


    def play_raw_audio_buffer(self, raw_bytes):
        """
        Ingests binary PCM string and flushes it directly into Pepper's 
        loudspeakers over the remote network proxy.
        """
        try:
            print("Processing raw remote byte stream for Pepper ({} bytes)...".format(len(raw_bytes)))
            
            # 16-bit Stereo has 4 bytes per frame (2 left, 2 right)
            # 16000Hz * 4 bytes = 64,000 bytes per second of audio
            
            # We chunk the audio into 4000 frames (16,000 bytes per push) 
            # to remain strictly below the maximum 16384 network buffer limit.
            chunk_size_frames = 4000 
            chunk_size_bytes = chunk_size_frames * 4
            
            print("Streaming native binary blocks directly over remote ALProxy...")
            
            for i in range(0, len(raw_bytes), chunk_size_bytes):
                byte_chunk = raw_bytes[i:i + chunk_size_bytes]
                frames_in_chunk = len(byte_chunk) / 4
                
                # FIX: In Python 2.7, casting a raw byte sequence to a plain string 
                # matches the internal remote proxy signature for raw binary buffers.
                raw_string_payload = str(byte_chunk)
                
                # Execute remote audio call over Wi-Fi
                self.audio.sendRemoteBufferToOutput(int(frames_in_chunk), raw_string_payload)
                
            print("Playback streaming complete.")
            
        except Exception as e:
            print("Failed to execute hardware speaker playback: {}".format(e))
    
    def open_tablet_webpage(self, url):
        self.tablet.showWebview(url)

    def record_audio(self, duration_seconds=5, audio_socket=None):
        """
        Records audio from Pepper's microphones and streams it over a TCP socket.
        """
        try:
            print("Starting audio recording for {} seconds...".format(duration_seconds))
            self.sound_receiver.start_listening(audio_socket)
            time.sleep(duration_seconds)
            self.sound_receiver.stop_listening()
            print("Audio recording completed.")
        except Exception as e:
            print("Error during audio recording: {}".format(e))

    def do_macarena(self, text="EHH MACARENA!"):
        """
        Executes the classic Macarena dance choreography safely.
        Designed to maintain Pepper's center of gravity while waving arms.
        """
        try:
            print("Starting Macarena Dance... Music cue!")
            
            # 1. Wake up and stand up straight
            self.motion.wakeUp()
            self.posture.goToPosture("StandInit", 0.5)
            self.start_looking_at_user()
            self.tts.say(text)
            
            # Define arm joints we want to move
            left_arm = ["LShoulderPitch", "LShoulderRoll", "LElbowYaw", "LElbowRoll", "LWristYaw"]
            right_arm = ["RShoulderPitch", "RShoulderRoll", "RElbowYaw", "RElbowRoll", "RWristYaw"]
            both_arms = left_arm + right_arm
            
            # --- PHASE 1: Right Arm Out, Left Arm Out (Palm Down) ---
            print("Step 1: Arms Out...")
            # Right arm out straight
            self.motion.angleInterpolationWithSpeed(right_arm, [0.0, -0.2, 0.0, 0.0, 0.0], 0.3)
            time.sleep(0.5)
            # Left arm out straight
            self.motion.angleInterpolationWithSpeed(left_arm, [0.0, 0.2, 0.0, 0.0, 0.0], 0.3)
            time.sleep(0.8)
            
            # --- PHASE 2: Flip Palms Up ---
            print("Step 2: Flip Palms Up...")
            # Rotate wrists 180 degrees (approx 1.5 radians)
            self.motion.angleInterpolationWithSpeed(["LWristYaw", "RWristYaw"], [-1.5, 1.5], 0.2)
            time.sleep(0.8)
            
            # --- PHASE 3: Right Hand to Left Shoulder, Left Hand to Right Shoulder ---
            print("Step 3: Cross Hands to Shoulders...")
            # Right hand to left shoulder
            self.motion.angleInterpolationWithSpeed(right_arm, [math.radians(-40), math.radians(-10), math.radians(-80), math.radians(85), 0.0], 0.3)
            time.sleep(0.5)
            # Left hand to right shoulder
            self.motion.angleInterpolationWithSpeed(left_arm, [math.radians(-40), math.radians(10), math.radians(80), math.radians(-85), 0.0], 0.3)
            time.sleep(0.8)
            
            # --- PHASE 4: Hands Behind Head ---
            print("Step 4: Hands Behind Head...")
            # Move elbows high and wrap hands behind neck/head
            self.motion.angleInterpolationWithSpeed(both_arms, [
                math.radians(-80), math.radians(20), math.radians(-40), math.radians(-60), 0.0, # Left
                math.radians(-80), math.radians(-20), math.radians(40), math.radians(60), 0.0  # Right
            ], 0.25)
            time.sleep(0.8)
            
            # --- PHASE 5: Hands to Hips ---
            print("Step 5: Hands to Hips...")
            # Bring arms down onto the hip joints
            self.motion.angleInterpolationWithSpeed(both_arms, [
                math.radians(60), math.radians(15), math.radians(-40), math.radians(-40), 0.0, # Left
                math.radians(60), math.radians(-15), math.radians(40), math.radians(40), 0.0  # Right
            ], 0.3)
            time.sleep(0.8)
            
            # --- PHASE 6: Hip Shake & The Jump (Base Rotation) ---
            print("Step 6: EHH MACARENA! *Jump/Turn*")
            
            # Shake hips by rotating the spine briefly left and right
            for _ in range(2):
                self.motion.setAngles("HipRoll", math.radians(5), 0.2)
                time.sleep(0.15)
                self.motion.setAngles("HipRoll", math.radians(-5), 0.2)
                time.sleep(0.15)
            self.motion.setAngles("HipRoll", 0.0, 0.2)
            
            # Simulate the 90-degree hop by rotating the wheel base!
            # moveTo(x_meters, y_meters, theta_radians)
            # 90 degrees = pi / 2 (approx 1.57 radians)
            self.motion.moveTo(0.0, 0.0, 1.57) 
            
            # 7. Return to standard posture safely
            print("Dance cycle complete.")
            self.posture.goToPosture("StandInit", 0.4)
            self.stop_looking_at_user()
            
        except Exception as e:
            print("Macarena execution crashed: {}".format(e))
            # Emergency safety reset to keep Pepper from locking up frozen in an odd shape
            self.posture.goToPosture("Stand", 0.5)
        