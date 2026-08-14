from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.routers import admin, addresses, categories, dashboard, deals, orders, products, profile, reviews, shops

settings = get_settings()

app = FastAPI(
    title="LocalMart API",
    description="Backend for the LocalMart hyperlocal marketplace — customer browsing/ordering, "
    "shopkeeper inventory & order management, and admin oversight, all layered on top of "
    "Supabase Postgres with Row-Level Security.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(categories.router)
app.include_router(shops.router)
app.include_router(products.router)
app.include_router(deals.router)
app.include_router(addresses.router)
app.include_router(orders.router)
app.include_router(profile.router)
app.include_router(dashboard.router)
app.include_router(reviews.router)
app.include_router(admin.router)


@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok"}
