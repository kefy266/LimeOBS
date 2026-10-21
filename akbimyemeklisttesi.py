from akbim_api import ensure_login, load_index, BASEURL, session
import json
from pypdf import PdfReader
import io

if not ensure_login():
    exit()

data = load_index()
print(data)

response = session.get(
    f"{BASEURL}/pages/student/require/foodListAction.php",
    params={"request": "get-food-list"}
    )

data = response.json()