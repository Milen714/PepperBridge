from naoqi import ALProxy
import math
import time
import struct


class PepperController(object):

    def __init__(self, ip, port=9559):
        self.motion = ALProxy("ALMotion", ip, port)
        self.posture = ALProxy("ALRobotPosture", ip, port)
        self.tts = ALProxy("ALTextToSpeech", ip, port)
        self.awareness = ALProxy("ALBasicAwareness", ip, port)
        self.tablet = ALProxy("ALTabletService", ip, port)
        self.audio = ALProxy("ALAudioDevice", ip, port)

    def start_looking_at_user(self):
        self.awareness.setEngagementMode("FullyEngaged")
        self.awareness.setTrackingMode("Head")
        self.awareness.startAwareness()

    def stop_looking_at_user(self):
        self.awareness.stopAwareness()

    def greet(self, text="Hello! Nice to meet you."):
        self.motion.wakeUp()

        if isinstance(text, unicode):
            text = text.encode("utf-8")
        self.tts.post.say(text)

        # Start from a predictable position.
        self.posture.goToPosture("StandInit", 0.4)

        self.start_looking_at_user()

        time.sleep(1.0)

        # Start speaking asynchronously.

        # Small head movement toward the user / more "alive" pose.
        self.motion.setAngles(
            ["HeadYaw", "HeadPitch"],
            [
                math.radians(5),
                math.radians(-3)
            ],
            0.15
        )

        # Open the hand before raising the arm.
        self.motion.openHand("RHand")

        # Raise the right arm into a waving pose.
        names = [
            "RShoulderPitch",
            "RShoulderRoll",
            "RElbowYaw",
            "RElbowRoll",
            "RWristYaw"
        ]

        greeting_pose = [
            math.radians(-35),
            math.radians(-25),
            math.radians(80),
            math.radians(65),
            0.0
        ]

        self.motion.angleInterpolationWithSpeed(
            names,
            greeting_pose,
            0.15
        )

        # Wave mainly with the wrist.
        self.motion.angleInterpolation(
            "RWristYaw",
            [
                math.radians(-40),
                math.radians(40),
                math.radians(-40),
                math.radians(40),
                0.0
            ],
            [
                0.35,
                0.70,
                1.05,
                1.40,
                1.75
            ],
            True
        )

        # Pause very briefly before returning.
        time.sleep(0.3)

        # Back to a neutral posture.
        self.posture.goToPosture("StandInit", 0.3)
        self.stop_looking_at_user()
        # self.tablet.showWebview("http://192.168.1.246:5174/")

    def open_tablet_webpage(self, url):
        self.tablet.showWebview(url)

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
        