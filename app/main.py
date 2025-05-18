from fastapi import FastAPI
from auth import router as auth_router
from product import router as product_router

app = FastAPI()
app.include_router(auth_router)
app.include_router(product_router)