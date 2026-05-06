from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select, create_engine
from models import WomenProduct

sqlite_url = "sqlite:///holzkern.db"
engine = create_engine(sqlite_url)

app = FastAPI(title="Holzkern Watches API", version="1.0.0")


@app.get("/")
def home():
    return FileResponse('static/index.html')


@app.get("/women-watches-accessories")
def get_women_watches_accessories():
    """
    Retrieve all women watches and accessories from the database.
    """
    with Session(engine) as session:
        results = session.exec(select(WomenProduct)).all()
        if not results:
            raise HTTPException(status_code=404, detail="No women watches found")
        return {
            "total": len(results),
            "data": results
        }


app.mount("/static", StaticFiles(directory="static", html=True), name="static")


def fetch_all_women_watches():
    """
    Fetch all women watches from the database and display them.
    """
    with Session(engine) as session:
        women_watches = session.exec(select(WomenProduct)).all()
        
        if not women_watches:
            print("No women watches found in the database.")
            return
        
        print(f"\n{'='*100}")
        print(f"Total Women Watches & Accessories: {len(women_watches)}")
        print(f"{'='*100}\n")
        
        for watch in women_watches:
            print(f"ID: {watch.id}")
            print(f"Name: {watch.product_name}")
            print(f"Category: {watch.category}")
            print(f"Subcategory: {watch.subcategory}")
            print(f"Material: {watch.material}")
            print(f"Color: {watch.color}")
            print(f"Price: ${watch.price}")
            print(f"Availability: {watch.availability}")
            print(f"Description: {watch.description[:100]}..." if watch.description else "Description: N/A")
            print(f"Product URL: {watch.product_url}")
            print(f"Image URL: {watch.image_url}")
            print(f"{'-'*100}\n")


if __name__ == "__main__":
    fetch_all_women_watches()
