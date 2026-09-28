"""业务异常类型：服务层抛出，路由层或全局错误处理器转 fail()。"""


class ApiError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message
