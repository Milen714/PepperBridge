# from naoqi import ALProxy

# PEPPER_IP = "192.168.1.122"
# PORT = 9559

# tts = ALProxy(
#     "ALTextToSpeech",
#     PEPPER_IP,
#     PORT
# )

# tts.say("Hello. I am Pepper. I am a robot. I can talk to you and answer your questions.")



from naoqi import ALProxy
import math
import time

# PEPPER_IP = "127.0.0.1"
# PEPPER_IP = "192.168.1.122"
# PEPPER_IP = "169.254.46.223"
#PEPPER_IP = "172.28.111.16"
# PEPPER_IP = "10.68.67.16"
PORT = 9559

motion = ALProxy("ALMotion", PEPPER_IP, PORT)
posture = ALProxy("ALRobotPosture", PEPPER_IP, PORT)

motion.wakeUp()
posture.goToPosture("StandInit", 0.4)

time.sleep(1)

motion.setAngles(
    [
        "LShoulderPitch",
        "LShoulderRoll",
        "LElbowYaw",
        "LElbowRoll"
    ],
    [
        math.radians(-30),
        math.radians(25),
        math.radians(-60),
        math.radians(-45)
    ],
    0.15
)

time.sleep(3)

posture.goToPosture("StandInit", 0.3)