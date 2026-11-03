
import threading
import math
import logging

from naoqi import ALProxy

log = logging.getLogger(__name__)


class EarLedAnimator(object):
    STATES = (
        "idle",
        "listening",
        "thinking",
        "speaking",
        "off"
    )

    def __init__(self, ip, port=9559):
        self.leds = ALProxy("ALLeds", ip, port)

        self._state = "idle"
        self._lock = threading.Lock()
        self._stop = threading.Event()

        # Both ears share the same angular positions.
        # Each custom group controls 1 LED per ear.
        for i in range(10):
            degrees = i * 36
            names = [
                "Ears/Led/Left/{}Deg/Actuator/Value".format(degrees),
                "Ears/Led/Right/{}Deg/Actuator/Value".format(degrees)
            ]
            self.leds.createGroup(
                "CompanionEarPair{}".format(i),
                names
            )

        self._thread = threading.Thread(
            target=self._animate
        )
        self._thread.daemon = True
        self._thread.start()

    def set_state(self, state):
        if state not in self.STATES:
            raise ValueError(
                "Unknown LED state: {}".format(state)
            )

        with self._lock:
            self._state = state

    def get_state(self):
        with self._lock:
            return self._state

    def _animate(self):
        previous_state = None
        step = 0

        while not self._stop.is_set():
            state = self.get_state()

            try:
                # Reset the ear LEDs only when changing state.
                if state != previous_state:
                    self.leds.setIntensity("EarLeds", 0.0)
                    previous_state = state
                    step = 0

                    if state == "idle":
                        self.leds.setIntensity("EarLeds", 0.15)

                    elif state == "off":
                        self.leds.off("EarLeds")

                if state == "listening":
                    # Smooth breathing pattern.
                    brightness = (
                        0.55 +
                        0.45 * math.sin(step * 0.12)
                    )
                    self.leds.setIntensity(
                        "EarLeds",
                        brightness
                    )
                    step += 1

                elif state == "thinking":
                    # Rotating light with a dim trailing LED.
                    current = step % 10
                    previous = (current - 1) % 10
                    older = (current - 2) % 10

                    self.leds.setIntensity(
                        "CompanionEarPair{}".format(older),
                        0.05
                    )
                    self.leds.setIntensity(
                        "CompanionEarPair{}".format(previous),
                        0.35
                    )
                    self.leds.setIntensity(
                        "CompanionEarPair{}".format(current),
                        1.0
                    )

                    step += 1

                elif state == "speaking":
                    # Alternate even and odd LED segments.
                    even = 1.0 if step % 2 == 0 else 0.15
                    odd = 0.15 if step % 2 == 0 else 1.0

                    self.leds.setIntensity(
                        "LeftEarLedsEven", even
                    )
                    self.leds.setIntensity(
                        "RightEarLedsEven", even
                    )
                    self.leds.setIntensity(
                        "LeftEarLedsOdd", odd
                    )
                    self.leds.setIntensity(
                        "RightEarLedsOdd", odd
                    )

                    step += 1

            except Exception:
                log.exception("Ear LED animation failed")

            # Event.wait lets shutdown interrupt the delay.
            if state == "listening":
                delay = 0.06
            elif state == "thinking":
                delay = 0.13
            elif state == "speaking":
                delay = 0.30
            else:
                delay = 0.10

            self._stop.wait(delay)

    def close(self):
        self._stop.set()
        self._thread.join(3.0)

        if not self._thread.is_alive():
            self.leds.off("EarLeds")
        else:
            log.warning("Ear LED animator did not stop cleanly")
