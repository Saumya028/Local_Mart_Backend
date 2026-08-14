from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.security import get_scoped_client
from app.models.common import DashboardSummaryOut, RevenuePointOut, ShopCustomerOut, TopProductOut

router = APIRouter(prefix="/shops/{shop_id}", tags=["dashboard"])

# Every route here calls a Postgres function (see supabase/owner_dashboard.sql)
# through the caller's own RLS-scoped client — a shop owner only ever gets
# numbers for a shop they actually own. Postgres itself raises (and we
# surface as 403) if that's not the case.


def _rpc_or_403(client, fn_name: str, params: dict):
    res = client.rpc(fn_name, params).execute()
    return res.data


@router.get("/dashboard/summary", response_model=DashboardSummaryOut)
def dashboard_summary(shop_id: UUID, client=Depends(get_scoped_client)):
    data = _rpc_or_403(client, "shop_dashboard_summary", {"p_shop_id": str(shop_id)})
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No data for this shop.")
    return data[0]


@router.get("/dashboard/revenue-daily", response_model=list[RevenuePointOut])
def dashboard_revenue_daily(shop_id: UUID, days: int = Query(7, ge=1, le=90), client=Depends(get_scoped_client)):
    return _rpc_or_403(client, "shop_revenue_daily", {"p_shop_id": str(shop_id), "p_days": days})


@router.get("/dashboard/top-products", response_model=list[TopProductOut])
def dashboard_top_products(shop_id: UUID, limit: int = Query(5, ge=1, le=50), client=Depends(get_scoped_client)):
    return _rpc_or_403(client, "shop_top_products", {"p_shop_id": str(shop_id), "p_limit": limit})


@router.get("/customers", response_model=list[ShopCustomerOut])
def shop_customers(shop_id: UUID, client=Depends(get_scoped_client)):
    try:
        return _rpc_or_403(client, "shop_customers", {"p_shop_id": str(shop_id)})
    except Exception as exc:  # the RPC raises a plain Postgres exception on ownership failure
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this shop's customers."
        ) from exc
