# custom_transport_protocol

implemented a reliable data transmission protocol over UDP. The three files simulate the behavior of TCP, ensuring reliable, ordered data delivery with congestion control, acknowledgment handling, retransmissions, and sequence number management. sender.py and receiver.py implement the core functionality of reliable UDP communication, ensuring data integrity, congestion control, retransmissions, and ordered delivery. utils.py provides essential support functions like logging, time tracking, and sequence number management, enabling the sender and receiver to operate efficiently and reliably.

receiver.py:
   UDP-based communication system that handles out-of-order, duplicate, and in-order packets. It uses sequence numbers to ensure data integrity and processes messages efficiently. It also manages the flow of data, acknowledging receipt, and ensuring the data is printed out in the correct order.

sender.py: 
  simulates a reliable data transfer over UDP with congestion control, acknowledgment handling, and retransmission logic. It uses a TCP-like approach to ensure data is sent in order, properly acknowledged, and retransmitted in case of packet loss or timeout.

utils.py:
  provides three utility functions that are used for logging, handling time, and managing sequence numbers in the sender and receiver scripts. 

  
