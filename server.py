import os
from flask import Flask, request
from flask_socketio import SocketIO, join_room, leave_room, emit
import threading
import time

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

rooms = {}
lock = threading.Lock()

@app.route("/")
def home():
    return "✅ Sudoku Multiplayer Server Running"

@socketio.on("join")
def handle_join(data):
    name = data["name"]
    room = data["room"]

    with lock:
        if room not in rooms:
            rooms[room] = [name]
            join_room(room)
            emit("waiting", {"msg": f"{name} is waiting for an opponent..."}, room=room)
        elif len(rooms[room]) < 2:
            rooms[room].append(name)
            join_room(room)
            n1, n2 = rooms[room]
            emit("start_game", {"player": n1, "opponent": n2}, room=room)
            print(f"[MATCH FOUND] {n1} vs {n2} in room {room}")
        else:
            emit("room_full", {"msg": "Room is full."})

@socketio.on("move")
def handle_move(data):
    emit("move", data, room=data["room"], include_self=False)

@socketio.on("disconnect")
def handle_disconnect():
    print(f"[DISCONNECT] {request.sid}")

def cleanup_rooms():
    while True:
        time.sleep(60)
        with lock:
            for r, players in list(rooms.items()):
                if len(players) == 0:
                    del rooms[r]
                    print(f"[CLEANUP] Room {r} removed")

if __name__ == "__main__":
    threading.Thread(target=cleanup_rooms, daemon=True).start()
    port = int(os.environ.get("PORT", 8080))
    socketio.run(app, host="0.0.0.0", port=port)
