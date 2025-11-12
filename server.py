import os
import socket
import threading
import json

HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 5555))


rooms = {}
names = {}

def broadcast(room, message):
    """Send message to everyone in a room."""
    if room in rooms:
        for c in rooms[room]:
            try:
                c.send(json.dumps(message).encode())
            except:
                rooms[room].remove(c)
                c.close()

def handle_client(conn, addr):
    try:
        data = conn.recv(1024).decode()
        if not data:
            return
        info = json.loads(data)
        name = info["name"]
        room = info["room"]
        names[conn] = name

        print(f"[JOIN] {name} joined room {room} from {addr}")

        if room not in rooms:
            rooms[room] = [conn]
            conn.send(json.dumps({"type": "waiting"}).encode())
        else:
            rooms[room].append(conn)
            if len(rooms[room]) == 2:
                p1, p2 = rooms[room]
                n1, n2 = names[p1], names[p2]
                p1.send(json.dumps({"type": "start_game", "player": n1, "opponent": n2}).encode())
                p2.send(json.dumps({"type": "start_game", "player": n2, "opponent": n1}).encode())
                print(f"[MATCH FOUND] {n1} vs {n2} in room {room}")
            else:
                conn.send(json.dumps({"type": "room_full"}).encode())
                conn.close()
                return

        # Forward moves between clients
        while True:
            msg = conn.recv(2048).decode()
            if not msg:
                break
            data = json.loads(msg)
            if "room" in data:
                for c in rooms.get(data["room"], []):
                    if c != conn:
                        try:
                            c.send(json.dumps(data).encode())
                        except:
                            pass
    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        print(f"[DISCONNECT] {addr}")
        for room, players in list(rooms.items()):
            if conn in players:
                players.remove(conn)
                if not players:
                    del rooms[room]
        conn.close()

def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen()
    print(f"[SERVER] Running on {HOST}:{PORT}")

    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    start_server()
