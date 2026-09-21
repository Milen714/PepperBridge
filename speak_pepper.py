from naoqi import ALProxy

# PEPPER_IP = "192.168.1.122"
PEPPER_IP = "172.28.111.16"
# PEPPER_IP = "127.0.0.1"
PORT = 9559

tts = ALProxy(
    "ALTextToSpeech",
    PEPPER_IP,
    PORT
)

tts.say("Hi, Ommar!")

