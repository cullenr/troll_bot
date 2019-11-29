import sys
import psycopg2
import face_recognition

if  __name__ == '__main__':
    image = face_recognition.load_image_file(sys.argv[1])
    face_encoding = face_recognition.face_encodings(image)[0]

    try:
        conn = psycopg2.connect(host="localhost",database="troll",
                user="troll_admin", password="rootroot")
        cur = conn.cursor()
        cur.execute('INSERT INTO troll.users (name, encoding) VALUES (%s, %s) RETURNING id;',
                (sys.argv[2], face_encoding.tolist()))
        user_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()

