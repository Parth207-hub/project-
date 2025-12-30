import cv2
import os

name = input("Enter Student Name: ").strip()
save_path = f"faces/{name}"
os.makedirs(save_path, exist_ok=True)

cap = cv2.VideoCapture(0)

BOX_SIZE = 300
count = 0

face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)

print("[INFO] Align your face inside the box and press C to capture")

while count < 20:
    ret, frame = cap.read()
    if not ret:
        break

    h, w, _ = frame.shape

    x1 = w // 2 - BOX_SIZE // 2
    y1 = h // 2 - BOX_SIZE // 2
    x2 = x1 + BOX_SIZE
    y2 = y1 + BOX_SIZE

    cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)

    roi = frame[y1:y2, x1:x2]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    faces = face_cascade.detectMultiScale(gray, 1.3, 5)

    for (fx, fy, fw, fh) in faces:
        if fw < 120 or fh < 120:
            continue

        face_img = gray[fy:fy+fh, fx:fx+fw]
        face_img = cv2.resize(face_img, (200, 200))

        cv2.imshow("Captured Face", face_img)

        key = cv2.waitKey(1)
        if key == ord('c'):
            cv2.imwrite(f"{save_path}/{count}.jpg", face_img)
            print("Captured:", count + 1)
            count += 1

    cv2.imshow("Register Face", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print("[DONE] Face registration completed")
