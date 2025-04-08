import json
import math
import select
import socket
import sys
import random
from sender import growCWND

from utils import current_time, log, wrap_sequence



# Maximum transmission unit (MTU)
MSG_SIZE = 1500
# Maximum size of data we can send in a packet (excludes header information)
DATA_SIZE = 1200
# Round trip time, unknown at start
RTT = None
# Retransmission timeout, initialized to 30 seconds
RTO = 30
# Current sequence number
SEQUENCE = random.randrange(0, 2**32-1)
# Maps expected ACK to loaded packets (have not been sent yet)
LOADED = {}
# Maps expected ACK to buffered packets
SENT = {}
# Number of duplicate ACKs we have received
DUP_ACKS = 0
# Congestion window, initialized to 1
CWND = 1
# Slow start threshold, initialized to 4
SSTHRESH = 4
# Flag indicating if we've read all the data
END_OF_FILE = False


def sockSend(msg_info):
    
    msg_template = {
        'sequence': SEQUENCE,
        'data': None,
        'syn': False,
        'ack': False,
        'eof': False
    }
    # override template with values
    msg = dict(msg_template, **msg_info)
    # Prepare the packet
    packet = str.encode(json.dumps(msg))
    # Check for errors
    if sock.sendto(packet, dest) < len(packet):
        log('[error] unable to fully send packet')
    else:
        length = len(msg['data']) if msg['data'] else 0
        log('[send data] {sequence} ({length})'.format(
            sequence=msg['sequence'],
            length=length
        ))


def sendPackets():
    
    global LOADED
    global SENT

    for idx, seq_num in enumerate(sorted(LOADED)):
        if idx < CWND and len(SENT) < CWND:
            msg = LOADED.pop(seq_num)
            msg['timestamp'] = current_time()
            msg['timeout'] = msg['timestamp'] + RTO
            SENT[seq_num] = msg
            sockSend(msg)
        else:
            return


def loadPackets():
    
    global END_OF_FILE
    global SEQUENCE
    global LOADED

    if END_OF_FILE:
        
        return

    for unused_i in range(int(math.floor(CWND) - len(LOADED))):
        # read data
        data = sys.stdin.read(DATA_SIZE)

        if (len(data) > 0):
            # aet the EOF flag 
            END_OF_FILE = len(data) < DATA_SIZE
            msg = {'sequence': SEQUENCE, 'data': data, 'eof': END_OF_FILE}
            # increment the sequence number
            SEQUENCE = wrap_sequence(SEQUENCE, data)
            # save the packet to be sent later
            LOADED[SEQUENCE] = msg
        else:
            
            msg = {'eof': True}
            sockSend(msg)
            END_OF_FILE = True
        if END_OF_FILE:
            break


def handshake():
  
    global SEQUENCE
    syn_packet = {'syn': True}
    sockSend(syn_packet)

    # calls select with the UDP socket with a low timeout
    ready, unused_ignore, unused_ignore2 = select.select([sock], [], [], 2.5)

    if ready:
        result = sock.recvfrom(MSG_SIZE)
        if result:
            (data, unused_addr) = result
            try:
                decoded = json.loads(bytes.decode(data))
                ack_sequence = wrap_sequence(SEQUENCE + 1)

                #  ACK is expected to send the sequence number incremented by 1
                if decoded.get('syn') is not None and decoded.get('ack') == ack_sequence:
                    SEQUENCE = ack_sequence
                    log('[recv syn/ack] {syn}/{ack}'.format(
                        syn=decoded['syn'],
                        ack=decoded['ack']
                    ))

                    ack_packet = {'syn': True, 'ack': decoded['syn'] + 1}
                    sockSend(ack_packet)
                    return True
                else:
                    log('[error] syn/ack did not match expectation {syn}/{ack}'.format(
                        syn=decoded.get('syn'),
                        ack=decoded.get('ack')
                    ))
                    return False
            except (ValueError, KeyError, TypeError):
                log('[recv corrupt packet during handshake]')
        else:
            log('[error] timeout during handshake')
            return False


def resetSent():
    
    global SENT
    global LOADED
    LOADED.update(SENT)
    SENT = {}


def handleTimeout():
   
    global CWND
    global SSTHRESH
    log('[timeout] resending packets')
    SSTHRESH = CWND / 2
    CWND = 1

    calculateRTT(current_time() - RTO)

    # resend packets
    resetSent()
    sendPackets()


def calculateRTT(timestamp):
   
    global RTT
    global RTO
    # calculate the sample
    sample = current_time() - timestamp
    # calculate the new RTT as a moving average, using recommended alpha of 0.875
    alpha = 0.875
    RTT = (alpha * RTT) + ((1 - alpha) * sample)
    RTO = max(2 * RTT, 0.5)
    log('[update RTO] {timeout}'.format(timeout=RTO))


def growCWND():
   
    global CWND
    # slow start
    if (CWND < SSTHRESH):
        CWND += 1
    # congestion avoidance
    else:
        CWND += 1 / CWND


def fastRetransmit():
  
    global CWND
    log('[fast retransmit] resending packets')
    # resend packets
    resetSent()
    sendPackets()
    # fast recovery; avoid unnecessary return to slow start
    CWND = SSTHRESH / 2


def handleACK(packet):
   
    global SENT
    global DUP_ACKS
    ack = packet['ack']
    # if an ACK was received for an in-flight packet
    if (ack in SENT):
        log('[recv ack] {ack}'.format(ack=ack))
        
        DUP_ACKS = 0
        
        sent_packet = SENT.pop(ack)
      
        calculateRTT(sent_packet['timestamp'])
        # grow congestion window
        growCWND()
        return True
    elif packet.get('syn'):
       
        return False
    else:
        DUP_ACKS += 1
        if DUP_ACKS == 3:
            DUP_ACKS = 0
            fastRetransmit()
        return False


if __name__ == '__main__':
  
    IP_PORT = sys.argv[1]
    UDP_IP = IP_PORT[0:IP_PORT.find(':')]
    UDP_PORT = int(IP_PORT[IP_PORT.find(':') + 1:])
    dest = (UDP_IP, UDP_PORT)

    # set up the socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(RTO)

    # initiate three way handshake and estimate RTT 
    handshake_start = current_time()
    while not handshake():
        continue
    RTT = current_time() - handshake_start
    RTO = max(2 * RTT, 0.5)

    # send packets 
    while True:
        # load and send packets 
        loadPackets()
        sendPackets()

        log('ABOUT TO SLEEP')

        # calls select with the UDP socket
        ready, unused_ignore, unused_ignore2 = select.select([sock], [], [], RTO)

        if ready:
            result = sock.recvfrom(MSG_SIZE)
            if result:
                (data, addr) = result
                try:
                    decoded = json.loads(bytes.decode(data))

                    # send the next packet if an ACK for an in-flight packet was received
                    if handleACK(decoded):
                        #  send next packet; exit if no more data
                        if END_OF_FILE and not len(SENT) and not len(LOADED):
                            log('[completed]')
                            sys.exit(0)
                except (ValueError, KeyError, TypeError) as err:
                    log('[recv corrupt packet] error: {error}'.format(error=err))
            else:
                log('[error] timeout')
                sys.exit(-1)
        else:
            handleTimeout()