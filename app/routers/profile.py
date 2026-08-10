from fastapi import APIRouter, Depends

from app.core.security import CurrentUser, get_current_user, get_scoped_client
from app.models.common import ProfileOut, ProfileUpdate

router = APIRouter(prefix="/me", tags=["profile"])


@router.get("", response_model=ProfileOut)
def get_my_profile(user: CurrentUser = Depends(get_current_user), client=Depends(get_scoped_client)):
    res = client.table("profiles").select("*").eq("id", user.id).single().execute()
    return res.data


@router.patch("", response_model=ProfileOut)
def update_my_profile(
    payload: ProfileUpdate,
    user: CurrentUser = Depends(get_current_user),
    client=Depends(get_scoped_client),
):
    row = payload.model_dump(mode="json", exclude_none=True)
    res = client.table("profiles").update(row).eq("id", user.id).execute()
    return res.data[0]
