# Bank-Distributed-System
In this university project I simulated a distributed system between a Stock Exchange and multiple Bank components and also the scenario in which a Bank goes broke and the other bank components have to decide and communicate with eachother if they can save the bank

I got conftorble in the use of ##Docker in order to simulate the whole system
I also got conftorble in the use of ##Sockets both UDP and TCP for the communtication between the components
A web interface was also creted in order to communicate via HTTP with the Banks and the HTTP server was implemented form cero using no external library
The use of MOM like ##MQTT was key in order to do the communication need for saving a bank
Also ##RPC were also implemented to implement bank transfers between the components using ##ApacheThrift
