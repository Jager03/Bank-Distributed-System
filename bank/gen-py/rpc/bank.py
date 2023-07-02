import socket
import json
import threading
import sys
import os
from jinja2 import Environment, FileSystemLoader
import paho.mqtt.client as mqtt
import time
import uuid
  
initMeasure = 0
finalMeasure = 0

#Append the RPC generated code to the path
sys.path.append('gen-py')

from rpc import Bank
from rpc.ttypes import TransferRequest

from thrift.transport import TSocket
from thrift.transport import TTransport
from thrift.protocol import TBinaryProtocol
from thrift.server import TServer


#Get the system variables
container_name = os.environ.get('NAME')
env = Environment(loader=FileSystemLoader('./templates'))
bruto_value = int(os.environ.get('BRUTO_VAL'))
role = int(os.environ.get('ROLE'))
numberOfBanks = int(os.environ.get('NUM_BANK'))

#Initialize the transfer history dictionary and dictonary to store the Value of each bank
transferHistory = {}
bankValueHistory = {}

#Initialize list of Banks that are and are not willing to save the broken bank
#aswell as the bank to safe
noVoters = []
yesVoters = []
bankToSafe = ""

#Takes a parameter to match wether to return a TCP or UDP socket
#Returns socket  
def setup_socket(option):
    local_adress = '0.0.0.0' #Listening on all available network interfaces
    local_port = 80
    
    match option:
        case 0:
            tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp_socket.bind((local_adress, local_port))
            return tcp_socket
        case 1:
            ##Adress family Internet to make creat socket with IPv4 
            ##SOCK_DGRAM for UDP socket
            udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

            ##socket level option reuse address so the socket can reuse the local address after being closed
            udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            #Bind
            udp_socket.bind((local_adress, local_port)) #Tuple address and port
            
            return udp_socket

#Thread that listens for a HTTP request and starts a HTTP_handler thread
# Takes a TCP socket as parameter as listening socket
def listen_thread(socket):
    while True:
        socket.listen()
        client_socket, client_address = socket.accept()
        print('New connection from', client_address, file=sys.stdout)
        sys.stdout.flush()
        
        http_thread = threading.Thread(target=HTTP_handler, args=(client_socket,))
        http_thread.start()

