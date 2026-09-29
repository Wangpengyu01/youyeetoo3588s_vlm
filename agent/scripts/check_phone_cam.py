import socket
import urllib.request

ip = '10.42.0.23'
print(f"Scanning {ip}...")
open_ports = []
for port in [8080, 4747, 8081, 8082, 554, 8000, 8888]:
    s = socket.socket()
    s.settimeout(0.6)
    r = s.connect_ex((ip, port))
    s.close()
    if r == 0:
        open_ports.append(port)
        print(f"Port {port} is OPEN!")

if not open_ports:
    print("No camera ports open yet on phone.")

if 8080 in open_ports:
    try:
        url = f"http://{ip}:8080/shot.jpg"
        with urllib.request.urlopen(url, timeout=2.0) as resp:
            data = resp.read()
            print(f"Success! Grabbed {len(data)} bytes from {url}")
    except Exception as e:
        print(f"Error fetching from 8080: {e}")
