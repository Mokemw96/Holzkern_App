from sqlmodel import SQLModel,Field,create_engine

class WomenProduct(SQLModel, table=True):
    __tablename__ = "women_watches_accessories"

    id: int | None = Field(default=None, primary_key=True)
    product_name: str
    category: str
    subcategory: str | None = None
    material: str | None = None
    color: str | None = None
    price: float | None = None
    availability: str | None = None
    description: str | None = None
    product_url: str | None = None
    image_url: str | None = None

class MenProduct(SQLModel, table=True):
    __tablename__ = "men_watches_accessories"

    id: int | None = Field(default=None, primary_key=True)
    product_name: str
    category: str
    subcategory: str | None = None
    material: str | None = None
    color: str | None = None
    price: float | None = None
    availability: str | None = None
    description: str | None = None
    product_url: str | None = None
    image_url: str | None = None

engine = create_engine("sqlite:///holzkern.db")
SQLModel.metadata.create_all(engine)