#This function handles the webpage of the bank, including GET and POST requests and uses jija2 to render the HTML
# Recives as paremeter the socket where the conection with the client was made 
def HTTP_handler(client_socket):
    #Getting the request, making sure that if the request is fragmented, we still would get the entire request 
    request = b''
    while(True):
        chunk = client_socket.recv(1024)
        request += chunk

        # Check if the request ends with double newline characters ('\r\n\r\n')
        if b'\r\n\r\n' in request:
            #checking if the request is POST to make sure the hole body was recived
            if(request.startswith(b'POST')):
                headers, body = request.split(b'\r\n\r\n', 1)
                #getting the content lenght
                content_length = int(headers.split(b'Content-Length: ')[1].split(b'\r\n', 1)[0])

                #first check if the body was already recived
                if(len(body)<content_length):
                    print("check ", len(body), file=sys.stdout)
                    sys.stdout.flush()
                    received_data = b''
                    while len(received_data) < content_length:
                        chunk = client_socket.recv(1024)
                        if not chunk:
                            break
                        received_data += chunk

            print(request.decode(), file=sys.stdout)
            sys.stdout.flush()
            break


    portfolio_value = calc_portfolio()
    global bruto_value
    

    #Handling if the request is GET or POST
    if request.startswith(b'GET'):
        #Geting the url from the request by accesing the 2nd element form the array returned from split(). The first element being the GET
        url = request.split(b' ')[1]
        url = url.decode()

        #Returning the index page
        if url == '/':
            template = env.get_template('index.html')
            output = template.render(portfolio=portfolio_value)

        elif url == '/transaction.html':
            template = env.get_template('transaction.html')
            output = template.render()

        elif url == '/handle.html':
            template = env.get_template('handle.html')
            output = template.render(actions=aktien_name, quantitys=aktien_quantity)

        #If client is asking a file thats not in the server
        else:
            response = 'HTTP/1.1 404 Not Found\nContent-Type: text/html\n\n'
            response += '<html><body><h1>404 Not Found</h1></body></html>'
            client_socket.sendall(response.encode())
            return

        response = 'HTTP/1.1 200 OK\nContent-Type: text/html\n\n'
        response_bytes = response.encode() + output.encode()
        client_socket.sendall(response_bytes)


    elif request.startswith(b'POST'):
         #Geting the url from the request by accesing the 2nd element form the array returned from split(). The first element being the POST
        url = request.split(b' ')[1]
        url = url.decode()

        #Geting the data from the request by accesing the 2nd element form the array returned from split(). The first element being the POST header
        data = request.split(b'\r\n\r\n')[1]
        data = data.decode()

        #Extracting the variables form the data. They come in the form of amount=60&options=withdraw
        post_data = {}
        for item in data.split('&'):
            key, value = item.split('=')
            post_data[key] = value
        
        post_amount = int(post_data["amount"])

        #handle the handle action request
        if url == "/handle.html":
            #Grabing the aktie to change from the portfolio
            aktie_quantity = 0
            
            for aktie in portfolio:
                if aktie["name"] == post_data["actName"]:
                    aktie_quantity = aktie["quantity"]

            #handle sell request
            if post_data["options"] == "sell":
                #Making sure there are enough actions
                if aktie_quantity > post_amount:
                    #change the quantity value and bruto_value
                    for aktie in portfolio:
                        if aktie["name"] == post_data["actName"]:
                            aktie["quantity"] = aktie["quantity"] - post_amount
                            bruto_value += (aktie["price"]*post_amount)

                    template = env.get_template('thanks.html')
                    output = template.render(code="You sold "+ post_data["amount"] + " actions from " + aktie["name"])
                else:
                    template = env.get_template('error.html')
                    output = template.render(error_code = "You want to sell more actions than the " + str(aktie_quantity) + " that we have")

            #handle buy request        
            elif post_data["options"] == "buy":
                #change the quantity value and bruto_value
                for aktie in portfolio:
                    if aktie["name"] == post_data["actName"]:
                        aktie["quantity"] = aktie["quantity"] + post_amount
                        bruto_value -= (aktie["price"]*post_amount)
                
                template = env.get_template('thanks.html')
                output = template.render(code="You bought "+ post_data["amount"] + " actions from " + aktie["name"])

        #handle the transaction request
        elif url == "/transaction.html":
            if post_data["options"] == "deposit": 
                bruto_value += post_amount
                template = env.get_template('thanks.html')
                output = template.render(code="You deposited "+ post_data["amount"] + " euros into Joha Bank")

            elif post_data["options"] == "withdraw":
                #Handle error if customer wants to withdraw more than the bruto_value of the bank
                if post_amount > bruto_value:
                    template = env.get_template('error.html')
                    output = template.render(error_code = "You want to withdraw more money than the " + str(bruto_value) + " euros we have")
                else:
                    bruto_value -= post_amount
                    template = env.get_template('thanks.html')
                    output = template.render(code="You withdrew "+ post_data["amount"] + " euros from Joha Bank")

        
        response = f'HTTP/1.1 200 OK\nContent-Type: text/html\n Content-Length:{len(output)}\n\n'
        response_bytes = response.encode() + output.encode()
        client_socket.sendall(response_bytes)
        

    client_socket.close()

