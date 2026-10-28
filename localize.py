import qi
import time

PEPPER_IP = "192.168.1.122"
PORT = 9559

MAP_PATH = "/home/nao/.local/share/Explorer/2026-10-26T095339.753Z.explo"

session = qi.Session()
session.connect("tcp://{}:{}".format(PEPPER_IP, PORT))

navigation = session.service("ALNavigation")


def get_pose():
    result = navigation.getRobotPositionInMap()

    return {
        "x": result[0][0],
        "y": result[0][1],
        "theta": result[0][2]
    }


navigation.stopLocalization()

print("Loading map...")
navigation.loadExploration(MAP_PATH)

print("Starting localization...")
navigation.startLocalization()

time.sleep(3)

print("START:", get_pose())


# ------------------------------------------------
# Move somewhere
# ------------------------------------------------

raw_input("\nPress ENTER to navigate to [2, 0, 0]...")

result = navigation.navigateToInMap([2.0, 0.0, 0.0])

print("Navigation result:", result)
print("POSITION:", get_pose())


# ------------------------------------------------
# Keep localization running!
# ------------------------------------------------

raw_input("\nPress ENTER when ready to return to [0, 0, 0]...")

result = navigation.navigateToInMap([0.0, 0.0, 0.0])

print("Navigation result:", result)
print("POSITION:", get_pose())


raw_input("\nPress ENTER to finish...")

navigation.stopLocalization()