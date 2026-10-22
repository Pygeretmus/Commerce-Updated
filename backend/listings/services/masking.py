def mask_name(username: str | None) -> str | None:
    """
    The public form of a username in bid histories and live updates: "alice" becomes "a***e".
    Deleted accounts have no name at all (None); the client shows "Deleted user".
    """
    if not username:
        return None
    if len(username) <= 2:
        return f'{username[0]}***'
    return f'{username[0]}***{username[-1]}'
