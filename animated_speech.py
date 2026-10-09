import time
from naoqi import ALProxy

ROBOT_IP = "192.168.1.122"
PORT = 9559

def fix_and_speak():
    try:
        print("Connecting to proxies...")
        motion = ALProxy("ALMotion", ROBOT_IP, PORT)
        posture = ALProxy("ALRobotPosture", ROBOT_IP, PORT)
        animated_speech = ALProxy("ALAnimatedSpeech", ROBOT_IP, PORT)
        speaking_movement = ALProxy("ALSpeakingMovement", ROBOT_IP, PORT)

        # 1. Force the robot to wake up and turn on motor stiffness
        print("Waking up the robot and engaging motors...")
        motion.wakeUp() 
        
        # 2. Ensure the robot is in a proper standing posture to move safely
        print("Going to Stand posture...")
        posture.goToPosture("StandInit", 0.5)

        # 3. Ensure Speaking Movement is globally enabled
        print("Enabling speaking movements...")
        speaking_movement.setEnabled(True)
        animated_speech.setBodyLanguageMode(2) # 2 = Contextual mode

        # Test speech with explicit fallback tag
        print("Speaking...")
        # Note: If you are using Pepper, use paths like "animations/Effort_1" or "animations/Stand/Gestures/Hey_1"
        # text = "Hello! ^start(animations/Stand/Gestures/Hey_1) Can you see me moving now?"
        text = "Hello! I'm here to help with AI ethics questions. What would you like to discuss today?"
        animated_speech.say(text)

    except Exception as e:
        print("Error: {}".format(e))
    finally:
        # Optional: rest the robot if you are finished testing to save battery/motors
        # motion.rest()
        pass

if __name__ == "__main__":
    fix_and_speak()
