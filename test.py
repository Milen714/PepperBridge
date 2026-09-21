
from pepper_controller import PepperController
# PEPPER_IP = "172.28.111.16"
# PEPPER_IP = "192.168.1.122"
PEPPER_IP = "127.0.0.1"

pepper = PepperController(PEPPER_IP)

# pepper.greet("Hello.")
pepper.greet("Hello! How can I assist you today")
# pepper.open_tablet_webpage("http://192.168.1.246:5173/")