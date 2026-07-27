class WyyzDBFError(Exception):
    """库内部所有对外抛出的基类异常。"""
    pass


class DBFHeaderError(WyyzDBFError):
    """DBF 文件头读取 / 写入错误。"""
    pass


class DBFRecordError(WyyzDBFError):
    """单条记录解析 / 写入错误。"""
    pass