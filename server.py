import os
import time
import threading
from flask import Flask, request
from flask_socketio import SocketIO, join_room, leave_room, emit

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Global data structures
rooms = {}     # { room_code: [ { "sid": ..., "name": ... }, ... ] }
lock = threading.Lock()


@app.route("/")
def home():
    return "✅ Sudoku Multiplayer Server Running"


# --- Player joins a room ---
@socketio.on("join")
def handle_join(data):
    name = data.get("name")
    room = str(data.get("room"))

    if not name or not room:
        emit("error", {"msg": "Invalid name or room"})
        return

    sid = request.sid
    print(f"[JOIN REQUEST] {name} joined room {room} ({sid})")

    with lock:
        if room not in rooms:
            rooms[room] = [{"sid": sid, "name": name}]
            join_room(room)
            emit("waiting", {"msg": f"{name} is waiting for an opponent..."}, to=sid)
            print(f"[WAITING] {name} waiting in room {room}")
        elif len(rooms[room]) == 1:
            # Second player joins → match start
            rooms[room].append({"sid": sid, "name": name})
            join_room(room)
            p1, p2 = rooms[room]

            socketio.emit("start_game", {
                "player": p1["name"],
                "opponent": p2["name"]
            }, to=p1["sid"])

            socketio.emit("start_game", {
                "player": p2["name"],
                "opponent": p1["name"]
            }, to=p2["sid"])

            print(f"[MATCH FOUND] {p1['name']} vs {p2['name']} in room {room}")
        else:
            emit("room_full", {"msg": "Room is full."}, to=sid)
            print(f"[FULL] {name} tried to join full room {room}")


# --- Handle player moves ---
@socketio.on("move")
def handle_move(data):
    """Forward move to opponent in the same room."""
    room = str(data.get("room"))
    emit("move", data, room=room, include_self=False)


# --- Handle disconnect ---
@socketio.on("disconnect")
def handle_disconnect():
    sid = request.sid
    with lock:
        for room, players in list(rooms.items()):
            for player in players:
                if player["sid"] == sid:
                    name = player["name"]
                    players.remove(player)
                    leave_room(room)
                    emit("opponent_disconnected", {"msg": f"{name} disconnected."}, room=room)
                    print(f"[DISCONNECT] {name} left room {room}")
                    break

            # Remove empty rooms
            if len(players) == 0:
                del rooms[room]
                print(f"[ROOM REMOVED] {room}")
    print(f"[DISCONNECT EVENT] SID={sid}")


# --- Background cleanup thread ---
def cleanup_rooms():
    while True:
        time.sleep(60)
        with lock:
            empty = [r for r, p in rooms.items() if len(p) == 0]
            for r in empty:
                del rooms[r]
                print(f"[CLEANUP] Removed empty room {r}")


# --- Start server ---
if __name__ == "__main__":
    threading.Thread(target=cleanup_rooms, daemon=True).start()
    port = int(os.environ.get("PORT", 8080))
    print(f"[SERVER START] Sudoku Multiplayer running on 0.0.0.0:{port}")
    socketio.run(app, host="0.0.0.0", port=port)
