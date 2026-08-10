from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import CurrentUser, get_current_user, get_scoped_client
from app.models.common import AddressCreate, AddressOut

router = APIRouter(prefix="/addresses", tags=["addresses"])


@router.get("", response_model=list[AddressOut])
def list_my_addresses(user: CurrentUser = Depends(get_current_user), client=Depends(get_scoped_client)):
    """The signed-in customer's saved delivery addresses."""
    res = client.table("addresses").select("*").eq("customer_id", user.id).execute()
    return res.data


@router.post("", response_model=AddressOut, status_code=status.HTTP_201_CREATED)
def add_address(
    payload: AddressCreate,
    user: CurrentUser = Depends(get_current_user),
    client=Depends(get_scoped_client),
):
    row = payload.model_dump(mode="json")
    row["customer_id"] = user.id
    res = client.table("addresses").insert(row).execute()
    return res.data[0]


@router.delete("/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_address(address_id: UUID, client=Depends(get_scoped_client)):
    res = client.table("addresses").delete().eq("id", str(address_id)).execute()
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Address not found.")
