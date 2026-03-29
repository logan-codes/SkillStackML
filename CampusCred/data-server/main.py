from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def get_data():
    result ={
        "name":"abc",
        "register_no":1234567,
    }
    return result