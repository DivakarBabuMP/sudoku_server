import os
import socket
import threading
import json
import time

HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", 10000))  # Render uses PORT env variable

rooms = {}
names = {}
lock = threading.Lock()  # Thread safety for shared data

def broadcast(room, message):
    """Send message to everyone in a room."""
    with lock:
        if room in rooms:
            dead_connections = []
            for c in rooms[room]:
                try:
                    c.send(json.dumps(message).encode())
                except:
                    dead_connections.append(c)
            
            # Clean up dead connections
            for c in dead_connections:
                if c in rooms[room]:
                    rooms[room].remove(c)
                try:
                    c.close()
                except:
                    pass

def handle_client(conn, addr):
    room = None
    player_name = None
    
    try:
        # Set socket timeout to prevent hanging
        conn.settimeout(300)  # 5 minutes timeout
        
        # Receive initial join data
        data = conn.recv(1024).decode('utf-8').strip()
        if not data:
            print(f"[ERROR] Empty initial data from {addr}")
            return
        
        try:
            info = json.loads(data)
        except json.JSONDecodeError as e:
            print(f"[JSON ERROR] Invalid join data from {addr}: {e}")
            return
        
        player_name = info.get("name")
        room = info.get("room")
        
        if not player_name or not room:
            print(f"[ERROR] Missing name or room from {addr}")
            return
        
        with lock:
            names[conn] = player_name
        
        print(f"[JOIN] {player_name} joined room {room} from {addr}")
        
        # Handle room joining
        with lock:
            if room not in rooms:
                rooms[room] = [conn]
                try:
                    conn.send(json.dumps({"type": "waiting"}).encode())
                except:
                    return
            else:
                if len(rooms[room]) >= 2:
                    # Room is full
                    try:
                        conn.send(json.dumps({"type": "room_full"}).encode())
                    except:
                        pass
                    return
                
                rooms[room].append(conn)
                
                if len(rooms[room]) == 2:
                    p1, p2 = rooms[room]
                    n1, n2 = names[p1], names[p2]
                    try:
                        p1.send(json.dumps({"type": "start_game", "player": n1, "opponent": n2}).encode())
                        p2.send(json.dumps({"type": "start_game", "player": n2, "opponent": n1}).encode())
                        print(f"[MATCH FOUND] {n1} vs {n2} in room {room}")
                    except Exception as e:
                        print(f"[ERROR] Failed to start game: {e}")
                        return
        
        # Forward moves between clients
        while True:
            try:
                msg = conn.recv(4096).decode('utf-8').strip()
                
                # Check if connection closed
                if not msg:
                    print(f"[INFO] Connection closed by {player_name} ({addr})")
                    break
                
                # Parse JSON
                try:
                    data = json.loads(msg)
                except json.JSONDecodeError as e:
                    print(f"[JSON ERROR] Invalid move data from {player_name} ({addr}): {e}")
                    continue
                
                # Forward to other players in room
                if "room" in data:
                    with lock:
                        room_players = rooms.get(data["room"], [])
                    
                    for c in room_players:
                        if c != conn:
                            try:
                                c.send(json.dumps(data).encode())
                            except Exception as send_err:
                                print(f"[SEND ERROR] Failed to forward to client: {send_err}")
                
            except socket.timeout:
                print(f"[TIMEOUT] {player_name} ({addr}) - connection timed out")
                break
            except ConnectionResetError:
                print(f"[CONNECTION RESET] {player_name} ({addr})")
                break
            except socket.error as e:
                print(f"[SOCKET ERROR] {player_name} ({addr}): {e}")
                break
            except Exception as e:
                print(f"[ERROR] {player_name} ({addr}): {e}")
                break
                
    except Exception as e:
        print(f"[ERROR] {addr}: {e}")
    finally:
        print(f"[DISCONNECT] {player_name or 'Unknown'} ({addr})")
        
        # Clean up connection from rooms
        with lock:
            for room_key, players in list(rooms.items()):
                if conn in players:
                    players.remove(conn)
                    # Notify other player if match was active
                    if len(players) == 1 and player_name:
                        try:
                            players[0].send(json.dumps({
                                "type": "opponent_disconnected",
                                "message": f"{player_name} disconnected"
                            }).encode())
                        except:
                            pass
                    # Remove empty rooms
                    if not players:
                        del rooms[room_key]
                        print(f"[ROOM CLOSED] Room {room_key} deleted")
            
            # Clean up name mapping
            if conn in names:
                del names[conn]
        
        # Close connection safely
        try:
            conn.close()
        except:
            pass

def cleanup_stale_rooms():
    """Periodically clean up empty rooms"""
    while True:
        time.sleep(60)  # Run every minute
        with lock:
            empty_rooms = [room for room, players in rooms.items() if not players]
            for room in empty_rooms:
                del rooms[room]
                print(f"[CLEANUP] Removed empty room: {room}")

def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server.bind((HOST, PORT))
        server.listen(5)
        print(f"[SERVER] Running on {HOST}:{PORT}")
        print(f"[INFO] Waiting for connections...")
        
        # Start cleanup thread
        cleanup_thread = threading.Thread(target=cleanup_stale_rooms, daemon=True)
        cleanup_thread.start()
        
        while True:
            try:
                conn, addr = server.accept()
                print(f"[NEW CONNECTION] {addr}")
                thread = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
                thread.start()
            except KeyboardInterrupt:
                print("\n[SERVER] Shutting down...")
                break
            except Exception as e:
                print(f"[ACCEPT ERROR] {e}")
                
    except Exception as e:
        print(f"[SERVER ERROR] Failed to start server: {e}")
    finally:
        server.close()
        print("[SERVER] Closed")

if __name__ == "__main__":
    print("=" * 50)
    print("SUDOKU MULTIPLAYER SERVER")
    print("=" * 50)
    start_server()
