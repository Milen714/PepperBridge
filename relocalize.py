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
        "theta": result[0][2],
        "uncertainty": result[1]
    }

def relocalize_with_hint(hint):
    navigation.stopLocalization()
    navigation.loadExploration(MAP_PATH)

    navigation.relocalizeInMap(hint)
    navigation.startLocalization()

    for i in range(20):
        time.sleep(1)

        pose = get_pose()
        print("Localization:", pose)

        # Thresholds need to be determined experimentally!
        uncertainty = pose["uncertainty"]

        if (uncertainty[0] < 3.0 and
            uncertainty[1] < 3.0 and
            uncertainty[2] < 5.0):

            print("Localization accepted.")
            return pose

    raise RuntimeError("Localization did not converge.")




hint = [0.0, 0.0, 0.0]

relocalize_with_hint(hint)

pose_a = get_pose()

target = [1.5, 0.0, 0.0]

navigation.navigateToInMap(target)

time.sleep(3)

pose_b = get_pose()
print("KNOWN PHYSICAL LOCATION:", pose_b)


pose_b_hint = [pose_b["x"], pose_b["y"], pose_b["theta"]]

relocalize_with_hint(pose_b_hint)

raw_input("Press ENTER to finish...")

res =navigation.navigateToInMap([2.0, 0.0, 0.0])
print("Navigation result:", res)

print("POSITION After Attempting to return Home:", get_pose())

navigation.stopLocalization()