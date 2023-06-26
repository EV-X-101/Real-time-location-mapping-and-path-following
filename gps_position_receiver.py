import socket
import os
import dotenv

dotenv.load_dotenv()

# Create a socket object
serversocket = socket.socket()

# Get the IP address from the environment variable
RPI_IP_ADDRESS = os.environ.get('RPI_IP_ADDRESS')

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((RPI_IP_ADDRESS, 5000)) # Replace with Raspberry Pi IP address
print('Socket connection established')

while True:
    # Establish a connection
    clientsocket, addr = serversocket.accept()

    print("Got a connection from %s" % str(addr))
    
    while True:
        # Receive up to 1024 bytes from the client
        data = clientsocket.recv(1024)
        if not data: break
        print(data.decode())

    # Close the client connection
    clientsocket.close()
