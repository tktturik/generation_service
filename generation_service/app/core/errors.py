class AppError(Exception):
    """
    Ожидаемая ошибка приложения с машинным кодом для клиента.

    HTTP-статус не задаётся здесь:
    слой core не знает о HTTP, статус сопоставляет exc_handler.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class NotFoundError(AppError):
    pass


class NoSuitableLegError(AppError):
    def __init__(self, message: str = "No suitable provider leg") -> None:
        super().__init__("NO_SUITABLE_LEG", message)


class InsufficientTokensError(AppError):
    def __init__(self, message: str = "Insufficient tokens") -> None:
        super().__init__("INSUFFICIENT_TOKENS", message)


class TooManyActiveTasksError(AppError):
    def __init__(self, message: str = "Too many active tasks") -> None:
        super().__init__("TOO_MANY_ACTIVE_TASKS", message)


class InvalidSignatureError(AppError):
    def __init__(self, message: str = "Invalid signature") -> None:
        super().__init__("INVALID_SIGNATURE", message)
