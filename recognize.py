import cv2
import os
import csv
import numpy as np
from datetime import datetime
import mediapipe as mp

# ---------------- CONFIG ----------------
CONF_THRESHOLD = 60        # recognition threshold
REQUIRED_BLINKS = 1
CAMERA_INDEX = 0
# ----------------------------------------

# Load face detector
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

# Load recognizer
recognizer = cv2.face.LBPHFaceRecognizer_create()
recognizer.read("model/face_model.yml")

# Label map
label_map = {}
for i, name in enumerate(sorted(os.listdir("faces"))):
    label_map[i] = name

# MediaPipe Face Mesh
mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

# Eye landmarks
LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]

def eye_aspect_ratio(eye):
    A = np.linalg.norm(eye[1] - eye[5])
    B = np.linalg.norm(eye[2] - eye[4])
    C = np.linalg.norm(eye[0] - eye[3])
    return (A + B) / (2.0 * C)

marked = set()
blink_frames = 0
blink_count = 0

cap = cv2.VideoCapture(CAMERA_INDEX)

print("[INFO] Attendance system started (blink enabled)")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mesh_result = face_mesh.process(rgb)

    for (x, y, w, h) in faces:
        face_img = gray[y:y+h, x:x+w]
        face_img = cv2.resize(face_img, (200, 200))

        label, conf = recognizer.predict(face_img)
        name = label_map[label]

        # Draw face box
        cv2.rectangle(frame, (x, y), (x+w, y+h), (0,255,0), 2)

        if conf <= CONF_THRESHOLD:
            cv2.putText(frame, f"{name} ({int(conf)})",
                        (x, y-10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.8, (0,255,0), 2)

            # ---- BLINK DETECTION ----
            if mesh_result.multi_face_landmarks:
                landmarks = mesh_result.multi_face_landmarks[0].landmark

                left_eye = np.array([[int(landmarks[i].x * frame.shape[1]),
                                       int(landmarks[i].y * frame.shape[0])]
                                      for i in LEFT_EYE])

                right_eye = np.array([[int(landmarks[i].x * frame.shape[1]),
                                        int(landmarks[i].y * frame.shape[0])]
                                       for i in RIGHT_EYE])

                ear = (eye_aspect_ratio(left_eye) +
                       eye_aspect_ratio(right_eye)) / 2

                if ear < 0.20:
                    blink_frames += 1
                else:
                    if blink_frames >= 2:
                        blink_count += 1
                        blink_frames = 0
                        print("[BLINK DETECTED]")
                cv2.putText(frame, f"Blinks: {blink_count}",
                            (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.7, (255,255,0), 2)

            # ---- MARK ATTENDANCE AFTER BLINK ----
            if blink_count >= REQUIRED_BLINKS and name not in marked:
                with open("attendance.csv", "a", newline="") as f:
                    csv.writer(f).writerow(
                        [name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
                    )
                marked.add(name)
                print("[ATTENDANCE MARKED]", name)

        else:
            cv2.putText(frame, "Unknown",
                        (x, y-10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.8, (0,0,255), 2)

    cv2.imshow("Blink-Based Attendance System", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
