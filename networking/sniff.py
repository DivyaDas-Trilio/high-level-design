import socket

def sniff():
    # Create raw socket to capture IP packets
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(("192.168.1.44", 8445))
    print("Sniffing... Press Ctrl+C to stop.")
    while True:
        raw_data, addr = sock.recvfrom(65535)
        print(f"Packet from {addr}: {len(raw_data)} bytes")
        # Print first 40 bytes in hex
        print(raw_data[:40].hex())

if __name__ == "__main__":
    sniff()
