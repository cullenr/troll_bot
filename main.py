"""
Read a camera input and emit websocket events for detected faces. Listen to a db
for new faces to recognise.

The camera is read by a thread on the main process, it adds frames to a
multiprocess queue if the queue is not full, otherwise it discards the frame and
loops.

The processes that analyse the frames pick up a frame and work on it in an
infinite loop. Recognised faces are added to queue that is read by the main
process.

The websocket thread runs a coroutine loop and must be fed blocking events from
another thread, in this case the main thread.

Another thread on the main process listens to the database for changes, if a
new face is added to the database by this process or any other then it will
update all the sub processes cache of faces.
"""

import multiprocessing as mp
import numpy as np
import time
import threading
import queue
import os
import signal
import cv2
import psycopg2
import psycopg2.extensions
import face_recognition
import asyncio
import websockets
import select

# globals are atomic
is_running = True

def run_capture(video_q):
    """
    Dump camera frames into Queue if its not full
    """
    cam = cv2.VideoCapture(0)
    print(f"width: {cam.get(3)}, height: {cam.get(4)}, fps: {cam.get(5)}")
    while is_running:

        if not video_q.full(): 
            ok, frame = cam.read()
            if not ok:
                # camera disconnected
                break

            video_q.put(frame)

    cam.release()

    # empty the queue otherwise the main process will hand as the queue feeder
    # thread will not terminate while the queue has items. Empty it here as this
    # is the only place that adds to the queue
    while not video_q.empty():
        video_q.get()

    print("camera thread exited")

def run_decode(video_q, names, faces, face_q):
    # This is a sub process, loop until we get a exit signal
    while (True):
        try:
            bgr_frame = video_q.get(True) # True waits until an item is available
            rgb_frame = bgr_frame[:, :, ::-1]

            locations = face_recognition.face_locations(rgb_frame)
            encodings = face_recognition.face_encodings(rgb_frame, locations)

            for (t, r, b, l), face in zip(locations, encodings):
                # See if the face is a match for the known face(s)
                matches = face_recognition.compare_faces(faces, face)
                name = "Unknown"

                # If a match was found in known_face_encodings, just use the first one.
                if True in matches:
                    i = matches.index(True)
                    name = names[i]

                face_q.put((name, face))
        except (KeyboardInterrupt, SystemExit):
            print(f"exit decode process {os.getpid()}")
            break

def run_syncronise_faces(names, faces):
    db = psycopg2.connect(host="localhost",database="troll",
            user="troll_admin", password="rootroot")
    db.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
    cur = db.cursor()
    cur.execute('SELECT name, encoding FROM troll.users;')
    users = cur.fetchall()
    cur.close()

    if len(users) > 0:
        zipped = list(zip(*users))
        names += zipped[0]
        faces += list(map(lambda arr: np.asarray(arr, dtype=np.float64), zipped[1]))

    cur = db.cursor()
    cur.execute('LISTEN "troll_users_insert";')

    print("Waiting for notifications on channel 'troll_users_insert'")
    while is_running:
        # http://initd.org/psycopg/docs/advanced.html recommends using select to
        # prevent psycopg from eating cpu polling
        if select.select([db],[],[],5) == ([],[],[]):
            print("timeout")
            pass
        else:
            print("connection has data")
            db.poll()
            while db.notifies:
                notify = db.notifies.pop(0)
                if notify.channel == 'troll_users_insert':
                    user_cur = db.cursor()
                    user_cur.execute('SELECT name, encoding FROM troll.users '
                            'WHERE id = %s', (notify.payload,))
                    user = user_cur.fetchone()
                    user_cur.close()
                    names.append(user[0])
                    faces.append(user[1])

    cur.close()
    db.close()
    print("db thread exited")

class WebsocketThread(threading.Thread):
    """
    A thread for handling websockets. 
    """
    def __init__(self):
        super(WebsocketThread, self).__init__()
        self.loop = asyncio.new_event_loop()

    def run(self):
        self.clients = set()
        # this must be set before we call websockets.serve
        asyncio.set_event_loop(self.loop)

        start_server = websockets.serve(self._handle_connection, 'localhost',
                8008)

        self.loop.run_until_complete(start_server)
        self.loop.run_forever()
        self.loop.close()
        print("websocket thread exited")

    def stop(self):
        self.loop.call_soon_threadsafe(self.loop.stop)

    def broadcast(self, data):
        future = asyncio.run_coroutine_threadsafe(self._handle_broadcast(data),
                self.loop)
        result = future.result()

    async def _handle_connection(self, client, path):
        print(f'got connection from {path}')
        self.clients.add(client)
        await client.wait_closed()
        self.clients.remove(client)

    async def _handle_broadcast(self, data):
        #print('handle broadcast', data)
        for client in self.clients:
            await client.send(data)

if __name__ == '__main__':
    # shared state between db thread and the worker processes, db thread
    # writes and the workers read
    manager = mp.Manager();
    faces = manager.list()
    names = manager.list()
    n_workers = 6
    # vidoe frames written by the capture thread, read by the worker processes
    video_q = mp.Queue(n_workers)
    # faces written to by the worker processes, read by the broadcast thread
    face_q = mp.Queue()

    # reads camera frames to the video queue
    capture = threading.Thread(target=run_capture, args=(video_q,))
    capture.start()

    # syncronises the local cache of faces with the remote source of truth
    db = threading.Thread(target=run_syncronise_faces, args=(names, faces))
    db.start()

    # dispatches websocket events for detected faces in the faces queue
    websocket_thread = WebsocketThread()
    websocket_thread.start()

    # worker processes to process video frames
    workers = []
    for i in range(n_workers):
        workers.append(mp.Process(target=run_decode, args=(video_q, names, faces,
            face_q)))
        workers[i].start()

    # keep the faces and names lists up to date, the db is the source of truth
    while (True):
        try:
            # replace this bit with something to get a new face from the db.
            # another process does the adding faces stuff.
            (name, face) = face_q.get(True)
            #print(f"got face of {name}")
            websocket_thread.broadcast(name)
        except (KeyboardInterrupt, SystemExit):
            print("Exiting...")
            break

    # prevent double sigint, the second one will interupt this cleanup
    # and leave some zombies or orphans
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    print("kill threads")
    is_running = False
    capture.join()
    db.join()

# workers inherit signal handlers
#    for worker in workers:
#        print(f"terminate worker {worker.pid}")
#        worker.terminate()
#        worker.join()

    face_q.close()

    websocket_thread.stop()
    websocket_thread.join()

    for t in threading.enumerate():
        print(t)

    print("exiting")

