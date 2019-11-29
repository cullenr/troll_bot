"""
Read a camera input and emit websocket events for detected faces.

The camera is read by a thread on the main process, it adds frames to a
multiprocess queue if the queue is not full, otherwise it discards the frame and
loops.

The processes that analyse the frames pick up a frame and work on it in an
infinite loop. Recognised faces are added to queue that feeds a websocket
broadcast thread on the main process.

The main thread on the main process listens to the database for changes, if a
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
import face_recognition

# globals are atomic
is_running = True

def generate(video_q):
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

def work(video_q, names, faces, face_q):
    pid = os.getpid()
    # workers should not use the inherrited sigint as they will cause the parent
    # to crash and cannot reliably clean up after themselves.
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    while (True):
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

def broadcast(face_q):
    #https://asyncio.readthedocs.io/en/latest/producer_consumer.html
    # make this an asyncio thread - or maybe the main thread can be...
    while is_running:
        try:
            (name, face) = face_q.get(True, 0.5) # lets is_running get checked
            print(f"found {name}'s wonderful face")
        except OSError:
            print("queue close")
            break
        except:
            print("other error")
            break
    print("broadcast thread exited")

def get_named_faces(db):
    cur = db.cursor()
    cur.execute('SELECT name, encoding FROM troll.users;')
    users = cur.fetchall()
    zipped = list(zip(*users))
    cur.close()

    # Create arrays of known face encodings and their names
    face_names = zipped[0]
    face_encodings = list(map(lambda arr: np.asarray(arr, dtype=np.float64), zipped[1]))

    return face_names, face_encodings

if __name__ == '__main__':
    n_workers = 1
    # vidoe frames written by the camera thread, read by the worker processes
    video_q = mp.Queue(n_workers)
    # faces written to by the worker processes, read by the broadcast thread
    face_q = mp.Queue()

    # reads camera frames to the video queue
    camera = threading.Thread(target=generate, args=(video_q,))
    camera.start()
    
    # dispatches websocket events for detected faces in the faces queue
    broadcaster = threading.Thread(target=broadcast, args=(face_q,))
    broadcaster.start()

    # shared state between this thread and the worker processes, this thread
    # writes and the workers read
    manager = mp.Manager();
    faces = manager.list()
    names = manager.list()
    db = psycopg2.connect(host="localhost",database="troll",
            user="troll_admin", password="rootroot")
    db_names, db_faces = get_named_faces(db)
    names += db_names
    faces += db_faces

    # worker processes to process video frames
    workers = []
    for i in range(n_workers):
        workers.append(mp.Process(target=work, args=(video_q, names, faces,
            face_q)))
        workers[i].start()

    # keep the faces and names lists up to date, the db is the source of truth
    while (True):
        try:
            # replace this bit with something to get a new face from the db.
            # another process does the adding faces stuff.
            time.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            print("Exiting...")
            break
            # prevent double sigint, the second one will interupt this cleanup
            # and leave some zombies or orphans

    # begin cleanup
    print("close db")
    db.close()

    signal.signal(signal.SIGINT, signal.SIG_IGN)
    print("kill threads")
    is_running = False
    camera.join()

    for worker in workers:
        print("terminate worker")
        worker.terminate()
        worker.join()

    face_q.close()
    broadcaster.join()

    for t in threading.enumerate():
        print(t)

    print("exiting")
