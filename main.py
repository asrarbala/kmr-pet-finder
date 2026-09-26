from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def root():
    return {"message": "KMR Pet Finder API is running"}
