from app.errors import raise_api_error
from app.models import Resource, User


def ensure_same_organization(user: User, resource: Resource) -> None:
    if resource.owner.organization_id != user.organization_id:
        raise_api_error("not_found", "Resource not found.", 404)


def ensure_resource_write_scope(user: User, resource: Resource) -> None:
    ensure_same_organization(user, resource)
    if user.role == "lab_manager" and resource.owner_id != user.id:
        raise_api_error(
            "forbidden",
            "You are not authorized to manage this resource.",
            403,
        )
