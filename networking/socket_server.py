from concurrent.futures import thread
import socket, threading, ssl

lock = threading.Lock()

def handler(fd, addr, context):
    with lock:
        print(fd, addr)
        import time; time.sleep(10)
        with context.wrap_socket(fd) as tls_conn:
            print(tls_conn.recv(1024))
            tls_conn.sendall(b"Hello Client...")

def start_server():
    IP = "192.168.1.44"
    PORT = 8445
    server  = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((IP, PORT))
    server.listen()
    
    context = ssl.SSLContext(ssl.PROTOCOL_TLS)
    context.load_cert_chain("./cert.pem", "./key.pem")
    
    while True:
        fd, addr = server.accept()
        fd1, addr = server.accept()
        th1 = threading.Thread(target=handler, args=(fd, addr, context))
        th2 = threading.Thread(target=handler, args=(fd1, addr, context))
        th1.start()
        th2.start() 
        th1.join()
        th2.join()   
    
if __name__ == "__main__":
    start_server()