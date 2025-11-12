import os, qrcode

url = "http://127.0.0.1:5000/qrpage"

directorio = r"C:\Users\kaleb\Desktop\simulación_robo_demo\static"
os.makedirs(directorio, exist_ok=True)

ruta = os.path.join(directorio, "qr.png")
img = qrcode.make(url)
img.save(ruta)

print(f"QR generado correctamente en: {ruta}")