#This is the parser that handles messages gotten from both the MQTT broker and sockets
#Takes as paremter the message to be handeled
def message_handler(message):
    global bruto_value
    global bankToSafe
    global transactionId

    if(message["code"] == "ok"):
            print(message["message"], "\n", file=sys.stdout)
            sys.stdout.flush()

    #Handle the message of a changed 
    elif(message["code"] == "change"):
        #get the aktie that changed from the name in the message
        for aktie in portfolio:
            if(message["action"] == aktie["name"]):
                aktie_to_change = aktie
                break
        aktie_to_change["price"]=message["price"] #change locally the price of the aktie with the one in the message
        #print('The price of ', aktie_to_change["name"], ' changed', file=sys.stdout)
        sys.stdout.flush()
    
    #Handle MQTT status message
    elif(message["code"] == "status"):
        #Saving the current value of the Bank locally
        bankValueHistory[message["bank"]] = float(message["value"])

    #Handel MQTT broke message
    elif(message["code"] == "broke"):
        #Save the name of the bank that is crying for help
        bankToSafe = message["bank"]

        #Handling according if you're the broke Bank or not
        if(message["bank"] == container_name):                  #Imediatly sending yes vote if you are the bank crying for help
            answer = {
                    "code": "answer",
                    "bank": container_name,
                    "decision": True,
                }
        else:
            #Deciding if Bank is willing to save or not
            if (bruto_value > 5000):
                answer = {
                    "code": "answer",
                    "bank": container_name,
                    "decision": True,
                }
                pipeline.publish(json.dumps(answer))
            else:
                answer = {
                    "code": "answer",
                    "bank": container_name,
                    "decision": False,
                }
                pipeline.publish(json.dumps(answer))    

    #Hanlding the answer MQTT message
    elif(message["code"] == "answer"):
        #Adding to voters list
        if(message["decision"]):
            yesVoters.append(message["bank"])
        else:
            noVoters.append(message["bank"])

    #Handeling the decision of the Banks
    elif(message["code"] == "decisionMade"):
        if(message["decision"]):
            #Broke Bank should not send money
            if(bankToSafe != container_name):
                # Create a Thrift client
                transport = TSocket.TSocket(bankToSafe, 9090)           #Send the money to the bank in need
                transport = TTransport.TBufferedTransport(transport)
                protocol = TBinaryProtocol.TBinaryProtocol(transport)
                client = Bank.Client(protocol)

                #Deciding the amount of the loan
                loan = bruto_value*0.1
                transferId = uuid.uuid1().fields[1] #Getting a 16bit unique id for the transfer
                request = TransferRequest(ID=transferId, amount=loan)   #Define the TransferRequest class

                #Send the money
                transport.open()
                result = client.transferMoney(request)
                transport.close()

                #Checking if Bank accepted the loan
                if(result):
                    #Substract the loan from the bruto value to keep data consistent
                    bruto_value = bruto_value - loan

                    print("Bank was safed!", file=sys.stdout)
                else:
                    print("Not able to send Transaction")
        else:
            print("Bank was not saved", file=sys.stdout)
            sys.stdout.flush()

#Thread that is constatly listening in for udp traffic in port 80
#Takes as parameter the udp socket
def recive_data(socket):
    while(True):
        #Recive
        buffer_size = 1024  # Set the maximum size of the received message
        data, sender_address = socket.recvfrom(buffer_size)
        
        # Print the received message and sender address sys.stdout to redirect print() to main process
        message = json.loads(data.decode())
        """ print('Received  ', message["code"], 'message from ', sender_address, file=sys.stdout)
        sys.stdout.flush() """

        message_handler(message)
      
#Function to calculate the total money of the Bank
def calc_portfolio():
    value = 0
    for aktie in portfolio:
        value += aktie["quantity"] * aktie["price"]
    return value + bruto_value

#Thread to serve the Apache Thrift RPC service
def serverRPC():

    class BankHandler:
        def transferMoney(self, request):
            global bruto_value
            global transferHistory
            amount = request.amount

            bruto_value += amount
            transferHistory[request.ID] = amount
            return True
        
        def cancelTransfer(self, ID):
            global bruto_value
           
            bruto_value -= transferHistory[ID]
            return transferHistory[ID]

    # Create a Thrift server
    handler = BankHandler()
    processor = Bank.Processor(handler)
    transport = TSocket.TServerSocket(port=9090)
    tfactory = TTransport.TBufferedTransportFactory()
    pfactory = TBinaryProtocol.TBinaryProtocolFactory()

    server = TServer.TSimpleServer(processor, transport, tfactory, pfactory)

    # Start the server
    print("Starting the RPC server...", file=sys.stdout)
    server.serve()
    print("RPC Server stopped.", file=sys.stdout)
    sys.stdout.flush()

