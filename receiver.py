import sys
import socket
import json

from enum import Enum
from utils import log, wrap_sequence


#(MTU)
MSG_SIZE = 1500
# Socket timeout initialized to 30 seconds
TIMEOUT = 30
# The messages received out-of-order
BUFFERED = {}
# The sequence number that has been ACKed
ACKED_SEQUENCE = 0
# Flag indicating if we've received the last of the data
END_OF_FILE = False

# Bind to localhost and an ephemeral port
UDP_IP = '127.0.0.1'
UDP_PORT = 0



class Status(Enum):
    IN_ORDER = 1
    OUT_OF_ORDER = 2
    DUPLICATE = 3


def prune_buffer():
    """writes buffered messages to stdout"""
    global ACKED_SEQUENCE
    global BUFFERED
    while True:
        if ACKED_SEQUENCE in BUFFERED:
            msg = BUFFERED.pop(ACKED_SEQUENCE)
            sys.stdout.write(msg)
            ACKED_SEQUENCE = wrap_sequence(ACKED_SEQUENCE, msg)
        else:
            break


def receiveInOrder(msg):
    global ACKED_SEQUENCE
    sequence = msg['sequence']
    data = msg['data']
    log('[recv data] {sequence} ({length}) ACCEPTED (in-order)'.format(
        sequence=sequence,
        length=len(data)
    ))
    sys.stdout.write(data)
    ACKED_SEQUENCE = wrap_sequence(sequence, data)
    return {'ack': ACKED_SEQUENCE}


def receiveOutOrder(msg, status):
    global BUFFERED
    sequence = msg['sequence']
    data = msg['data']
    if status == Status.OUT_OF_ORDER:
        log('[recv data] {sequence} ({length}) ACCEPTED (out-of-order)'.format(
            sequence=sequence,
            length=len(data)
        ))
        BUFFERED[sequence] = data
    elif status == Status.DUPLICATE:
        log('[recv data] {sequence} ({length}) IGNORED (duplicate)'.format(
            sequence=sequence,
            length=len(data)
        ))
    return {'ack': wrap_sequence(sequence, data)}


def packetCheck(packet):
    """Compare the packet's sequence number to the current ACKED_SEQUENCE value"""
    if packet['sequence'] == ACKED_SEQUENCE:
        return Status.IN_ORDER
    elif packet['sequence'] > ACKED_SEQUENCE and packet['sequence'] not in BUFFERED:
        #not expecting to receive this packet yet
        return Status.OUT_OF_ORDER
    else:
        # The sequence number is lower than bytes we've already sent an ACK for
        return Status.DUPLICATE


def acknowledge(msg, addr):
    """Acknowledge data was received from the sender"""
    json_packet = json.dumps(msg)
    log('ABOUT TO SEND ' + json_packet)

    packet = str.encode(json_packet)
    if sock.sendto(packet, addr) < len(packet):
        log('[error] unable to fully send packet')


if __name__ == '__main__':
    # Set up socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    sock.settimeout(TIMEOUT)

    # Get port we bound to
    UDP_PORT = sock.getsockname()[1]
    log('[bound] {port}'.format(port=UDP_PORT))

    # listen for packets
    while True:
        result = sock.recvfrom(MSG_SIZE)

        # if nothing is ready, we hit the timeout
        if result:
            (data, addr) = result

            try:
                decoded = json.loads(bytes.decode(data))
                status = packetCheck(decoded)

                # if the SYN flag is set, handle the handshake
                if decoded.get('syn'):
                    if decoded.get('ack'):
                        log('[recv ack] handshake complete')
                    else:
                        sequence = decoded['sequence']
                        log('[recv syn] {sequence}'.format(sequence=sequence))
                        ACKED_SEQUENCE = wrap_sequence(sequence + 1)
                        packet = {'syn': sequence, 'ack': ACKED_SEQUENCE}
                        acknowledge(packet, addr)
                    continue

                # if the EOF flag is set on the message or we've previously received EOF, set
                END_OF_FILE = decoded.get('eof') or END_OF_FILE

                # if there is data and it came in order, we accept it and print it out
                if status == Status.IN_ORDER and decoded.get('data'):
                    packet = receiveInOrder(decoded)
                    # send back an ack to the sender
                    acknowledge(packet, addr)
                    # see if anything in BUFFERED can be written to stdout
                    prune_buffer()
                else:
                    packet = receiveOutOrder(decoded, status)
                    # send back an ack to the sender
                    acknowledge(packet, addr)

                if END_OF_FILE and not len(BUFFERED):
                    log('[completed]')
                    sys.exit(0)

            except (ValueError, KeyError, TypeError) as e:
                log('[recv corrupt packet]')
                raise e
        else:
            log('[error] timeout')
            sys.exit(-1)