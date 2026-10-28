import qi

PEPPER_IP = "192.168.1.122"
PORT = 9559

session = qi.Session()
session.connect("tcp://{}:{}".format(PEPPER_IP, PORT))

navigation = session.service("ALNavigation")

# Explore a 5-meter radius around Pepper's starting position
print("Starting exploration...")
result = navigation.explore(8.0)

print("Exploration result:", result)

if result == 0:
    print("Exploration completed successfully.")

    # Save the generated exploration/map
    map_path = navigation.saveExploration()

    print("Map saved!")
    print("Path on Pepper:", map_path)
else:
    print("Exploration failed with code:", result)