import socket
import json
import threading
import sys
import unicodedata
from pepper_controller import PepperController

# --- CONFIGURATION ---
PEPPER_IP = "192.168.1.122"  # Replace with Pepper's actual Wi-Fi IP
# PEPPER_IP = "127.0.0.1"  # Replace with Pepper's actual Wi-Fi IP
PEPPER_PORT = 9559
BRIDGE_HOST = "127.0.0.1"    # Listen on localhost for FastAPI requests
BRIDGE_PORT = 9999           # Port where FastAPI will connect

class PepperBridge(object):
    def __init__(self, ip, port):
        print("Connecting to Pepper at {}:{}...".format(ip, port))
        
        try:
            self.pepper = PepperController(ip=ip)
            print("Successfully connected to Pepper!")
            
            
            
        except Exception as e:
            print("Failed to connect to Pepper: {}".format(e))
            sys.exit(1)

    def handle_command(self, payload):
        """Parses incoming JSON payload from FastAPI and triggers Pepper API."""
        try:
            data = json.loads(payload)
            command = data.get("command")
            target = data.get("target")

            print("Received command: {}".format(command))

            if command == "posture":
                print(u"Target length: {}".format(len(target)))
                print(u"Changing posture to: {}".format(target).encode("utf-8"))

                try:
                    self.pepper.greet(target)
                    print("PepperController.greet completed")
                    return {"status": "success", "message": "Greeting completed"}
                except Exception as e:
                    print("Pepper greeting failed: {}".format(e))
                    return {"status": "error", "message": str(e)}

            elif command == "leds":
                # Handle your LEDs here via self.pepper or native
                return {"status": "success", "message": "LEDs updated"}

            elif command == "stream_audio":
                # We return a unique status telling the handler to prepare for binary data
                size = data.get("size", 0)
                return {"status": "ready_for_audio", "size": size}

            else:
                return {"status": "error", "message": "Unknown command"}

        except Exception as e:
            return {"status": "error", "message": str(e)}

def client_handler(client_socket, bridge):
    """Handles the persistent connection from FastAPI, supporting text & raw audio bytes."""
    buffer_data = ""
    while True:
        try:
            data = client_socket.recv(4096)
            if not data:
                break
            
            buffer_data += data
            
            # Check if a text command has finished arriving
            if "\n" in buffer_data:
                payload, buffer_data = buffer_data.split("\n", 1)
                response = bridge.handle_command(payload)
                
                # Check if the command we just processed was an audio alert
                if response.get("status") == "ready_for_audio":
                    expected_size = response.get("size", 0)
                    
                    # Send acknowledgment back to FastAPI so it knows it can dump the raw bytes
                    client_socket.send(json.dumps({"status": "acknowledged"}) + "\n")
                    
                    # Collect the raw binary audio data chunk by chunk
                    audio_buffer = ""
                    # If some audio data accidentally slipped into our initial read buffer, grab it
                    if buffer_data:
                        audio_buffer = buffer_data
                        buffer_data = ""
                        
                    while len(audio_buffer) < expected_size:
                        chunk = client_socket.recv(min(expected_size - len(audio_buffer), 4096))
                        if not chunk:
                            raise Exception("Socket closed prematurely while reading audio bytes")
                        audio_buffer += chunk
                    
                    # SUCCESS: We have the full audio stream in memory. Forward it to your Controller!
                    print("Full audio file received ({} bytes). Playing...".format(len(audio_buffer)))
                    bridge.pepper.play_raw_audio_buffer(audio_buffer)
                    
                    # Send a final success response back to FastAPI
                    client_socket.send(json.dumps({"status": "success", "message": "Audio played"}) + "\n")
                else:
                    # Normal text command response (like posture change)
                    client_socket.send(json.dumps(response) + "\n")
                
        except Exception as e:
            print("Error handling socket client: {}".format(e))
            break
            
    client_socket.close()
    print("FastAPI connection closed.")


def start_server():
    # Initialize the link to Pepper
    pepper = PepperBridge(PEPPER_IP, PEPPER_PORT)

    # Initialize the local network socket server
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((BRIDGE_HOST, BRIDGE_PORT))
    server.listen(5)
    print("Bridge server listening on {}:{}... Ready for FastAPI.".format(BRIDGE_HOST, BRIDGE_PORT))

    try:
        while True:
            client_sock, addr = server.accept()
            print("FastAPI backend connected from: {}".format(str(addr)))

            client_thread = threading.Thread(target=client_handler, args=(client_sock, pepper))
            client_thread.daemon = True
            client_thread.start()
    except KeyboardInterrupt:
        print("\nShutting down bridge server.")
    finally:
        server.close()

def tts_text(text):
    if not isinstance(text, unicode):
        text = text.decode("utf-8")

    replacements = {
        u"\u2014": u"-",   # em dash
        u"\u2013": u"-",   # en dash
        u"\u2019": u"'",   # curly apostrophe
        u"\u201c": u'"',
        u"\u201d": u'"',
    }

    for source, replacement in replacements.items():
        text = text.replace(source, replacement)

    return unicodedata.normalize("NFKC", text)

if __name__ == "__main__":
    start_server()