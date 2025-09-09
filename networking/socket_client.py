import socket, ssl


def start_client():
    HOST= "192.168.1.44"
    PORT = 8445
    conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    #sock = conn.connect((HOST,PORT))
    
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    
    
    while True:
        with socket.create_connection((HOST, PORT)) as sock:
            with context.wrap_socket(sock, server_hostname=HOST) as tls_conn:
                msg = tls_conn.sendall(b"Hello Server")
            
                print(tls_conn.recv(1024))
    
if __name__ == "__main__":
    start_client()