#Class that implements the MQTTPipeline and conection to the Mosquitto's Broker
class MQTTPipeline:
    def __init__(self, broker, port, topic):
        self.broker = broker
        self.port = port
        self.topic = topic

        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

    def on_connect(self, client, userdata, flags, rc):
        if(not rc):
            print("Connected to mosquito's MQTT test server")
            self.client.subscribe(self.topic)
        else:
            print("Something went wrong connecting to mosquito's MQTT test server")

    def on_message(self, client, userdata, msg):
        global yesVoters
        global noVoters

        #Send the decoded message to the message_handler
        message_handler(json.loads(msg.payload.decode()))

        #Role == 1 means the Bank is the Coordinator 
        #Coordinator has to check wether the Banks agreed to save or not
        if(role == 1):
            #Did all Banks vote?
            if(len(noVoters) + len(yesVoters) == numberOfBanks):
                #Do all want to safe the bank?
                if(len(noVoters) == 0):

                    #First check if at the end of every transaction, the bank would have more money than the minimum 1000
                    #Uses the bankValueHistory Dictionary to build the sum of all the 10% loans  
                    #If the sum isn't enough, then the bank is not saved
                    valueSum = 0.0
                    for value in bankValueHistory.values():
                        print(value)
                        valueSum += value*0.1
                        
                    if valueSum < 1000:
                        message = {
                            "code": "decisionMade",
                            "decision": False,
                        }
                        pipeline.publish(json.dumps(message))
                        return
                    else:
                        message = {
                            "code": "decisionMade",
                            "decision": True,
                        }
                        pipeline.publish(json.dumps(message))
                
                else:
                    message = {
                        "code": "decisionMade",
                        "decision": False,
                    }
                    pipeline.publish(json.dumps(message))
                
                #Empty the arrays
                noVoters = []
                yesVoters = [] 

    def publish(self, message):
        self.client.publish(self.topic, message)

    def start(self):
        self.client.connect(self.broker, self.port)
        self.client.loop_start()

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()


#initiate the socket
udp_socket = setup_socket(1)
tcp_socket = setup_socket(0)

broker = "test.mosquitto.org"  # Mosquitto's test server
port = 1883  # Mosquittos port
topic = "broke"  # topic

#Starting the pipeline
pipeline = MQTTPipeline(broker, port, topic)
pipeline.start()

#Define aktien
AMZ = {
    "name":"AMZ",
    "quantity":10,
    "price": 300,
}

ALPH = {
    "name":"ALPH",
    "quantity":8,
    "price": 200,
}

JPM = {
    "name":"JPM",
    "quantity":10,
    "price": 270,
}

#Role 0 means that the bank is meant to go broke, so it should have no Actions
if(role == 0):
    AMZ["quantity"] = 0
    ALPH["quantity"] = 0
    JPM["quantity"] = 0

#safe the names of the aktions
portfolio = [JPM, ALPH, AMZ]
aktien_name = []
for aktie in portfolio:
    aktien_name.append(aktie["name"])

#create the subscriptions message
sub_message = {
    "code":"sub",
    "aktien": aktien_name,
    "bank":container_name,
}

#Subscribe to Borse
udp_socket.sendto(json.dumps(sub_message).encode(), ("borse_1", 80))

#Initiate the recive message thread
recieve_thread = threading.Thread(target=recive_data, args=(udp_socket,))
recieve_thread.start()

#Initiate the thread that listens for HTTP conections
listen = threading.Thread(target=listen_thread, args=(tcp_socket,))
listen.start()

#Initiate the RPC server
rpc = threading.Thread(target=serverRPC)
rpc.start()

#Define the Status report message
statusReport = {
    "code": "status",
    "bank": container_name,
    "value": 0,
}

while True:
    value = calc_portfolio()

    print("Portfolio value: ", value, '\n')
    
    statusReport["value"] = value
    pipeline.publish(json.dumps(statusReport))

    if(bruto_value < 1000):
        print("Crying for help!\n")
        brokeMessage = {
            "code": "broke",
            "bank": container_name,
        }
        pipeline.publish(json.dumps(brokeMessage))

    time.sleep(3)


