import socket
import json
import threading
import sys
import random
import time

subs_banks = []

def setup_socket():
    ##Adress family Internet to make creat socket with IPv4 
    ##SOCK_DGRAM for UDP socket
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    ##socket level option reuse address so the socket can reuse the local address after being closed
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    #Bind
    local_adress = '0.0.0.0' #Listening on all available network interfaces
    local_port = 80
    udp_socket.bind((local_adress, local_port)) #Tuple address and port
    
    return udp_socket


def message_handler(message, socket):
    global subs_banks #to make it global
    if(message["code"] == "sub"):
            subs_banks.append(message["bank"])

            send = {
                "code":"ok",
                "message": "You were added to Borse_1"
            } 
            socket.sendto(json.dumps(send).encode(), (message["bank"], 80))


def recive_data(socket):
    while(True):
        #Recive
        buffer_size = 1024  # Set the maximum size of the received message
        data, sender_address = socket.recvfrom(buffer_size)
        
        # Print the received message and sender address
        message = json.loads(data.decode())
        print('Received  ', message["code"], 'message from ', sender_address, "\n", file=sys.stdout)
        sys.stdout.flush()

        message_handler(message, socket)


#Define aktions
AMZ = {
    "name":"AMZ",
    "price": 300,
}

ALPH = {
    "name":"ALPH",
    "price": 200,
}

JPM = {
    "name":"JPM",
    "price": 270,
}    

#setup socket
udp_socket = setup_socket()

#Start thread funtion with the recieve call 
recieve_thread = threading.Thread(target=recive_data, args=(udp_socket,))
recieve_thread.start()

aktien = [AMZ, ALPH, JPM]

while(True):
    index = random.randint(0, 2)
    variance = random.uniform(10, 100)
    sign = random.choice([0, 1])
    amount = random.randint(10, 100)

    aktie = aktien[index]
    if sign:
        aktie["price"] = aktie["price"]+variance
    else:
        aktie["price"] = aktie["price"]-variance

    message={
        "code":"change",
        "action": aktie["name"],
        "price":aktie["price"],
        "amount": amount
    }

    if(subs_banks):
        for bank in subs_banks:
            udp_socket.sendto(json.dumps(message).encode(), (bank, 80))
    
    time.sleep(5)
