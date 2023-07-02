import sys
import time
import uuid
import random

sys.path.append('gen-py')

time.sleep(10)

#id = uuid.uuid1().int
id = 1

from rpc import Bank
from rpc.ttypes import TransferRequest

from thrift.transport import TSocket
from thrift.transport import TTransport
from thrift.protocol import TBinaryProtocol

# Create a Thrift client
transport = TSocket.TSocket("bank_1", 9090)
transport = TTransport.TBufferedTransport(transport)
protocol = TBinaryProtocol.TBinaryProtocol(transport)
client = Bank.Client(protocol)

# Connect to the server
timeWithOpen = time.time()
transport.open()

index = 0
timeWithoutOpen = time.time()
while(index < 10):
    #Creating the TransferRequest Struct
    request = TransferRequest(ID=id, amount=300)

    #Calling the RPC transferMoney
    result = client.transferMoney(request)
    #if result:
    #    print("Money transfered succesfully")
    #else:
    #    print("Bank didnt accept the transfer")

    #Calling RPC cancelTransfer to cancel the before made Transfer
    #result = client.cancelTransfer(id)
    #print("You need to give back the ", result, " eruos")

    index += 1
    id += 1
endWithoutOpen = time.time()

# Close the connection
transport.close()
endWithOpen = time.time()

print("Time with open: ", endWithOpen - timeWithOpen)
print("Time without open: ", endWithoutOpen - timeWithoutOpen)
  