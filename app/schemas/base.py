from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class BaseResponse(BaseModel, Generic[T]):
    """
    Standard API response wrapper.
    Follows Rule 8: {"success": true, "data": {}, "message": "..."}
    """

    success: bool = True
    data: Optional[T] = None
    message: str = "Operation successful"


class ErrorResponse(BaseModel):
    """
    Standard API error response.
    Follows Rule 8: {"success": false, "error": "..."}
    """

    success: bool = False
    error: str
