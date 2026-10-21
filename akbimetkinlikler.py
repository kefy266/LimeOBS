from akbim_api import ensure_login, load_index
if not ensure_login():
    print("Giriş yapılamadı!")
    exit()

data = load_index()
eventList =data ["data"]["eventList"]

if not eventList:
    print("Etkinlik bulunamadı.")
    exit()

print("=== ETKİNLİKLER ===")
print(eventList)
