import logging
import math
import os
import threading
import time
import random
from pepper_animations import ANIMATIONS

from naoqi import ALProxy

from ear_led_animator import EarLedAnimator

log = logging.getLogger(__name__)


class PepperController:
    ANIMATIONS = ANIMATIONS

    def __init__(self, ip, port=9559):
        self.motion = ALProxy("ALMotion", ip, port)
        self.posture = ALProxy("ALRobotPosture", ip, port)
        self.tts = ALProxy("ALTextToSpeech", ip, port)
        self.animated_speech = ALProxy("ALAnimatedSpeech", ip, port)
        self.speaking_movement = ALProxy("ALSpeakingMovement", ip, port)
        self.awareness = ALProxy("ALBasicAwareness", ip, port)
        self.leds_enabled = os.environ.get(
            "PEPPER_LEDS_ENABLED", "true"
        ).strip().lower() not in ("0", "false", "no", "off")
        self.leds = ALProxy("ALLeds", ip, port) if self.leds_enabled else None
        self.led_state = None
        self.tablet = ALProxy("ALTabletService", ip, port)
        self.audio = ALProxy("ALAudioDevice", ip, port)
        self.memory = ALProxy("ALMemory", ip, port)
        self.people_perception = ALProxy("ALPeoplePerception", ip, port)
        self.animation_player = ALProxy("ALAnimationPlayer", ip, port)
        self.ear_animator = (
            EarLedAnimator(ip, port) if self.leds_enabled else None
        )

        self._audio_stream_lock = threading.RLock()
        self._audio_stream_active = False
        self._audio_stream_sample_rate = None
        self._audio_stream_channels = None
        self._audio_stream_format = None

        self._animation_lock = threading.Lock()
        self._animation_indices = {}

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
        except Exception:
            log.exception("Pepper speech failed")

            try:
                self.stop_looking_at_user()
            except Exception:
                log.exception("Failed to stop awareness")

            raise

    def play_raw_audio_buffer(self, raw_bytes):
        """
        Ingests binary PCM string and flushes it directly into Pepper's
        loudspeakers over the remote network proxy.
        """
        try:
            print(
                "Processing raw remote byte stream for Pepper ({} bytes)...".format(
                    len(raw_bytes)
                )
            )

            # 16-bit Stereo has 4 bytes per frame (2 left, 2 right)
            # 16000Hz * 4 bytes = 64,000 bytes per second of audio

            # We chunk the audio into 4000 frames (16,000 bytes per push)
            # to remain strictly below the maximum 16384 network buffer limit.
            chunk_size_frames = 4000
            chunk_size_bytes = chunk_size_frames * 4

            print("Streaming native binary blocks directly over remote ALProxy...")

            for i in range(0, len(raw_bytes), chunk_size_bytes):
                byte_chunk = raw_bytes[i : i + chunk_size_bytes]
                frames_in_chunk = len(byte_chunk) // 4

                # FIX: In Python 2.7, casting a raw byte sequence to a plain string
                # matches the internal remote proxy signature for raw binary buffers.
                raw_string_payload = str(byte_chunk)

                # Execute remote audio call over Wi-Fi
                self.audio.sendRemoteBufferToOutput(
                    int(frames_in_chunk), raw_string_payload
                )

            print("Playback streaming complete.")

        except Exception:
            log.exception("Failed to play PCM through Pepper")
            raise

    def open_tablet_webpage(self, url):
        self.tablet.showWebview(url)

    def is_person_present(self, max_distance=2.0):
        people = self.memory.getData("PeoplePerception/VisiblePeopleList") or []

        for person_id in people:
            try:
                distance = self.memory.getData(
                    "PeoplePerception/Person/{}/Distance".format(person_id)
                )

                if distance <= max_distance:
                    return True

            except Exception:
                log.exception("Could not read person distance")

        return False

    def set_led_state(self, state):
        """
        Sets the LED state of Pepper's ears and eyes.
        Valid states: "listening", "thinking", "speaking", "off"
        """
        try:
            if state not in ["listening", "thinking", "speaking", "idle"]:
                raise ValueError("Invalid LED state: {}".format(state))

            self.led_state = state
            if not self.leds_enabled:
                return
            self.ear_animator.set_state(state)

            if state == "listening":
                self.leds.on("FaceLeds")
                self.leds.fadeRGB("FaceLeds", 0x00FF00, 0.5)  # Green
            elif state == "thinking":
                self.leds.on("FaceLeds")
                self.leds.fadeRGB("FaceLeds", 0xFFFF00, 0.5)  # Yellow
            elif state == "speaking":
                self.leds.on("FaceLeds")
                self.leds.fadeRGB("FaceLeds", 0x0000FF, 0.5)  # Blue
            elif state == "idle":
                self.leds.off("FaceLeds")

        except Exception:
            log.exception("Failed to set LED state")

    def stop(self):
        try:
            self.motion.rest()
        except Exception:
            log.exception("Failed to stop ear LED animator")

    def start_audio_stream(self, sample_rate, channels, audio_format):
        """
        Prepare Pepper for incremental PCM playback.
        ALAudioDevice.sendRemoteBufferToOutput() receives each PCM block
        immediately. There is no separate audio stream handle to open.
        """
        with self._audio_stream_lock:
            if self._audio_stream_active:
                raise RuntimeError("An audio stream is already active")
            if sample_rate != 48000:
                raise ValueError("Expected 48000 Hz audio, got {}".format(sample_rate))
            if channels != 2:
                raise ValueError(
                    "Expected stereo audio, got {} channels".format(channels)
                )
            if audio_format != "s16le":
                raise ValueError("Expected s16le audio, got {}".format(audio_format))
            self.motion.wakeUp()
            self.set_led_state("speaking")
            # Keep Pepper's speech synthesizer silent. Audio is supplied
            # directly through ALAudioDevice instead.
            self.tts.setVolume(0.0)
            self._audio_stream_sample_rate = sample_rate
            self._audio_stream_channels = channels
            self._audio_stream_format = audio_format
            self._audio_stream_active = True
            log.info(
                "Started Pepper audio stream: %s Hz, %s channels, %s",
                sample_rate,
                channels,
                audio_format,
            )

    def write_audio(self, pcm_bytes):
        """
        Send one PCM block to Pepper.
        pcm_bytes must contain interleaved stereo signed 16-bit little-endian
        samples. At 2 channels and 2 bytes per sample, every audio frame is
        exactly 4 bytes.
        """
        if not pcm_bytes:
            return
        with self._audio_stream_lock:
            if not self._audio_stream_active:
                raise RuntimeError("No audio stream is active")
            bytes_per_sample = 2
            bytes_per_frame = self._audio_stream_channels * bytes_per_sample
            if len(pcm_bytes) % bytes_per_frame:
                raise ValueError(
                    "PCM block is not frame-aligned: {} bytes".format(len(pcm_bytes))
                )
            number_of_frames = len(pcm_bytes) // bytes_per_frame
            # Python 2.7's remote ALProxy expects a plain str for binary data.
            if not isinstance(pcm_bytes, str):
                pcm_bytes = str(pcm_bytes)
            self.audio.sendRemoteBufferToOutput(
                int(number_of_frames),
                pcm_bytes,
            )

    def finish_audio_stream(self):
        """
        Finish a PCM stream and restore Pepper's idle state.
        Audio blocks are submitted to ALAudioDevice as they arrive. There is
        no complete-buffer operation to wait for here. The final block has
        already been submitted when this method is called.
        """
        with self._audio_stream_lock:
            if not self._audio_stream_active:
                return
            try:
                log.info("Finished Pepper audio stream")
            finally:
                self._reset_audio_stream()
                self.set_led_state("idle")

    def stop_audio_stream(self):
        """
        Abort the current PCM stream and reset the stream state.
        ALAudioDevice does not expose a reliable per-stream canc    ellation
        handle through sendRemoteBufferToOutput(). This method prevents
        additional blocks from being submitted and resets the controller.
        """
        with self._audio_stream_lock:
            if not self._audio_stream_active:
                return
            try:
                log.info("Stopped Pepper audio stream")
            finally:
                self._reset_audio_stream()
                self.set_led_state("idle")

    def _reset_audio_stream(self):
        self._audio_stream_active = False
        self._audio_stream_sample_rate = None
        self._audio_stream_channels = None
        self._audio_stream_format = None

    def execute_animation(self, action):
        variants = self.ANIMATIONS.get(action)
        if not variants:
            raise ValueError("Unsupported gesture: %s" % action)
        if not self._animation_lock.acquire(False):
            raise RuntimeError("Gesture already in progress")
        try:
            # Avoid arm motion during incremental PCM playback.
            with self._audio_stream_lock:
                if self._audio_stream_active:
                    raise RuntimeError("Audio stream active")
            index = self._animation_indices.get(action, 0)
            animation = variants[index % len(variants)]
            # Advance only after success; deterministic and no immediate repeats.
            # self.motion.wakeUp()
            self.animation_player.run(animation)
            self._animation_indices[action] = index + 1
            return {"status": "success", "action": action, "animation": animation}
        finally:
            self._animation_lock.release()

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
            left_arm = [
                "LShoulderPitch",
                "LShoulderRoll",
                "LElbowYaw",
                "LElbowRoll",
                "LWristYaw",
            ]
            right_arm = [
                "RShoulderPitch",
                "RShoulderRoll",
                "RElbowYaw",
                "RElbowRoll",
                "RWristYaw",
            ]
            both_arms = left_arm + right_arm

            # --- PHASE 1: Right Arm Out, Left Arm Out (Palm Down) ---
            print("Step 1: Arms Out...")
            # Right arm out straight
            self.motion.angleInterpolationWithSpeed(
                right_arm, [0.0, -0.2, 0.0, 0.0, 0.0], 0.3
            )
            time.sleep(0.5)
            # Left arm out straight
            self.motion.angleInterpolationWithSpeed(
                left_arm, [0.0, 0.2, 0.0, 0.0, 0.0], 0.3
            )
            time.sleep(0.8)

            # --- PHASE 2: Flip Palms Up ---
            print("Step 2: Flip Palms Up...")
            # Rotate wrists 180 degrees (approx 1.5 radians)
            self.motion.angleInterpolationWithSpeed(
                ["LWristYaw", "RWristYaw"], [-1.5, 1.5], 0.2
            )
            time.sleep(0.8)

            # --- PHASE 3: Right Hand to Left Shoulder, Left Hand to Right Shoulder ---
            print("Step 3: Cross Hands to Shoulders...")
            # Right hand to left shoulder
            self.motion.angleInterpolationWithSpeed(
                right_arm,
                [
                    math.radians(-40),
                    math.radians(-10),
                    math.radians(-80),
                    math.radians(85),
                    0.0,
                ],
                0.3,
            )
            time.sleep(0.5)
            # Left hand to right shoulder
            self.motion.angleInterpolationWithSpeed(
                left_arm,
                [
                    math.radians(-40),
                    math.radians(10),
                    math.radians(80),
                    math.radians(-85),
                    0.0,
                ],
                0.3,
            )
            time.sleep(0.8)

            # --- PHASE 4: Hands Behind Head ---
            print("Step 4: Hands Behind Head...")
            # Move elbows high and wrap hands behind neck/head
            self.motion.angleInterpolationWithSpeed(
                both_arms,
                [
                    math.radians(-80),
                    math.radians(20),
                    math.radians(-40),
                    math.radians(-60),
                    0.0,  # Left
                    math.radians(-80),
                    math.radians(-20),
                    math.radians(40),
                    math.radians(60),
                    0.0,  # Right
                ],
                0.25,
            )
            time.sleep(0.8)

            # --- PHASE 5: Hands to Hips ---
            print("Step 5: Hands to Hips...")
            # Bring arms down onto the hip joints
            self.motion.angleInterpolationWithSpeed(
                both_arms,
                [
                    math.radians(60),
                    math.radians(15),
                    math.radians(-40),
                    math.radians(-40),
                    0.0,  # Left
                    math.radians(60),
                    math.radians(-15),
                    math.radians(40),
                    math.radians(40),
                    0.0,  # Right
                ],
                0.3,
            )
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
