import cv2
import os
import numpy as np

os.makedirs("model", exist_ok=True)

face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

faces = []
labels = []
label_map = {}
label_id = 0

for person in sorted(os.listdir("faces")):
    label_map[label_id] = person
    for img in os.listdir(f"faces/{person}"):   
        image = cv2.imread(f"faces/{person}/{img}")
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        detected = face_cascade.detectMultiScale(gray, 1.3, 5)

        for (x, y, w, h) in detected:
            face = gray[y:y+h, x:x+w]
            face = cv2.resize(face, (200, 200))
            faces.append(face)
            labels.append(label_id)

    label_id += 1

recognizer = cv2.face.LBPHFaceRecognizer_create()
recognizer.train(faces, np.array(labels))
recognizer.save("model/face_model.yml")

print("Model trained correctly with face detection")
